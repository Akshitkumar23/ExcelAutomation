"""
smart_upload.py - Smart File Upload Router for BuildFlow AI

Handles unstructured / variable-schema CSV and Excel files:
  1. Reads ANY file regardless of column names
  2. Uses Gemini to map unknown columns → standard field names
  3. Auto-generates IDs if no ID column is found
  4. Saves to a session workspace so chat can query it
  5. Rebuilds RAG index for that session

POST /api/smart-upload   → Upload a file, get back session_id + mapping
GET  /api/smart-upload/schema/{session_id} → Get detected schema for a session
"""

from __future__ import annotations

import io
import json
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/smart-upload", tags=["Smart Upload"])

# Store detected schema metadata per session
_session_schemas: dict[str, dict[str, Any]] = {}

# ---------------------------------------------------------------------------
# Standard field names that the system understands
# ---------------------------------------------------------------------------
STANDARD_FIELDS = {
    "project_id": "Unique project identifier (ID, serial number, code)",
    "project_name": "Name or title of the project/task/item",
    "location": "City, site, or address",
    "budget_lac": "Total budget or allocated amount (in Lac or any unit)",
    "spent_lac": "Amount already spent, used, or paid",
    "status": "Current status (e.g. OnTrack, Delayed, Completed, OnHold, Pending)",
    "start_date": "Start date of project or task",
    "end_date": "End date, deadline, or completion date",
    "labour_count": "Number of workers, employees, or labour",
    "cement_used_tons": "Cement or material quantity used",
    "material_used_tons": "Total materials consumed",
    "progress_percent": "Percentage completion or progress",
    "client_name": "Client, customer, or owner name",
    "site_engineer": "Engineer, manager, or responsible person",
    "phase": "Current phase, stage, or category",
}


# ---------------------------------------------------------------------------
# Gemini-powered column mapper
# ---------------------------------------------------------------------------

def _map_columns_with_gemini(columns: list[str], sample_rows: list[dict]) -> dict[str, str]:
    """
    Ask Gemini to map unknown column names to standard field names.
    Returns a dict: { original_col_name -> standard_field_name | "unknown" }
    """
    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(settings.GEMINI_MODEL)

        sample_text = json.dumps(sample_rows[:3], ensure_ascii=False, default=str)
        standard_desc = "\n".join(
            f"  - {k}: {v}" for k, v in STANDARD_FIELDS.items()
        )

        prompt = f"""You are a data schema mapper for a construction project management system.

I have a spreadsheet with these column names:
{columns}

Here are sample rows from the file:
{sample_text}

These are the standard field names I understand:
{standard_desc}

Task: Map each original column name to the most appropriate standard field name.
- If a column clearly matches a standard field, use that standard field name.
- If a column could be an ID (serial number, unique code, row number), map it to "project_id".
- If no good match exists, use "unknown".
- Each standard field can only be assigned ONCE (choose the best match).
- Return ONLY a valid JSON object, no explanation. Format:
{{"original_column_name": "standard_field_name_or_unknown"}}

Important rules:
- "Lagat", "Budget", "Total Cost", "Allocated Amount" → budget_lac
- "Kharcha", "Spent", "Used", "Paid" → spent_lac  
- "Halat", "Status", "Condition", "State" → status
- "Kaam", "Project", "Task", "Work", "Name" → project_name
- "Sr", "Sr No", "S.No", "Row", "No." → project_id (if values look unique)
- "Progress", "% Done", "Completion" → progress_percent
"""
        response = model.generate_content(prompt)
        text = response.text.strip()
        # Extract JSON from response
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            mapping = json.loads(json_match.group())
            return mapping
    except Exception as e:
        logger.warning("Gemini column mapping failed: %s", e)

    # Fallback: simple keyword-based mapping
    return _fallback_column_map(columns)


def _fallback_column_map(columns: list[str]) -> dict[str, str]:
    """Simple keyword-based column mapping when Gemini is unavailable."""
    mapping = {}
    col_lower = {c: c.lower().strip().replace(" ", "_").replace(".", "") for c in columns}

    keyword_map = {
        "project_id":       ["id", "sr", "srno", "sno", "serial", "code", "projectid", "no", "number"],
        "project_name":     ["name", "project", "kaam", "task", "work", "title", "description"],
        "location":         ["location", "city", "site", "place", "address", "area"],
        "budget_lac":       ["budget", "lagat", "total", "allocated", "amount", "cost"],
        "spent_lac":        ["spent", "kharcha", "used", "paid", "actual", "expense"],
        "status":           ["status", "halat", "state", "condition", "stage"],
        "start_date":       ["start", "begin", "from", "startdate"],
        "end_date":         ["end", "deadline", "to", "enddate", "completion"],
        "labour_count":     ["labour", "labor", "worker", "staff", "employee", "count"],
        "progress_percent": ["progress", "percent", "completion", "done", "complete"],
        "client_name":      ["client", "customer", "owner", "party"],
        "site_engineer":    ["engineer", "manager", "incharge", "supervisor"],
        "phase":            ["phase", "stage", "category", "type"],
    }

    used_standards = set()
    for col in columns:
        col_l = col_lower[col]
        matched = None
        for std_field, keywords in keyword_map.items():
            if std_field in used_standards:
                continue
            if any(kw in col_l for kw in keywords):
                matched = std_field
                used_standards.add(std_field)
                break
        mapping[col] = matched if matched else "unknown"

    return mapping


# ---------------------------------------------------------------------------
# Auto-ID generation
# ---------------------------------------------------------------------------

def _ensure_id_column(df: pd.DataFrame, mapping: dict[str, str]) -> tuple[pd.DataFrame, dict[str, str], bool]:
    """
    If no column maps to 'project_id', auto-generate IDs.
    Returns (modified_df, updated_mapping, was_auto_generated)
    """
    has_id = any(v == "project_id" for v in mapping.values())
    if has_id:
        return df, mapping, False

    # Check if there's a column with unique numeric-looking values that could be an ID
    for col in df.columns:
        try:
            unique_vals = df[col].nunique()
            if unique_vals == len(df) and df[col].dtype in [object, str]:
                # Looks like unique identifiers
                mapping[col] = "project_id"
                logger.info("Auto-detected ID column: '%s'", col)
                return df, mapping, False
        except Exception:
            pass

    # No suitable ID column found — auto-generate
    logger.info("No ID column found. Auto-generating IDs.")
    df.insert(0, "auto_id", [f"ROW_{str(i+1).zfill(3)}" for i in range(len(df))])
    mapping["auto_id"] = "project_id"
    return df, mapping, True


# ---------------------------------------------------------------------------
# DataFrame normalizer
# ---------------------------------------------------------------------------

def _normalize_dataframe(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    """
    Rename columns to standard names based on mapping.
    Unknown columns are kept as-is (they'll still be searchable via RAG).
    """
    rename_map = {}
    for orig_col, std_col in mapping.items():
        if std_col != "unknown" and orig_col in df.columns:
            rename_map[orig_col] = std_col

    df_normalized = df.rename(columns=rename_map)

    # Ensure project_id column exists (should always be true after _ensure_id_column)
    if "project_id" not in df_normalized.columns:
        df_normalized.insert(0, "project_id", [f"ROW_{str(i+1).zfill(3)}" for i in range(len(df_normalized))])

    # Clean up numeric columns
    for num_col in ["budget_lac", "spent_lac", "progress_percent", "labour_count",
                    "cement_used_tons", "material_used_tons"]:
        if num_col in df_normalized.columns:
            df_normalized[num_col] = pd.to_numeric(
                df_normalized[num_col].astype(str).str.replace(r"[^\d.]", "", regex=True),
                errors="coerce"
            ).fillna(0.0)

    return df_normalized


# ---------------------------------------------------------------------------
# Session workspace helper
# ---------------------------------------------------------------------------

def _save_to_session(df: pd.DataFrame, session_id: str) -> Path:
    """Save normalized DataFrame to session workspace CSV."""
    session_dir = Path(f"./data/workspaces/{session_id}")
    session_dir.mkdir(parents=True, exist_ok=True)
    csv_path = session_dir / "projects.csv"
    df.to_csv(csv_path, index=False)
    logger.info("Saved %d rows to session workspace: %s", len(df), csv_path)
    return csv_path


def _rebuild_rag_for_session(csv_path: Path, session_id: str) -> int:
    """Rebuild the RAG index for a session and cache it."""
    from rag.ingestion import RAGIngestionPipeline
    from agents.chat_agent import _session_rag_indexes

    pipeline = RAGIngestionPipeline(
        data_path=str(csv_path),
        api_key=settings.GEMINI_API_KEY,
    )
    pipeline.load_csv()
    pipeline.create_documents()
    index = pipeline.build_simple_index()
    _session_rag_indexes[session_id] = index
    logger.info("RAG index rebuilt for session %s: %d entries", session_id, len(index))
    return len(index)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("")
async def smart_upload_file(
    file: UploadFile = File(...),
    session_id: str = Form(default=""),
):
    """
    Upload any CSV or Excel file (regardless of column structure).
    
    The endpoint will:
    1. Auto-detect file format
    2. Map columns to standard field names using Gemini AI
    3. Generate IDs if none exist
    4. Save to a session workspace
    5. Return session_id to use in subsequent chat requests
    """
    # Validate file type
    filename = file.filename or ""
    ext = Path(filename).suffix.lower()
    if ext not in (".csv", ".xlsx", ".xls"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Only .csv, .xlsx, .xls are supported."
        )

    # Read file content
    content = await file.read()

    # Parse file
    try:
        if ext == ".csv":
            # Try multiple encodings
            for encoding in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
                try:
                    df_raw = pd.read_csv(io.BytesIO(content), encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError("Could not decode CSV file with any supported encoding.")
        else:
            df_raw = pd.read_excel(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to read file: {str(e)}")

    # Basic validation
    if df_raw.empty:
        raise HTTPException(status_code=422, detail="The uploaded file is empty.")

    if len(df_raw.columns) < 2:
        raise HTTPException(status_code=422, detail="File must have at least 2 columns.")

    # Clean column names
    df_raw.columns = [str(c).strip() for c in df_raw.columns]
    original_columns = list(df_raw.columns)

    # Drop fully empty rows/columns
    df_raw = df_raw.dropna(how="all").dropna(axis=1, how="all")
    df_raw = df_raw.reset_index(drop=True)

    # Sample rows for Gemini analysis (max 5)
    sample_rows = df_raw.head(5).fillna("").to_dict(orient="records")

    # Map columns using Gemini
    logger.info("Mapping columns for file '%s': %s", filename, original_columns)
    column_mapping = _map_columns_with_gemini(original_columns, sample_rows)

    # Ensure ID column
    df_raw, column_mapping, auto_id_generated = _ensure_id_column(df_raw, column_mapping)

    # Normalize DataFrame
    df_normalized = _normalize_dataframe(df_raw.copy(), column_mapping)

    # Create or reuse session
    if not session_id:
        session_id = str(uuid.uuid4())

    # Save to session workspace
    csv_path = _save_to_session(df_normalized, session_id)

    # Rebuild RAG index
    try:
        rag_entries = _rebuild_rag_for_session(csv_path, session_id)
    except Exception as e:
        logger.warning("RAG rebuild failed (non-fatal): %s", e)
        rag_entries = 0

    # Store schema metadata
    unmapped_cols = [
        orig for orig, std in column_mapping.items() if std == "unknown"
    ]
    mapped_cols = {
        orig: std for orig, std in column_mapping.items() if std != "unknown"
    }

    _session_schemas[session_id] = {
        "session_id": session_id,
        "filename": filename,
        "original_columns": original_columns,
        "column_mapping": column_mapping,
        "mapped_columns": mapped_cols,
        "unmapped_columns": unmapped_cols,
        "auto_id_generated": auto_id_generated,
        "row_count": len(df_normalized),
        "rag_entries": rag_entries,
    }

    # Build user-friendly mapping summary
    mapping_summary = []
    for orig, std in column_mapping.items():
        if orig == "auto_id":
            mapping_summary.append({
                "original": "⚡ Auto-Generated",
                "mapped_to": "project_id",
                "note": "No ID column found, auto-generated ROW_001, ROW_002..."
            })
        elif std != "unknown":
            mapping_summary.append({
                "original": orig,
                "mapped_to": std,
                "note": ""
            })
        else:
            mapping_summary.append({
                "original": orig,
                "mapped_to": "⚠️ Not recognized",
                "note": "Still searchable via AI chat"
            })

    return JSONResponse({
        "status": "success",
        "session_id": session_id,
        "filename": filename,
        "row_count": len(df_normalized),
        "column_count": len(original_columns),
        "rag_entries": rag_entries,
        "auto_id_generated": auto_id_generated,
        "auto_id_message": (
            "⚠️ File mein koi ID column nahi mila. Auto-generated IDs (ROW_001, ROW_002...) assign kar diye gaye hain."
            if auto_id_generated else ""
        ),
        "mapping_summary": mapping_summary,
        "unmapped_columns": unmapped_cols,
        "preview": df_normalized.head(3).fillna("").to_dict(orient="records"),
        "message": (
            f"✅ File '{filename}' successfully uploaded! "
            f"{len(df_normalized)} rows ingested. "
            f"Ab is session mein chat karke apni file ke baare mein pooch sakte hain."
        )
    })


@router.get("/schema/{session_id}")
async def get_session_schema(session_id: str):
    """Get the detected schema and column mapping for an uploaded session."""
    if session_id not in _session_schemas:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return _session_schemas[session_id]


@router.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """Clear a session's data and RAG index."""
    from agents.chat_agent import _session_rag_indexes

    session_dir = Path(f"./data/workspaces/{session_id}")
    if session_dir.exists():
        import shutil
        shutil.rmtree(session_dir)

    _session_rag_indexes.pop(session_id, None)
    _session_schemas.pop(session_id, None)

    return {"status": "cleared", "session_id": session_id}
