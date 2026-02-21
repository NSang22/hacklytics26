"""
Actian VectorAI client — embedding storage and similarity search.
STUB: returns mock data. Implement with VectorAI REST API later.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


async def insert_embedding(
    vector_id: str,
    vector: List[float],
    metadata: Dict[str, Any],
) -> None:
    """Store an embedding vector with metadata.

    Args:
        vector_id: Unique ID (e.g. ``{session_id}_{segment_name}``).
        vector: The embedding (list of floats).
        metadata: Arbitrary metadata dict (project_id, segment, etc.).
    """
    # TODO: POST to VectorAI /insert
    pass


async def search_similar(
    vector: List[float],
    top_k: int = 10,
    filter_metadata: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Find the top-k most similar vectors.

    Args:
        vector: Query embedding.
        top_k: Number of results.
        filter_metadata: Optional metadata filter.

    Returns:
        List of result dicts with ``id``, ``score``, ``metadata``.
    """
    # TODO: POST to VectorAI /search
    return [
        {
            "id": "mock_result_1",
            "score": 0.95,
            "metadata": {"segment_name": "puzzle", "dominant_emotion": "frustration"},
        }
    ]


async def delete_embedding(vector_id: str) -> None:
    """Delete a stored embedding by ID.

    Args:
        vector_id: The ID to delete.
    """
    # TODO: DELETE on VectorAI
    pass
