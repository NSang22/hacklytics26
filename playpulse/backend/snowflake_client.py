"""
Snowflake client — read/write structured playtest data.
STUB: returns mock data. Implement with Snowflake REST API later.
"""

from __future__ import annotations

from typing import Any, Dict, List


async def write_bronze_event(session_id: str, event: Dict[str, Any]) -> None:
    """Write a raw event to the Snowflake bronze_events table.

    Args:
        session_id: The session this event belongs to.
        event: Raw event dict (game_event, presage frame, etc.).
    """
    # TODO: POST to Snowflake REST API /api/v2/statements
    pass


async def write_silver_timeline(session_id: str, fused_rows: List[Dict[str, Any]]) -> None:
    """Write fused (aligned) rows to the silver_timeline table.

    Args:
        session_id: Session identifier.
        fused_rows: Output of ``fusion.fuse_events_and_emotions``.
    """
    # TODO: batch INSERT into silver_timeline
    pass


async def write_gold_segment_scores(
    project_id: str, session_id: str, scores: List[Dict[str, Any]]
) -> None:
    """Write per-segment aggregated scores to the gold table.

    Args:
        project_id: Project this session belongs to.
        session_id: Session identifier.
        scores: List of segment score dicts.
    """
    # TODO: batch INSERT into gold_segment_scores
    pass


async def read_session_events(session_id: str) -> List[Dict[str, Any]]:
    """Read all bronze events for a session.

    Returns:
        List of event dicts (mock for now).
    """
    # TODO: SELECT * FROM bronze_events WHERE session_id = ?
    return []


async def read_silver_timeline(session_id: str) -> List[Dict[str, Any]]:
    """Read fused timeline rows for a session from the silver table.

    Returns:
        List of fused row dicts (mock for now).
    """
    # TODO: SELECT * FROM silver_timeline WHERE session_id = ?
    return []


async def read_gold_scores(project_id: str) -> List[Dict[str, Any]]:
    """Read aggregated segment scores for a project from the gold table.

    Returns:
        List of segment score dicts (mock for now).
    """
    # TODO: SELECT * FROM gold_segment_scores WHERE project_id = ?
    return []
