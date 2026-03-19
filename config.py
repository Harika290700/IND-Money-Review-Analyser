import os
from dotenv import load_dotenv

load_dotenv()

# ── App identity ──────────────────────────────────────────────
APP_ID = "in.indwealth"
DEFAULT_WEEKS = 10
REVIEWS_PER_BATCH = 200
MAX_BATCHES = 50          # safety cap: 50 × 200 = 10 000 reviews max

# ── Gemini ────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.0-flash"

# ── SMTP ──────────────────────────────────────────────────────
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

# ── Scheduler ────────────────────────────────────────────────
SCHEDULE_DAY = os.getenv("SCHEDULE_DAY", "mon")
SCHEDULE_HOUR = int(os.getenv("SCHEDULE_HOUR", "9"))
SCHEDULE_MINUTE = int(os.getenv("SCHEDULE_MINUTE", "0"))
RECIPIENT_NAME = os.getenv("RECIPIENT_NAME", "Team")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", "")
