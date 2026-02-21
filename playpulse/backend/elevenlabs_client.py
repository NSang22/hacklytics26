"""
ElevenLabs client — text-to-speech audio report generation.
STUB: returns a placeholder path. Implement with ElevenLabs REST API later.
"""

from __future__ import annotations


async def generate_audio_report(text: str, session_id: str) -> str:
    """Generate a voice-narrated playtest report.

    Args:
        text: The report text to synthesise.
        session_id: Used to name the output file.

    Returns:
        File path (or URL) to the generated MP3 audio report.
    """
    # TODO: POST to https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}
    #       with xi-api-key header, save response bytes to file.
    return f"reports/{session_id}_report.mp3"
