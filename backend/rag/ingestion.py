"""
rag/ingestion.py - RAG ingestion pipeline for BuildFlow AI.

Uses a simple in-memory keyword index (no ChromaDB dependency) so the
pipeline works out-of-the-box without any external vector store.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


class RAGIngestionPipeline:
    """
    Reads a CSV file of construction projects, converts each row to a
    text document, optionally chunks long texts, and builds a lightweight
    in-memory keyword index.

    Parameters
    ----------
    data_path : str
        Path to the CSV file (e.g. ``"./data/projects.csv"``).
    api_key : str
        Gemini API key (kept for interface compatibility; not used in
        the simple keyword-based flow).
    """

    def __init__(self, data_path: str, api_key: str = "") -> None:
        self.data_path = Path(data_path)
        self.api_key = api_key
        self._df: pd.DataFrame | None = None
        self._documents: list[dict[str, Any]] = []
        self._chunks: list[dict[str, Any]] = []
        # index: { project_id -> {"text": str, "meta": dict} }
        self._index: dict[str, dict[str, Any]] = {}
        logger.info("RAGIngestionPipeline initialised with data_path='%s'", data_path)

    # ------------------------------------------------------------------ #
    # Public pipeline steps                                                #
    # ------------------------------------------------------------------ #

    def load_csv(self) -> pd.DataFrame:
        """
        Load the projects from SQLite database (or fallback to CSV file if SQLite fails).

        Returns
        -------
        pd.DataFrame
        """
        try:
            from database import get_connection
            conn = get_connection()
            # Verify if table exists and has rows
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='projects'")
            table_exists = cursor.fetchone()
            if table_exists:
                self._df = pd.read_sql_query("SELECT * FROM projects", conn)
                logger.info("RAG: Loaded %d projects from SQLite database.", len(self._df))
                conn.close()
                return self._df
            conn.close()
        except Exception as exc:
            logger.warning("RAG SQLite load failed (falling back to CSV): %s", exc)

        # Fallback to original CSV parsing
        if not self.data_path.exists():
            logger.warning("CSV not found at '%s'; using empty DataFrame.", self.data_path)
            self._df = pd.DataFrame()
            return self._df

        logger.info("Loading CSV from '%s' …", self.data_path)
        self._df = pd.read_csv(self.data_path)
        # Normalise column names
        self._df.columns = [
            c.strip().lower().replace(" ", "_") for c in self._df.columns
        ]
        logger.info("Loaded %d rows, columns: %s", len(self._df), list(self._df.columns))
        return self._df

    def create_documents(self) -> list[dict[str, Any]]:
        """
        Convert each DataFrame row into a text document string.

        Returns
        -------
        list[dict]  Each dict has keys ``id``, ``text``, ``meta``.
        """
        if self._df is None:
            self.load_csv()

        if self._df.empty:
            logger.warning("DataFrame is empty; no documents created.")
            self._documents = []
            return self._documents

        logger.info("Creating documents from %d rows …", len(self._df))
        docs: list[dict[str, Any]] = []

        for _, row in self._df.iterrows():
            row_dict = row.fillna("").to_dict()
            project_id = str(row_dict.get("project_id", row_dict.get("id", f"row_{_}")))

            # Build a human-readable text block
            lines: list[str] = [f"Project ID: {project_id}"]
            for key, value in row_dict.items():
                if key in ("project_id", "id"):
                    continue
                label = key.replace("_", " ").title()
                lines.append(f"{label}: {value}")

            text = "\n".join(lines)
            docs.append({"id": project_id, "text": text, "meta": row_dict})

        self._documents = docs
        logger.info("Created %d documents.", len(docs))
        return docs

    def chunk_documents(self, chunk_size: int = 500) -> list[dict[str, Any]]:
        """
        Split documents whose text exceeds *chunk_size* characters into
        smaller chunks that share the same ``id`` (with a ``_chunkN`` suffix).

        Parameters
        ----------
        chunk_size : int
            Maximum character length per chunk.

        Returns
        -------
        list[dict]  Flat list of chunk dicts.
        """
        if not self._documents:
            self.create_documents()

        logger.info(
            "Chunking %d documents with chunk_size=%d …",
            len(self._documents),
            chunk_size,
        )
        chunks: list[dict[str, Any]] = []

        for doc in self._documents:
            text: str = doc["text"]
            if len(text) <= chunk_size:
                chunks.append(doc)
                continue

            # Split into overlapping chunks (50-char overlap)
            overlap = 50
            start = 0
            chunk_idx = 0
            while start < len(text):
                end = start + chunk_size
                chunk_text = text[start:end]
                chunks.append(
                    {
                        "id": f"{doc['id']}_chunk{chunk_idx}",
                        "text": chunk_text,
                        "meta": doc["meta"],
                        "parent_id": doc["id"],
                    }
                )
                start += chunk_size - overlap
                chunk_idx += 1

        self._chunks = chunks
        logger.info("Produced %d chunks.", len(chunks))
        return chunks

    def build_simple_index(self) -> dict[str, dict[str, Any]]:
        """
        Build an in-memory dict index keyed by ``project_id``.

        Structure
        ---------
        {
          "P1000": {"text": "...", "meta": {...}},
          "P1001": {"text": "...", "meta": {...}},
          ...
        }

        Returns
        -------
        dict
        """
        if not self._documents:
            self.create_documents()

        logger.info("Building in-memory keyword index …")
        index: dict[str, dict[str, Any]] = {}

        for doc in self._documents:
            pid = doc["id"]
            if pid in index:
                # Merge chunks with the same parent id
                index[pid]["text"] += "\n" + doc["text"]
            else:
                index[pid] = {"text": doc["text"], "meta": doc.get("meta", {})}

        self._index = index
        logger.info("Index built with %d entries.", len(index))
        return index

    # ------------------------------------------------------------------ #
    # Convenience: run full pipeline                                       #
    # ------------------------------------------------------------------ #

    def run(self, chunk_size: int = 500) -> dict[str, dict[str, Any]]:
        """Run the full ingestion pipeline and return the index."""
        self.load_csv()
        self.create_documents()
        self.chunk_documents(chunk_size=chunk_size)
        return self.build_simple_index()

    # ------------------------------------------------------------------ #
    # Properties                                                           #
    # ------------------------------------------------------------------ #

    @property
    def index(self) -> dict[str, dict[str, Any]]:
        return self._index

    @property
    def document_count(self) -> int:
        return len(self._documents)

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)
