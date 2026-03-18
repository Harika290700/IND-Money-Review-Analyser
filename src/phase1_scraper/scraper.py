"""
Phase 1 -- Play Store Review Scraper

Fetches recent reviews for the IND Money app using google-play-scraper.
Paginates beyond the 200-review default using continuation tokens and
stops once reviews fall outside the requested date window.
Filters out non-English reviews and reviews with fewer than 5 words.
"""

from __future__ import annotations

import logging
import time
import random
from datetime import datetime, timedelta, timezone

from google_play_scraper import Sort, reviews
from langdetect import detect, LangDetectException

import config

logger = logging.getLogger(__name__)

MIN_WORD_COUNT = 5


def _is_english(text: str) -> bool:
    """Return True if the text is detected as English."""
    try:
        return detect(text) == "en"
    except LangDetectException:
        return False


def fetch_recent_reviews(
    app_id: str = config.APP_ID,
    weeks: int = config.DEFAULT_WEEKS,
) -> list[dict]:
    """
    Fetch Play Store reviews from the last *weeks* weeks.

    Paginates in batches of 200 using continuation tokens until either:
      - all reviews within the date window have been collected, or
      - the safety cap (MAX_BATCHES) is reached, or
      - no more reviews are available.

    Applies filters:
      - Discards reviews with fewer than 5 words.
      - Discards non-English reviews.

    Returns a list of ReviewRecord dicts sorted by date descending.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(weeks=weeks)
    collected: list[dict] = []
    seen_ids: set[str] = set()
    continuation_token: str | None = None
    reached_cutoff = False
    skipped_lang = 0

    for batch_num in range(1, config.MAX_BATCHES + 1):
        logger.info("Fetching batch %d …", batch_num)

        try:
            batch, continuation_token = reviews(
                app_id,
                lang="en",
                country="in",
                sort=Sort.NEWEST,
                count=config.REVIEWS_PER_BATCH,
                continuation_token=continuation_token,
            )
        except Exception:
            logger.exception("Error fetching batch %d", batch_num)
            break

        if not batch:
            logger.info("Empty batch received — no more reviews available.")
            break

        new_in_batch = 0
        for raw in batch:
            review_id = raw.get("reviewId", "")
            if review_id in seen_ids:
                continue
            seen_ids.add(review_id)

            review_date = raw.get("at")
            if review_date is None:
                continue

            if isinstance(review_date, datetime):
                if review_date.tzinfo is None:
                    review_date = review_date.replace(tzinfo=timezone.utc)
            else:
                continue

            if review_date < cutoff:
                reached_cutoff = True
                continue

            text = (raw.get("content") or "").strip()
            if not text or len(text.split()) < MIN_WORD_COUNT:
                continue

            if not _is_english(text):
                skipped_lang += 1
                continue

            collected.append(
                {
                    "review_text": text,
                    "rating": raw.get("score", 0),
                    "date": review_date.strftime("%Y-%m-%d %H:%M:%S"),
                    "thumbs_up_count": raw.get("thumbsUpCount", 0),
                }
            )
            new_in_batch += 1

        logger.info(
            "Batch %d: %d new reviews (total so far: %d)",
            batch_num,
            new_in_batch,
            len(collected),
        )

        if reached_cutoff:
            logger.info("Reached date cutoff (%s) — stopping.", cutoff.date())
            break

        if continuation_token is None:
            logger.info("No continuation token — all reviews fetched.")
            break

        time.sleep(random.uniform(0.5, 1.5))

    collected.sort(key=lambda r: r["date"], reverse=True)
    logger.info(
        "Total reviews collected: %d (skipped %d non-English)",
        len(collected),
        skipped_lang,
    )
    return collected
