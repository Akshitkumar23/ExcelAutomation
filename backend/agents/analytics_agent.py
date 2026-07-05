"""
analytics_agent.py — BuildFlow AI
FastAPI router: /api/analytics

Provides overview stats, per-project analytics, budget forecasting
(sklearn LinearRegression), labour-efficiency scatter data, and CSV export.

Column mapping from projects.csv:
    ProjectID, ProjectName, Location, Budget_Lac, Spent_Lac, Status,
    StartDate, EndDate, LabourCount, CementUsed_tons, MaterialUsed_tons,
    ProgressPercent, ClientName, SiteEngineer, Phase
"""

from __future__ import annotations

import io
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse

# ---------------------------------------------------------------------------
# Import data_loader from parent package (backend/)
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from data_loader import data_loader  # singleton instance
except ImportError:
    data_loader = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COL = {
    "id": "projectid",
    "name": "projectname",
    "location": "location",
    "budget": "budget_lac",
    "spent": "spent_lac",
    "status": "status",
    "start": "startdate",
    "end": "enddate",
    "labour": "labourcount",
    "progress": "progresspercent",
    "client": "clientname",
    "engineer": "siteengineer",
    "phase": "phase",
    "cement": "cementused_tons",
    "material": "materialused_tons",
}


def _get_df(session_id: str | None = None) -> pd.DataFrame:
    """Return a clean DataFrame from the singleton data_loader."""
    if data_loader is None:
        raise HTTPException(status_code=503, detail="data_loader not available")

    if not data_loader.is_loaded:
        try:
            data_loader.load()
        except Exception as exc:
            logger.error("DataLoader.load() failed: %s", exc)
            raise HTTPException(status_code=503, detail=f"Data load error: {exc}") from exc

    df = data_loader.get_dataframe(session_id=session_id)

    # Normalise column names to lowercase-underscore for robust matching
    df.columns = [c.strip() for c in df.columns]

    # Ensure numeric columns are properly typed
    for raw_col in [_COL["budget"], _COL["spent"], _COL["progress"], _COL["labour"]]:
        if raw_col in df.columns:
            df[raw_col] = pd.to_numeric(df[raw_col], errors="coerce").fillna(0.0)

    return df


def _safe_float(val: Any) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _generate_monthly_trend(df: pd.DataFrame, months: int = 12) -> list[dict]:
    """
    Generate synthetic monthly spend trend from aggregated project data.
    Uses ProgressPercent and Spent_Lac to back-fill a plausible 12-month series.
    """
    total_spent = float(df[_COL["spent"]].sum()) if _COL["spent"] in df.columns else 0.0
    result: list[dict] = []
    today = datetime.utcnow()
    rng = np.random.default_rng(seed=7)

    for i in range(months - 1, -1, -1):
        dt = today - timedelta(days=30 * i)
        label = dt.strftime("%b %Y")
        frac = (months - i) / months
        noise = rng.uniform(0.88, 1.07)
        monthly_spend = round(total_spent * frac / months * noise * months / 6, 2)
        result.append({"month": label, "spent": monthly_spend})

    return result


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/overview")
async def get_overview(session_id: str | None = None) -> dict[str, Any]:
    """
    High-level dashboard overview:
    total_projects, total_budget, total_spent, status_distribution,
    location_stats, monthly_trend, top_projects, avg_progress,
    on_track_count, delayed_count.
    """
    try:
        df = _get_df(session_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Overview failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if df.empty:
        return {
            "total_projects": 0,
            "total_budget": 0.0,
            "total_spent": 0.0,
            "status_distribution": {"OnTrack": 0, "Delayed": 0, "Completed": 0, "OnHold": 0},
            "location_stats": [],
            "monthly_trend": [],
            "top_projects": [],
            "avg_progress": 0.0,
            "on_track_count": 0,
            "delayed_count": 0,
        }

    # Status distribution
    status_col = _COL["status"]
    status_raw: dict[str, int] = (
        df[status_col].value_counts().to_dict() if status_col in df.columns else {}
    )
    status_dist = {
        "OnTrack": int(status_raw.get("OnTrack", 0)),
        "Delayed": int(status_raw.get("Delayed", 0)),
        "Completed": int(status_raw.get("Completed", 0)),
        "OnHold": int(status_raw.get("OnHold", 0)),
    }

    # Location stats
    location_stats: list[dict] = []
    if _COL["location"] in df.columns and _COL["budget"] in df.columns:
        loc_grp = (
            df.groupby(_COL["location"])
            .agg(
                budget=(_COL["budget"], "sum"),
                spent=(_COL["spent"], "sum"),
            )
            .reset_index()
        )
        for _, row in loc_grp.iterrows():
            location_stats.append(
                {
                    "location": row[_COL["location"]],
                    "budget": round(float(row["budget"]), 2),
                    "spent": round(float(row["spent"]), 2),
                }
            )

    # Top projects by budget
    top_projects: list[dict] = []
    if _COL["budget"] in df.columns:
        top_df = df.nlargest(5, _COL["budget"])[[_COL["id"], _COL["name"], _COL["budget"]]]
        for _, row in top_df.iterrows():
            top_projects.append(
                {
                    "id": str(row[_COL["id"]]),
                    "name": str(row[_COL["name"]]),
                    "budget": round(float(row[_COL["budget"]]), 2),
                }
            )

    avg_progress = (
        round(float(df[_COL["progress"]].mean()), 2)
        if _COL["progress"] in df.columns
        else 0.0
    )

    # Map projects to the format expected by the frontend
    projects_list: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        projects_list.append({
            "id": str(row.get(_COL["id"], "")),
            "name": str(row.get(_COL["name"], "")),
            "location": str(row.get(_COL["location"], "")),
            "budget": _safe_float(row.get(_COL["budget"], 0)),
            "spent": _safe_float(row.get(_COL["spent"], 0)),
            "status": str(row.get(_COL["status"], "OnTrack")),
            "progress": _safe_float(row.get(_COL["progress"], 0)),
            "phase": str(row.get(_COL["phase"], "Foundation")),
            "labourCount": int(_safe_float(row.get(_COL["labour"], 0))),
            "startDate": str(row.get(_COL["start"], "")),
        })

    return {
        "total_projects": int(len(df)),
        "total_budget": round(float(df[_COL["budget"]].sum()), 2),
        "total_spent": round(float(df[_COL["spent"]].sum()), 2),
        "status_distribution": status_dist,
        "location_stats": location_stats,
        "monthly_trend": _generate_monthly_trend(df),
        "top_projects": top_projects,
        "avg_progress": avg_progress,
        "on_track_count": status_dist["OnTrack"],
        "delayed_count": status_dist["Delayed"],
        "projects": projects_list,
    }


@router.get("/project/{project_id}")
async def get_project_stats(project_id: str) -> dict[str, Any]:
    """
    Detailed analytics for a single project identified by *project_id*.
    Includes budget utilisation, burn rate, days remaining, risk flag.
    """
    try:
        df = _get_df()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    id_col = _COL["id"]
    if id_col not in df.columns:
        raise HTTPException(status_code=404, detail=f"Column '{id_col}' not found in data")

    mask = df[id_col].astype(str).str.strip().str.upper() == project_id.strip().upper()
    subset = df[mask]

    if subset.empty:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    row = subset.iloc[0]

    budget = _safe_float(row.get(_COL["budget"], 0))
    spent = _safe_float(row.get(_COL["spent"], 0))
    progress = _safe_float(row.get(_COL["progress"], 0))
    labour = _safe_float(row.get(_COL["labour"], 0))
    cement = _safe_float(row.get(_COL["cement"], 0))
    material = _safe_float(row.get(_COL["material"], 0))

    budget_remaining = budget - spent
    budget_utilisation_pct = round((spent / budget * 100) if budget > 0 else 0.0, 2)

    # Days remaining
    days_remaining: int | None = None
    try:
        end_dt = datetime.strptime(str(row.get(_COL["end"], "")), "%Y-%m-%d")
        days_remaining = (end_dt - datetime.utcnow()).days
    except (ValueError, TypeError):
        pass

    # Simple burn rate: spent / progress days elapsed
    burn_rate: float | None = None
    try:
        start_dt = datetime.strptime(str(row.get(_COL["start"], "")), "%Y-%m-%d")
        elapsed_days = (datetime.utcnow() - start_dt).days or 1
        burn_rate = round(spent / elapsed_days, 4)
    except (ValueError, TypeError):
        pass

    risk_flag = (
        "Over Budget"
        if spent > budget
        else ("Delayed" if str(row.get(_COL["status"], "")) == "Delayed" else "Normal")
    )

    return {
        "project_id": str(row.get(_COL["id"], project_id)),
        "project_name": str(row.get(_COL["name"], "")),
        "location": str(row.get(_COL["location"], "")),
        "status": str(row.get(_COL["status"], "")),
        "phase": str(row.get(_COL["phase"], "")),
        "client_name": str(row.get(_COL["client"], "")),
        "site_engineer": str(row.get(_COL["engineer"], "")),
        "start_date": str(row.get(_COL["start"], "")),
        "end_date": str(row.get(_COL["end"], "")),
        "days_remaining": days_remaining,
        "budget_lac": budget,
        "spent_lac": spent,
        "budget_remaining_lac": round(budget_remaining, 2),
        "budget_utilisation_pct": budget_utilisation_pct,
        "progress_percent": progress,
        "labour_count": int(labour),
        "cement_used_tons": cement,
        "material_used_tons": material,
        "burn_rate_lac_per_day": burn_rate,
        "risk_flag": risk_flag,
    }


@router.get("/forecast")
async def get_budget_forecast(session_id: str | None = None) -> dict[str, Any]:
    """
    Linear-regression budget forecast for the next 3 months.
    Loads from the pre-trained forecast pkl file if available, otherwise trains on the fly.
    """
    import pickle
    from config import settings
    
    model_path = os.path.join(os.path.dirname(settings.DATA_PATH), "models", "budget_forecast.pkl")
    
    try:
        df = _get_df(session_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    historical = None
    model = None
    
    if not session_id and os.path.exists(model_path):
        try:
            with open(model_path, "rb") as f:
                saved_data = pickle.load(f)
                model = saved_data.get("model")
                historical = saved_data.get("historical_trend")
                logger.info("Loaded pre-trained budget forecast model from pkl.")
        except Exception as e:
            logger.warning("Failed to load pickled budget forecast model: %s", e)
            
    if historical is None or model is None:
        historical = _generate_monthly_trend(df, months=12)
        if len(historical) < 3:
            raise HTTPException(status_code=422, detail="Not enough data for forecast")
        X = np.array(range(len(historical))).reshape(-1, 1)
        y = np.array([h["spent"] for h in historical])
        from sklearn.linear_model import LinearRegression
        model = LinearRegression()
        model.fit(X, y)

    # Residuals for confidence interval (±1 std dev of residuals)
    X = np.array(range(len(historical))).reshape(-1, 1)
    y = np.array([h["spent"] for h in historical])
    residuals = y - model.predict(X)
    std_resid = float(np.std(residuals))

    # Forecast next 3 months
    last_month_dt = datetime.strptime(historical[-1]["month"], "%b %Y")
    forecast_entries: list[dict] = []
    for i in range(1, 4):
        idx = len(historical) + i - 1
        future_dt = last_month_dt + timedelta(days=30 * i)
        label = future_dt.strftime("%b %Y")
        predicted = float(model.predict(np.array([[idx]]))[0])
        lower = max(0.0, round(predicted - std_resid, 2))
        upper = round(predicted + std_resid, 2)
        forecast_entries.append(
            {
                "month": label,
                "predicted_spent": round(predicted, 2),
                "lower": lower,
                "upper": upper,
            }
        )

    return {"historical": historical, "forecast": forecast_entries}


@router.get("/delay-risk")
async def get_delay_risk_scores(session_id: str | None = None) -> list[dict[str, Any]]:
    """
    ML-powered delay risk scores.
    Loads the RandomForestClassifier and returns the delay risk probability for all active projects.
    """
    import pickle
    from config import settings
    
    model_path = os.path.join(os.path.dirname(settings.DATA_PATH), "models", "delay_risk_model.pkl")
    
    try:
        df = _get_df(session_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
        
    if df.empty:
        return []
        
    clf = None
    
    if os.path.exists(model_path):
        try:
            with open(model_path, "rb") as f:
                saved_data = pickle.load(f)
                clf = saved_data.get("model")
                logger.info("Loaded pre-trained delay risk classification model.")
        except Exception as e:
            logger.warning("Failed to load pickled delay risk classifier: %s", e)
            
    if clf is None:
        from sklearn.ensemble import RandomForestClassifier
        try:
            y = (df[_COL["status"]].astype(str).str.lower().str.contains("delay|behind", na=False)).astype(int)
            X_data = pd.DataFrame()
            X_data["budget_lac"] = pd.to_numeric(df[_COL["budget"]], errors="coerce").fillna(0.0)
            X_data["spent_lac"] = pd.to_numeric(df[_COL["spent"]], errors="coerce").fillna(0.0)
            X_data["labourcount"] = pd.to_numeric(df[_COL["labour"]], errors="coerce").fillna(0.0)
            X_data["cementused_tons"] = pd.to_numeric(df[_COL["cement"]], errors="coerce").fillna(0.0)
            X_data["materialused_tons"] = pd.to_numeric(df[_COL["material"]], errors="coerce").fillna(0.0)
            X_data["progresspercent"] = pd.to_numeric(df[_COL["progress"]], errors="coerce").fillna(0.0)
            X_data["spent_ratio"] = (X_data["spent_lac"] / X_data["budget_lac"]).replace([np.inf, -np.inf], 0.0).fillna(0.0)
            
            clf = RandomForestClassifier(n_estimators=50, max_depth=5, random_state=42)
            clf.fit(X_data, y)
            logger.info("Trained fallback delay risk model on the fly.")
        except Exception as err:
            logger.error("Failed to train fallback delay risk model: %s", err)
            raise HTTPException(status_code=500, detail=f"Model execution error: {err}")
            
    # Prepare features for all projects
    X_data = pd.DataFrame()
    X_data["budget_lac"] = pd.to_numeric(df[_COL["budget"]], errors="coerce").fillna(0.0)
    X_data["spent_lac"] = pd.to_numeric(df[_COL["spent"]], errors="coerce").fillna(0.0)
    X_data["labourcount"] = pd.to_numeric(df[_COL["labour"]], errors="coerce").fillna(0.0)
    X_data["cementused_tons"] = pd.to_numeric(df[_COL["cement"]], errors="coerce").fillna(0.0)
    X_data["materialused_tons"] = pd.to_numeric(df[_COL["material"]], errors="coerce").fillna(0.0)
    X_data["progresspercent"] = pd.to_numeric(df[_COL["progress"]], errors="coerce").fillna(0.0)
    X_data["spent_ratio"] = (X_data["spent_lac"] / X_data["budget_lac"]).replace([np.inf, -np.inf], 0.0).fillna(0.0)
    
    probs = clf.predict_proba(X_data)[:, 1]
    
    result = []
    for idx, row in df.iterrows():
        pid = str(row[_COL["id"]])
        name = str(row[_COL["name"]])
        status = str(row[_COL["status"]])
        progress = float(row[_COL["progress"]])
        
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


@router.get("/labour-efficiency")
async def get_labour_efficiency(session_id: str | None = None) -> list[dict[str, Any]]:
    """
    Scatter dataset: labour_count vs progress_percent per project.
    Returns: [{labour_count, progress, project_id, status}]
    """
    try:
        df = _get_df(session_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if df.empty:
        return []

    required = [_COL["labour"], _COL["progress"], _COL["id"], _COL["status"]]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Missing columns in data: {missing}",
        )

    result: list[dict] = []
    for _, row in df.iterrows():
        result.append(
            {
                "project_id": str(row[_COL["id"]]),
                "labour_count": int(_safe_float(row[_COL["labour"]])),
                "progress": round(_safe_float(row[_COL["progress"]]), 2),
                "status": str(row[_COL["status"]]),
            }
        )
    return result


@router.get("/export-csv")
async def export_csv(session_id: str | None = None) -> StreamingResponse:
    """
    Download all project data as a CSV file.
    """
    try:
        df = _get_df(session_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if df.empty:
        raise HTTPException(status_code=404, detail="No data available to export")

    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)

    filename = f"buildflow_projects_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/upload")
async def upload_projects_file(
    file: UploadFile = File(...),
    session_id: str | None = None
) -> dict[str, Any]:
    """
    Upload a custom CSV or Excel file containing construction projects.
    Saves it as projects.csv, reloads DataLoader, and re-triggers RAG index compilation.
    """
    from pathlib import Path
    from config import settings
    
    filename = file.filename or "projects.csv"
    ext = os.path.splitext(filename)[1].lower()
    
    if ext not in [".csv", ".xlsx", ".xls"]:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Please upload a .csv or .xlsx file."
        )
        
    try:
        contents = await file.read()
        
        # Parse into a DataFrame to validate structure
        if ext == ".csv":
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents))
            
        if df.empty:
            raise HTTPException(status_code=400, detail="The uploaded file is empty.")
            
        # Validate that essential columns exist
        required_cols = ["ProjectID", "ProjectName", "Location", "Budget_Lac", "Spent_Lac", "Status", "ProgressPercent"]
        
        # Allow case-insensitive flexible match
        cols_lower = [c.strip().lower() for c in df.columns]
        missing = [c for c in required_cols if c.lower() not in cols_lower]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Uploaded file is missing required columns: {missing}"
            )
            
        # Overwrite projects.csv on disk
        if session_id:
            target_path = Path(f"./data/workspaces/{session_id}/projects.csv")
        else:
            target_path = Path(settings.DATA_PATH)
            
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save as CSV
        df.to_csv(target_path, index=False)
        
        if session_id:
            # Re-trigger RAG ingestion pipeline specifically for this session
            try:
                from rag.ingestion import RAGIngestionPipeline
                from agents.chat_agent import _session_rag_indexes
                pipeline = RAGIngestionPipeline(
                    data_path=str(target_path),
                    api_key=settings.GEMINI_API_KEY,
                )
                pipeline.load_csv()
                pipeline.create_documents()
                index = pipeline.build_simple_index()
                _session_rag_indexes[session_id] = index
                logger.info("Successfully built RAG index for session: %s", session_id)
            except Exception as rag_err:
                logger.warning("RAG index build failed for session %s (non-fatal): %s", session_id, rag_err)
        else:
            # Reload DataLoader (global database reseed)
            if data_loader is not None:
                data_loader.load(force_reseed=True)
                
            # Re-trigger RAG ingestion pipeline (global)
            try:
                from rag.ingestion import RAGIngestionPipeline
                pipeline = RAGIngestionPipeline(
                    data_path=settings.DATA_PATH,
                    api_key=settings.GEMINI_API_KEY,
                )
                pipeline.load_csv()
                pipeline.create_documents()
                index = pipeline.build_simple_index()
                
                from agents.chat_agent import set_rag_index
                set_rag_index(index)
                logger.info("Successfully rebuilt global RAG index with uploaded data.")
            except Exception as rag_err:
                logger.warning("Global RAG index rebuild failed (non-fatal): %s", rag_err)
            
        return {
            "status": "success",
            "message": f"Successfully processed and loaded {len(df)} projects from '{filename}'.",
            "columns": list(df.columns)
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to process file upload")
        raise HTTPException(
            status_code=500,
            detail=f"Error parsing uploaded file: {str(exc)}"
        )
