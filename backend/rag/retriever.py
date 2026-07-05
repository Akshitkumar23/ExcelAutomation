"""
rag/retriever.py - Keyword-based retriever for BuildFlow AI RAG pipeline.

Provides TF-based scoring so the system works without any external
vector-store or embedding model.
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from typing import Any

logger = logging.getLogger(__name__)


class SimpleRetriever:
    """
    Keyword-based retriever that operates over the in-memory index
    produced by :class:`~rag.ingestion.RAGIngestionPipeline`.

    Parameters
    ----------
    index : dict
        Mapping of ``project_id -> {"text": str, "meta": dict}``.
    """

    def __init__(self, index: dict[str, dict[str, Any]]) -> None:
        self.index = index
        logger.info("SimpleRetriever initialised with %d documents.", len(index))

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """
        Search the index for documents relevant to *query*.

        Each document is scored using :meth:`keyword_match_score` and the
        top *top_k* results are returned in descending score order.

        Parameters
        ----------
        query : str
            Natural-language query from the user.
        top_k : int
            Maximum number of results to return.

        Returns
        -------
        list[dict]
            Each result dict has keys ``id``, ``score``, ``text``, ``meta``.
        """
        if not self.index:
            logger.warning("Index is empty; returning no results.")
            return []

        results: list[dict[str, Any]] = []

        for doc_id, doc in self.index.items():
            score = self.keyword_match_score(query, doc["text"])
            if score > 0:
                results.append(
                    {
                        "id": doc_id,
                        "score": score,
                        "text": doc["text"],
                        "meta": doc.get("meta", {}),
                    }
                )

        results.sort(key=lambda x: x["score"], reverse=True)
        top = results[:top_k]

        logger.debug(
            "Query '%s' matched %d docs; returning top %d.", query, len(results), len(top)
        )
        return top

    def format_context(self, results: list[dict[str, Any]]) -> str:
        """
        Format a list of retrieval results into a single context string
        suitable for inclusion in a prompt.

        Parameters
        ----------
        results : list[dict]
            Output from :meth:`search`.

        Returns
        -------
        str
            Formatted context block.
        """
        if not results:
            return "No specific project data found for this query."

        lines: list[str] = [
            "=== Relevant Project Data ===",
            f"(Top {len(results)} match(es) retrieved)\n",
        ]

        for i, res in enumerate(results, start=1):
            lines.append(f"--- Match {i} | ID: {res['id']} | Score: {res['score']:.3f} ---")
            lines.append(res["text"])
            lines.append("")  # blank line between entries

        return "\n".join(lines)

    def keyword_match_score(self, query: str, text: str) -> float:
        """
        Compute a simple TF-based relevance score.

        The score is the sum of ``(term_freq_in_doc * idf_proxy)`` over all
        query tokens.  A basic IDF proxy is used (``1 / sqrt(term_freq + 1)``)
        so common terms score lower than rare, specific ones.

        Parameters
        ----------
        query : str
        text : str

        Returns
        -------
        float
            Non-negative score; 0 means no match.
        """
        query_tokens = self._tokenise(query)
        doc_tokens = self._tokenise(text)

        if not query_tokens or not doc_tokens:
            return 0.0

        doc_freq = Counter(doc_tokens)
        doc_len = len(doc_tokens)

        score = 0.0
        for token in query_tokens:
            tf = doc_freq.get(token, 0)
            if tf == 0:
                continue
            # Normalised TF: occurrences / document length
            tf_norm = tf / doc_len
            # IDF proxy: penalise very frequent terms
            idf = 1.0 / math.sqrt(tf + 1)
            score += tf_norm * idf

        return round(score, 6)

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _tokenise(text: str) -> list[str]:
        """Lower-case, strip punctuation, split on whitespace."""
        text = text.lower()
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        return [t for t in text.split() if len(t) > 1]
