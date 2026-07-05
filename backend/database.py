"""
database.py - SQLite database module for BuildFlow AI.
Handles storage of project data, chat history sessions, orchestration runs, and generated documents.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd
from config import settings

logger = logging.getLogger(__name__)

DB_PATH = Path("./data/buildflow.db")


def get_connection() -> sqlite3.Connection:
    """Create a connection to the SQLite database and set the row factory."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(force_recreate: bool = False) -> None:
    """Initialize database tables. Recreates them if force_recreate is True."""
    logger.info("Initializing database at %s", DB_PATH)
    conn = get_connection()
    cursor = conn.cursor()

    if force_recreate:
        cursor.execute("DROP TABLE IF EXISTS projects")
        cursor.execute("DROP TABLE IF EXISTS chat_sessions")
        cursor.execute("DROP TABLE IF EXISTS orchestration_runs")
        cursor.execute("DROP TABLE IF EXISTS generated_documents")

    # 1. Projects Table (matching exact normalized CSV column names for analytics_agent compatibility)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            projectid TEXT PRIMARY KEY,
            projectname TEXT,
            location TEXT,
            budget_lac REAL,
            spent_lac REAL,
            status TEXT,
            startdate TEXT,
            enddate TEXT,
            labourcount INTEGER,
            cementused_tons REAL,
            materialused_tons REAL,
            progresspercent REAL,
            clientname TEXT,
            siteengineer TEXT,
            phase TEXT
        )
    """)

    # 2. Chat Sessions Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            content TEXT,
            timestamp TEXT
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_sessions_session_id ON chat_sessions(session_id)")

    # 3. Multi-Agent Orchestration Runs Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orchestration_runs (
            run_id TEXT PRIMARY KEY,
            workflow_type TEXT,
            project_id TEXT,
            status TEXT,
            agents_json TEXT,  -- JSON list of agent states
            started_at TEXT,
            completed_at TEXT,
            summary TEXT
        )
    """)

    # 4. Generated Documents Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS generated_documents (
            doc_id TEXT PRIMARY KEY,
            doc_type TEXT,
            project_id TEXT,
            project_name TEXT,
            generated_at TEXT,
            file_path TEXT,
            metadata_json TEXT  -- JSON dict of extra params
        )
    """)

    conn.commit()
    conn.close()
    logger.info("Database initialized successfully.")


# =================================================================----------
# Projects DB Helpers
# =================================================================----------

def get_all_projects_db() -> list[dict[str, Any]]:
    """Query and return all projects from the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_project_by_id_db(project_id: str) -> Optional[dict[str, Any]]:
    """Query a project by its projectid (case-insensitive)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM projects WHERE UPPER(TRIM(projectid)) = ?",
        (project_id.strip().upper(),)
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_projects_by_status_db(status: str) -> list[dict[str, Any]]:
    """Query projects by their status (case-insensitive)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM projects WHERE LOWER(TRIM(status)) = ?",
        (status.strip().lower(),)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_projects_by_location_db(location: str) -> list[dict[str, Any]]:
    """Query projects whose location matches search text."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM projects WHERE LOWER(location) LIKE ?",
        (f"%{location.strip().lower()}%",)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_delayed_projects_db() -> list[dict[str, Any]]:
    """Query projects whose status contains delay or behind."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM projects WHERE LOWER(status) LIKE '%delay%' OR LOWER(status) LIKE '%behind%'"
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_project_db(project_id: str, updates: dict[str, Any]) -> bool:
    """Update database record fields dynamically."""
    conn = get_connection()
    cursor = conn.cursor()

    # Get valid database columns
    cursor.execute("PRAGMA table_info(projects)")
    columns = [row[1] for row in cursor.fetchall()]

    valid_updates = {}
    for k, v in updates.items():
        col_name = k.lower().replace(" ", "_")
        if col_name in columns:
            valid_updates[col_name] = v

    if not valid_updates:
        conn.close()
        return False

    set_clause = ", ".join([f"{col} = ?" for col in valid_updates.keys()])
    values = list(valid_updates.values()) + [project_id.strip().upper()]

    cursor.execute(
        f"UPDATE projects SET {set_clause} WHERE UPPER(TRIM(projectid)) = ?",
        values
    )
    rowcount = cursor.rowcount
    conn.commit()
    conn.close()
    return rowcount > 0


def save_projects_dataframe_db(df: pd.DataFrame) -> None:
    """Bulk replace the projects table with a pandas DataFrame."""
    df_copy = df.copy()
    df_copy.columns = [c.strip().lower().replace(" ", "_") for c in df_copy.columns]

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM projects")
    conn.commit()

    df_copy.to_sql("projects", conn, if_exists="append", index=False)
    conn.commit()
    conn.close()
    logger.info("Successfully loaded DataFrame into projects database table.")


# =================================================================----------
# Chat Session History DB Helpers
# =================================================================----------

def get_chat_history_db(session_id: str) -> list[dict[str, str]]:
    """Fetch chat history for a session sorted chronologically."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, content FROM chat_sessions WHERE session_id = ? ORDER BY id ASC",
        (session_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"role": row["role"], "content": row["content"]} for row in rows]


def add_chat_message_db(session_id: str, role: str, content: str) -> None:
    """Add a chat message to history."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chat_sessions (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
        (session_id, role, content, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()


def clear_chat_history_db(session_id: str) -> None:
    """Delete chat history for a session."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chat_sessions WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()


# =================================================================----------
# Multi-Agent Orchestration Runs DB Helpers
# =================================================================----------

def get_orchestration_run_db(run_id: str) -> Optional[dict[str, Any]]:
    """Retrieve an orchestration run detail by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orchestration_runs WHERE run_id = ?", (run_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        run = dict(row)
        run["agents"] = json.loads(run["agents_json"])
        del run["agents_json"]
        return run
    return None


def save_orchestration_run_db(
    run_id: str,
    workflow_type: str,
    project_id: str,
    status: str,
    agents: list[Any],
    started_at: str,
    completed_at: Optional[str] = None,
    summary: str = ""
) -> None:
    """Create or update orchestration run record."""
    conn = get_connection()
    cursor = conn.cursor()
    agents_json = json.dumps(agents)
    cursor.execute(
        """
        INSERT OR REPLACE INTO orchestration_runs (
            run_id, workflow_type, project_id, status, agents_json, started_at, completed_at, summary
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (run_id, workflow_type, project_id, status, agents_json, started_at, completed_at, summary)
    )
    conn.commit()
    conn.close()


def get_all_orchestration_runs_db() -> list[dict[str, Any]]:
    """Get all orchestration runs sorted newest first."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orchestration_runs ORDER BY started_at DESC")
    rows = cursor.fetchall()
    conn.close()
    runs = []
    for row in rows:
        run = dict(row)
        run["agents"] = json.loads(run["agents_json"])
        del run["agents_json"]
        runs.append(run)
    return runs


# =================================================================----------
# Generated Documents DB Helpers
# =================================================================----------

def save_generated_document_db(
    doc_id: str,
    doc_type: str,
    project_id: str,
    project_name: str,
    generated_at: str,
    file_path: str,
    metadata: dict[str, Any]
) -> None:
    """Save document metadata to database."""
    conn = get_connection()
    cursor = conn.cursor()
    metadata_json = json.dumps(metadata)
    cursor.execute(
        """
        INSERT OR REPLACE INTO generated_documents (
            doc_id, doc_type, project_id, project_name, generated_at, file_path, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (doc_id, doc_type, project_id, project_name, generated_at, file_path, metadata_json)
    )
    conn.commit()
    conn.close()


def get_recent_generated_documents_db(limit: int = 10) -> list[dict[str, Any]]:
    """Retrieve metadata of recent generated documents."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM generated_documents ORDER BY generated_at DESC LIMIT ?",
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()
    docs = []
    for row in rows:
        doc = dict(row)
        extra = json.loads(doc["metadata_json"])
        del doc["metadata_json"]
        doc.update(extra)
        docs.append(doc)
    return docs
