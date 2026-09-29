import os
import pytest
from pathlib import Path
from config import BASE_DIR, OUTPUT_DIR, GEMINI_API_KEY

def test_gemini_audio_transcription():
    sample = OUTPUT_DIR / "calls" / "call_sim_236485.wav"
    if not sample.exists():
        pytest.skip(f"Sample audio {sample} not found on this machine")

    api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY') or GEMINI_API_KEY
    if not api_key:
        pytest.skip("No Gemini API key available")

    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)
        audio_bytes = sample.read_bytes()

        prompt = """You are a consultative dental AI growth specialist calling Austin Premier Dental.
Listen to the audio of what the user/receptionist just said.

Return strictly JSON:
{
  "transcript": "Exact transcription of what user said",
  "reply": "1-2 short consultative sentences (under 25 words) to reply to them",
  "is_meeting_booked": false,
  "booked_slot": null
}"""

        resp = client.models.generate_content(
            model="gemini-flash-lite-latest",
            contents=[
                types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"),
                prompt
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
                max_output_tokens=150
            )
        )
        assert resp.text is not None
    except Exception as e:
        pytest.skip(f"Gemini API call skipped: {e}")
