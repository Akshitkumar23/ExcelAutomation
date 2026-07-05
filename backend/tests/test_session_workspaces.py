import pytest
import io
import shutil
from pathlib import Path
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

# Clean up any test workspace files after running tests
@pytest.fixture(autouse=True)
def run_around_tests():
    # Before test runs
    yield
    # After test runs
    test_workspace_dir = Path("./data/workspaces/test_session_123")
    if test_workspace_dir.exists():
        shutil.rmtree(test_workspace_dir)

def test_workspace_lifecycle():
    session_id = "test_session_123"

    # 1. Verify workspace is initially empty
    res = client.get(f"/api/chat/workspace/{session_id}")
    assert res.status_code == 200
    assert res.json()["has_workspace"] is False

    # 2. Upload mock CSV file specifically to this session
    csv_content = (
        "ProjectID,ProjectName,Location,Budget_Lac,Spent_Lac,Status,ProgressPercent\n"
        "P9999,Workspace Mock Project,Noida,150.0,75.0,OnTrack,50.0\n"
    )
    file_payload = {
        "file": ("projects.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")
    }

    res = client.post(f"/api/analytics/upload?session_id={session_id}", files=file_payload)
    assert res.status_code == 200
    assert "success" in res.json()["status"]

    # 3. Check workspace status is now active
    res = client.get(f"/api/chat/workspace/{session_id}")
    assert res.status_code == 200
    status_data = res.json()
    assert status_data["has_workspace"] is True
    assert status_data["project_count"] == 1

    # 4. Check overview with session_id returns only the workspace project
    res = client.get(f"/api/analytics/overview?session_id={session_id}")
    assert res.status_code == 200
    session_overview = res.json()
    assert session_overview["total_projects"] == 1
    assert session_overview["top_projects"][0]["id"] == "P9999"

    # 5. Check overview without session_id returns the permanent projects list (>= 50 projects)
    res = client.get("/api/analytics/overview")
    assert res.status_code == 200
    global_overview = res.json()
    assert global_overview["total_projects"] >= 50

    # 6. Delete the workspace
    res = client.delete(f"/api/chat/workspace/{session_id}")
    assert res.status_code == 200
    assert res.json()["status"] == "success"

    # 7. Verify workspace is empty again
    res = client.get(f"/api/chat/workspace/{session_id}")
    assert res.status_code == 200
    assert res.json()["has_workspace"] is False
