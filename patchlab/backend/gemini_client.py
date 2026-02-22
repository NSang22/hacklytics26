"""
Gemini client — wraps Google's Gemini API for:

  1. process_chunk()            — analyse a 15-sec gameplay video chunk (gemini-2.0-flash)
  2. analyze_optimal_playthrough() — produce the "intent" reference (gemini-2.5-flash)
  3. generate_session_insights()   — markdown summary of one session (gemini-2.5-flash)
  4. generate_cross_tester_insights() — aggregate comparison (gemini-2.5-flash)

Uses different models per task for cost/quality tradeoff.
STUB — returns plausible mock data so the rest of the pipeline runs
without a real API key. When GEMINI_API_KEY is set, calls the real API.
"""

from __future__ import annotations

import json
import os
import random
from typing import Any, Dict, List, Optional

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# ── Model selection per task ──────────────────────────────────
MODEL_CHUNK_ANALYSIS = "gemini-2.5-flash"       # runs every 10s during gameplay
MODEL_OPTIMAL_ANALYSIS = "gemini-2.5-flash"      # runs once for optimal playthrough
MODEL_INSIGHT_GENERATION = "gemini-2.5-flash"    # post-session insight generation

# ── Video frame sampling ──────────────────────────────────────
CHUNK_FPS = int(os.getenv("CHUNK_FPS", "2"))     # 2 FPS default → 30 frames per 15s chunk


class GeminiClient:
    """Google Gemini multimodal API client.

    Falls back to stub responses when no API key is configured.
    """

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or GEMINI_API_KEY
        self._client = None
        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except ImportError:
                pass

    # ── Chunk analysis (gemini-2.0-flash) ───────────────────
    async def process_chunk(
        self,
        video_bytes: bytes,
        prompt: str,
        session_id: str = "",
    ) -> Dict:
        """Send a 15-sec .webm chunk + prompt to Gemini and return parsed JSON.

        Uses MODEL_CHUNK_ANALYSIS (gemini-2.0-flash) for speed.
        Subsamples video to CHUNK_FPS frames per second.
        Falls back to stub if no API key.
        """
        if self._client and video_bytes:
            try:
                return await self._call_gemini(
                    model=MODEL_CHUNK_ANALYSIS,
                    video_bytes=video_bytes,
                    prompt=prompt,
                    fps=CHUNK_FPS,
                )
            except Exception as e:
                print(f"[gemini] Chunk analysis error: {e}, falling back to stub")

        return self._stub_chunk(prompt)

    # ── Frame-based DFA analysis (gemini-2.5-flash) ─────────
    async def process_frames(
        self,
        frames: List[bytes],
        prompt: str,
        session_id: str = "",
    ) -> Dict:
        """Send extracted JPEG frames as inline images to Gemini for DFA analysis.

        Instead of uploading a video file, sends individual frames as inline
        image parts. This gives Gemini explicit frame-by-frame sequential
        context for detecting state transitions (DFA transition function style).

        Uses MODEL_CHUNK_ANALYSIS (gemini-2.5-flash).
        Falls back to stub if no API key.
        """
        if self._client and frames:
            try:
                return await self._call_gemini_frames(
                    model=MODEL_CHUNK_ANALYSIS,
                    frames=frames,
                    prompt=prompt,
                )
            except Exception as e:
                print(f"[gemini] Frame analysis error: {e}, falling back to stub")

        return self._stub_chunk(prompt)

    async def _call_gemini_frames(
        self, model: str, frames: List[bytes], prompt: str,
    ) -> Dict:
        """Send frames as inline image parts + text prompt to Gemini.

        Each frame is sent as a JPEG image Part, followed by the text prompt.
        Gemini processes the frames in order, enabling DFA-style sequential
        state transition detection.
        """
        from google.genai import types

        print(f"[gemini] Sending {len(frames)} inline frames to {model} for DFA transition analysis...")

        contents = []
        for frame_bytes in frames:
            contents.append(
                types.Part.from_bytes(data=frame_bytes, mime_type="image/jpeg")
            )
        contents.append(prompt)

        response = self._client.models.generate_content(
            model=model,
            contents=contents,
        )

        text = response.text
        # Extract JSON from response
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        return json.loads(text.strip())

    # ── Optimal playthrough analysis (gemini-2.5-flash) ─────
    async def analyze_optimal_playthrough(
        self,
        video_bytes: bytes,
        dfa_config_dict: Dict,
    ) -> Dict:
        """Analyse an optimal/dev playthrough to build reference expectations.

        Uses MODEL_OPTIMAL_ANALYSIS (gemini-2.5-flash) for deeper reasoning.
        """
        if self._client and video_bytes:
            states = dfa_config_dict.get("states", [])
            state_names = [s.get("name", "unknown") for s in states]
            prompt = (
                f"Analyze this optimal gameplay video. The game has these DFA states: {state_names}.\n"
                "For each state, estimate: expected_duration_sec, expected emotion profile "
                "(frustration, confusion, delight, boredom, surprise as 0-1 scores), and expected HR range.\n"
                "Return JSON: {state_name: {expected_duration_sec, expected_emotions: {...}, expected_hr_range: [min, max]}}"
            )
            try:
                return await self._call_gemini(
                    model=MODEL_OPTIMAL_ANALYSIS,
                    video_bytes=video_bytes,
                    prompt=prompt,
                    fps=1,  # Lower FPS for longer video
                )
            except Exception as e:
                print(f"[gemini] Optimal analysis error: {e}, falling back to stub")

        return self._stub_optimal(dfa_config_dict)

    # ── Session insights (gemini-2.5-flash) ─────────────────
    async def generate_session_insights(
        self,
        fused_rows: List[Dict],
        verdicts: List[Dict],
        health_score: float,
    ) -> str:
        """Generate a markdown summary of a single playtest session.

        Uses MODEL_INSIGHT_GENERATION (gemini-2.5-flash).
        """
        if self._client:
            prompt = (
                f"You are a game UX analyst. Analyze this playtest session data.\n\n"
                f"Health Score: {health_score:.2f}\n"
                f"Verdicts: {json.dumps(verdicts[:10], default=str)}\n"
                f"Timeline sample (first 20 rows): {json.dumps(fused_rows[:20], default=str)}\n\n"
                "Write a concise markdown report with:\n"
                "1. Overall assessment\n2. Key problem areas\n3. Specific actionable recommendations\n"
                "4. What's working well"
            )
            try:
                response = self._client.models.generate_content(
                    model=MODEL_INSIGHT_GENERATION,
                    contents=prompt,
                )
                return response.text
            except Exception as e:
                print(f"[gemini] Insights error: {e}, falling back to stub")

        return self._stub_insights(fused_rows, verdicts, health_score)

    # ── Cross-tester insights (gemini-2.5-flash) ────────────
    async def generate_cross_tester_insights(
        self,
        aggregate_data: List[Dict],
    ) -> str:
        """Compare verdicts / scores across multiple testers.

        Uses MODEL_INSIGHT_GENERATION (gemini-2.5-flash).
        """
        if self._client:
            prompt = (
                f"You are a game UX analyst. Compare these playtest sessions:\n\n"
                f"{json.dumps(aggregate_data[:10], default=str)}\n\n"
                "Write a concise markdown report identifying:\n"
                "1. Common pain points across all testers\n"
                "2. States that consistently fail or warn\n"
                "3. Differences between best and worst sessions\n"
                "4. Actionable design recommendations"
            )
            try:
                response = self._client.models.generate_content(
                    model=MODEL_INSIGHT_GENERATION,
                    contents=prompt,
                )
                return response.text
            except Exception as e:
                print(f"[gemini] Cross-tester insights error: {e}, falling back to stub")

        return self._stub_cross_tester(aggregate_data)

    # ── Real Gemini API call ────────────────────────────────
    async def _call_gemini(
        self, model: str, video_bytes: bytes, prompt: str, fps: int = 2
    ) -> Dict:
        """Upload video bytes and call Gemini with prompt."""
        import io
        import tempfile
        import time as sync_time

        # Write video to temp file for upload
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
            tmp.write(video_bytes)
            tmp_path = tmp.name

        try:
            video_file = self._client.files.upload(file=tmp_path)

            # Wait for file to be ACTIVE (required for video processing)
            print(f"[gemini] Uploaded file {video_file.name}, waiting for ACTIVE state...")
            while video_file.state.name != "ACTIVE":
                sync_time.sleep(1)
                video_file = self._client.files.get(name=video_file.name)
                if video_file.state.name == "FAILED":
                    raise Exception(f"Video file processing failed: {video_file.name}")
            print(f"[gemini] File {video_file.name} is ACTIVE, generating content...")

            response = self._client.models.generate_content(
                model=model,
                contents=[
                    video_file,
                    f"Analyze at {fps} FPS (subsample the video). {prompt}",
                ],
            )

            text = response.text
            # Try to extract JSON from response
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            
            # Clean up uploaded file from Gemini servers
            try:
                self._client.files.delete(name=video_file.name)
                print(f"[gemini] Deleted file {video_file.name} from Gemini servers")
            except Exception as cleanup_err:
                print(f"[gemini] Could not delete file {video_file.name}: {cleanup_err}")
            
            return json.loads(text.strip())
        except (json.JSONDecodeError, Exception) as e:
            print(f"[gemini] Parse error: {e}")
            return {"states_observed": [], "transitions": [], "events": [], "notes": str(e)}
        finally:
            import os as _os
            try:
                _os.unlink(tmp_path)
            except OSError:
                pass

    # ── Stub fallbacks ──────────────────────────────────────

    def _stub_chunk(self, prompt: str) -> Dict:
        chunk_idx = 0
        if "chunk #" in prompt.lower():
            try:
                chunk_idx = int(prompt.lower().split("chunk #")[1].split(")")[0].strip())
            except (ValueError, IndexError):
                pass

        stub_states = ["tutorial", "puzzle_room", "surprise_event", "gauntlet", "victory"]
        state = stub_states[min(chunk_idx, len(stub_states) - 1)]

        return {
            "states_observed": [
                {"state": state, "confidence": round(random.uniform(0.7, 0.95), 2), "timestamp_in_chunk_sec": 0.0},
                {"state": state, "confidence": round(random.uniform(0.8, 0.98), 2), "timestamp_in_chunk_sec": 7.5},
            ],
            "transitions": [],
            "events": [
                {
                    "label": f"chunk_{chunk_idx}_observation",
                    "description": f"Player appears to be in {state} state.",
                    "timestamp_sec": 3.0,
                    "severity": "info",
                }
            ],
            "notes": f"Chunk {chunk_idx} processed. Player in {state}.",
        }

    def _stub_optimal(self, dfa_config_dict: Dict) -> Dict:
        states = dfa_config_dict.get("states", [])
        reference = {}
        for s in states:
            name = s.get("name", "unknown")
            reference[name] = {
                "expected_duration_sec": random.randint(15, 60),
                "expected_emotions": {
                    "frustration": round(random.uniform(0.0, 0.15), 2),
                    "confusion": round(random.uniform(0.0, 0.15), 2),
                    "delight": round(random.uniform(0.3, 0.7), 2),
                    "boredom": round(random.uniform(0.0, 0.1), 2),
                    "surprise": round(random.uniform(0.0, 0.3), 2),
                },
                "expected_hr_range": [65, 95],
            }
        return reference

    def _stub_insights(self, fused_rows, verdicts, health_score) -> str:
        num_fail = sum(1 for v in verdicts if v.get("verdict") == "FAIL")
        num_warn = sum(1 for v in verdicts if v.get("verdict") == "WARN")
        return (
            f"## Session Insights\n\n"
            f"**Playtest Health Score:** {health_score:.2f}\n\n"
            f"- {num_fail} states received FAIL verdicts\n"
            f"- {num_warn} states received WARN verdicts\n"
            f"- Duration: {len(fused_rows)} seconds of data\n\n"
            f"*Detailed analysis requires Gemini API key.*"
        )

    def _stub_cross_tester(self, aggregate_data) -> str:
        return (
            "## Cross-Tester Insights\n\n"
            f"Compared {len(aggregate_data)} sessions.\n\n"
            "*Detailed cross-tester analysis requires Gemini API key.*"
        )

    def is_configured(self) -> bool:
        return bool(self.api_key)
