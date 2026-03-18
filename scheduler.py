"""
Weekly Scheduler -- Automated Pipeline Runner via CLI

Runs the full pipeline every week using the CLI (cli.py).
The schedule, recipient name, and recipient email are configured via .env.

Schedule defaults: Every Monday at 15:35 IST (Asia/Kolkata).

Usage:
  python3.11 scheduler.py          # start the scheduler (runs in foreground)
  python3.11 scheduler.py --now    # run the pipeline immediately, then exit
"""

from __future__ import annotations

import argparse
import logging
import signal
import subprocess
import sys
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("scheduler")


def run_pipeline() -> None:
    """Execute the full pipeline via cli.py."""
    start = datetime.now()
    logger.info("=" * 60)
    logger.info("Scheduled pipeline started at %s", start.strftime("%Y-%m-%d %H:%M:%S %Z"))
    logger.info("=" * 60)

    name = config.RECIPIENT_NAME
    email = config.RECIPIENT_EMAIL
    weeks = config.DEFAULT_WEEKS

    if not email:
        logger.error("RECIPIENT_EMAIL not set in .env -- aborting.")
        return

    cmd = [
        sys.executable, "cli.py", "run",
        "--weeks", str(weeks),
        "--name", name,
        "--email", email,
    ]

    logger.info("Running: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            capture_output=False,
            text=True,
        )

        elapsed = (datetime.now() - start).total_seconds()

        if result.returncode == 0:
            logger.info("=" * 60)
            logger.info("Pipeline completed in %.1f seconds.", elapsed)
            logger.info("=" * 60)
        else:
            logger.error("Pipeline failed with exit code %d.", result.returncode)

    except Exception:
        logger.exception("Pipeline execution failed!")


def main() -> None:
    parser = argparse.ArgumentParser(description="IND Money Weekly Pulse Scheduler")
    parser.add_argument(
        "--now",
        action="store_true",
        help="Run the pipeline immediately and exit (no scheduling).",
    )
    args = parser.parse_args()

    if args.now:
        logger.info("Running pipeline immediately (--now flag).")
        run_pipeline()
        return

    day = config.SCHEDULE_DAY
    hour = config.SCHEDULE_HOUR
    minute = config.SCHEDULE_MINUTE

    scheduler = BlockingScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(
        run_pipeline,
        trigger=CronTrigger(
            day_of_week=day,
            hour=hour,
            minute=minute,
            timezone="Asia/Kolkata",
        ),
        id="weekly_pulse",
        name="IND Money Weekly Pulse",
        misfire_grace_time=3600,
    )

    def shutdown(signum, frame):
        logger.info("Shutting down scheduler …")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logger.info(
        "Scheduler started. Pipeline will run every %s at %02d:%02d IST.",
        day.upper(), hour, minute,
    )
    logger.info("Recipient: %s <%s>", config.RECIPIENT_NAME, config.RECIPIENT_EMAIL)
    logger.info("Press Ctrl+C to stop.")
    scheduler.start()


if __name__ == "__main__":
    main()
