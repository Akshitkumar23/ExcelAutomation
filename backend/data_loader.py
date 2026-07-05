from __future__ import annotations

import logging
import io
from pathlib import Path
from typing import Any

import pandas as pd

from config import settings
from database import init_db, save_projects_dataframe_db, update_project_db

logger = logging.getLogger(__name__)

RAW_PROJECTS_CSV = """ProjectID,ProjectName,Location,Budget_Lac,Spent_Lac,Status,StartDate,EndDate,LabourCount,CementUsed_tons,MaterialUsed_tons,ProgressPercent,ClientName,SiteEngineer,Phase
P1000,Green Valley Residency,Noida,320,280,OnTrack,2024-01-10,2025-06-30,55,410,650,75,ABC Corp,Rajesh Kumar,Structure
P1001,Metro Heights Tower,Gurgaon,480,500,Delayed,2023-08-15,2025-03-31,70,490,780,82,Metro Infrastructure,Suresh Sharma,Finishing
P1002,Sunrise Villa Complex,Faridabad,150,150,Completed,2023-03-01,2024-09-15,30,200,350,100,Raj Constructions,Amit Singh,Completed
P1003,Urban Nest Apartments,Delhi,250,190,OnTrack,2024-05-20,2025-12-31,45,320,510,68,City Developers,Priya Mehta,Structure
P1004,Royal Gardens Phase-2,Greater Noida,410,90,OnHold,2024-09-01,2026-06-30,12,110,180,20,National Housing,Vikas Gupta,Foundation
P1005,Tech Park Commercial,Noida,500,460,OnTrack,2023-11-01,2025-08-31,75,480,790,88,ABC Corp,Deepak Verma,Finishing
P1006,Heritage Homes Society,Lucknow,180,175,Completed,2023-02-14,2024-07-31,35,230,380,100,Green Build,Sandeep Yadav,Completed
P1007,Silver Arch Towers,Gurgaon,440,350,OnTrack,2024-02-01,2026-01-31,65,420,700,72,XYZ Builders,Ritu Sharma,Structure
P1008,City Square Mall,Delhi,490,520,Delayed,2023-07-01,2025-05-31,80,500,800,91,Metro Infrastructure,Anil Pandey,Finishing
P1009,Greenfield Enclave,Agra,120,60,OnTrack,2024-06-01,2025-11-30,20,140,240,45,Raj Constructions,Kavita Joshi,Foundation
P1010,Skyline Business Park,Noida,380,310,OnTrack,2024-03-15,2025-10-31,60,390,640,78,Urban Projects,Mohit Agarwal,Structure
P1011,Lotus Petal Villas,Faridabad,200,200,Completed,2023-01-10,2024-05-31,40,260,420,100,City Developers, नेहा गुप्ता,Completed
P1012,Dream Residency Block-A,Greater Noida,290,130,Delayed,2024-04-01,2025-09-30,38,280,460,42,National Housing,Sanjay Tiwari,Structure
P1013,Pride Boulevard,Gurgaon,350,50,OnHold,2025-01-01,2026-09-30,8,60,100,10,XYZ Builders,Arjun Malhotra,Foundation
P1014,Raj Tower Commercial,Kanpur,160,155,Completed,2023-05-20,2024-10-15,28,190,320,100,Raj Constructions,Pooja Saxena,Completed
P1015,Imperial Gardens,Delhi,430,380,OnTrack,2024-01-25,2025-11-30,68,440,720,84,ABC Corp,Vivek Chauhan,Finishing
P1016,Shanti Nagar Housing,Lucknow,110,80,OnTrack,2024-07-01,2025-08-31,18,120,210,65,Green Build,Sunil Dixit,Structure
P1017,Annapurna Enclave,Agra,95,95,Completed,2023-06-01,2024-03-31,14,80,150,100,Urban Projects,Geeta Mishra,Completed
P1018,Grand Horizon Towers,Noida,470,400,OnTrack,2024-02-10,2026-03-31,72,460,760,77,Metro Infrastructure,Rahul Srivastava,Structure
P1019,Emerald City Residency,Gurgaon,340,100,OnHold,2024-10-01,2026-08-31,15,130,220,28,City Developers,Manish Kapoor,Foundation
P1020,Pearl Valley Condos,Faridabad,220,200,Delayed,2023-12-01,2025-04-30,42,280,460,87,National Housing,Anjali Rao,Finishing
P1021,Sunshine Colony Phase-1,Greater Noida,185,140,OnTrack,2024-04-15,2025-07-31,32,200,340,73,Raj Constructions,Pankaj Jain,Structure
P1022,Windsor Eco Park,Delhi,395,350,OnTrack,2023-10-01,2025-06-30,62,400,660,85,ABC Corp,Shilpa Nair,Finishing
P1023,Fortune Towers Block-B,Kanpur,140,30,OnHold,2025-02-01,2026-05-31,10,70,130,18,XYZ Builders,Rohit Bajpai,Foundation
P1024,Saffron Heights,Lucknow,260,230,OnTrack,2024-03-01,2025-09-30,48,340,560,82,Green Build,Tanya Singh,Structure
P1025,Coral Springs Villas,Agra,130,125,Completed,2023-04-10,2024-08-31,22,160,280,100,Urban Projects,Dinesh Awasthi,Completed
P1026,Nova Commercial Hub,Noida,420,380,OnTrack,2024-01-05,2025-12-31,66,430,710,83,Metro Infrastructure,Kiran Verma,Finishing
P1027,Elysian Residences,Gurgaon,310,270,Delayed,2023-09-15,2025-02-28,50,360,590,86,City Developers,Neeraj Sharma,Finishing
P1028,Blue Lagoon Apartments,Faridabad,175,80,OnTrack,2024-05-01,2025-10-31,28,190,330,50,National Housing,Smita Kulkarni,Structure
P1029,Orchid Valley Society,Greater Noida,240,220,Delayed,2023-11-20,2025-03-31,44,300,490,90,ABC Corp,Ajay Pandey,Finishing
P1030,Capital View Towers,Delhi,500,460,OnTrack,2024-02-20,2026-02-28,78,490,800,85,Metro Infrastructure,Harish Chandra,Structure
P1031,Mahaveer Gardens,Kanpur,100,95,Completed,2023-07-01,2024-04-30,16,100,190,100,Raj Constructions,Vandana Shukla,Completed
P1032,Harmony Park Villas,Lucknow,195,90,OnTrack,2024-06-10,2025-11-30,30,220,370,55,Green Build,Suresh Dwivedi,Structure
P1033,Daffodil Enclave,Agra,85,40,OnHold,2024-11-01,2026-01-31,10,55,105,40,Urban Projects,Meena Pathak,Foundation
P1034,Prestige Square,Noida,460,420,OnTrack,2024-01-15,2025-11-30,74,470,770,88,XYZ Builders,Lalit Bhatia,Finishing
P1035,Golf Greens Residency,Gurgaon,390,350,OnTrack,2024-03-10,2026-04-30,62,400,660,82,ABC Corp,Preethi Nair,Structure
P1036,Crystal Palace Condos,Faridabad,165,155,Completed,2023-02-01,2024-06-30,26,210,350,100,City Developers,Rajiv Tandon,Completed
P1037,Vishal Nagar Society,Greater Noida,275,200,OnTrack,2024-04-20,2025-10-31,46,330,540,70,National Housing,Anita Bhatt,Structure
P1038,Pioneer Business Centre,Delhi,440,130,Delayed,2024-07-01,2026-01-31,22,160,280,28,Metro Infrastructure,Sudhir Agarwal,Foundation
P1039,Lakeview Retreat,Kanpur,135,70,OnTrack,2024-05-15,2025-09-30,20,150,260,52,Raj Constructions,Monika Soni,Structure
P1040,Marigold Township,Lucknow,310,280,OnTrack,2024-01-20,2025-08-31,54,380,620,85,Green Build,Prakash Mishra,Finishing
P1041,Amber Heights Block-C,Agra,115,100,Delayed,2023-10-10,2025-01-31,18,130,230,85,Urban Projects,Seema Tripathi,Finishing
P1042,Sterling Residency,Noida,355,310,OnTrack,2024-02-25,2025-12-31,58,370,610,80,XYZ Builders,Vipin Srivastava,Structure
P1043,Diamond City Phase-3,Gurgaon,480,50,OnHold,2025-03-01,2027-02-28,8,65,120,10,ABC Corp,Kavya Menon,Foundation
P1044,Jasmine Gardens,Faridabad,155,75,OnTrack,2024-06-01,2025-11-30,24,170,300,50,City Developers,Dhruv Khanna,Structure
P1045,Panorama Towers,Greater Noida,430,390,Delayed,2023-08-01,2025-02-28,68,440,720,89,National Housing,Rashmi Gupta,Finishing
P1046,Ashoka Enclave,Delhi,285,255,OnTrack,2024-03-05,2025-10-31,50,340,560,85,Metro Infrastructure,Gaurav Joshi,Structure
P1047,Tranquil Villas,Kanpur,90,85,Completed,2023-08-15,2024-05-31,14,90,165,100,Raj Constructions,Asha Tiwari,Completed
P1048,Springdale Residency,Lucknow,210,100,OnTrack,2024-07-10,2026-01-31,32,240,400,45,Green Build,Rakesh Dubey,Structure
P1049,Celeste Commercial Hub,Agra,370,330,OnTrack,2024-02-15,2025-12-31,60,390,640,84,Urban Projects,Nandini Pal,Finishing
"""


class DataLoader:
    """
    CSV-backed DataLoader acting as a direct bridge to projects.csv.
    Enables true Excel automation by reading and writing files dynamically.
    """

    _instance: "DataLoader | None" = None
    _loaded: bool = False

    def __new__(cls) -> "DataLoader":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load(self, path: str | None = None, force_reseed: bool = False) -> None:
        """Ensure projects.csv exists. If not, recreate it from embedded RAW_PROJECTS_CSV."""
        csv_path = Path(path or settings.DATA_PATH)
        
        if not csv_path.exists() or force_reseed:
            logger.info("Initializing projects.csv on disk.")
            try:
                csv_path.parent.mkdir(parents=True, exist_ok=True)
                csv_path.write_text(RAW_PROJECTS_CSV.strip(), encoding="utf-8")
                logger.info("Successfully wrote projects.csv to disk.")
            except Exception as e:
                logger.error("Could not write projects.csv to disk: %s", e)
                
        # Also initialize SQLite DB tables for generated_documents and orchestration_runs
        try:
            init_db()
            # SYNC: Read from CSV and overwrite projects table in database
            df = self._read_csv()
            save_projects_dataframe_db(df)
            logger.info("Synchronized projects from CSV to SQLite database.")
        except Exception as e:
            logger.warning("Could not initialize SQLite DB or sync projects: %s", e)

        self._loaded = True
        logger.info("DataLoader initialized. Source: projects.csv")

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            raise RuntimeError(
                "DataLoader has not been initialised. Call load() first."
            )

    def _read_csv(self, session_id: str | None = None) -> pd.DataFrame:
        """Helper to read the live CSV file (or session-specific CSV)."""
        csv_path = Path(settings.DATA_PATH)
        if session_id:
            session_path = Path(f"./data/workspaces/{session_id}/projects.csv")
            if session_path.exists():
                csv_path = session_path

        try:
            df = pd.read_csv(csv_path)
            # Ensure column names are stripped of whitespace and lowercase
            df.columns = [c.strip().lower() for c in df.columns]
            return df
        except Exception as e:
            logger.error("Failed to read projects.csv: %s", e)
            # Fallback to parsing RAW_PROJECTS_CSV
            df = pd.read_csv(io.StringIO(RAW_PROJECTS_CSV.strip()))
            df.columns = [c.strip().lower() for c in df.columns]
            return df

    def get_all_projects(self, session_id: str | None = None) -> list[dict[str, Any]]:
        """Return all projects as a list of dicts with empty string fallbacks."""
        self._ensure_loaded()
        df = self._read_csv(session_id)
        records = df.to_dict(orient="records")
        # Standardize keys to lowercase for compatibility with code expecting lowercase SQL column keys
        standardized_records = []
        for r in records:
            clean_r = {k.strip().lower(): v for k, v in r.items()}
            standardized_records.append(self._clean_record(clean_r))
        return standardized_records

    def get_dataframe(self, session_id: str | None = None) -> pd.DataFrame:
        """Return a live pandas DataFrame from the CSV file."""
        self._ensure_loaded()
        return self._read_csv(session_id)

    def get_project_by_id(self, project_id: str, session_id: str | None = None) -> dict[str, Any] | None:
        """Return a single project dict matching *project_id*."""
        self._ensure_loaded()
        df = self._read_csv(session_id)
        id_col = next((c for c in df.columns if c.lower() == "projectid"), None)
        if not id_col:
            return None
        match = df[df[id_col].astype(str).str.strip().str.upper() == project_id.strip().upper()]
        if match.empty:
            return None
        r = match.iloc[0].to_dict()
        clean_r = {k.strip().lower(): v for k, v in r.items()}
        return self._clean_record(clean_r)

    def get_projects_by_status(self, status: str, session_id: str | None = None) -> list[dict[str, Any]]:
        """Return all projects whose 'status' column matches *status*."""
        self._ensure_loaded()
        df = self._read_csv(session_id)
        status_col = next((c for c in df.columns if c.lower() == "status"), None)
        if not status_col:
            return []
        match = df[df[status_col].astype(str).str.strip().str.lower() == status.strip().lower()]
        records = match.to_dict(orient="records")
        return [self._clean_record({k.strip().lower(): v for k, v in r.items()}) for r in records]

    def get_projects_by_location(self, location: str, session_id: str | None = None) -> list[dict[str, Any]]:
        """Return all projects whose location matches search text."""
        self._ensure_loaded()
        df = self._read_csv(session_id)
        loc_col = next((c for c in df.columns if c.lower() == "location"), None)
        if not loc_col:
            return []
        match = df[df[loc_col].astype(str).str.strip().str.lower().str.contains(location.strip().lower(), na=False)]
        records = match.to_dict(orient="records")
        return [self._clean_record({k.strip().lower(): v for k, v in r.items()}) for r in records]

    def get_delayed_projects(self, session_id: str | None = None) -> list[dict[str, Any]]:
        """Return projects marked as delayed/behind schedule."""
        self._ensure_loaded()
        df = self._read_csv(session_id)
        status_col = next((c for c in df.columns if c.lower() == "status"), None)
        if not status_col:
            return []
        match = df[df[status_col].astype(str).str.strip().str.lower().str.contains("delay|behind", na=False)]
        records = match.to_dict(orient="records")
        return [self._clean_record({k.strip().lower(): v for k, v in r.items()}) for r in records]

    def get_summary_stats(self, session_id: str | None = None) -> dict[str, Any]:
        """Return aggregate statistics about all projects."""
        self._ensure_loaded()
        df = self._read_csv(session_id)
        normalized_cols = {c.lower(): c for c in df.columns}

        stats: dict[str, Any] = {"total_projects": len(df)}

        # Status counts
        status_c = normalized_cols.get("status")
        if status_c:
            stats["status_counts"] = (
                df[status_c].astype(str).str.strip().value_counts().to_dict()
            )
            delayed_mask = df[status_c].astype(str).str.lower().str.contains(
                "delay|behind", na=False, regex=True
            )
            stats["delayed_count"] = int(delayed_mask.sum())
        else:
            stats["status_counts"] = {}
            stats["delayed_count"] = 0

        # Budget / spend
        budget_c = normalized_cols.get("budget_lac")
        spent_c = normalized_cols.get("spent_lac")
        
        if budget_c:
            numeric = pd.to_numeric(df[budget_c], errors="coerce").fillna(0.0)
            stats["total_budget"] = float(numeric.sum())
            stats["avg_budget_lac"] = float(numeric.mean())
        else:
            stats["total_budget"] = 0.0
            
        if spent_c:
            numeric = pd.to_numeric(df[spent_c], errors="coerce").fillna(0.0)
            stats["total_spent"] = float(numeric.sum())
            stats["avg_spent_lac"] = float(numeric.mean())
        else:
            stats["total_spent"] = 0.0

        # Progress
        progress_c = normalized_cols.get("progresspercent")
        if progress_c:
            numeric = pd.to_numeric(df[progress_c], errors="coerce").fillna(0.0)
            stats["avg_progress"] = float(numeric.mean())
        else:
            stats["avg_progress"] = 0.0

        return stats

    def update_project(self, project_id: str, updates: dict[str, Any], session_id: str | None = None) -> bool:
        """Update a project's fields in projects.csv and trigger RAG rebuild."""
        self._ensure_loaded()
        csv_path = Path(settings.DATA_PATH)
        if session_id:
            session_path = Path(f"./data/workspaces/{session_id}/projects.csv")
            if session_path.exists():
                csv_path = session_path

        df = self._read_csv(session_id)
        
        id_col = next((c for c in df.columns if c.lower() == "projectid"), None)
        if not id_col:
            logger.error("ProjectID column not found in projects.csv. Cannot update.")
            return False
            
        # Match project row
        mask = df[id_col].astype(str).str.strip().str.upper() == project_id.strip().upper()
        if not mask.any():
            logger.warning("Project '%s' not found in projects.csv. Update failed.", project_id)
            return False
            
        # Standardize updates dict keys to match CSV column case
        column_mapping = {c.lower().strip().replace("_", ""): c for c in df.columns}
        
        for k, v in updates.items():
            clean_k = k.lower().strip().replace("_", "")
            csv_col = column_mapping.get(clean_k)
            if csv_col:
                # Type conversions
                if "percent" in clean_k or "used" in clean_k or "lac" in clean_k:
                    try:
                        v = float(str(v).replace("%", ""))
                    except ValueError:
                        pass
                elif "count" in clean_k or "labour" in clean_k:
                    try:
                        v = int(v)
                    except ValueError:
                        pass
                df.loc[mask, csv_col] = v
                
        try:
            df.to_csv(csv_path, index=False)
            logger.info("Successfully updated project %s in projects.csv", project_id)
            
            if not session_id:
                # SYNC: Also update SQLite database projects table for global data
                try:
                    update_project_db(project_id, updates)
                    logger.info("Synchronized project %s update to SQLite database.", project_id)
                except Exception as dberr:
                    logger.warning("Could not sync update to SQLite database: %s", dberr)
            
            # Rebuild RAG index
            try:
                from rag.ingestion import RAGIngestionPipeline
                pipeline = RAGIngestionPipeline(
                    data_path=str(csv_path),
                    api_key=settings.GEMINI_API_KEY,
                )
                pipeline.load_csv()
                pipeline.create_documents()
                index = pipeline.build_simple_index()

                if session_id:
                    from agents.chat_agent import _session_rag_indexes
                    _session_rag_indexes[session_id] = index
                    logger.info("RAG index successfully rebuilt for session: %s", session_id)
                else:
                    from agents.chat_agent import set_rag_index
                    set_rag_index(index)
                    logger.info("Global RAG index successfully rebuilt after CSV update.")
            except Exception as e:
                logger.warning("RAG index rebuild failed after CSV update (non-fatal): %s", e)
            return True
        except Exception as e:
            logger.error("Failed to write updates to projects.csv: %s", e)
            return False

    def _clean_record(self, record: dict[str, Any]) -> dict[str, Any]:
        """Convert None values to empty strings to preserve backward compatibility."""
        return {k: ("" if v is None or pd.isna(v) else v) for k, v in record.items()}

    @property
    def is_loaded(self) -> bool:
        return self._loaded


# Module-level singleton
data_loader = DataLoader()
