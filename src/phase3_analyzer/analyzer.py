"""
Phase 3 -- Gemini LLM Analysis

Two-step analysis pipeline:
  Step A: Discover exactly 3 recurring themes from the review corpus.
  Step B: Group reviews under themes, pick representative quotes,
          generate action ideas, and write an executive summary.

Uses Gemini 2.0 Flash with structured JSON output.
"""

from __future__ import annotations

import json
import logging
import time

import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted

import config

logger = logging.getLogger(__name__)

_model = None

MAX_RETRIES = 5


def _get_model():
    global _model
    if _model is None:
        if not config.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not set. Add it to .env or Streamlit secrets.")
        genai.configure(api_key=config.GEMINI_API_KEY)
        _model = genai.GenerativeModel(config.GEMINI_MODEL)
    return _model


def _call_gemini(prompt: str) -> dict:
    """Send a prompt to Gemini with retry on rate-limit errors."""
    model = _get_model()
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.3,
                ),
            )
            return json.loads(response.text)
        except ResourceExhausted as e:
            wait = min(15 * attempt, 60)
            logger.warning(
                "Rate limited (attempt %d/%d). Retrying in %ds …",
                attempt, MAX_RETRIES, wait,
            )
            if attempt == MAX_RETRIES:
                raise
            time.sleep(wait)


def _format_reviews_block(reviews: list[dict]) -> str:
    """Format reviews into a numbered text block for the prompt."""
    lines = []
    for i, r in enumerate(reviews, 1):
        stars = r.get("rating", "?")
        text = r.get("review_text", "")
        lines.append(f"[{i}] ({stars}★) {text}")
    return "\n".join(lines)


def _discover_themes(reviews: list[dict]) -> dict:
    """Step A: Identify exactly 3 recurring themes."""
    logger.info("Step A: Discovering themes from %d reviews …", len(reviews))

    prompt = f"""You are a senior product analyst at a fintech company.

Here are {len(reviews)} recent user reviews for the IND Money app:

{_format_reviews_block(reviews)}

Identify exactly 3 recurring themes (no more, no less). For each theme provide:
- theme_name: a short descriptive label (max 6 words)
- description: one-sentence explanation of what users are saying
- sentiment: "positive", "negative", or "mixed"
- estimated_count: approximate number of reviews about this theme

Return JSON in this exact format:
{{
  "themes": [
    {{
      "theme_name": "...",
      "description": "...",
      "sentiment": "positive|negative|mixed",
      "estimated_count": <number>
    }}
  ]
}}"""

    result = _call_gemini(prompt)
    themes = result.get("themes", [])
    logger.info("Discovered %d themes: %s", len(themes), [t["theme_name"] for t in themes])
    return result


def _group_and_extract(reviews: list[dict], themes: dict) -> dict:
    """Step B: Group reviews under themes, pick quotes, generate actions."""
    logger.info("Step B: Grouping reviews and extracting insights …")

    themes_list = json.dumps(themes.get("themes", []), indent=2)

    prompt = f"""You are a senior product analyst at a fintech company.

Here are {len(reviews)} recent user reviews for the IND Money app:

{_format_reviews_block(reviews)}

Here are the discovered themes:
{themes_list}

Perform these tasks:
1. For each theme, count how many reviews belong to it and pick 2-3 sample review texts.
2. Select exactly 3 of the most representative and impactful user quotes (verbatim from the reviews above). Pick quotes that best illustrate the key issues or praise.
3. Generate exactly 3 actionable product improvement ideas based on the themes. Each idea should be concrete and implementable.
4. Write a 2-3 sentence executive summary of the overall review sentiment and key takeaways.

Return JSON in this exact format:
{{
  "theme_groups": [
    {{
      "theme_name": "...",
      "review_count": <number>,
      "sentiment": "positive|negative|mixed",
      "sample_reviews": ["review text 1", "review text 2"]
    }}
  ],
  "top_quotes": [
    {{ "quote": "exact user quote", "rating": <1-5>, "theme": "theme name" }}
  ],
  "action_ideas": [
    {{
      "title": "short action title",
      "description": "concrete description of what to do",
      "priority": "high|medium|low",
      "related_theme": "theme name"
    }}
  ],
  "summary": "2-3 sentence executive summary..."
}}"""

    result = _call_gemini(prompt)
    logger.info(
        "Extraction complete: %d theme groups, %d quotes, %d actions",
        len(result.get("theme_groups", [])),
        len(result.get("top_quotes", [])),
        len(result.get("action_ideas", [])),
    )
    return result


def analyze_reviews(reviews: list[dict]) -> dict:
    """
    Two-step Gemini analysis: discover themes, then group and extract.

    Args:
        reviews: List of review dicts with 'review_text' and 'rating' keys.

    Returns:
        Combined analysis dict with keys:
          - themes (from Step A)
          - theme_groups, top_quotes, action_ideas, summary (from Step B)
    """
    if not reviews:
        raise ValueError("No reviews provided for analysis.")

    themes = _discover_themes(reviews)
    extraction = _group_and_extract(reviews, themes)

    return {
        "themes": themes.get("themes", []),
        "theme_groups": extraction.get("theme_groups", []),
        "top_quotes": extraction.get("top_quotes", []),
        "action_ideas": extraction.get("action_ideas", []),
        "summary": extraction.get("summary", ""),
    }
