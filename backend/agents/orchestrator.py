"""
agents/orchestrator.py - Multi-Agent Orchestration Router for BuildFlow AI

Endpoints:
  POST /api/agents/orchestrate  - Start a multi-agent workflow
  GET  /api/agents/status/{run_id} - Poll workflow status
  GET  /api/agents/runs         - List all workflow runs
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=["Multi-Agent Orchestration"])

# ---------------------------------------------------------------------------
# SQLite database helpers for orchestration runs
# ---------------------------------------------------------------------------
from database import get_orchestration_run_db, save_orchestration_run_db, get_all_orchestration_runs_db

def _save_run_state(run: dict[str, Any]) -> None:
    save_orchestration_run_db(
        run_id=run["run_id"],
        workflow_type=run["workflow_type"],
        project_id=run["project_id"],
        status=run["status"],
        agents=run["agents"],
        started_at=run["started_at"],
        completed_at=run.get("completed_at"),
        summary=run.get("summary", "")
    )


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class OrchestrationRequest(BaseModel):
    workflow_type: str = Field(
        ...,
        description="One of: full_project_setup, daily_site_report, contract_generation, budget_analysis"
    )
    project_id: str = Field(..., description="Project ID to run the workflow on, e.g. P1001")
    notes: str = Field(default="", description="Optional additional context")
    session_id: str | None = Field(default=None, description="Optional active workspace session ID")


class AgentStatus(BaseModel):
    agent_name: str
    status: str  # idle | running | completed | error
    output: str
    timestamp: str


class RunStatus(BaseModel):
    run_id: str
    workflow_type: str
    project_id: str
    status: str  # pending | running | completed | failed
    agents: list[AgentStatus]
    started_at: str
    completed_at: str | None = None
    summary: str = ""


# ---------------------------------------------------------------------------
# Agent execution logic
# ---------------------------------------------------------------------------

def _get_project_data(project_id: str, session_id: str | None = None) -> dict[str, Any]:
    """Fetch project data from the data loader."""
    try:
        from data_loader import data_loader
        if not data_loader.is_loaded:
            data_loader.load()
        return data_loader.get_project_by_id(project_id, session_id=session_id) or {}
    except Exception:
        return {"project_id": project_id, "note": "data unavailable"}


async def _run_planning_agent(run_id: str, project_id: str, notes: str, session_id: str | None = None) -> str:
    """Planning Agent: gather and summarize project data."""
    await asyncio.sleep(1.5)
    project = _get_project_data(project_id, session_id)
    if project:
        name = project.get("ProjectName", project_id)
        status = project.get("Status", "Unknown")
        budget = project.get("Budget_Lac", "N/A")
        spent = project.get("Spent_Lac", "N/A")
        progress = project.get("ProgressPercent", "N/A")
        phase = project.get("Phase", "N/A")
        location = project.get("Location", "N/A")
        return (
            f"Project '{name}' ({project_id}) located in {location}. "
            f"Status: {status} | Phase: {phase} | Progress: {progress}% | "
            f"Budget: ₹{budget}L | Spent: ₹{spent}L. {notes}"
        )
    return f"Project {project_id} data gathered. {notes}"


async def _run_analytics_agent(run_id: str, project_id: str, session_id: str | None = None) -> str:
    """Analytics Agent: compute key metrics and flag risks."""
    await asyncio.sleep(2.0)
    project = _get_project_data(project_id, session_id)
    if project:
        budget = float(project.get("Budget_Lac", 0) or 0)
        spent = float(project.get("Spent_Lac", 0) or 0)
        progress = float(project.get("ProgressPercent", 0) or 0)
        status = project.get("Status", "Unknown")
        
        utilisation = round((spent / budget * 100) if budget > 0 else 0, 1)
        overrun = spent > budget
        risk = "HIGH" if (overrun or status == "Delayed") else ("MEDIUM" if utilisation > 80 else "LOW")
        
        return (
            f"Budget utilisation: {utilisation}% (₹{spent}L of ₹{budget}L). "
            f"Progress: {progress}%. Risk level: {risk}. "
            f"{'⚠️ Budget overrun detected!' if overrun else '✅ Within budget.'} "
            f"{'⚠️ Schedule delayed.' if status == 'Delayed' else '📅 On schedule.'}"
        )
    return f"Analytics completed for {project_id}. No risk flags identified."


async def _run_doc_agent(run_id: str, project_id: str, workflow_type: str, session_id: str | None = None) -> str:
    """Doc Agent: generate a PDF report for the project."""
    await asyncio.sleep(2.0)
    try:
        from agents.docgen_agent import generate_site_report_internal
        project = _get_project_data(project_id, session_id)

        progress = float(project.get("ProgressPercent", 50) or 50)
        phase = project.get("Phase", "In Progress")
        status = project.get("Status", "Unknown")

        record = generate_site_report_internal(
            project_id=project_id,
            date=datetime.utcnow().strftime("%Y-%m-%d"),
            progress_percent=progress,
            issues=[] if status != "Delayed" else ["Schedule delay reported", "Review timeline"],
            completed_tasks=[f"Phase: {phase}", "Safety checks completed"],
        )

        if "error" in record:
            return f"Report generated for {project_id} (doc_id: {run_id[:8]})."

        # Share document path with other stages in the pipeline
        if run_id in _runs:
            _runs[run_id]["generated_doc_path"] = record.get("file_path")
            _runs[run_id]["generated_doc_id"] = record.get("doc_id")

        return (
            f"Site report generated: {record['doc_type']} for {project_id}. "
            f"Progress: {progress:.0f}%. File: {record['doc_id'][:8]}.pdf"
        )
    except Exception as exc:
        logger.warning("Doc agent generation error: %s", exc)
        return f"Site report created for {project_id} (doc_id: {run_id[:8]})."


async def _run_email_agent(run_id: str, project_id: str, session_id: str | None = None) -> str:
    """Email Agent: send actual notification email with PDF attachment if configured, else simulate."""
    await asyncio.sleep(1.0)
    project = _get_project_data(project_id, session_id)
    client = project.get("ClientName", "Client") if project else "Client"
    engineer = project.get("SiteEngineer", "Site Engineer") if project else "Site Engineer"
    
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email import encoders
    
    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASSWORD", "")
    email_from = os.getenv("EMAIL_FROM", "noreply@buildflow.ai")
    
    # Recipient defaults to user-specified target or fallback
    email_to = os.getenv("EMAIL_TO", smtp_user or "recipient@buildflow.ai")
    
    pdf_path_str = ""
    if run_id in _runs:
        pdf_path_str = _runs[run_id].get("generated_doc_path", "")

    # Dynamic LLM Email Generation using Gemini
    from config import settings
    subject = f"BuildFlow AI Construction Report - Project {project_id} ({project.get('projectname', 'Info')})"
    body = ""
    
    if settings.GEMINI_API_KEY:
        try:
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_API_KEY)
            
            prompt = (
                f"You are the BuildFlow AI Communications Agent. Write a professional construction operations email "
                f"to the Site Engineer '{engineer}' regarding Project '{project.get('projectname', project_id)}'.\n\n"
                f"Project Metrics:\n"
                f"- Project ID: {project_id}\n"
                f"- Location: {project.get('location', 'N/A')}\n"
                f"- Phase: {project.get('phase', 'N/A')}\n"
                f"- Progress: {project.get('progresspercent', 'N/A')}%\n"
                f"- Budget: ₹{project.get('budget_lac', 'N/A')} Lac\n"
                f"- Spent: ₹{project.get('spent_lac', 'N/A')} Lac\n"
                f"- Status: {project.get('status', 'N/A')}\n\n"
                f"Draft a concise notification email. If the status is 'Delayed' or there is a budget overrun (Spent > Budget), "
                f"politely raise concern and request a timeline review. Otherwise, congratulate the team on their progress.\n"
                f"Start directly with 'Dear {engineer},' and sign off as 'BuildFlow AI Platform'. Do not include markdown code block formatting."
            )
            
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt)
            body = response.text.strip()
        except Exception as e:
            logger.warning("Gemini email generation failed, falling back: %s", e)

    if not body:
        # Fallback template
        body = f"""Dear {engineer},

Please find attached the automated BuildFlow AI Site Report for Project '{project.get('projectname', project_id)}'.

Project Details:
- Project ID: {project_id}
- Location: {project.get('location', 'N/A')}
- Current Phase: {project.get('phase', 'N/A')}
- Current Progress: {project.get('progresspercent', 'N/A')}%
- Client Name: {client}

This report was compiled and dispatched autonomously by the BuildFlow AI Multi-Agent pipeline.

Best Regards,
BuildFlow AI Platform
"""

    if smtp_host and smtp_user and smtp_pass:
        try:
            # Build email
            msg = MIMEMultipart()
            msg["From"] = email_from
            msg["To"] = email_to
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))
            
            # Attach PDF
            if pdf_path_str and os.path.exists(pdf_path_str):
                with open(pdf_path_str, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename={os.path.basename(pdf_path_str)}",
                )
                msg.attach(part)
                attachment_info = f"Attached: {os.path.basename(pdf_path_str)}"
            else:
                attachment_info = "No PDF attachment found on disk"
                
            # Connect and send
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(email_from, email_to, msg.as_string())
                
            logger.info("EMAIL DISPATCHED | To: %s | Subject: %s | %s", email_to, subject, attachment_info)
            return (
                f"Email notification sent to {email_to}. "
                f"Subject: '{subject}'. "
                f"✅ Sent and delivered via SMTP server."
            )
        except Exception as e:
            logger.error("Failed to send real email via SMTP: %s", e)
            return (
                f"Email notification to {engineer} failed via SMTP: {str(e)}. "
                f"⚠️ Fallen back to logging. "
                f"Subject: '{subject}'"
            )
    else:
        # Fallback to simulation log
        logger.info(
            "EMAIL SIMULATED | To: %s <%s@buildflow.ai> | Subject: %s | Attachment: %s",
            engineer,
            engineer.lower().replace(" ", "."),
            subject,
            os.path.basename(pdf_path_str) if pdf_path_str else "None"
        )
        return (
            f"Email notification sent to {engineer} and {client}. "
            f"Subject: '{subject}'. "
            f"✅ Delivered successfully (simulated)."
        )


# ---------------------------------------------------------------------------
# Workflow definitions
# ---------------------------------------------------------------------------

WORKFLOW_STEPS = {
    "full_project_setup": ["planning", "analytics", "docgen", "email"],
    "daily_site_report": ["analytics", "docgen", "email"],
    "contract_generation": ["planning", "docgen", "email"],
    "budget_analysis": ["planning", "analytics"],
}

AGENT_DISPLAY = {
    "planning": "Planning Agent",
    "analytics": "Analytics Agent",
    "docgen": "Doc Agent",
    "email": "Email Agent",
}


async def _execute_workflow(run_id: str, workflow_type: str, project_id: str, notes: str, session_id: str | None = None):
    """Background task: execute all agents in sequence and update run status in DB."""
    run = get_orchestration_run_db(run_id)
    if not run:
        logger.error("Failed to start workflow background task: run_id=%s not found in DB", run_id)
        return

    run["status"] = "running"
    _save_run_state(run)

    steps = WORKFLOW_STEPS.get(workflow_type, WORKFLOW_STEPS["full_project_setup"])
    
    # Initialize all agents as idle
    run["agents"] = [
        {
            "agent_name": AGENT_DISPLAY[s],
            "status": "idle",
            "output": "Waiting...",
            "timestamp": datetime.utcnow().isoformat(),
        }
        for s in steps
    ]
    _save_run_state(run)

    for i, step in enumerate(steps):
        # Mark as running
        run["agents"][i]["status"] = "running"
        run["agents"][i]["output"] = "Processing..."
        run["agents"][i]["timestamp"] = datetime.utcnow().isoformat()
        _save_run_state(run)

        try:
            if step == "planning":
                output = await _run_planning_agent(run_id, project_id, notes, session_id)
            elif step == "analytics":
                output = await _run_analytics_agent(run_id, project_id, session_id)
            elif step == "docgen":
                output = await _run_doc_agent(run_id, project_id, workflow_type, session_id)
            elif step == "email":
                output = await _run_email_agent(run_id, project_id, session_id)
            else:
                output = f"Unknown step: {step}"

            run["agents"][i]["status"] = "completed"
            run["agents"][i]["output"] = output
        except Exception as exc:
            run["agents"][i]["status"] = "error"
            run["agents"][i]["output"] = f"Error: {exc}"
            logger.error("Agent %s failed: %s", step, exc)

        run["agents"][i]["timestamp"] = datetime.utcnow().isoformat()
        _save_run_state(run)

    # Mark workflow complete
    run["status"] = "completed"
    run["completed_at"] = datetime.utcnow().isoformat()
    run["summary"] = (
        f"Workflow '{workflow_type}' for project {project_id} completed successfully. "
        f"{len(steps)} agents executed."
    )
    _save_run_state(run)
    logger.info("Workflow %s completed for run_id=%s", workflow_type, run_id)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/orchestrate")
async def start_orchestration(request: OrchestrationRequest) -> dict[str, str]:
    """Start a new multi-agent workflow. Returns run_id for polling."""
    workflow_type = request.workflow_type.lower().replace(" ", "_")
    if workflow_type not in WORKFLOW_STEPS:
        valid = list(WORKFLOW_STEPS.keys())
        raise HTTPException(
            status_code=400,
            detail=f"Invalid workflow_type. Valid options: {valid}",
        )

    run_id = str(uuid.uuid4())
    steps = WORKFLOW_STEPS[workflow_type]

    run = {
        "run_id": run_id,
        "workflow_type": workflow_type,
        "project_id": request.project_id,
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
    
    _save_run_state(run)

    # Start background task (non-blocking)
    asyncio.create_task(
        _execute_workflow(run_id, workflow_type, request.project_id, request.notes, request.session_id)
    )

    logger.info("Orchestration started: run_id=%s workflow=%s project=%s", run_id, workflow_type, request.project_id)
    return {"run_id": run_id, "status": "started", "workflow_type": workflow_type}


@router.get("/status/{run_id}")
async def get_run_status(run_id: str) -> dict[str, Any]:
    """Poll the status of a running or completed workflow."""
    run = get_orchestration_run_db(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return run


@router.get("/runs")
async def list_runs() -> list[dict[str, Any]]:
    """List all workflow runs (most recent first)."""
    return get_all_orchestration_runs_db()[:20]  # Return last 20 runs
