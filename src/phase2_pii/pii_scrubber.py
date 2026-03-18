"""
Phase 2 -- PII Scrubber

Detects and redacts Personally Identifiable Information from review text
before it reaches the LLM or any output.

Covers:
  - Email addresses
  - Indian phone numbers (+91 / 10-digit mobile / landline)
  - Aadhaar numbers (12-digit)
  - PAN card numbers
  - UPI IDs
  - Person names (common Indian name patterns)
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# ── Regex patterns for India-specific PII ─────────────────────

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+", re.IGNORECASE)

_PHONE_RE = re.compile(
    r"(?:\+91[\s-]?)?\b[6-9]\d{4}[\s-]?\d{5}\b"
    r"|(?:\+91[\s-]?)?\b[6-9]\d{9}\b"
    r"|\b0\d{2,4}[\s-]?\d{6,8}\b"
)

_AADHAAR_RE = re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b")

_PAN_RE = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")

_UPI_RE = re.compile(r"\b[\w.-]+@[a-z]{2,}\b", re.IGNORECASE)

_NAME_RE = re.compile(
    r"\b(?:Mr|Mrs|Ms|Dr|Shri|Smt)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b"
)

_REGEX_PIPELINE: list[tuple[re.Pattern, str]] = [
    (_EMAIL_RE, "[REDACTED_EMAIL]"),
    (_PHONE_RE, "[REDACTED_PHONE]"),
    (_AADHAAR_RE, "[REDACTED_AADHAAR]"),
    (_PAN_RE, "[REDACTED_PAN]"),
    (_UPI_RE, "[REDACTED_UPI]"),
    (_NAME_RE, "[REDACTED_NAME]"),
]


def scrub_pii(text: str) -> str:
    """
    Remove all PII from the input text using regex patterns.

    Covers email, phone, Aadhaar, PAN, UPI, and titled person names.
    Returns sanitized text with redaction tokens.
    """
    for pattern, replacement in _REGEX_PIPELINE:
        text = pattern.sub(replacement, text)
    return text


def scrub_reviews(reviews: list[dict]) -> list[dict]:
    """
    Scrub PII from a list of review dicts (in-place on 'review_text').
    Returns the same list with cleaned text.
    """
    logger.info("Scrubbing PII from %d reviews …", len(reviews))
    for i, review in enumerate(reviews):
        review["review_text"] = scrub_pii(review["review_text"])
        if (i + 1) % 100 == 0:
            logger.info("  … scrubbed %d / %d", i + 1, len(reviews))
    logger.info("PII scrubbing complete.")
    return reviews
