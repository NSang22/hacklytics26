"""
VectorAI client — stores and queries window embeddings via Actian VectorAI.

Uses the REST API for upsert/search/delete operations.
Falls back to in-memory cosine similarity when credentials are missing.
"""

from __future__ import annotations

import logging
import math
import os
from typing import Any, Dict, List, Optional

import httpx

from config import VECTORAI_URL, VECTORAI_API_KEY, VECTORAI_COLLECTION

logger = logging.getLogger(__name__)


class VectorAIClient:
    """Actian VectorAI REST client with in-memory fallback."""

    def __init__(self):
        self._store: List[Dict] = []  # in-memory fallback
        self._http: Optional[httpx.AsyncClient] = None

    def _use_real(self) -> bool:
        return bool(VECTORAI_URL and VECTORAI_API_KEY)

    def _get_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(
                base_url=VECTORAI_URL.rstrip("/"),
                headers={
                    "Authorization": f"Bearer {VECTORAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
        return self._http

    async def _ensure_collection(self):
        """Create the collection if it doesn't exist."""
        client = self._get_http()
        try:
            resp = await client.get(f"/collections/{VECTORAI_COLLECTION}")
            if resp.status_code == 404:
                # Create collection — first embedding will define dimensionality
                await client.post("/collections", json={
                    "name": VECTORAI_COLLECTION,
                    "distance": "cosine",
                })
                logger.info(f"[vectorai] Created collection: {VECTORAI_COLLECTION}")
        except Exception as exc:
            logger.warning(f"[vectorai] ensure_collection check failed: {exc}")

    async def upsert(self, embeddings: List[Dict]) -> int:
        """Store embeddings (id, vector, metadata).

        Each embedding dict must have: { "id": str, "vector": List[float], "metadata": dict }
        """
        if not embeddings:
            return 0

        if not self._use_real():
            for emb in embeddings:
                self._store = [e for e in self._store if e["id"] != emb["id"]]
                self._store.append(emb)
            logger.info(f"[vectorai][mem] upserted {len(embeddings)} embeddings")
            return len(embeddings)

        client = self._get_http()
        await self._ensure_collection()

        # Batch upsert
        points = []
        for emb in embeddings:
            points.append({
                "id": emb["id"],
                "vector": emb["vector"],
                "metadata": emb.get("metadata", {}),
            })

        try:
            resp = await client.post(
                f"/collections/{VECTORAI_COLLECTION}/points",
                json={"points": points},
            )
            resp.raise_for_status()
            logger.info(f"[vectorai] Upserted {len(points)} points to {VECTORAI_COLLECTION}")
            return len(points)
        except httpx.HTTPStatusError as exc:
            logger.error(f"[vectorai] Upsert HTTP error: {exc.response.status_code} {exc.response.text}")
            # Fallback to in-memory
            for emb in embeddings:
                self._store = [e for e in self._store if e["id"] != emb["id"]]
                self._store.append(emb)
            return len(embeddings)
        except Exception as exc:
            logger.error(f"[vectorai] Upsert failed: {exc}")
            for emb in embeddings:
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
        if not self._use_real():
            return self._search_mem(query_vector, top_k, filters)

        client = self._get_http()
        payload: Dict[str, Any] = {
            "vector": query_vector,
            "top_k": top_k,
        }
        if filters:
            payload["filter"] = filters

        try:
            resp = await client.post(
                f"/collections/{VECTORAI_COLLECTION}/search",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", data.get("points", []))
            logger.info(f"[vectorai] Search returned {len(results)} results")
            return results
        except Exception as exc:
            logger.error(f"[vectorai] Search failed, falling back to mem: {exc}")
            return self._search_mem(query_vector, top_k, filters)

    async def delete_session(self, session_id: str) -> int:
        """Delete all embeddings for a session."""
        if not self._use_real():
            before = len(self._store)
            self._store = [
                e for e in self._store
                if e.get("metadata", {}).get("session_id") != session_id
            ]
            return before - len(self._store)

        client = self._get_http()
        try:
            resp = await client.post(
                f"/collections/{VECTORAI_COLLECTION}/points/delete",
                json={"filter": {"session_id": session_id}},
            )
            resp.raise_for_status()
            data = resp.json()
            deleted = data.get("deleted", 0)
            logger.info(f"[vectorai] Deleted {deleted} points for session {session_id}")
            return deleted
        except Exception as exc:
            logger.error(f"[vectorai] Delete failed: {exc}")
            before = len(self._store)
            self._store = [
                e for e in self._store
                if e.get("metadata", {}).get("session_id") != session_id
            ]
            return before - len(self._store)

    def _search_mem(
        self,
        query_vector: List[float],
        top_k: int,
        filters: Optional[Dict[str, Any]],
    ) -> List[Dict]:
        """In-memory cosine similarity search."""
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

    def is_configured(self) -> bool:
        return bool(VECTORAI_URL and VECTORAI_API_KEY)


def _cosine_sim(a: List[float], b: List[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(y * y for y in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)
