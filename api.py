"""
FastAPI Backend -- REST API for the IND Money Review Analyser pipeline.

Serves the Next.js frontend. Endpoints expose each pipeline phase
and a combined "run all" endpoint.

Usage:
  uvicorn api:app --reload --port 8000
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr

import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("api")

app = FastAPI(title="IND Money Review Analyser API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory state for the current session ──────────────────────
_state: dict = {
    "reviews": None,
    "scrubbed": None,
    "analysis": None,
    "metadata": None,
    "html_report": None,
    "text_report": None,
}


def _build_metadata(reviews: list[dict]) -> dict:
    dates = sorted(r["date"] for r in reviews)
    ratings = [r["rating"] for r in reviews]
    return {
        "date_range": f"{dates[0][:10]} to {dates[-1][:10]}",
        "total_reviews": len(reviews),
        "avg_rating": round(sum(ratings) / len(ratings), 2),
    }


# ── Request / Response models ────────────────────────────────────

class ScrapeRequest(BaseModel):
    weeks: int = config.DEFAULT_WEEKS

class AnalyzeRequest(BaseModel):
    weeks: int = config.DEFAULT_WEEKS

class ReportRequest(BaseModel):
    weeks: int = config.DEFAULT_WEEKS
    recipient_name: str = "Team"

class EmailRequest(BaseModel):
    recipient_name: str = "Team"
    recipient_email: str

class RunAllRequest(BaseModel):
    weeks: int = config.DEFAULT_WEEKS
    recipient_name: str = "Team"
    recipient_email: str


# ── Endpoints ────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/scrape")
def scrape(req: ScrapeRequest):
    """Phase 1: Scrape Play Store reviews."""
    try:
        from src.phase1_scraper import fetch_recent_reviews

        logger.info("Phase 1: Scraping reviews (last %d weeks) …", req.weeks)
        reviews = fetch_recent_reviews(weeks=req.weeks)
        _state["reviews"] = reviews
        _state["metadata"] = _build_metadata(reviews)
        logger.info("Fetched %d reviews.", len(reviews))
        return {
            "phase": 1,
            "total_reviews": len(reviews),
            "metadata": _state["metadata"],
        }
    except Exception as e:
        logger.exception("Phase 1 failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/scrub")
def scrub():
    """Phase 2: Scrub PII from reviews."""
    if not _state["reviews"]:
        raise HTTPException(status_code=400, detail="No reviews to scrub. Run /api/scrape first.")
    try:
        from src.phase2_pii import scrub_reviews

        logger.info("Phase 2: Scrubbing PII …")
        scrubbed = scrub_reviews(_state["reviews"])
        _state["scrubbed"] = scrubbed
        logger.info("PII scrubbing complete.")
        return {"phase": 2, "scrubbed_count": len(scrubbed)}
    except Exception as e:
        logger.exception("Phase 2 failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze")
def analyze():
    """Phase 3: LLM analysis."""
    if not _state["scrubbed"]:
        raise HTTPException(status_code=400, detail="No scrubbed reviews. Run /api/scrub first.")
    try:
        from src.phase3_analyzer import analyze_reviews

        logger.info("Phase 3: Running Gemini analysis …")
        analysis = analyze_reviews(_state["scrubbed"])
        _state["analysis"] = analysis
        logger.info("Analysis complete: %d themes.", len(analysis.get("themes", [])))
        return {
            "phase": 3,
            "themes_count": len(analysis.get("themes", [])),
            "themes": analysis.get("themes", []),
        }
    except Exception as e:
        logger.exception("Phase 3 failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/report")
def report(req: ReportRequest):
    """Phase 4: Generate HTML report."""
    if not _state["analysis"]:
        raise HTTPException(status_code=400, detail="No analysis data. Run /api/analyze first.")
    try:
        from src.phase4_report import generate_report

        logger.info("Phase 4: Generating report for %s …", req.recipient_name)
        html, plain = generate_report(
            _state["analysis"], _state["metadata"], recipient_name=req.recipient_name
        )
        _state["html_report"] = html
        _state["text_report"] = plain
        return {"phase": 4, "html_length": len(html), "text_length": len(plain)}
    except Exception as e:
        logger.exception("Phase 4 failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/report/preview", response_class=HTMLResponse)
def report_preview():
    """Return the generated HTML report for preview."""
    if not _state["html_report"]:
        raise HTTPException(status_code=400, detail="No report generated yet.")
    return _state["html_report"]


@app.post("/api/email")
def send_email(req: EmailRequest):
    """Phase 5: Send email."""
    if not _state["html_report"] or not _state["text_report"]:
        raise HTTPException(status_code=400, detail="No report to send. Run /api/report first.")
    try:
        from src.phase5_email import send_pulse_email

        logger.info("Phase 5: Sending email to %s <%s> …", req.recipient_name, req.recipient_email)
        send_pulse_email(
            html_content=_state["html_report"],
            text_content=_state["text_report"],
            recipient_email=req.recipient_email,
            recipient_name=req.recipient_name,
            date_range=_state["metadata"]["date_range"],
        )
        return {"phase": 5, "sent_to": req.recipient_email, "status": "sent"}
    except Exception as e:
        logger.exception("Phase 5 failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/run")
def run_all(req: RunAllRequest):
    """Run the full pipeline (Phases 1-5) in one call."""
    try:
        scrape_result = scrape(ScrapeRequest(weeks=req.weeks))
        scrub_result = scrub()
        analyze_result = analyze()
        report_result = report(ReportRequest(
            weeks=req.weeks, recipient_name=req.recipient_name
        ))
        email_result = send_email(EmailRequest(
            recipient_name=req.recipient_name, recipient_email=req.recipient_email
        ))

        return {
            "status": "complete",
            "total_reviews": scrape_result["total_reviews"],
            "themes_count": analyze_result["themes_count"],
            "themes": analyze_result["themes"],
            "analysis": _state["analysis"],
            "metadata": _state["metadata"],
            "email_sent_to": req.recipient_email,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Full pipeline failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/state")
def get_state():
    """Return current pipeline state (what data is available)."""
    return {
        "has_reviews": _state["reviews"] is not None,
        "review_count": len(_state["reviews"]) if _state["reviews"] else 0,
        "has_analysis": _state["analysis"] is not None,
        "themes_count": len(_state["analysis"].get("themes", [])) if _state["analysis"] else 0,
        "has_report": _state["html_report"] is not None,
        "metadata": _state["metadata"],
    }
