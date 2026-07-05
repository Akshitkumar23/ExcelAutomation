import os
import sys
import pytest
from pathlib import Path

# Ensure backend root is in search path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

import database
# Override DB path for testing environment
database.DB_PATH = backend_path / "data" / "test_buildflow.db"

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    # Force recreate test database
    database.init_db(force_recreate=True)
    
    # Initialize and pre-load database from data_loader
    from data_loader import data_loader
    data_loader.load()
    
    yield
    
    # Cleanup test database file after session finishes
    if database.DB_PATH.exists():
        try:
            database.DB_PATH.unlink()
        except OSError:
            pass
