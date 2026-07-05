import os
import pandas as pd
import pytest
from pathlib import Path
from data_loader import data_loader
from database import get_connection

def test_excel_upload_and_reseed():
    """Verify Excel parsing, data load, and SQLite reseed dynamically."""
    # 1. Create mock construction project data
    mock_data = {
        "ProjectID": ["P9990", "P9991"],
        "ProjectName": ["Excel Test Residency", "Excel Height Tower"],
        "Location": ["Mumbai", "Bangalore"],
        "Budget_Lac": [750.0, 920.0],
        "Spent_Lac": [150.0, 480.0],
        "Status": ["OnTrack", "Delayed"],
        "StartDate": ["2025-01-01", "2024-06-15"],
        "EndDate": ["2026-12-31", "2026-03-31"],
        "LabourCount": [120, 180],
        "CementUsed_tons": [800.0, 1100.0],
        "MaterialUsed_tons": [1400.0, 1900.0],
        "ProgressPercent": [20.0, 52.0],
        "ClientName": ["Mumbai Devs", "Bangalore Corp"],
        "SiteEngineer": ["Karan Johar", "Vikram Sen"],
        "Phase": ["Foundation", "Structure"]
    }
    
    df = pd.DataFrame(mock_data)
    
    # 2. Write to Excel file
    backend_path = Path(__file__).parent.parent
    excel_file = backend_path / "data" / "temp_mock_upload.xlsx"
    excel_file.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        df.to_excel(excel_file, index=False)
        
        # 3. Parse mock Excel file using the pandas logic in our upload endpoint
        parsed_df = pd.read_excel(excel_file)
        
        # Overwrite projects.csv on disk (simulating backend file save)
        csv_path = backend_path / "data" / "projects.csv"
        parsed_df.to_csv(csv_path, index=False)
        
        # 4. Trigger database reseed
        data_loader.load(force_reseed=False)
        
        # 5. Verify records exist in SQLite DB
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects WHERE projectid IN ('P9990', 'P9991')")
        rows = cursor.fetchall()
        conn.close()
        
        assert len(rows) == 2, "Failed to load both projects into database"
        assert rows[0]["projectname"] == "Excel Test Residency"
        assert rows[1]["location"] == "Bangalore"
        
    finally:
        # Cleanup temp excel file
        if excel_file.exists():
            excel_file.unlink()
            
        # Restore original database seed
        csv_path = backend_path / "data" / "projects.csv"
        if csv_path.exists():
            csv_path.unlink()
        data_loader.load(force_reseed=True)
