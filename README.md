# IND Money Review Analyser

Automatically turns Play Store reviews for the **IND Money** app into a one-page **weekly pulse report** containing top themes, real user quotes, and actionable product ideas -- then emails it to your team.

## What It Does

1. **Scrapes** recent Play Store reviews (configurable 4-16 weeks)
2. **Strips PII** -- emails, phone numbers, names, Aadhaar, PAN are redacted before any analysis
3. **Analyses** reviews using **Gemini 2.5 Flash** -- discovers 3-5 themes, picks representative quotes, generates action ideas
4. **Generates** a professional HTML one-page pulse report with personalised greeting
5. **Emails** the report to a recipient via Gmail SMTP
6. **Schedules** weekly runs automatically (local cron or GitHub Actions)

## Project Structure

```
IND-Money-Review-Analyser/
├── src/
│   ├── phase1_scraper/       # Play Store review scraper
│   ├── phase2_pii/           # PII scrubbing (Presidio + regex)
│   ├── phase3_analyzer/      # Gemini LLM two-step analysis
│   ├── phase4_report/        # Jinja2 HTML report generator
│   └── phase5_email/         # SMTP email sender
├── templates/
│   └── weekly_pulse.html     # Jinja2 report template
├── frontend/                 # Next.js dashboard (TypeScript + Tailwind)
├── cli.py                    # Command-line interface
├── api.py                    # FastAPI REST backend
├── scheduler.py              # APScheduler weekly cron
├── config.py                 # Centralised configuration
├── .github/workflows/
│   └── weekly-pulse.yml      # GitHub Actions weekly workflow
├── requirements.txt          # Python dependencies
└── ARCHITECTURE.md           # Detailed architecture document
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+ (for the web UI)
- A [Gemini API key](https://aistudio.google.com/apikey)
- A Gmail account with an [App Password](https://myaccount.google.com/apppasswords)

### 1. Install dependencies

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
cd frontend && npm install && cd ..
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your keys:

```
GEMINI_API_KEY=your-gemini-api-key
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-gmail-app-password
SCHEDULE_DAY=mon
SCHEDULE_HOUR=15
SCHEDULE_MINUTE=35
RECIPIENT_NAME=Team
RECIPIENT_EMAIL=recipient@example.com
```

### 3. Run the pipeline

**Option A: CLI**

```bash
# Full pipeline -- scrape, analyse, generate report, send email
python3.11 cli.py run --name Harika --email recipient@example.com

# Individual phases
python3.11 cli.py scrape --weeks 10
python3.11 cli.py analyze
python3.11 cli.py report --name Harika
python3.11 cli.py email --name Harika --email recipient@example.com
```

**Option B: Web UI**

```bash
# Terminal 1: Start the FastAPI backend
uvicorn api:app --reload --port 8000

# Terminal 2: Start the Next.js frontend
cd frontend && npm run dev
```

Open http://localhost:3000 in your browser.

**Option C: Scheduler (automated weekly)**

```bash
# Runs every Monday at 3:35 PM IST (configurable in .env)
python3.11 scheduler.py

# Or run immediately for testing
python3.11 scheduler.py --now
```

**Option D: GitHub Actions**

The workflow at `.github/workflows/weekly-pulse.yml` runs automatically every Monday at 3:35 PM IST. Configure secrets in your repo settings (see [ARCHITECTURE.md](ARCHITECTURE.md) for details).

## Pipeline Overview

```
Play Store Reviews
      │
      ▼
 Phase 1: Scrape (google-play-scraper)
      │  Filter: English only, 5+ words
      ▼
 Phase 2: PII Scrub (Presidio + regex)
      │  Redact: names, emails, phones, Aadhaar, PAN, UPI
      ▼
 Phase 3: Analyse (Gemini 2.5 Flash)
      │  Step A: Discover 3-5 themes
      │  Step B: Group reviews, pick quotes, generate actions
      ▼
 Phase 4: Report (Jinja2 HTML template)
      │  Personalised greeting, sentiment badges, star ratings
      ▼
 Phase 5: Email (SMTP/Gmail)
      │  Multipart: HTML + plain-text fallback
      ▼
 Recipient Inbox
```

## Tech Stack

| Component | Technology |
|---|---|
| Review scraping | `google-play-scraper` |
| Language detection | `langdetect` |
| PII scrubbing | `presidio-analyzer`, `presidio-anonymizer`, regex |
| LLM analysis | Gemini 2.5 Flash (`google-generativeai`) |
| Report generation | `Jinja2` |
| Email dispatch | Python `smtplib` (Gmail SMTP) |
| Backend API | `FastAPI` + `uvicorn` |
| Frontend UI | `Next.js` (TypeScript + Tailwind CSS) |
| Scheduler | `APScheduler` + GitHub Actions |
| Configuration | `python-dotenv` |

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full detailed architecture including Mermaid diagrams, API endpoints, prompt templates, and design decisions.

## License

This project is for educational and internal use.
