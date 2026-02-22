"""
Sphinx client — proxy for Sphinx natural-language query engine.

Translates user plain-English questions into structured queries over
the PatchLab data, returning markdown-formatted answers.

STUB — returns canned responses.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

SPHINX_API_KEY = os.getenv("SPHINX_API_KEY", "")
SPHINX_ENDPOINT = os.getenv("SPHINX_ENDPOINT", "")


class SphinxClient:
    """Stub for the Sphinx NL query service."""

    def __init__(self):
        self.api_key = SPHINX_API_KEY
        self.endpoint = SPHINX_ENDPOINT

    async def query(
        self,
        question: str,
        project_id: str,
        session_ids: Optional[List[str]] = None,
    ) -> Dict:
        """Send a natural-language question and get a structured answer.

        Returns:
            {
                "answer": "markdown answer text",
                "sources": [list of session/state references],
                "confidence": 0.0-1.0,
            }
        """
        # STUB — keyword matching for demo
        q = question.lower()

        if "frustrat" in q:
            answer = (
                "**Frustration Analysis**\n\n"
                "The highest frustration was observed during the *puzzle_room* state, "
                "averaging 0.42 across testers. This exceeds the expected baseline "
                "of 0.15 by 2.8x."
            )
        elif "stuck" in q or "death" in q:
            answer = (
                "**Stuck/Death Analysis**\n\n"
                "Players died an average of 3.2 times in the *gauntlet* state. "
                "2 out of 5 testers were stuck for over 30 seconds in *puzzle_room*."
            )
        elif "heart" in q or "hr" in q:
            answer = (
                "**Heart Rate Insights**\n\n"
                "Average HR spiked to 105 BPM during *surprise_event* "
                "(expected: 70-90 BPM). HR variability dropped significantly in "
                "*gauntlet*, indicating sustained stress."
            )
        elif "best" in q or "worst" in q:
            answer = (
                "**Tester Comparison**\n\n"
                "The best playtest health score was 0.87 (Tester A). "
                "The worst was 0.52 (Tester C), primarily due to FAIL verdicts "
                "in *puzzle_room* and *gauntlet*."
            )
        else:
            answer = (
                f"I analysed the data for project `{project_id}`. "
                f"Your question: *\"{question}\"*\n\n"
                "*Detailed Sphinx analysis requires a valid API key.*"
            )

        return {
            "answer": answer,
            "sources": session_ids or [],
            "confidence": 0.75,
        }

    def is_configured(self) -> bool:
        return bool(self.api_key and self.endpoint)
