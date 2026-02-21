"""
Google Gemini client — playthrough analysis and insight generation.
STUB: returns mock text. Implement with google-generativeai SDK later.
"""

from __future__ import annotations

from typing import Any, Dict, List


async def analyze_optimal_playthrough(
    video_path: str,
    segments: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Process a developer's optimal playthrough video with Gemini vision.

    Args:
        video_path: Path or URL to the uploaded video.
        segments: Project segment definitions with intended emotions.

    Returns:
        Structured analysis of segment timestamps and key events.
    """
    # TODO: upload video with genai.upload_file, call gemini-2.0-flash
    return {
        "segments": [
            {
                "name": seg.get("name", "unknown"),
                "start_time": i * 30.0,
                "end_time": (i + 1) * 30.0,
                "key_events": ["placeholder_event"],
                "expected_duration_sec": 30,
                "design_cues": ["placeholder_cue"],
            }
            for i, seg in enumerate(segments)
        ]
    }


async def generate_session_insights(
    intent_comparison: List[Dict[str, Any]],
    key_moments: List[Dict[str, Any]],
) -> str:
    """Generate developer-facing natural-language analysis of a single playtest.

    Args:
        intent_comparison: Per-segment intent vs reality results.
        key_moments: High-frustration / confusion / delight moments.

    Returns:
        Markdown-formatted analysis string.
    """
    # TODO: call gemini-2.0-flash with prompt
    return (
        "## Session Insights (mock)\n\n"
        "- **Tutorial**: Worked as intended — player felt calm.\n"
        "- **Puzzle Room**: Slight frustration detected — consider adding a hint.\n"
        "- **Surprise**: Strong surprise reaction — great design!\n"
        "- **Gauntlet**: Frustration spiked on 3rd obstacle — consider reducing difficulty.\n"
        "- **Victory**: Positive relief and satisfaction.\n"
    )


async def generate_aggregate_insights(
    aggregate_scores: List[Dict[str, Any]],
    pain_points: List[Dict[str, Any]],
    num_testers: int,
) -> str:
    """Generate cross-tester pattern analysis.

    Args:
        aggregate_scores: Per-segment scores averaged across all testers.
        pain_points: Recurring pain points with frequency.
        num_testers: Total number of testers analysed.

    Returns:
        Markdown-formatted aggregate analysis string.
    """
    # TODO: call gemini-2.0-flash
    return (
        f"## Aggregate Insights ({num_testers} testers — mock)\n\n"
        "- **Puzzle Room** is the primary pain point.\n"
        "- **Gauntlet** difficulty is well-calibrated for most testers.\n"
        "- Recommendation: add visual hint in puzzle room.\n"
    )
