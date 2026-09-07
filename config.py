import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Base directories
BASE_DIR = Path(__file__).resolve().parent
if os.getenv("VERCEL"):
    OUTPUT_DIR = Path("/tmp/output")
else:
    OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

# Google Maps Scraping Configuration
DEFAULT_LOCATION = "Texas"
DEFAULT_CATEGORY = "Dentists"
DEFAULT_MAX_RESULTS = 20
HEADLESS_BROWSER = True
MAPS_BASE_URL = "https://www.google.com/maps"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

# Opportunity Scoring Weights (0 - 100 max)
SCORING_WEIGHTS = {
    "missing_ai_chatbot": 25,       # No AI chat or live chat widget found
    "missing_online_booking": 20,   # No direct online scheduling (Calendly, Acuity, NexHealth, etc.)
    "outdated_or_slow": 20,         # Missing modern viewport, slow response, or basic old HTML indicators
    "low_reviews_or_missing_faq": 15, # < 50 reviews or no structured FAQ section
    "missing_social_or_whatsapp": 10, # Missing active social or messaging links
    "missing_ssl": 10,              # Insecure HTTP
}

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
