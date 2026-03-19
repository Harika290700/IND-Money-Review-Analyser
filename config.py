import os
from dotenv import load_dotenv

load_dotenv()

# ── App identity ──────────────────────────────────────────────
APP_ID = "in.indwealth"
DEFAULT_WEEKS = 10
REVIEWS_PER_BATCH = 100
MAX_REVIEWS_FOR_LLM = 300  # cap total reviews sent to LLM to stay within token budget

# ── Groq LLM ─────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

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
