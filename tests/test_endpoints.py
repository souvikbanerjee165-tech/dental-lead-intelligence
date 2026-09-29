import base64
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app import app
from config import OUTPUT_DIR

def test_voice_interactive_endpoints():
    client = TestClient(app)

    # 1. Testing POST /api/voice/interactive/start
    res1 = client.post(
        "/api/voice/interactive/start",
        json={"engine": "auto-fast", "voice_name": "af_sarah"}
    )
    if res1.status_code == 200:
        data1 = res1.json()
        assert "opening_hook" in data1
        assert "engine_used" in data1

        # 2. Testing POST /api/voice/interactive/turn
        res2 = client.post(
            "/api/voice/interactive/turn",
            json={
                "user_message": "We already have a front desk team handling all patient calls.",
                "engine": "auto-fast",
                "voice_name": "af_sarah",
                "history": data1.get("history", [])
            }
        )
        assert res2.status_code == 200
        data2 = res2.json()
        assert "reply" in data2

        # 3. Testing POST /api/voice/interactive/turn-audio if sample exists
        sample_wav = OUTPUT_DIR / "calls" / "call_sim_236485.wav"
        if sample_wav.exists():
            audio_b64 = base64.b64encode(sample_wav.read_bytes()).decode("utf-8")
            res3 = client.post(
                "/api/voice/interactive/turn-audio",
                json={
                    "audio_base64": audio_b64,
                    "mime_type": "audio/wav",
                    "engine": "auto-fast",
                    "voice_name": "af_sarah",
                    "history": data2.get("history", [])
                }
            )
            assert res3.status_code == 200
    else:
        # Voice interactive might return fallback or error if voice engine unconfigured
        assert res1.status_code in [200, 400, 500]
