"""
Phase 2 -- PII Scrubber

Detects and redacts Personally Identifiable Information from review text
before it reaches the LLM or any output.

Processing order:
  1. Regex-based redaction (email, phone, Aadhaar, PAN, UPI)
  2. Presidio NER-based redaction (person names)

Regex runs first so structured identifiers are removed before the NER
model has a chance to misclassify them.
"""

from __future__ import annotations

import logging
import re

from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

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

_REGEX_PIPELINE: list[tuple[re.Pattern, str]] = [
    (_EMAIL_RE, "[REDACTED_EMAIL]"),
    (_PHONE_RE, "[REDACTED_PHONE]"),
    (_AADHAAR_RE, "[REDACTED_AADHAAR]"),
    (_PAN_RE, "[REDACTED_PAN]"),
    (_UPI_RE, "[REDACTED_UPI]"),
]

# ── Presidio engine (lazy-initialized singleton) ──────────────

_analyzer: AnalyzerEngine | None = None
_anonymizer: AnonymizerEngine | None = None


def _get_engines() -> tuple[AnalyzerEngine, AnonymizerEngine]:
    """Lazy-init presidio engines so the spaCy model loads only once."""
    global _analyzer, _anonymizer
    if _analyzer is None:
        nlp_config = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}],
        }
        nlp_engine = NlpEngineProvider(nlp_configuration=nlp_config).create_engine()
        registry = RecognizerRegistry()
        registry.load_predefined_recognizers(nlp_engine=nlp_engine)
        _analyzer = AnalyzerEngine(
            nlp_engine=nlp_engine, registry=registry
        )
        _anonymizer = AnonymizerEngine()
        logger.info("Presidio engines initialized.")
    return _analyzer, _anonymizer


def _regex_scrub(text: str) -> str:
    """Apply all regex-based PII patterns in order."""
    for pattern, replacement in _REGEX_PIPELINE:
        text = pattern.sub(replacement, text)
    return text


def _presidio_scrub(text: str) -> str:
    """Use Presidio to detect and redact PERSON names."""
    analyzer, anonymizer = _get_engines()

    results = analyzer.analyze(
        text=text,
        language="en",
        entities=["PERSON"],
    )

    if not results:
        return text

    anonymized = anonymizer.anonymize(
        text=text,
        analyzer_results=results,
        operators={"PERSON": OperatorConfig("replace", {"new_value": "[REDACTED_NAME]"})},
    )
    return anonymized.text


def scrub_pii(text: str) -> str:
    """
    Remove all PII from the input text.

    Applies regex patterns first (email, phone, Aadhaar, PAN, UPI),
    then Presidio NER for person names.

    Returns sanitized text with redaction tokens.
    """
    text = _regex_scrub(text)
    text = _presidio_scrub(text)
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
