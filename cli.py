"""
CLI -- Command-line interface for the IND Money Review Analyser pipeline.

Usage:
  python3.11 cli.py run --name Harika --email hpinni1@ext.uber.com
  python3.11 cli.py scrape
  python3.11 cli.py analyze
  python3.11 cli.py report --name Harika
  python3.11 cli.py email --name Harika --email hpinni1@ext.uber.com
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime

import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("cli")


def _build_metadata(reviews: list[dict]) -> dict:
    dates = sorted(r["date"] for r in reviews)
    ratings = [r["rating"] for r in reviews]
    return {
        "date_range": f"{dates[0][:10]} to {dates[-1][:10]}",
        "total_reviews": len(reviews),
        "avg_rating": sum(ratings) / len(ratings),
    }


def cmd_scrape(args: argparse.Namespace) -> list[dict]:
    from src.phase1_scraper import fetch_recent_reviews

    weeks = args.weeks if hasattr(args, "weeks") and args.weeks else config.DEFAULT_WEEKS
    logger.info("Phase 1: Scraping reviews (last %d weeks) …", weeks)
    reviews = fetch_recent_reviews(weeks=weeks)
    logger.info("Fetched %d reviews.", len(reviews))

    with open("scraped_reviews.json", "w", encoding="utf-8") as f:
        json.dump(reviews, f, indent=2, ensure_ascii=False, default=str)
    logger.info("Saved to scraped_reviews.json")
    return reviews


def cmd_analyze(args: argparse.Namespace) -> dict:
    try:
        with open("scraped_reviews.json") as f:
            reviews = json.load(f)
    except FileNotFoundError:
        logger.info("No scraped_reviews.json found, running scraper first …")
        reviews = cmd_scrape(args)

    from src.phase2_pii import scrub_reviews

    logger.info("Phase 2: Scrubbing PII from %d reviews …", len(reviews))
    scrubbed = scrub_reviews(reviews)

    from src.phase3_analyzer import analyze_reviews

    logger.info("Phase 3: Running Gemini analysis …")
    analysis = analyze_reviews(scrubbed)
    logger.info("Analysis complete: %d themes.", len(analysis.get("themes", [])))

    with open("analysis_output.json", "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)
    logger.info("Saved to analysis_output.json")
    return analysis


def cmd_report(args: argparse.Namespace) -> tuple[str, str]:
    try:
        with open("analysis_output.json") as f:
            analysis = json.load(f)
        with open("scraped_reviews.json") as f:
            reviews = json.load(f)
    except FileNotFoundError:
        logger.info("Missing data files, running full analysis first …")
        analysis = cmd_analyze(args)
        with open("scraped_reviews.json") as f:
            reviews = json.load(f)

    from src.phase4_report import generate_report

    metadata = _build_metadata(reviews)
    name = args.name if hasattr(args, "name") and args.name else config.RECIPIENT_NAME

    logger.info("Phase 4: Generating report for %s …", name)
    html, plain = generate_report(analysis, metadata, recipient_name=name)

    with open("weekly_pulse.html", "w", encoding="utf-8") as f:
        f.write(html)
    with open("weekly_pulse.txt", "w", encoding="utf-8") as f:
        f.write(plain)
    logger.info("Saved weekly_pulse.html and weekly_pulse.txt")
    return html, plain


def cmd_email(args: argparse.Namespace) -> None:
    try:
        with open("weekly_pulse.html") as f:
            html = f.read()
        with open("weekly_pulse.txt") as f:
            plain = f.read()
        with open("scraped_reviews.json") as f:
            reviews = json.load(f)
    except FileNotFoundError:
        logger.info("Missing report files, generating first …")
        html, plain = cmd_report(args)
        with open("scraped_reviews.json") as f:
            reviews = json.load(f)

    from src.phase5_email import send_pulse_email

    metadata = _build_metadata(reviews)
    name = args.name if hasattr(args, "name") and args.name else config.RECIPIENT_NAME
    email = args.email if hasattr(args, "email") and args.email else config.RECIPIENT_EMAIL

    if not email:
        logger.error("No recipient email. Use --email or set RECIPIENT_EMAIL in .env")
        sys.exit(1)

    logger.info("Phase 5: Sending email to %s <%s> …", name, email)
    send_pulse_email(
        html_content=html,
        text_content=plain,
        recipient_email=email,
        recipient_name=name,
        date_range=metadata["date_range"],
    )
    logger.info("Email sent successfully.")


def cmd_run(args: argparse.Namespace) -> None:
    """Run the full pipeline end-to-end."""
    start = datetime.now()
    logger.info("=" * 50)
    logger.info("Full pipeline started")
    logger.info("=" * 50)

    cmd_scrape(args)
    cmd_analyze(args)
    cmd_report(args)
    cmd_email(args)

    elapsed = (datetime.now() - start).total_seconds()
    logger.info("=" * 50)
    logger.info("Pipeline completed in %.1f seconds.", elapsed)
    logger.info("=" * 50)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="IND Money Review Analyser CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3.11 cli.py run --name Harika --email user@example.com
  python3.11 cli.py scrape --weeks 12
  python3.11 cli.py analyze
  python3.11 cli.py report --name Harika
  python3.11 cli.py email --name Harika --email user@example.com
        """,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # -- scrape --------------------------------------------------------
    p_scrape = sub.add_parser("scrape", help="Phase 1: Scrape Play Store reviews")
    p_scrape.add_argument("--weeks", type=int, default=config.DEFAULT_WEEKS, help="Weeks of reviews to fetch")

    # -- analyze -------------------------------------------------------
    p_analyze = sub.add_parser("analyze", help="Phases 1-3: Scrape + PII scrub + LLM analysis")
    p_analyze.add_argument("--weeks", type=int, default=config.DEFAULT_WEEKS)

    # -- report --------------------------------------------------------
    p_report = sub.add_parser("report", help="Phases 1-4: Full analysis + generate report")
    p_report.add_argument("--weeks", type=int, default=config.DEFAULT_WEEKS)
    p_report.add_argument("--name", type=str, default=config.RECIPIENT_NAME, help="Recipient name for greeting")

    # -- email ---------------------------------------------------------
    p_email = sub.add_parser("email", help="Phase 5: Send the generated report via email")
    p_email.add_argument("--name", type=str, default=config.RECIPIENT_NAME, help="Recipient name")
    p_email.add_argument("--email", type=str, default=config.RECIPIENT_EMAIL, help="Recipient email")

    # -- run (full pipeline) -------------------------------------------
    p_run = sub.add_parser("run", help="Run the full pipeline (Phases 1-5)")
    p_run.add_argument("--weeks", type=int, default=config.DEFAULT_WEEKS)
    p_run.add_argument("--name", type=str, default=config.RECIPIENT_NAME, help="Recipient name")
    p_run.add_argument("--email", type=str, default=config.RECIPIENT_EMAIL, help="Recipient email")

    args = parser.parse_args()

    commands = {
        "scrape": cmd_scrape,
        "analyze": cmd_analyze,
        "report": cmd_report,
        "email": cmd_email,
        "run": cmd_run,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
