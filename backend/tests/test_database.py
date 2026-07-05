# pytest database unit tests
import pytest
from database import (
    get_all_projects_db,
    get_project_by_id_db,
    get_projects_by_status_db,
    get_projects_by_location_db,
    get_delayed_projects_db,
    update_project_db,
    get_chat_history_db,
    add_chat_message_db,
    clear_chat_history_db,
    get_orchestration_run_db,
    save_orchestration_run_db,
    get_all_orchestration_runs_db,
    save_generated_document_db,
    get_recent_generated_documents_db,
)


def test_project_queries():
    """Test standard project query functions."""
    projects = get_all_projects_db()
    assert len(projects) > 0, "No projects returned from seed DB"

    # Test query by ID
    project = get_project_by_id_db("P1000")
    assert project is not None
    assert project["projectname"] == "Green Valley Residency"

    # Test query by status
    completed_projects = get_projects_by_status_db("Completed")
    assert len(completed_projects) > 0
    assert all(p["status"] == "Completed" for p in completed_projects)

    # Test query by location
    noida_projects = get_projects_by_location_db("Noida")
    assert len(noida_projects) > 0
    assert all("noida" in p["location"].lower() for p in noida_projects)


def test_project_update():
    """Test updating a project record."""
    pid = "P1000"
    original = get_project_by_id_db(pid)
    assert original is not None

    new_status = "Delayed"
    success = update_project_db(pid, {"status": new_status, "cementused_tons": 500})
    assert success

    updated = get_project_by_id_db(pid)
    assert updated["status"] == new_status
    assert updated["cementused_tons"] == 500


def test_chat_history_db():
    """Test chat sessions insertion and retrieval."""
    session_id = "test_session_123"
    clear_chat_history_db(session_id)

    history = get_chat_history_db(session_id)
    assert len(history) == 0

    add_chat_message_db(session_id, "user", "Hello agent")
    add_chat_message_db(session_id, "assistant", "Hello human")

    history = get_chat_history_db(session_id)
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["content"] == "Hello human"

    clear_chat_history_db(session_id)
    history = get_chat_history_db(session_id)
    assert len(history) == 0


def test_orchestration_runs_db():
    """Test orchestration runs logging."""
    run_id = "run_test_999"
    agents = [
        {"agent_name": "Planning Agent", "status": "completed", "output": "Done", "timestamp": "now"}
    ]

    save_orchestration_run_db(
        run_id=run_id,
        workflow_type="budget_analysis",
        project_id="P1001",
        status="completed",
        agents=agents,
        started_at="2026-07-01",
        completed_at="2026-07-01",
        summary="Test summary"
    )

    run = get_orchestration_run_db(run_id)
    assert run is not None
    assert run["workflow_type"] == "budget_analysis"
    assert len(run["agents"]) == 1
    assert run["agents"][0]["agent_name"] == "Planning Agent"

    all_runs = get_all_orchestration_runs_db()
    assert len(all_runs) > 0
    assert any(r["run_id"] == run_id for r in all_runs)


def test_generated_documents_db():
    """Test document logs list serialization."""
    doc_id = "doc_test_abc"
    save_generated_document_db(
        doc_id=doc_id,
        doc_type="CONTRACT",
        project_id="P1000",
        project_name="Green Valley Residency",
        generated_at="2026-07-01",
        file_path="mock/path.pdf",
        metadata={"preview_text": "Lorem Ipsum"}
    )

    recent = get_recent_generated_documents_db()
    assert len(recent) > 0
    match = next((d for d in recent if d["doc_id"] == doc_id), None)
    assert match is not None
    assert match["doc_type"] == "CONTRACT"
    assert match["preview_text"] == "Lorem Ipsum"
