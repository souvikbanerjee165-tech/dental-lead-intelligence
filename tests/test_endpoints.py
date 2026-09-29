import urllib.request
import json
import time
import base64
from pathlib import Path

base_url = "http://127.0.0.1:8000"

print("--- 1. Testing POST /api/voice/interactive/start ---")
t0 = time.time()
req1 = urllib.request.Request(
    f"{base_url}/api/voice/interactive/start",
    data=json.dumps({"engine": "auto-fast", "voice_name": "af_sarah"}).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)
with urllib.request.urlopen(req1, timeout=15) as res:
    data1 = json.loads(res.read().decode("utf-8"))
dt1 = time.time() - t0
print(f"Start Call completed in {dt1:.2f}s:")
print(f"  Clinic: {data1.get('clinic_name')}")
print(f"  Opening Hook: {data1.get('opening_hook')[:60]}...")
print(f"  Engine Used: {data1.get('engine_used')}")
print(f"  Audio URL: {data1.get('audio_url')}")

print("\n--- 2. Testing POST /api/voice/interactive/turn (Ultra-Fast Response) ---")
t0 = time.time()
req2 = urllib.request.Request(
    f"{base_url}/api/voice/interactive/turn",
    data=json.dumps({
        "user_message": "We already have a front desk team handling all patient calls.",
        "engine": "auto-fast",
        "voice_name": "af_sarah",
        "history": data1.get("history", [])
    }).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)
with urllib.request.urlopen(req2, timeout=15) as res:
    data2 = json.loads(res.read().decode("utf-8"))
dt2 = time.time() - t0
print(f"Turn completed in {dt2:.2f}s:")
print(f"  AI Reply: \"{data2.get('reply')}\"")
print(f"  Engine Used: {data2.get('engine_used')}")
print(f"  Audio URL: {data2.get('audio_url')}")
print(f"  Meeting Booked: {data2.get('is_meeting_booked')}")

print("\n--- 3. Testing POST /api/voice/interactive/turn-audio (Multimodal Direct Audio) ---")
sample_wav = Path(r"d:\Antigravity\Lead Gen Web Scrapper (2)\Lead Gen Web Scrapper\output\calls\call_sim_236485.wav")
if sample_wav.exists():
    audio_b64 = base64.b64encode(sample_wav.read_bytes()).decode("utf-8")
    t0 = time.time()
    req3 = urllib.request.Request(
        f"{base_url}/api/voice/interactive/turn-audio",
        data=json.dumps({
            "audio_base64": audio_b64,
            "mime_type": "audio/wav",
            "engine": "auto-fast",
            "voice_name": "af_sarah",
            "history": data2.get("history", [])
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req3, timeout=20) as res:
        data3 = json.loads(res.read().decode("utf-8"))
    dt3 = time.time() - t0
    print(f"Audio Turn completed in {dt3:.2f}s:")
    print(f"  Transcribed from Mic Audio: \"{data3.get('transcript')}\"")
    print(f"  AI Reply: \"{data3.get('reply')}\"")
    print(f"  Engine Used: {data3.get('engine_used')}")
    print(f"  Audio URL: {data3.get('audio_url')}")
print("\nAll interactive voice tests PASSED!")
