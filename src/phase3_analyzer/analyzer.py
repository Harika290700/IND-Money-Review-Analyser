"""
Phase 3 -- Groq LLM Analysis (Batched)

Two-step analysis pipeline with batching for Groq's 128K context window:
  Step A: Discover exactly 3 themes from a representative sample.
  Step B: Process ALL reviews in batches against those themes,
          then merge results across batches.

Uses Groq (llama-3.3-70b-versatile) with JSON output.
"""

from __future__ import annotations

import json
import logging
import time
from collections import Counter

from groq import Groq, RateLimitError

import config

logger = logging.getLogger(__name__)

_client = None

MAX_RETRIES = 5
BATCH_SIZE = config.REVIEWS_PER_BATCH  # 200 reviews per batch


def _get_client():
    global _client
    if _client is None:
        if not config.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY not set. Add it to .env or Streamlit secrets.")
        _client = Groq(api_key=config.GROQ_API_KEY)
    return _client


def _call_llm(prompt: str) -> dict:
    """Send a prompt to Groq with retry on rate-limit errors."""
    client = _get_client()
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=config.GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                response_format={"type": "json_object"},
            )
            return json.loads(response.choices[0].message.content)
        except RateLimitError:
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


def _make_batches(reviews: list[dict]) -> list[list[dict]]:
    """Split reviews into batches of BATCH_SIZE."""
    batches = []
    for i in range(0, len(reviews), BATCH_SIZE):
        batches.append(reviews[i : i + BATCH_SIZE])
    logger.info("Split %d reviews into %d batches of up to %d", len(reviews), len(batches), BATCH_SIZE)
    return batches


# ── Step A: Theme Discovery ──────────────────────────────────

def _discover_themes(reviews: list[dict]) -> dict:
    """Discover exactly 3 themes from a representative sample."""
    sample = reviews[:BATCH_SIZE]
    logger.info("Step A: Discovering themes from %d reviews (sample) …", len(sample))

    prompt = f"""You are a senior product analyst at a fintech company.

Here are {len(sample)} recent user reviews for the IND Money app:

{_format_reviews_block(sample)}

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

    result = _call_llm(prompt)
    themes = result.get("themes", [])
    logger.info("Discovered %d themes: %s", len(themes), [t["theme_name"] for t in themes])
    return result


# ── Step B: Batch Extraction ─────────────────────────────────

def _extract_from_batch(reviews: list[dict], themes: dict, batch_num: int) -> dict:
    """Process one batch: group reviews, pick quotes, generate actions."""
    logger.info("Step B (batch %d): Processing %d reviews …", batch_num, len(reviews))

    themes_list = json.dumps(themes.get("themes", []), indent=2)

    prompt = f"""You are a senior product analyst at a fintech company.

Here are {len(reviews)} user reviews for the IND Money app (batch {batch_num}):

{_format_reviews_block(reviews)}

Here are the discovered themes:
{themes_list}

Perform these tasks:
1. For each theme, count how many reviews in THIS batch belong to it and pick 2-3 sample review texts.
2. Select exactly 3 of the most representative and impactful user quotes (verbatim from the reviews above).
3. Generate exactly 3 actionable product improvement ideas based on the themes.
4. Write a 2-3 sentence executive summary of the overall review sentiment in this batch.

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

    result = _call_llm(prompt)
    logger.info(
        "Batch %d done: %d groups, %d quotes, %d actions",
        batch_num,
        len(result.get("theme_groups", [])),
        len(result.get("top_quotes", [])),
        len(result.get("action_ideas", [])),
    )
    return result


def _merge_batch_results(batch_results: list[dict]) -> dict:
    """Merge extraction results from multiple batches into a single output."""
    if len(batch_results) == 1:
        return batch_results[0]

    # Merge theme_groups: sum review_count, combine samples
    theme_map = {}
    for br in batch_results:
        for g in br.get("theme_groups", []):
            name = g["theme_name"]
            if name not in theme_map:
                theme_map[name] = {
                    "theme_name": name,
                    "review_count": 0,
                    "sentiment": g.get("sentiment", "mixed"),
                    "sample_reviews": [],
                }
            theme_map[name]["review_count"] += g.get("review_count", 0)
            theme_map[name]["sample_reviews"].extend(g.get("sample_reviews", []))

    for v in theme_map.values():
        v["sample_reviews"] = v["sample_reviews"][:3]

    merged_groups = sorted(theme_map.values(), key=lambda g: g["review_count"], reverse=True)

    # Collect all quotes, pick top 3 by rating
    all_quotes = []
    for br in batch_results:
        all_quotes.extend(br.get("top_quotes", []))
    all_quotes.sort(key=lambda q: q.get("rating", 0))
    top_quotes = all_quotes[:3]

    # Collect all action ideas, deduplicate by title, pick top 3
    seen_titles = set()
    all_actions = []
    for br in batch_results:
        for a in br.get("action_ideas", []):
            title_lower = a["title"].lower()
            if title_lower not in seen_titles:
                seen_titles.add(title_lower)
                all_actions.append(a)
    priority_order = {"high": 0, "medium": 1, "low": 2}
    all_actions.sort(key=lambda a: priority_order.get(a.get("priority", "medium"), 1))
    action_ideas = all_actions[:3]

    # Use the last batch's summary (it has the most complete picture)
    summary = batch_results[-1].get("summary", "")

    return {
        "theme_groups": merged_groups,
        "top_quotes": top_quotes,
        "action_ideas": action_ideas,
        "summary": summary,
    }


# ── Main Entry Point ─────────────────────────────────────────

def analyze_reviews(reviews: list[dict]) -> dict:
    """
    Two-step batched Groq analysis.

    Step A: Discover themes from a sample (first batch).
    Step B: Process each batch for extraction, then merge.

    Args:
        reviews: List of review dicts with 'review_text' and 'rating' keys.

    Returns:
        Combined analysis dict with keys:
          - themes, theme_groups, top_quotes, action_ideas, summary
    """
    if not reviews:
        raise ValueError("No reviews provided for analysis.")

    # Step A: Discover themes
    themes = _discover_themes(reviews)

    # Step B: Process batches
    batches = _make_batches(reviews)
    batch_results = []
    for i, batch in enumerate(batches, 1):
        result = _extract_from_batch(batch, themes, batch_num=i)
        batch_results.append(result)

    merged = _merge_batch_results(batch_results)

    return {
        "themes": themes.get("themes", []),
        "theme_groups": merged.get("theme_groups", []),
        "top_quotes": merged.get("top_quotes", []),
        "action_ideas": merged.get("action_ideas", []),
        "summary": merged.get("summary", ""),
    }
