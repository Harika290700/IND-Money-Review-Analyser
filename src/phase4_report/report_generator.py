"""
Phase 4 -- Report Generation

Renders the analysis JSON into:
  1. A professional single-page HTML report (Jinja2 template).
  2. A plain-text fallback for email clients that don't render HTML.
"""

from __future__ import annotations

import logging
from pathlib import Path
from textwrap import dedent

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "templates"
TEMPLATE_NAME = "weekly_pulse.html"


def _render_stars(rating: int) -> str:
    """Return a Unicode star string like '★★★☆☆'."""
    filled = min(max(int(rating), 0), 5)
    return "★" * filled + "☆" * (5 - filled)


def _build_plain_text(analysis: dict, metadata: dict, recipient_name: str) -> str:
    """Build a plain-text version of the weekly pulse report."""
    lines: list[str] = []

    lines.append("=" * 56)
    lines.append("  IND MONEY WEEKLY PULSE")
    lines.append(f"  {metadata['date_range']}")
    lines.append("=" * 56)
    lines.append("")
    lines.append(f"  Hi {recipient_name},")
    lines.append("  Here is your weekly pulse report for the IND Money app.")
    lines.append("")
    lines.append(
        f"  Reviews: {metadata['total_reviews']}  |  "
        f"Avg Rating: {metadata['avg_rating']:.1f}  |  "
        f"Themes: {len(analysis.get('themes', []))}"
    )
    lines.append("")

    lines.append("-" * 56)
    lines.append("  TOP THEMES")
    lines.append("-" * 56)
    for g in analysis.get("theme_groups", []):
        sentiment = g.get("sentiment", "").upper()
        lines.append(
            f"\n  {g['theme_name']}  [{sentiment}]  "
            f"({g['review_count']} reviews)"
        )
        for t in analysis.get("themes", []):
            if t["theme_name"] == g["theme_name"]:
                lines.append(f"  {t['description']}")
    lines.append("")

    lines.append("-" * 56)
    lines.append("  VOICE OF THE USER")
    lines.append("-" * 56)
    for q in analysis.get("top_quotes", []):
        stars = _render_stars(q.get("rating", 0))
        lines.append(f'\n  {stars}  [{q.get("theme", "")}]')
        lines.append(f'  "{q["quote"]}"')
    lines.append("")

    lines.append("-" * 56)
    lines.append("  ACTION IDEAS")
    lines.append("-" * 56)
    for i, a in enumerate(analysis.get("action_ideas", []), 1):
        priority = a.get("priority", "").upper()
        lines.append(f"\n  {i}. {a['title']}  [{priority}]")
        lines.append(f"     {a['description']}")
        lines.append(f"     Related: {a.get('related_theme', '')}")
    lines.append("")

    lines.append("-" * 56)
    lines.append("  EXECUTIVE SUMMARY")
    lines.append("-" * 56)
    lines.append(f"\n  {analysis.get('summary', '')}")
    lines.append("")
    lines.append("=" * 56)
    lines.append("  Generated automatically - IND Money Review Analyser")
    lines.append("=" * 56)

    return "\n".join(lines)


def generate_report(analysis: dict, metadata: dict, recipient_name: str = "Team") -> tuple[str, str]:
    """
    Render the weekly pulse report in HTML and plain text.

    Args:
        analysis:       Output dict from Phase 3 analyzer containing
                        themes, theme_groups, top_quotes, action_ideas, summary.
        metadata:       Dict with keys date_range (str), total_reviews (int),
                        avg_rating (float).
        recipient_name: Name of the recipient for the personalised greeting.
                        Defaults to "Team".

    Returns:
        (html_content, plain_text_content)
    """
    logger.info("Generating weekly pulse report for %s …", recipient_name)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=True,
    )
    template = env.get_template(TEMPLATE_NAME)

    html = template.render(
        metadata=metadata,
        recipient_name=recipient_name,
        themes=analysis.get("themes", []),
        theme_groups=analysis.get("theme_groups", []),
        top_quotes=analysis.get("top_quotes", []),
        action_ideas=analysis.get("action_ideas", []),
        summary=analysis.get("summary", ""),
    )

    plain = _build_plain_text(analysis, metadata, recipient_name)

    logger.info("Report generated (HTML: %d chars, text: %d chars)", len(html), len(plain))
    return html, plain
