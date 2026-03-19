"""
Streamlit UI for the IND Money Review Analyser pipeline.

Run locally:
    streamlit run streamlit_app.py
"""

from __future__ import annotations

import importlib
import logging
import os

import streamlit as st

try:
    for key, value in st.secrets.items():
        os.environ[key] = str(value)
except FileNotFoundError:
    pass

import config
importlib.reload(config)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("streamlit_app")

st.set_page_config(
    page_title="INDMoney Weekly Pulse",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

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


def _build_metadata(reviews):
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
    recipient_name = st.text_input("Recipient name", value="", placeholder="Name", label_visibility="visible")
    recipient_email = st.text_input("Recipient email", value="", placeholder="Enter your email here", label_visibility="visible")

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
        <h1 style="margin:0; font-size:28px;">INDMoney Review Analyser</h1>
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
    st.session_state.analysis = None
    st.session_state.html_report = None
    st.session_state.text_report = None
    st.session_state.metadata = None

    progress = st.progress(0)
    status = st.empty()
    pipeline_ok = False

    try:
        progress.progress(5)
        status.info("Scraping Play Store reviews...")
        from src.phase1_scraper import fetch_recent_reviews
        reviews = fetch_recent_reviews(weeks=weeks)
        st.session_state.reviews = reviews
        st.session_state.metadata = _build_metadata(reviews)

        progress.progress(25)
        status.info("Scrubbing PII...")
        from src.phase2_pii import scrub_reviews
        scrubbed = scrub_reviews(reviews)
        st.session_state.scrubbed = scrubbed

        progress.progress(40)
        status.info("Analyzing with LLM (this may take a minute)...")
        from src.phase3_analyzer import analyze_reviews
        analysis = analyze_reviews(scrubbed)
        st.session_state.analysis = analysis

        progress.progress(80)
        status.info("Generating report...")
        from src.phase4_report import generate_report
        html, plain = generate_report(
            analysis,
            st.session_state.metadata,
            recipient_name=recipient_name or "Team",
        )
        st.session_state.html_report = html
        st.session_state.text_report = plain

        progress.progress(100)
        status.empty()
        st.session_state.pipeline_done = True
        pipeline_ok = True

    except Exception as e:
        logger.exception("Pipeline failed")
        status.empty()
        st.error(f"Pipeline failed: {e}")

    if pipeline_ok:
        st.rerun()

# ── Send email ───────────────────────────────────────────────
if send_email_btn:
    if not recipient_email:
        st.error("Enter a recipient email address in the sidebar.")
    elif not st.session_state.html_report:
        st.error("Generate the report first before sending email.")
    else:
        email_ok = False
        with st.spinner("Sending email..."):
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
                email_ok = True
            except Exception as e:
                logger.exception("Email send failed")
                st.error(f"Email failed: {e}")
        if email_ok:
            st.rerun()

# ── Status banners ───────────────────────────────────────────
if st.session_state.pipeline_done:
    st.success("Pipeline completed successfully!")
if st.session_state.email_sent:
    st.success(f"Email sent to {recipient_email}!")

# ── HTML report only ─────────────────────────────────────────
if st.session_state.html_report:
    st.components.v1.html(st.session_state.html_report, height=1200, scrolling=True)

# ── Empty state ──────────────────────────────────────────────
if not st.session_state.html_report and not run_pipeline:
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
