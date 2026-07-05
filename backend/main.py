"""
main.py - BuildFlow AI Backend Entry Point
FastAPI application with CORS, routers, and startup initialization.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("buildflow")

# ---------------------------------------------------------------------------
# Lifespan: startup & shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: load data + build RAG index. Shutdown: cleanup."""
    logger.info("=== BuildFlow AI Backend Starting ===")

    # 1. Load CSV data
    from data_loader import data_loader as dl
    try:
        dl.load()
        logger.info("DataLoader: loaded %d projects", len(dl.get_all_projects()))
    except Exception as exc:
        logger.error("DataLoader failed: %s", exc)

    # 1.5 Train ML models on startup
    try:
        from train_models import run_training
        train_res = run_training()
        logger.info("ML Models trained on startup: %s", train_res.get("status"))
    except Exception as exc:
        logger.warning("ML Model training failed on startup (non-fatal): %s", exc)

    # 2. Build RAG index and inject into chat agent
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
        logger.info("RAG index built with %d entries", len(index))
    except Exception as exc:
        logger.warning("RAG index build failed (non-fatal): %s", exc)

    # 3. Ensure generated_docs directory exists
    os.makedirs(settings.DOCS_PATH, exist_ok=True)
    logger.info("Generated docs directory: %s", settings.DOCS_PATH)

    logger.info("=== BuildFlow AI Backend Ready on port %d ===", settings.PORT)
    yield
    logger.info("=== BuildFlow AI Backend Shutting Down ===")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="BuildFlow AI API",
    description="AI-powered Construction Operations Platform — backend API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Static files for generated documents
# ---------------------------------------------------------------------------

os.makedirs(settings.DOCS_PATH, exist_ok=True)
app.mount("/docs-files", StaticFiles(directory=settings.DOCS_PATH), name="generated_docs")

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

from agents.chat_agent import router as chat_router
from agents.analytics_agent import router as analytics_router
from agents.docgen_agent import router as docgen_router
from agents.orchestrator import router as orchestrator_router

app.include_router(chat_router)
app.include_router(analytics_router)
app.include_router(docgen_router)
app.include_router(orchestrator_router)

# ---------------------------------------------------------------------------
# Health & root
# ---------------------------------------------------------------------------

@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "BuildFlow AI API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "running",
    }


@app.get("/health", tags=["Health"])
async def health():
    from data_loader import data_loader as dl
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "data_loaded": dl.is_loaded,
        "project_count": len(dl.get_all_projects()) if dl.is_loaded else 0,
        "modules": ["chat", "analytics", "docgen", "orchestrator"],
        "gemini_configured": bool(settings.GEMINI_API_KEY),
    }


# ---------------------------------------------------------------------------
# Run directly
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
