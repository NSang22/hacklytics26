"""
VectorAI client — stores and queries window embeddings via Actian Vector
(or any vector DB).

STUB — keeps vectors in-memory and uses cosine similarity for search.
"""

from __future__ import annotations

import math
import os
from typing import Any, Dict, List, Optional

VECTORAI_ENDPOINT = os.getenv("VECTORAI_ENDPOINT", "")
VECTORAI_API_KEY = os.getenv("VECTORAI_API_KEY", "")


class VectorAIClient:
    """In-memory stub for Actian VectorAI."""

    def __init__(self):
        self._store: List[Dict] = []  # [{id, vector, metadata}]

    async def upsert(self, embeddings: List[Dict]) -> int:
        """Store embeddings (id, vector, metadata)."""
        for emb in embeddings:
            # Remove existing with same id
            self._store = [e for e in self._store if e["id"] != emb["id"]]
            self._store.append(emb)
        return len(embeddings)

    async def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict]:
        """Find top_k most similar embeddings by cosine similarity."""
        results = []
        for entry in self._store:
            if filters:
                meta = entry.get("metadata", {})
                if not all(meta.get(k) == v for k, v in filters.items()):
                    continue
            score = _cosine_sim(query_vector, entry["vector"])
            results.append({**entry, "score": round(score, 6)})

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    async def delete_session(self, session_id: str) -> int:
        before = len(self._store)
        self._store = [
            e for e in self._store
            if e.get("metadata", {}).get("session_id") != session_id
        ]
        return before - len(self._store)

    def is_configured(self) -> bool:
        return bool(VECTORAI_ENDPOINT)


def _cosine_sim(a: List[float], b: List[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(y * y for y in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)
