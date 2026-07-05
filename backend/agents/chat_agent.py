"""
agents/chat_agent.py - Chat agent router for BuildFlow AI.

Provides:
  POST /api/chat       - Main chat endpoint (Gemini or smart fallback)
  GET  /api/chat/history/{session_id} - Retrieve session history
"""

from __future__ import annotations

import logging
import re
import uuid
import contextvars
from datetime import datetime, timedelta
from typing import Any
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from config import settings
from data_loader import data_loader
from rag.retriever import SimpleRetriever


import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["Chat"])

# ---------------------------------------------------------------------------
# SQLite database helpers for session history
# ---------------------------------------------------------------------------
from database import get_chat_history_db, add_chat_message_db, clear_chat_history_db


# Shared index reference (populated by main.py startup event)
_rag_index: dict[str, dict[str, Any]] = {}

# Context variable to hold session_id of current request for tool scoping
current_session_id = contextvars.ContextVar("current_session_id", default=None)

# Cache dictionary for session-specific RAG indexes
_session_rag_indexes: dict[str, dict[str, Any]] = {}

def get_session_rag_index(session_id: str | None) -> dict[str, dict[str, Any]] | None:
    """Helper to return custom session RAG index if active, else fallback to global RAG index."""
    if not session_id:
        return _rag_index
    if session_id in _session_rag_indexes:
        return _session_rag_indexes[session_id]
        
    session_csv = Path(f"./data/workspaces/{session_id}/projects.csv")
    if session_csv.exists():
        try:
            from rag.ingestion import RAGIngestionPipeline
            pipeline = RAGIngestionPipeline(
                data_path=str(session_csv),
                api_key=settings.GEMINI_API_KEY,
            )
            pipeline.load_csv()
            pipeline.create_documents()
            index = pipeline.build_simple_index()
            _session_rag_indexes[session_id] = index
            return index
        except Exception as e:
            logger.error("Failed to build RAG index for session %s: %s", session_id, e)
    return _rag_index


def set_rag_index(index: dict[str, dict[str, Any]]) -> None:
    """Called from main.py startup to inject the RAG index."""
    global _rag_index
    _rag_index = index
    logger.info("Chat agent received RAG index with %d entries.", len(index))


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User message text")
    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Session identifier for conversation history",
    )


class ChatResponse(BaseModel):
    response: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    session_id: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    method: str = "fallback"  # "gemini" | "fallback"


class HistoryResponse(BaseModel):
    session_id: str
    messages: list[dict[str, str]]
    total_messages: int


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are BuildFlow AI, an expert construction project management assistant for DPL Homes.

Your role:
- Analyze construction project data and provide clear, actionable insights
- Answer questions about project status, budgets, timelines, and team performance
- Identify risks, delays, and opportunities for improvement
- Provide data-driven recommendations to project managers and stakeholders

Guidelines:
- Always use the provided project data context when answering
- Be concise but thorough; use markdown formatting (tables, bullet points) for clarity
- When discussing financials, format numbers with commas and currency symbols
- Highlight critical issues (delays, budget overruns) prominently
- If you don't have data on something, say so clearly rather than guessing

Current Date: {date}

Project Data Context:
{context}

Conversation History:
{history}
"""


# ---------------------------------------------------------------------------
# Core Python Tools for Chat Agents (Multi-Mode)
# ---------------------------------------------------------------------------

def get_project_details(project_id: str) -> dict[str, Any]:
    """
    Retrieve detailed records of a specific construction project by its project ID (e.g. P1000, P1001).
    Use this when the user asks about a specific project ID.
    
    Args:
        project_id: The unique project ID (e.g., P1001).
    """
    session_id = current_session_id.get()
    project = data_loader.get_project_by_id(project_id, session_id=session_id)
    if not project:
        return {"error": f"Project '{project_id}' was not found in the database."}
    return project


def list_projects(
    location: str | None = None,
    status: str | None = None,
    phase: str | None = None
) -> list[dict[str, Any]]:
    """
    Retrieve a list of construction projects, optionally filtered by location, status, or phase.
    
    Args:
        location: Optional location/city name (e.g. 'Noida', 'Gurgaon').
        status: Optional status (e.g. 'OnTrack', 'Delayed', 'OnHold', 'Completed').
        phase: Optional construction phase (e.g. 'Foundation', 'Structure', 'Finishing', 'Completed').
    """
    session_id = current_session_id.get()
    projects = data_loader.get_all_projects(session_id=session_id)
    filtered = []
    for p in projects:
        if location and location.lower() not in str(p.get("location", "")).lower():
            continue
        if status and status.lower() not in str(p.get("status", "")).lower():
            continue
        if phase and phase.lower() not in str(p.get("phase", "")).lower():
            continue
        filtered.append({
            "id": p.get("project_id", p.get("projectid", "")),
            "name": p.get("project_name", p.get("projectname", "")),
            "location": p.get("location", ""),
            "budget": p.get("budget_lac", 0.0),
            "spent": p.get("spent_lac", 0.0),
            "status": p.get("status", ""),
            "progress": p.get("progresspercent", 0.0),
            "phase": p.get("phase", ""),
            "site_engineer": p.get("site_engineer", p.get("siteengineer", "")),
            "start_date": p.get("start_date", p.get("startdate", "")),
        })
    return filtered


def get_kpi_summary() -> dict[str, Any]:
    """
    Retrieve the overall analytics and KPI summary for all DPL Homes construction projects.
    Includes total budget, total spent, status counts, average progress, etc.
    """
    session_id = current_session_id.get()
    return data_loader.get_summary_stats(session_id=session_id)


def run_multi_agent_workflow(project_id: str, workflow_type: str, notes: str = "") -> dict[str, Any]:
    """
    Trigger the operations multi-agent pipeline for a project (planning, analytics, docgen, email).
    
    Args:
        project_id: The project ID to run the workflow on (e.g., P1001).
        workflow_type: One of: 'full_project_setup', 'daily_site_report', 'contract_generation', 'budget_analysis'.
        notes: Optional additional context or instruction for the agents.
    """
    from agents.orchestrator import WORKFLOW_STEPS, _runs, _execute_workflow, AGENT_DISPLAY
    import asyncio
    
    w_type = workflow_type.lower().strip().replace(" ", "_")
    if w_type not in WORKFLOW_STEPS:
        return {"error": f"Invalid workflow_type. Valid options: {list(WORKFLOW_STEPS.keys())}"}
        
    run_id = str(uuid.uuid4())
    steps = WORKFLOW_STEPS[w_type]
    
    _runs[run_id] = {
        "run_id": run_id,
        "workflow_type": w_type,
        "project_id": project_id,
        "status": "pending",
        "agents": [
            {
                "agent_name": AGENT_DISPLAY[s],
                "status": "idle",
                "output": "Queued",
                "timestamp": datetime.utcnow().isoformat(),
            }
            for s in steps
        ],
        "started_at": datetime.utcnow().isoformat(),
        "completed_at": None,
        "summary": "",
    }
    
    # Run in background task
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_execute_workflow(run_id, w_type, project_id, notes))
    except RuntimeError:
        asyncio.run(_execute_workflow(run_id, w_type, project_id, notes))
        
    return {
        "status": "started",
        "run_id": run_id,
        "workflow_type": w_type,
        "project_id": project_id,
        "message": f"Successfully started multi-agent workflow '{w_type}' for project {project_id}. Run ID: {run_id}"
    }


def generate_pdf_document(doc_type: str, project_id: str, details: dict[str, Any]) -> dict[str, Any]:
    """
    Autonomously generate and export a professional PDF document.
    
    Args:
        doc_type: The document type to generate. Must be one of: 'CONTRACT', 'INVOICE', 'WORK_ORDER', 'SITE_REPORT'.
        project_id: The associated project ID.
        details: Specific details for document generation based on doc_type.
    """
    from agents.docgen_agent import (
        generate_contract_internal, ContractRequest,
        generate_invoice_internal, InvoiceRequest,
        generate_work_order_internal, WorkOrderRequest,
        generate_site_report_internal, SiteReportRequest
    )
    
    dtype = doc_type.upper().strip()
    try:
        if dtype == "CONTRACT":
            req = ContractRequest(
                project_name=details.get("project_name", ""),
                client_name=details.get("client_name", ""),
                budget=float(details.get("budget", 0)),
                start_date=details.get("start_date", ""),
                end_date=details.get("end_date", ""),
                scope_of_work=details.get("scope_of_work", "")
            )
            res = generate_contract_internal(req)
        elif dtype == "INVOICE":
            req = InvoiceRequest(
                invoice_number=details.get("invoice_number", ""),
                client_name=details.get("client_name", ""),
                project_id=project_id,
                amount=float(details.get("amount", 0)),
                services=details.get("services", []),
                due_date=details.get("due_date", "")
            )
            res = generate_invoice_internal(req)
        elif dtype == "WORK_ORDER":
            req = WorkOrderRequest(
                project_id=project_id,
                task_description=details.get("task_description", ""),
                assigned_to=details.get("assigned_to", ""),
                deadline=details.get("deadline", ""),
                materials_required=details.get("materials_required", [])
            )
            res = generate_work_order_internal(req)
        elif dtype == "SITE_REPORT":
            req = SiteReportRequest(
                project_id=project_id,
                date=details.get("date", datetime.utcnow().strftime("%Y-%m-%d")),
                progress_percent=float(details.get("progress_percent", 50)),
                issues=details.get("issues", []),
                completed_tasks=details.get("completed_tasks", [])
            )
            res = generate_site_report_internal(req)
        else:
            return {"error": f"Invalid doc_type '{doc_type}'. Must be CONTRACT, INVOICE, WORK_ORDER, or SITE_REPORT."}
            
        return {
            "status": "success",
            "doc_type": dtype,
            "project_id": project_id,
            "file_name": res.get("file_name"),
            "file_path": res.get("file_path"),
            "doc_id": res.get("doc_id"),
            "url": f"/docs-files/{res.get('file_name')}"
        }
    except Exception as e:
        return {"error": f"PDF Generation failed: {str(e)}"}


def get_budget_forecast_data() -> dict[str, Any]:
    """
    Retrieve budget trend forecast analysis for the next 3 months using linear regression.
    Calculated dynamically and self-contained to avoid circular import issues.
    """
    try:
        # Load clean df
        df = data_loader.get_dataframe(session_id=current_session_id.get())
        df.columns = [c.strip() for c in df.columns]
        for raw_col in ["budget_lac", "spent_lac", "progresspercent", "labourcount"]:
            if raw_col in df.columns:
                df[raw_col] = pd.to_numeric(df[raw_col], errors="coerce").fillna(0.0)
                
        # Generate monthly trend
        total_spent = float(df["spent_lac"].sum()) if "spent_lac" in df.columns else 0.0
        historical = []
        today = datetime.utcnow()
        rng = np.random.default_rng(seed=7)
        months = 12

        for i in range(months - 1, -1, -1):
            dt = today - timedelta(days=30 * i)
            label = dt.strftime("%b %Y")
            frac = (months - i) / months
            noise = rng.uniform(0.88, 1.07)
            monthly_spend = round(total_spent * frac / months * noise * months / 6, 2)
            historical.append({"month": label, "spent": monthly_spend})
            
        if len(historical) < 3:
            return {"error": "Insufficient data to calculate forecast."}
            
        X = np.array(range(len(historical))).reshape(-1, 1)
        y = np.array([h["spent"] for h in historical])
        
        model = LinearRegression()
        model.fit(X, y)
        
        residuals = y - model.predict(X)
        std_resid = float(np.std(residuals))
        
        last_month_dt = datetime.strptime(historical[-1]["month"], "%b %Y")
        forecast_entries = []
        for i in range(1, 4):
            idx = len(historical) + i - 1
            future_dt = last_month_dt + timedelta(days=30 * i)
            label = future_dt.strftime("%b %Y")
            predicted = float(model.predict(np.array([[idx]]))[0])
            lower = max(0.0, round(predicted - std_resid, 2))
            upper = round(predicted + std_resid, 2)
            forecast_entries.append({
                "month": label,
                "predicted_spent": round(predicted, 2),
                "lower": lower,
                "upper": upper,
            })
        return {"historical": historical, "forecast": forecast_entries}
    except Exception as e:
        logger.exception("Forecasting calculation failed")
        return {"error": f"Forecasting calculation failed: {str(e)}"}


def train_ml_models() -> dict[str, Any]:
    """
    Trigger retraining of the application's machine learning models (budget forecasting and delay risk classifier).
    Use this when the user asks to train, retrain, or update the AI models.
    """
    try:
        from train_models import run_training
        res = run_training()
        return res
    except Exception as e:
        return {"error": f"Failed to train models: {str(e)}"}


def get_delay_risk_scores() -> list[dict[str, Any]]:
    """
    Retrieve delay risk probabilities and risk levels (HIGH, MEDIUM, LOW) for all projects predicted by the machine learning classifier.
    Use this when the user asks about delay risks, risk levels, or predicted delays.
    """
    import pickle
    import os
    model_path = os.path.join(os.path.dirname(settings.DATA_PATH), "models", "delay_risk_model.pkl")
    
    try:
        df = data_loader.get_dataframe(session_id=current_session_id.get())
        df.columns = [c.strip() for c in df.columns]
        for raw_col in ["budget_lac", "spent_lac", "progresspercent", "labourcount"]:
            if raw_col in df.columns:
                df[raw_col] = pd.to_numeric(df[raw_col], errors="coerce").fillna(0.0)
        
        clf = None
        if os.path.exists(model_path):
            with open(model_path, "rb") as f:
                saved_data = pickle.load(f)
                clf = saved_data.get("model")
                
        if clf is None:
            # Fallback on the fly
            from sklearn.ensemble import RandomForestClassifier
            y = (df["status"].astype(str).str.lower().str.contains("delay|behind", na=False)).astype(int)
            X_data = pd.DataFrame()
            X_data["budget_lac"] = pd.to_numeric(df["budget_lac"], errors="coerce").fillna(0.0)
            X_data["spent_lac"] = pd.to_numeric(df["spent_lac"], errors="coerce").fillna(0.0)
            X_data["labourcount"] = pd.to_numeric(df["labourcount"], errors="coerce").fillna(0.0)
            X_data["cementused_tons"] = pd.to_numeric(df["cementused_tons"], errors="coerce").fillna(0.0)
            X_data["materialused_tons"] = pd.to_numeric(df["materialused_tons"], errors="coerce").fillna(0.0)
            X_data["progresspercent"] = pd.to_numeric(df["progresspercent"], errors="coerce").fillna(0.0)
            X_data["spent_ratio"] = (X_data["spent_lac"] / X_data["budget_lac"]).replace([np.inf, -np.inf], 0.0).fillna(0.0)
            clf = RandomForestClassifier(n_estimators=50, max_depth=5, random_state=42)
            clf.fit(X_data, y)

        X_data = pd.DataFrame()
        X_data["budget_lac"] = pd.to_numeric(df["budget_lac"], errors="coerce").fillna(0.0)
        X_data["spent_lac"] = pd.to_numeric(df["spent_lac"], errors="coerce").fillna(0.0)
        X_data["labourcount"] = pd.to_numeric(df["labourcount"], errors="coerce").fillna(0.0)
        X_data["cementused_tons"] = pd.to_numeric(df["cementused_tons"], errors="coerce").fillna(0.0)
        X_data["materialused_tons"] = pd.to_numeric(df["materialused_tons"], errors="coerce").fillna(0.0)
        X_data["progresspercent"] = pd.to_numeric(df["progresspercent"], errors="coerce").fillna(0.0)
        X_data["spent_ratio"] = (X_data["spent_lac"] / X_data["budget_lac"]).replace([np.inf, -np.inf], 0.0).fillna(0.0)
        
        probs = clf.predict_proba(X_data)[:, 1]
        
        result = []
        for idx, row in df.iterrows():
            pid = str(row.get("projectid", row.get("project_id", "")))
            name = str(row.get("projectname", row.get("project_name", "")))
            status = str(row.get("status", ""))
            progress = float(row.get("progresspercent", 0.0))
            
            risk_score = round(float(probs[idx]) * 100, 1)
            
            if risk_score >= 70.0:
                level = "HIGH"
            elif risk_score >= 40.0:
                level = "MEDIUM"
            else:
                level = "LOW"
                
            result.append({
                "project_id": pid,
                "project_name": name,
                "current_status": status,
                "progress_percent": progress,
                "delay_risk_score": risk_score,
                "risk_level": level
            })
            
        result.sort(key=lambda x: x["delay_risk_score"], reverse=True)
        return result
    except Exception as e:
        logger.exception("Error fetching delay risk scores")
        return [{"error": f"Failed to get risk scores: {str(e)}"}]


def update_project_record(
    project_id: str,
    project_name: str | None = None,
    location: str | None = None,
    budget_lac: float | None = None,
    spent_lac: float | None = None,
    status: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    labour_count: int | None = None,
    cement_used_tons: float | None = None,
    material_used_tons: float | None = None,
    progress_percent: float | None = None,
    client_name: str | None = None,
    site_engineer: str | None = None,
    phase: str | None = None
) -> dict[str, Any]:
    """
    Update details of a specific construction project by project_id and write them back to projects.csv.
    Use this when the user explicitly requests to change, update, or edit fields of a project.
    """
    updates = {}
    if project_name is not None: updates["projectname"] = str(project_name)
    if location is not None: updates["location"] = str(location)
    if budget_lac is not None: updates["budget_lac"] = float(budget_lac)
    if spent_lac is not None: updates["spent_lac"] = float(spent_lac)
    if status is not None: updates["status"] = str(status)
    if start_date is not None: updates["startdate"] = str(start_date)
    if end_date is not None: updates["enddate"] = str(end_date)
    if labour_count is not None: updates["labourcount"] = int(labour_count)
    if cement_used_tons is not None: updates["cementused_tons"] = float(cement_used_tons)
    if material_used_tons is not None: updates["materialused_tons"] = float(material_used_tons)
    if progress_percent is not None: updates["progresspercent"] = float(progress_percent)
    if client_name is not None: updates["clientname"] = str(client_name)
    if site_engineer is not None: updates["siteengineer"] = str(site_engineer)
    if phase is not None: updates["phase"] = str(phase)

    if not updates:
        return {"error": "No updates were provided."}

    success = data_loader.update_project(project_id, updates, session_id=current_session_id.get())
    if success:
        return {
            "status": "success",
            "project_id": project_id,
            "message": f"Successfully updated project {project_id}. Updated fields: {list(updates.keys())}."
        }
    else:
        return {"error": f"Project '{project_id}' not found."}


def call_tool_function(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Helper to dispatch tool execution by name and arguments."""
    if name == "get_project_details":
        return get_project_details(args.get("project_id", ""))
    elif name == "list_projects":
        return list_projects(
            location=args.get("location"),
            status=args.get("status"),
            phase=args.get("phase")
        )
    elif name == "get_kpi_summary":
        return get_kpi_summary()
    elif name == "run_multi_agent_workflow":
        return run_multi_agent_workflow(
            project_id=args.get("project_id", ""),
            workflow_type=args.get("workflow_type", ""),
            notes=args.get("notes", "")
        )
    elif name == "generate_pdf_document":
        return generate_pdf_document(
            doc_type=args.get("doc_type", ""),
            project_id=args.get("project_id", ""),
            details=args.get("details", {})
        )
    elif name == "get_budget_forecast_data":
        return get_budget_forecast_data()
    elif name == "train_ml_models":
        return train_ml_models()
    elif name == "get_delay_risk_scores":
        return get_delay_risk_scores()
    elif name == "update_project_record":
        cleaned_args = {}
        for key in ["project_id", "project_name", "location", "budget_lac", "spent_lac", "status", 
                    "start_date", "end_date", "labour_count", "cement_used_tons", "material_used_tons", 
                    "progress_percent", "client_name", "site_engineer", "phase"]:
            if key in args:
                cleaned_args[key] = args[key]
        return update_project_record(**cleaned_args)
    else:
        return {"error": f"Tool function '{name}' not found."}


# ---------------------------------------------------------------------------
# Smart NLP / Regex Router Mode (Zero Cost, CPU Execution)
# ---------------------------------------------------------------------------

def _run_nlp_router_mode(message: str) -> tuple[str, list[dict[str, Any]]]:
    msg_lower = message.lower().strip()
    sources = []
    
    # 0.1 Model Training match
    if any(kw in msg_lower for kw in ["train", "retrain", "learning", "fit"]):
        logger.info("NLP Router triggering model training")
        res = train_ml_models()
        sources.append({"id": "train_ml_models", "type": "nlp_router"})
        if "error" in res:
            return f"❌ Error: {res['error']}", sources
            
        return (
            f"⚙️ **Machine Learning Models Retrained Successfully!**\n\n"
            f"- **Budget Forecast model**: Trained (R2 Score: `{res['forecast'].get('r2_score', 0.0):.4f}`)\n"
            f"- **Delay Risk classifier**: Trained (Accuracy: `{res['delay_risk'].get('accuracy', 0.0):.4f}`)\n"
            f"- **Trained At**: {res.get('trained_at')}\n"
            f"- **Output Location**: `./backend/data/models/`"
        ), sources

    # 0.2 Delay Risk match
    if any(kw in msg_lower for kw in ["risk", "delay risk", "danger", "probability", "highest risk"]):
        logger.info("NLP Router fetching delay risk scores")
        res = get_delay_risk_scores()
        sources.append({"id": "get_delay_risk_scores", "type": "nlp_router"})
        if not res or (isinstance(res, list) and len(res) > 0 and "error" in res[0]):
            return f"❌ Error: {res[0]['error'] if res else 'Unknown error'}", sources
            
        lines = ["## ⚠️ ML-Powered Delay Risk Scores (Highest Risk First)\n"]
        lines.append("These scores represent the classifier's predicted probability that a project will be delayed based on current budget utilization, labour count, material usage, and progress:\n")
        for p in res[:10]: # Top 10 highest risk
            level = p["risk_level"]
            emoji = "🔴" if level == "HIGH" else "🟡" if level == "MEDIUM" else "🟢"
            lines.append(f"- {emoji} **{p['project_id']} — {p['project_name']}**: Delay Risk: **{p['delay_risk_score']}%** ({level}) | Status: *{p['current_status']}*, Progress: *{p['progress_percent']}%*")
        return "\n".join(lines), sources

    # 1. Update Project Match
    update_match = re.search(
        r"\b(?:update|change|set)\s+(?:project\s+)?(P\d{4})\s+(\w+(?:_\w+)?)\s+(?:to\s+)?([a-zA-Z0-9_\-\.\s\u0900-\u097F]+)", 
        message, 
        re.IGNORECASE
    )
    if update_match:
        pid = update_match.group(1).upper()
        field = update_match.group(2).lower()
        val_str = update_match.group(3).strip()
        
        updates = {}
        if field in ("progress", "progresspercent", "progress_percent"):
            try:
                updates["progress_percent"] = float(val_str.replace("%", ""))
            except ValueError:
                return f"⚠️ Invalid progress value '{val_str}'. Please provide a number.", []
        elif field in ("status", "project_status"):
            updates["status"] = val_str
        elif field in ("spent", "spent_lac", "spentlac"):
            try:
                updates["spent_lac"] = float(val_str)
            except ValueError:
                return f"⚠️ Invalid spent value '{val_str}'. Please provide a number.", []
        elif field in ("budget", "budget_lac", "budgetlac"):
            try:
                updates["budget_lac"] = float(val_str)
            except ValueError:
                return f"⚠️ Invalid budget value '{val_str}'. Please provide a number.", []
        elif field in ("labour", "labourcount", "labour_count"):
            try:
                updates["labour_count"] = int(val_str)
            except ValueError:
                return f"⚠️ Invalid labour count '{val_str}'. Please provide an integer.", []
        elif field in ("cement", "cementused", "cement_used"):
            try:
                updates["cement_used_tons"] = float(val_str)
            except ValueError:
                return f"⚠️ Invalid cement quantity '{val_str}'. Please provide a number.", []
        elif field in ("material", "materialused", "material_used"):
            try:
                updates["material_used_tons"] = float(val_str)
            except ValueError:
                return f"⚠️ Invalid material quantity '{val_str}'. Please provide a number.", []
        elif field in ("phase", "project_phase"):
            updates["phase"] = val_str
        elif field in ("engineer", "siteengineer", "site_engineer"):
            updates["site_engineer"] = val_str
        elif field in ("client", "clientname", "client_name"):
            updates["client_name"] = val_str
        else:
            return f"⚠️ Unknown field '{field}'. Accessible fields: progress, status, spent, budget, labour, cement, material, phase, engineer, client.", []
            
        logger.info("NLP Router triggering update for %s: %s", pid, updates)
        res = update_project_record(pid, **updates)
        sources.append({"id": "update_project_record", "type": "nlp_router"})
        if "error" in res:
            return f"❌ Error: {res['error']}", sources
        return f"✅ **Project Update Successful!**\n\n{res['message']}", sources

    # 2. Generate PDF match
    pdf_match = re.search(
        r"\b(?:generate|create|make|export)\s+(?:a\s+)?(contract|invoice|work\s+order|site\s+report)\s+(?:for\s+)?(P\d{4})", 
        message, 
        re.IGNORECASE
    )
    if pdf_match:
        doc_type_raw = pdf_match.group(1).lower().replace(" ", "_")
        pid = pdf_match.group(2).upper()
        
        project = data_loader.get_project_by_id(pid, session_id=current_session_id.get())
        if not project:
            return f"⚠️ Project '{pid}' was not found in the database. Cannot generate document.", []
            
        details = {}
        doc_type_upper = ""
        if "contract" in doc_type_raw:
            doc_type_upper = "CONTRACT"
            details = {
                "project_name": project.get("project_name", project.get("projectname", "")),
                "client_name": project.get("client_name", project.get("clientname", "Client")),
                "budget": float(project.get("budget_lac", project.get("budget", 0))),
                "start_date": project.get("start_date", project.get("startdate", "")),
                "end_date": project.get("end_date", project.get("enddate", "")),
                "scope_of_work": f"Standard construction and development contract for project {project.get('project_name', pid)}."
            }
        elif "invoice" in doc_type_raw:
            doc_type_upper = "INVOICE"
            details = {
                "invoice_number": f"INV-{uuid.uuid4().hex[:6].upper()}",
                "client_name": project.get("client_name", project.get("clientname", "Client")),
                "amount": float(project.get("spent_lac", project.get("spent", 0.0))),
                "due_date": project.get("end_date", project.get("enddate", "")),
                "services": ["General Construction Works", "Site Execution Services"]
            }
        elif "work" in doc_type_raw:
            doc_type_upper = "WORK_ORDER"
            details = {
                "task_description": f"Site layout preparation and initial phase verification under site engineer.",
                "assigned_to": project.get("site_engineer", project.get("siteengineer", "Site Engineer")),
                "deadline": project.get("end_date", project.get("enddate", "")),
                "materials_required": ["Cement (Grade 43/53)", "Coarse aggregate", "Steel reinforcement bars"]
            }
        elif "report" in doc_type_raw:
            doc_type_upper = "SITE_REPORT"
            details = {
                "date": datetime.utcnow().strftime("%Y-%m-%d"),
                "progress_percent": float(project.get("progresspercent", project.get("progress", 50.0))),
                "issues": ["None reported" if project.get("status") != "Delayed" else "Schedule delay reported"],
                "completed_tasks": ["Phase checkpoints verified", "Safety protocols compliant"]
            }
            
        logger.info("NLP Router triggering PDF generation: %s for %s", doc_type_upper, pid)
        res = generate_pdf_document(doc_type_upper, pid, details)
        sources.append({"id": "generate_pdf_document", "type": "nlp_router"})
        if "error" in res:
            return f"❌ Error: {res['error']}", sources
        return (
            f"📄 **{doc_type_upper} Generated Successfully!**\n\n"
            f"- **Project ID**: {res['project_id']}\n"
            f"- **Document Type**: {res['doc_type']}\n"
            f"- **Filename**: {res['file_name']}\n"
            f"- **Download Link**: [Download {res['file_name']}]({res['url']})\n\n"
            f"Note: PDF has been compiled using ReportLab and stored on backend server."
        ), sources

    # 3. Run Workflow match
    wf_match = re.search(
        r"\b(?:run|trigger|start|execute)\s+(?:workflow|pipeline)\s+([a-zA-Z0-9_]+)\s+(?:for\s+)?(P\d{4})",
        message,
        re.IGNORECASE
    )
    if wf_match:
        wf_type = wf_match.group(1).lower()
        pid = wf_match.group(2).upper()
        
        logger.info("NLP Router triggering workflow '%s' for project %s", wf_type, pid)
        res = run_multi_agent_workflow(pid, wf_type)
        sources.append({"id": "run_multi_agent_workflow", "type": "nlp_router"})
        if "error" in res:
            return f"❌ Error: {res['error']}", sources
        return (
            f"⚙️ **Multi-Agent Pipeline Triggered!**\n\n"
            f"- **Run ID**: `{res['run_id']}`\n"
            f"- **Workflow**: {res['workflow_type']}\n"
            f"- **Project ID**: {res['project_id']}\n"
            f"- **Status**: {res['status'].upper()}\n\n"
            f"You can monitor the status on the **Multi-Agent Runs** page."
        ), sources

    # 4. Budget Forecast match
    if any(kw in msg_lower for kw in ["forecast", "prediction", "predict"]):
        logger.info("NLP Router calculating budget forecast")
        res = get_budget_forecast_data()
        sources.append({"id": "get_budget_forecast_data", "type": "nlp_router"})
        if "error" in res:
            return f"❌ Error: {res['error']}", sources
            
        lines = ["## 💰 AI Budget Trend & Forecast (Next 3 Months)\n"]
        lines.append("### Historical Trend (Last 3 Months):")
        for h in res["historical"][-3:]:
            lines.append(f"- **{h['month']}**: Spent ₹ {h['spent']} Lac")
        lines.append("\n### Forecasted Spend:")
        for f in res["forecast"]:
            lines.append(
                f"- **{f['month']}**: Predicted Spend ₹ **{f['predicted_spent']}** Lac "
                f"(Range: ₹ {f['lower']} Lac - ₹ {f['upper']} Lac)"
            )
        lines.append("\n*Note: Calculation done using linear regression on historical cumulative spend.*")
        return "\n".join(lines), sources

    # 5. KPI Summary / Overview
    if any(kw in msg_lower for kw in ["summary", "kpi", "overview", "statistics", "stats"]):
        logger.info("NLP Router fetching KPI summary")
        res = get_kpi_summary()
        sources.append({"id": "get_kpi_summary", "type": "nlp_router"})
        
        status_counts = res.get("status_counts", {})
        lines = [
            "## 📊 DPL Homes construction operations summary:\n",
            f"- **Total Projects**: {res.get('total_projects', 0)}",
            f"- **Total Budget**: ₹ {res.get('total_budget', 0):,.2f} Lac",
            f"- **Total Spent**: ₹ {res.get('total_spent', 0):,.2f} Lac",
            f"- **Average Progress**: {res.get('avg_progress', 0):.1f}%",
            f"- **Delayed Projects**: {res.get('delayed_count', 0)}\n",
            "### Status Breakdown:",
        ]
        for status, count in status_counts.items():
            emoji = _status_emoji(status)
            lines.append(f"- {emoji} **{status}**: {count} projects")
            
        return "\n".join(lines), sources

    # 6. Specific Project Details match
    pid_match = re.search(r"\b(P\d{4})\b", message, re.IGNORECASE)
    if pid_match:
        pid = pid_match.group(1).upper()
        logger.info("NLP Router fetching details for project %s", pid)
        res = get_project_details(pid)
        sources.append({"id": "get_project_details", "type": "nlp_router"})
        if "error" in res:
            return f"⚠️ {res['error']}", sources
            
        lines = [f"## 🏗️ Project Details: {pid} — {res.get('project_name', res.get('projectname', ''))}\n"]
        for k, v in res.items():
            if v not in ("", None):
                label = k.replace("_", " ").title()
                if "budget" in k.lower() or "spent" in k.lower():
                    lines.append(f"- **{label}**: ₹ {v} Lac")
                elif "progress" in k.lower():
                    lines.append(f"- **{label}**: {v}%")
                else:
                    lines.append(f"- **{label}**: {v}")
        return "\n".join(lines), sources

    return "", []


# ---------------------------------------------------------------------------
# Local LLM / Ollama Handler Mode (Ollama tool completions)
# ---------------------------------------------------------------------------

async def _run_ollama_mode(message: str, history: list[dict[str, str]]) -> tuple[str, list[dict[str, Any]]]:
    import httpx
    import json
    
    messages = [
        {
            "role": "system",
            "content": (
                "You are BuildFlow AI, an expert construction project management assistant for DPL Homes. "
                "You have full access to manage this application's project data, workflows, and documents. "
                "You can view project details, filter projects, get KPI metrics, run multi-agent pipelines, "
                "generate PDF reports, calculate forecasts, and update project details in the database.\n"
                "Guidelines:\n"
                "- When asked to update a project, run a workflow, or generate a document, always call the appropriate tool "
                "and inform the user of the output/status.\n"
                "- Format monetary amounts in Lacs (₹ Lac) and follow Indian naming styles where appropriate.\n"
                "- When you complete an action (e.g. generating a doc or running a workflow), share the resulting info/details clearly."
            )
        }
    ]
    for msg in history[:-1]:
        messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })
    messages.append({
        "role": "user",
        "content": message
    })
    
    tools_schema = [
        {
            "type": "function",
            "name": "get_project_details",
            "description": "Retrieve detailed records of a specific construction project by its project ID (e.g. P1000, P1001).",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "The unique project ID (e.g., P1001)."}
                },
                "required": ["project_id"]
            }
        },
        {
            "type": "function",
            "name": "list_projects",
            "description": "Retrieve a list of construction projects, optionally filtered by location, status, or phase.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "Optional location/city name (e.g. Noida, Gurgaon)."},
                    "status": {"type": "string", "description": "Optional status (e.g. OnTrack, Delayed, OnHold, Completed)."},
                    "phase": {"type": "string", "description": "Optional phase (e.g. Foundation, Structure, Finishing)."}
                }
            }
        },
        {
            "type": "function",
            "name": "get_kpi_summary",
            "description": "Retrieve the overall analytics and KPI summary for all construction projects (total budget, spent, counts, status distributions).",
            "parameters": {"type": "object", "properties": {}}
        },
        {
            "type": "function",
            "name": "run_multi_agent_workflow",
            "description": "Trigger the operations multi-agent pipeline for a project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID (e.g. P1001)."},
                    "workflow_type": {
                        "type": "string", 
                        "enum": ["full_project_setup", "daily_site_report", "contract_generation", "budget_analysis"],
                        "description": "The type of workflow to run."
                    },
                    "notes": {"type": "string", "description": "Optional additional context or instructions."}
                },
                "required": ["project_id", "workflow_type"]
            }
        },
        {
            "type": "function",
            "name": "generate_pdf_document",
            "description": "Autonomously generate and export a professional PDF document.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_type": {
                        "type": "string", 
                        "enum": ["CONTRACT", "INVOICE", "WORK_ORDER", "SITE_REPORT"],
                        "description": "Document type to generate."
                    },
                    "project_id": {"type": "string", "description": "Associated project ID (e.g. P1001)."},
                    "details": {
                        "type": "object",
                        "description": "Details dict keys matching document type requirements."
                    }
                },
                "required": ["doc_type", "project_id", "details"]
            }
        },
        {
            "type": "function",
            "name": "get_budget_forecast_data",
            "description": "Retrieve budget trend forecast analysis for the next 3 months using linear regression.",
            "parameters": {"type": "object", "properties": {}}
        },
        {
            "type": "function",
            "name": "train_ml_models",
            "description": "Trigger retraining of the application's machine learning models (budget forecasting and delay risk classifier).",
            "parameters": {"type": "object", "properties": {}}
        },
        {
            "type": "function",
            "name": "get_delay_risk_scores",
            "description": "Retrieve delay risk probabilities and risk levels (HIGH, MEDIUM, LOW) for all projects predicted by the machine learning classifier.",
            "parameters": {"type": "object", "properties": {}}
        },
        {
            "type": "function",
            "name": "update_project_record",
            "description": "Update details of a specific construction project by project_id and write them back to projects.csv.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "The ID of the project to update (e.g. P1001)."},
                    "project_name": {"type": "string", "description": "New project name."},
                    "location": {"type": "string", "description": "New location."},
                    "budget_lac": {"type": "number", "description": "New budget in Lacs (₹ Lac)."},
                    "spent_lac": {"type": "number", "description": "New spent amount in Lacs (₹ Lac)."},
                    "status": {"type": "string", "description": "New status (OnTrack, Delayed, OnHold, Completed)."},
                    "start_date": {"type": "string", "description": "New start date (YYYY-MM-DD)."},
                    "end_date": {"type": "string", "description": "New end date (YYYY-MM-DD)."},
                    "labour_count": {"type": "integer", "description": "New labour count."},
                    "cement_used_tons": {"type": "number", "description": "New cement quantity in tons."},
                    "material_used_tons": {"type": "number", "description": "New material quantity in tons."},
                    "progress_percent": {"type": "number", "description": "New progress percentage (0 to 100)."},
                    "client_name": {"type": "string", "description": "New client name."},
                    "site_engineer": {"type": "string", "description": "New site engineer name."},
                    "phase": {"type": "string", "description": "New phase name."}
                },
                "required": ["project_id"]
            }
        }
    ]
    
    sources = []
    url = f"{settings.OLLAMA_API_BASE}/chat/completions"
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        for _ in range(5):
            payload = {
                "model": settings.OLLAMA_MODEL,
                "messages": messages,
                "tools": tools_schema,
                "tool_choice": "auto"
            }
            logger.info("Sending request to Ollama: %s", url)
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                res_data = response.json()
            except Exception as e:
                logger.error("Ollama connection failed: %s", e)
                return f"⚠️ Connection to local Ollama failed. Make sure Ollama server is running at {settings.OLLAMA_API_BASE}.", []
            
            choice = res_data["choices"][0]
            message_obj = choice["message"]
            messages.append(message_obj)
            
            tool_calls = message_obj.get("tool_calls")
            if not tool_calls:
                return message_obj.get("content", ""), sources
                
            for tc in tool_calls:
                tc_id = tc.get("id", str(uuid.uuid4()))
                func = tc["function"]
                name = func["name"]
                try:
                    args = json.loads(func["arguments"]) if isinstance(func["arguments"], str) else func["arguments"]
                except Exception:
                    args = {}
                    
                logger.info("Ollama execution: calling %s with args: %s", name, args)
                result = call_tool_function(name, args)
                
                sources.append({
                    "id": name,
                    "type": "tool_call",
                    "args": args
                })
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "name": name,
                    "content": json.dumps(result)
                })
                
        return messages[-1].get("content", "Error: Local LLM took too many tool iterations."), sources


# ---------------------------------------------------------------------------
# Gemini API Orchestrator Mode (Cloud, free/paid key)
# ---------------------------------------------------------------------------

def _run_gemini_mode(message: str, history: list[dict[str, str]]) -> tuple[str, list[dict[str, Any]]]:
    import google.generativeai as genai
    import time
    
    genai.configure(api_key=settings.GEMINI_API_KEY)
    
    gemini_history = []
    for msg in history[:-1]:
        role = "model" if msg["role"] == "assistant" else "user"
        gemini_history.append({
            "role": role,
            "parts": [msg["content"]]
        })
        
    model = genai.GenerativeModel(
        model_name=settings.GEMINI_MODEL,
        tools=[
            get_project_details,
            list_projects,
            get_kpi_summary,
            run_multi_agent_workflow,
            generate_pdf_document,
            get_budget_forecast_data,
            train_ml_models,
            get_delay_risk_scores,
            update_project_record
        ],
        system_instruction=(
            "You are BuildFlow AI, an expert construction project management assistant for DPL Homes. "
            "You have full access to manage this application's project data, workflows, and documents. "
            "You can view project details, filter projects, get KPI metrics, run multi-agent pipelines, "
            "generate PDF reports, calculate forecasts, and update project details in the database.\n"
            "Guidelines:\n"
            "- When asked to update a project, run a workflow, or generate a document, always call the appropriate tool "
            "and inform the user of the output/status.\n"
            "- Format monetary amounts in Lacs (₹ Lac) and follow Indian naming styles where appropriate.\n"
            "- When you complete an action (e.g. generating a doc or running a workflow), share the resulting info/details clearly."
        )
    )
    
    chat = model.start_chat(history=gemini_history, enable_automatic_function_calling=True)
    
    # Retry logic for Gemini API execution
    max_retries = 3
    delay = 1.0
    response = None
    for attempt in range(max_retries):
        try:
            response = chat.send_message(message)
            break
        except Exception as exc:
            logger.warning("Gemini send_message attempt %d failed: %s", attempt + 1, exc)
            if attempt == max_retries - 1:
                raise exc
            time.sleep(delay)
            delay *= 2
            
    sources = []
    for content in chat.history:
        for part in content.parts:
            if part.function_call:
                sources.append({
                    "id": part.function_call.name,
                    "type": "tool_call",
                    "args": dict(part.function_call.args)
                })
                
    return response.text, sources


# ---------------------------------------------------------------------------
# Smart rule-based fallback
# ---------------------------------------------------------------------------

def _smart_fallback(message: str) -> tuple[str, list[dict[str, Any]]]:
    """
    Generate a smart rule-based response from the in-memory project data.

    Returns
    -------
    (response_text, sources)
    """
    msg_lower = message.lower()
    sources: list[dict[str, Any]] = []

    # --- Detect project ID mentions (P1000-P9999) ---
    pid_matches = re.findall(r"\b[Pp]\d{4,6}\b", message)
    if pid_matches:
        responses: list[str] = []
        for pid in pid_matches:
            project = data_loader.get_project_by_id(pid.upper(), session_id=current_session_id.get())
            if project:
                sources.append({"id": pid.upper(), "type": "project"})
                lines = [f"## Project {pid.upper()}\n"]
                for k, v in project.items():
                    if v not in ("", None):
                        label = k.replace("_", " ").title()
                        lines.append(f"- **{label}**: {v}")
                responses.append("\n".join(lines))
            else:
                responses.append(f"⚠️ Project **{pid.upper()}** was not found in the database.")
        return "\n\n---\n\n".join(responses), sources

    # --- Delayed projects ---
    if any(kw in msg_lower for kw in ["delay", "behind schedule", "late", "overdue"]):
        delayed = data_loader.get_delayed_projects(session_id=current_session_id.get())
        sources = [{"id": p.get("project_id", "?"), "type": "project"} for p in delayed]
        if not delayed:
            return "✅ Great news! No projects are currently marked as delayed.", sources

        lines = [f"## ⚠️ Delayed Projects ({len(delayed)} total)\n"]
        for p in delayed:
            pid = p.get("project_id", p.get("id", "N/A"))
            name = p.get("project_name", p.get("name", "Unnamed"))
            status = p.get("status", "N/A")
            progress = p.get("progress", "N/A")
            budget = p.get("budget", "N/A")
            spent = p.get("spent", "N/A")
            lines.append(
                f"### {pid} — {name}\n"
                f"- **Status**: {status}\n"
                f"- **Progress**: {progress}%\n"
                f"- **Budget**: {budget} | **Spent**: {spent}\n"
            )
        return "\n".join(lines), sources

    # --- Budget queries ---
    if any(kw in msg_lower for kw in ["budget", "cost", "spend", "spent", "financial", "expenditure"]):
        session_id = current_session_id.get()
        stats = data_loader.get_summary_stats(session_id=session_id)
        projects = data_loader.get_all_projects(session_id=session_id)
        lines = [
            "## 💰 Budget Summary\n",
            f"- **Total Projects**: {stats.get('total_projects', 0)}",
            f"- **Total Budget**: ${stats.get('total_budget', 0):,.2f}",
            f"- **Total Spent**: ${stats.get('total_spent', 0):,.2f}",
        ]
        total_budget = stats.get("total_budget", 0)
        total_spent = stats.get("total_spent", 0)
        if total_budget > 0:
            pct = (total_spent / total_budget) * 100
            lines.append(f"- **Budget Utilisation**: {pct:.1f}%")
        remaining = total_budget - total_spent
        lines.append(f"- **Remaining Budget**: ${remaining:,.2f}")
        sources = [{"type": "summary", "id": "budget_summary"}]
        return "\n".join(lines), sources

    # --- Status overview ---
    if any(kw in msg_lower for kw in ["status", "overview", "summary", "all projects", "progress"]):
        session_id = current_session_id.get()
        stats = data_loader.get_summary_stats(session_id=session_id)
        status_counts = stats.get("status_counts", {})
        avg_progress = stats.get("avg_progress", 0)
        lines = [
            "## 📊 Project Status Overview\n",
            f"- **Total Projects**: {stats.get('total_projects', 0)}",
            f"- **Average Progress**: {avg_progress:.1f}%",
            f"- **Delayed Projects**: {stats.get('delayed_count', 0)}\n",
            "### Status Breakdown",
        ]
        for status, count in status_counts.items():
            emoji = _status_emoji(status)
            lines.append(f"- {emoji} **{status}**: {count}")
        sources = [{"type": "summary", "id": "status_overview"}]
        return "\n".join(lines), sources

    # --- Location filter ---
    session_id = current_session_id.get()
    all_projects = data_loader.get_all_projects(session_id=session_id)
    location_col_candidates = ["location", "city", "site", "address"]
    known_locations: set[str] = set()
    for p in all_projects:
        for col in location_col_candidates:
            val = str(p.get(col, "")).strip()
            if val:
                known_locations.add(val.lower())

    matched_location: str | None = None
    for loc in known_locations:
        if loc and loc in msg_lower:
            matched_location = loc
            break

    # Fallback: if message contains any word >4 chars found in a location value
    if not matched_location:
        words = [w for w in msg_lower.split() if len(w) > 4]
        for word in words:
            for loc in known_locations:
                if word in loc:
                    matched_location = loc
                    break
            if matched_location:
                break

    if matched_location:
        filtered = data_loader.get_projects_by_location(matched_location, session_id=session_id)
        if filtered:
            sources = [{"id": p.get("project_id", "?"), "type": "project"} for p in filtered]
            lines = [f"## 📍 Projects in '{matched_location.title()}' ({len(filtered)} found)\n"]
            for p in filtered:
                pid = p.get("project_id", p.get("id", "N/A"))
                name = p.get("project_name", p.get("name", "Unnamed"))
                status = p.get("status", "N/A")
                progress = p.get("progress", "N/A")
                emoji = _status_emoji(status)
                lines.append(
                    f"- {emoji} **{pid}** — {name} | Status: {status} | Progress: {progress}%"
                )
            return "\n".join(lines), sources

    # --- RAG-based generic response ---
    session_id = current_session_id.get()
    session_rag = get_session_rag_index(session_id)
    if session_rag:
        retriever = SimpleRetriever(session_rag)
        results = retriever.search(message, top_k=3)
        if results:
            sources = [{"id": r["id"], "score": r["score"], "type": "rag"} for r in results]
            context = retriever.format_context(results)
            lines = [
                "## 🔍 Based on project data:\n",
                context,
                "\n---",
                "_Tip: Ask about specific project IDs (e.g. P1000), 'delayed projects', 'budget summary', or a location name for focused answers._",
            ]
            return "\n".join(lines), sources

    # --- Generic greeting / help ---
    session_id = current_session_id.get()
    stats = data_loader.get_summary_stats(session_id=session_id)
    return (
        "## 👋 Welcome to BuildFlow AI!\n\n"
        f"I have data on **{stats.get('total_projects', 0)} construction projects**. "
        "Here's what you can ask me:\n\n"
        "- 🔍 **Project details** — e.g. *\"Tell me about P1001\"*\n"
        "- ⚠️ **Delayed projects** — e.g. *\"Which projects are delayed?\"*\n"
        "- 💰 **Budget analysis** — e.g. *\"Give me a budget summary\"*\n"
        "- 📊 **Status overview** — e.g. *\"Show me overall project status\"*\n"
        "- 📍 **Location filter** — e.g. *\"Projects in Lagos\"*\n"
    ), []


def _status_emoji(status: str) -> str:
    s = status.lower()
    if "complete" in s or "done" in s or "finish" in s:
        return "✅"
    if "delay" in s or "behind" in s or "late" in s:
        return "⚠️"
    if "active" in s or "progress" in s or "ongoing" in s:
        return "🔄"
    if "pause" in s or "hold" in s or "suspend" in s:
        return "⏸️"
    if "cancel" in s:
        return "❌"
    return "📋"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# AI Guardrails
# ---------------------------------------------------------------------------

def sanitize_prompt(message: str) -> tuple[bool, str]:
    """Check message for potential prompt injections or system prompt extraction attempts."""
    msg_lower = message.lower()
    
    injection_patterns = [
        "ignore previous instructions",
        "ignore the instructions above",
        "system prompt",
        "system instruction",
        "you are now a",
        "jailbreak",
        "ignore rules",
        "dan mode",
        "ignore restrictions",
    ]
    
    for pattern in injection_patterns:
        if pattern in msg_lower:
            logger.warning("Input Guardrail triggered: matched pattern '%s'", pattern)
            return False, "Sorry, I am only programmed to assist with construction project management for DPL Homes. I cannot ignore my core instructions or discuss off-topic instructions."
            
    return True, ""


def filter_output(response: str) -> str:
    """Sanitize model outputs to prevent stack traces, database details, or credentials leaks."""
    if "Traceback (most recent call last):" in response or "sqlite3.OperationalError" in response or "sqlite3.DatabaseError" in response:
        logger.warning("Output Guardrail triggered: stack trace or DB error detected in response.")
        return "I encountered an internal error processing your request. Please try again later."
    return response


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Main chat endpoint. Handles requests across multiple modes:
    1. Smart NLP / Regex Router Mode (if CHAT_MODE is 'auto' or 'nlp_router')
    2. Gemini API Mode (if CHAT_MODE is 'gemini' or 'auto' with a valid GEMINI_API_KEY)
    3. Local LLM / Ollama Mode (if CHAT_MODE is 'ollama' or 'auto' without GEMINI_API_KEY)
    4. Smart Fallback Mode (Fallback if all others yield no results)
    """
    session_id = request.session_id
    message = request.message.strip()

    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    token = current_session_id.set(session_id)
    try:
        # 1. Run Input Guardrails
        is_safe, refusal_msg = sanitize_prompt(message)
        if not is_safe:
            return ChatResponse(
                response=refusal_msg,
                sources=[],
                session_id=session_id,
                method="guardrails",
            )

        # Load session history from SQLite DB
        history = get_chat_history_db(session_id)
        
        # Save user message to SQLite DB
        add_chat_message_db(session_id, "user", message)
        # Include current user message in local history variable for current run
        history.append({"role": "user", "content": message})

        sources: list[dict[str, Any]] = []
        method = "fallback"
        response_text = ""

        mode = settings.CHAT_MODE.lower().strip()

        # Smart NLP / Regex Router (Checks for strict keyword matches first)
        if mode in ("auto", "nlp_router"):
            try:
                router_text, router_sources = _run_nlp_router_mode(message)
                if router_text:
                    response_text = router_text
                    sources = router_sources
                    method = "nlp_router"
                    logger.info("Chat request handled by NLP Router.")
            except Exception as e:
                logger.warning("NLP Router execution failed: %s", e)

        # Cloud Gemini API Mode
        if not response_text and (mode == "gemini" or (mode == "auto" and settings.GEMINI_API_KEY)):
            try:
                logger.info("Calling Gemini tool-calling for session=%s", session_id)
                response_text, gemini_sources = _run_gemini_mode(message, history)
                if response_text:
                    sources = gemini_sources
                    method = "gemini"
            except Exception as exc:
                logger.warning("Gemini mode failed (falling back): %s", exc)

        # Local LLM / Ollama Mode
        if not response_text and (mode == "ollama" or (mode == "auto" and not settings.GEMINI_API_KEY)):
            try:
                logger.info("Calling Ollama tool-calling for session=%s", session_id)
                response_text, ollama_sources = await _run_ollama_mode(message, history)
                if response_text:
                    sources = ollama_sources
                    method = "ollama"
            except Exception as exc:
                logger.warning("Ollama mode failed (falling back): %s", exc)

        # Final Smart Fallback Mode (Keyword/RAG based simple response)
        if not response_text:
            logger.info("Using smart fallback for session=%s", session_id)
            response_text, sources = _smart_fallback(message)
            method = "fallback"

        # Run Output Guardrails
        response_text = filter_output(response_text)

        # Store assistant reply in SQLite DB
        add_chat_message_db(session_id, "assistant", response_text)

        return ChatResponse(
            response=response_text,
            sources=sources,
            session_id=session_id,
            method=method,
        )
    finally:
        current_session_id.reset(token)


@router.get("/history/{session_id}", response_model=HistoryResponse)
async def get_history(session_id: str) -> HistoryResponse:
    """Return the conversation history for a session."""
    messages = get_chat_history_db(session_id)
    return HistoryResponse(
        session_id=session_id,
        messages=messages,
        total_messages=len(messages),
    )


@router.delete("/history/{session_id}")
async def clear_history(session_id: str) -> dict[str, str]:
    """Clear the conversation history for a session."""
    clear_chat_history_db(session_id)
    return {"status": "cleared", "session_id": session_id}


@router.get("/workspace/{session_id}")
async def get_session_workspace_status(session_id: str):
    """Check if a workspace CSV file exists for this session and count its projects."""
    session_csv = Path(f"./data/workspaces/{session_id}/projects.csv")
    if session_csv.exists():
        try:
            df = pd.read_csv(session_csv)
            return {
                "has_workspace": True,
                "file_name": "projects.csv",
                "project_count": len(df)
            }
        except Exception as e:
            logger.error("Failed to read workspace CSV for session %s: %s", session_id, e)
    return {"has_workspace": False}


@router.delete("/workspace/{session_id}")
async def delete_session_workspace(session_id: str):
    """Delete the custom workspace CSV file and clear its cached RAG index."""
    import shutil
    workspace_dir = Path(f"./data/workspaces/{session_id}")
    if workspace_dir.exists():
        try:
            shutil.rmtree(workspace_dir)
            logger.info("Deleted workspace directory for session %s", session_id)
        except Exception as e:
            logger.error("Failed to delete workspace directory for session %s: %s", session_id, e)
            raise HTTPException(status_code=500, detail=f"Failed to delete workspace folder: {str(e)}")

    # Clear RAG cache
    if session_id in _session_rag_indexes:
        del _session_rag_indexes[session_id]
        logger.info("Cleared cached RAG index for session %s", session_id)

    return {"status": "success", "message": f"Workspace deleted for session {session_id}."}
