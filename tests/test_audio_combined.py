import sys, os, time
sys.path.insert(0, r"d:\Antigravity\Lead Gen Web Scrapper (2)\Lead Gen Web Scrapper")
import dotenv
dotenv.load_dotenv(r"d:\Antigravity\Lead Gen Web Scrapper (2)\Lead Gen Web Scrapper\.env")
from google import genai
from google.genai import types
from pathlib import Path

api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
client = genai.Client(api_key=api_key)

sample = Path(r"d:\Antigravity\Lead Gen Web Scrapper (2)\Lead Gen Web Scrapper\output\calls\call_sim_236485.wav")
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

t0 = time.time()
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
print(f"Combined transcription + reply completed in {time.time()-t0:.2f}s:")
print(resp.text)
