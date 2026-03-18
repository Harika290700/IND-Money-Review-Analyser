"""
Streamlit UI for the IND Money Review Analyser pipeline.

Replaces the Next.js + FastAPI stack with a single deployable Python app.

Run locally:
    streamlit run streamlit_app.py
"""

from __future__ import annotations

import logging
import streamlit as st

import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("streamlit_app")

# ── Page config ──────────────────────────────────────────────
st.set_page_config(
    page_title="IND Money Weekly Pulse",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session state defaults ───────────────────────────────────
for key, default in {
    "reviews": None,
    "scrubbed": None,
    "analysis": None,
    "metadata": None,
    "html_report": None,
    "text_report": None,
    "pipeline_done": False,
    "email_sent": False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


def _build_metadata(reviews: list[dict]) -> dict:
    dates = sorted(r["date"] for r in reviews)
    ratings = [r["rating"] for r in reviews]
    return {
        "date_range": f"{dates[0][:10]} to {dates[-1][:10]}",
        "total_reviews": len(reviews),
        "avg_rating": round(sum(ratings) / len(ratings), 2),
    }


# ── Sidebar ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## Configuration")
    weeks = st.slider("Weeks of reviews", min_value=4, max_value=16, value=10)

    st.markdown("---")
    st.markdown("## Recipient Details")
    recipient_name = st.text_input("Recipient name", value="Team", placeholder="e.g. Harika")
    recipient_email = st.text_input("Recipient email", placeholder="user@example.com")

    st.markdown("---")
    st.markdown("## Actions")
    run_pipeline = st.button(
        "Generate Weekly Pulse",
        type="primary",
        use_container_width=True,
    )
    send_email_btn = st.button(
        "Send Email",
        use_container_width=True,
        disabled=st.session_state.html_report is None,
    )

    if st.session_state.html_report:
        st.download_button(
            "Download HTML Report",
            data=st.session_state.html_report,
            file_name="weekly_pulse.html",
            mime="text/html",
            use_container_width=True,
        )

# ── Header ───────────────────────────────────────────────────
st.markdown(
    """
    <div style="background: linear-gradient(135deg, #0f4c81, #1a73e8);
                color: white; padding: 28px 32px; border-radius: 12px;
                margin-bottom: 24px;">
        <h1 style="margin:0; font-size:28px;">IND Money Review Analyser</h1>
        <p style="margin:4px 0 0; opacity:0.85; font-size:15px;">
            Weekly Pulse Dashboard
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Pipeline execution ───────────────────────────────────────
if run_pipeline:
    st.session_state.pipeline_done = False
    st.session_state.email_sent = False
    progress = st.progress(0, text="Starting pipeline…")

    try:
        # Phase 1 -- Scrape
        progress.progress(5, text="Phase 1: Scraping Play Store reviews…")
        from src.phase1_scraper import fetch_recent_reviews
        reviews = fetch_recent_reviews(weeks=weeks)
        st.session_state.reviews = reviews
        st.session_state.metadata = _build_metadata(reviews)
        logger.info("Scraped %d reviews", len(reviews))

        # Phase 2 -- PII scrub
        progress.progress(25, text="Phase 2: Scrubbing PII…")
        from src.phase2_pii import scrub_reviews
        scrubbed = scrub_reviews(reviews)
        st.session_state.scrubbed = scrubbed
        logger.info("Scrubbed %d reviews", len(scrubbed))

        # Phase 3 -- LLM analysis
        progress.progress(40, text="Phase 3: Analyzing with Gemini (this may take a minute)…")
        from src.phase3_analyzer import analyze_reviews
        analysis = analyze_reviews(scrubbed)
        st.session_state.analysis = analysis
        logger.info("Analysis complete: %d themes", len(analysis.get("themes", [])))

        # Phase 4 -- Report
        progress.progress(80, text="Phase 4: Generating report…")
        from src.phase4_report import generate_report
        html, plain = generate_report(
            analysis,
            st.session_state.metadata,
            recipient_name=recipient_name or "Team",
        )
        st.session_state.html_report = html
        st.session_state.text_report = plain
        logger.info("Report generated")

        progress.progress(100, text="Pipeline complete!")
        st.session_state.pipeline_done = True

    except Exception as e:
        logger.exception("Pipeline failed")
        st.error(f"Pipeline failed: {e}")

# ── Send email ───────────────────────────────────────────────
if send_email_btn:
    if not recipient_email:
        st.error("Enter a recipient email address in the sidebar.")
    elif not st.session_state.html_report:
        st.error("Generate the report first before sending email.")
    else:
        with st.spinner("Sending email…"):
            try:
                from src.phase5_email import send_pulse_email
                send_pulse_email(
                    html_content=st.session_state.html_report,
                    text_content=st.session_state.text_report,
                    recipient_email=recipient_email,
                    recipient_name=recipient_name or "Team",
                    date_range=st.session_state.metadata["date_range"],
                )
                st.session_state.email_sent = True
            except Exception as e:
                logger.exception("Email send failed")
                st.error(f"Email failed: {e}")

# ── Status banners ───────────────────────────────────────────
if st.session_state.pipeline_done:
    st.success("Pipeline completed successfully!")
if st.session_state.email_sent:
    st.success(f"Email sent to {recipient_email}!")

# ── Metrics ──────────────────────────────────────────────────
if st.session_state.metadata:
    meta = st.session_state.metadata
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Reviews", meta["total_reviews"])
    c2.metric("Avg Rating", f"{meta['avg_rating']:.1f}")
    c3.metric("Date Range", meta["date_range"])

# ── Analysis details (expandable) ────────────────────────────
if st.session_state.analysis:
    analysis = st.session_state.analysis

    st.markdown("---")

    # Themes
    st.subheader("Top Themes")
    for group in analysis.get("theme_groups", []):
        sentiment = group.get("sentiment", "mixed")
        color = {"positive": "🟢", "negative": "🔴", "mixed": "🟡"}.get(sentiment, "⚪")
        with st.expander(
            f"{color}  **{group['theme_name']}**  —  "
            f"{group.get('review_count', 0)} reviews  |  {sentiment.upper()}"
        ):
            for t in analysis.get("themes", []):
                if t["theme_name"] == group["theme_name"]:
                    st.write(t.get("description", ""))
            samples = group.get("sample_reviews", [])
            if samples:
                st.markdown("**Sample reviews:**")
                for s in samples[:3]:
                    st.markdown(f"- _{s}_")

    # Quotes
    st.subheader("Voice of the User")
    for q in analysis.get("top_quotes", []):
        rating = q.get("rating", 0)
        stars = "★" * rating + "☆" * (5 - rating)
        st.markdown(
            f"> *\"{q['quote']}\"*\n>\n"
            f"> {stars}  ·  {q.get('theme', '')}"
        )

    # Action Ideas
    st.subheader("Action Ideas")
    for i, a in enumerate(analysis.get("action_ideas", []), 1):
        priority = a.get("priority", "medium")
        badge = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "⚪")
        st.markdown(
            f"**{i}. {a['title']}** {badge} `{priority.upper()}`\n\n"
            f"{a.get('description', '')}  \n"
            f"_Related: {a.get('related_theme', '')}_"
        )

    # Summary
    if analysis.get("summary"):
        st.subheader("Executive Summary")
        st.info(analysis["summary"])

# ── HTML report preview ──────────────────────────────────────
if st.session_state.html_report:
    st.markdown("---")
    st.subheader("Report Preview")
    st.components.v1.html(st.session_state.html_report, height=900, scrolling=True)

# ── Empty state ──────────────────────────────────────────────
if not st.session_state.metadata and not st.session_state.pipeline_done:
    st.markdown(
        """
        <div style="text-align:center; padding:60px 20px; color:#999;">
            <div style="font-size:64px; margin-bottom:16px;">📊</div>
            <h3 style="color:#666;">Ready to generate your weekly pulse</h3>
            <p>Configure weeks and recipient in the sidebar, then click
               <strong>Generate Weekly Pulse</strong>.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
