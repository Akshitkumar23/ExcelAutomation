"""
config.py - Application configuration for BuildFlow AI backend.
Loads settings from environment variables and .env file.
"""

import os
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()


class Settings:
    """Central configuration class for the BuildFlow AI backend."""

    # --- AI / LLM ---
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    # --- Storage paths ---
    CHROMA_PATH: str = os.getenv("CHROMADB_PATH", "./chroma_db")
    DOCS_PATH: str = os.getenv("GENERATED_DOCS_PATH", "./generated_docs")

    # --- Data ---
    DATA_PATH: str = "./data/projects.csv"

    # --- CORS ---
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")

    # --- Server ---
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # --- Logging ---
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # --- RAG ---
    RAG_CHUNK_SIZE: int = int(os.getenv("RAG_CHUNK_SIZE", "500"))
    RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "5"))

    # --- Gemini model ---
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    # --- Multi-mode Chat Agent ---
    CHAT_MODE: str = os.getenv("CHAT_MODE", "auto")
    OLLAMA_API_BASE: str = os.getenv("OLLAMA_API_BASE", "http://localhost:11434/v1")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")


# Singleton instance used across the application
settings = Settings()
