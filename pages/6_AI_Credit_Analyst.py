"""
AI Credit Analyst Dashboard.

Interactive natural language decision-support assistant:
- Plain language portfolio inquiries.
- Grounded strictly in calculated metrics, verified findings, and prescriptions.
- Pre-configured executive prompt buttons for rapid scenario analysis.
"""

from __future__ import annotations

import streamlit as st

from components.layout import render_footer, render_header, render_section_title
from config.settings import RAW_DATA_DIR, THEME
from src.analyst.ai_analyst import AICreditAnalyst
from src.data.io import datasets_exist, load_portfolio
from src.intelligence.anomaly_detection import run_full_anomaly_scan
from src.intelligence.recommendations import generate_prescriptive_recommendations
from src.metrics.portfolio import calculate_executive_kpis


def main() -> None:
    render_header(
        title="AI Credit Analyst",
        subtitle="Conversational credit risk intelligence: ask natural-language questions and receive evidence-grounded insights.",
        eyebrow="Intelligence",
    )

    if not datasets_exist(RAW_DATA_DIR):
        st.warning("Data not generated yet. Please run `python -m src.data.pipeline`.")
        render_footer()
        return

    @st.cache_data(show_spinner="Initializing AI Credit Analyst context...")
    def _init_analyst():
        p = load_portfolio(RAW_DATA_DIR)
        loans = p.loans
        customers = p.customers
        repayments = p.repayments
        if "customer_segment" not in loans.columns:
            loans = loans.merge(customers[["customer_id", "customer_segment"]], on="customer_id", how="left")
        kpis = calculate_executive_kpis(loans, repayments)
        findings = run_full_anomaly_scan(loans, repayments)
        recommendations = generate_prescriptive_recommendations(findings)
        return p, loans, repayments, kpis, findings, recommendations

    portfolio, loans, repayments, kpis, findings, recommendations = _init_analyst()
    analyst = AICreditAnalyst(kpis, findings, recommendations, loans)

    # ---------------------------------------------------------
    # Analyst Briefing Card
    # ---------------------------------------------------------
    render_section_title("Executive Analyst Briefing")
    st.markdown(
        f"""
        <div class="cp-panel" style="border-left: 4px solid {THEME.accent_teal};">
            <strong style="color: {THEME.primary_navy}; font-size: 1.05rem;">CreditPulse Copilot Ready</strong>
            <p style="font-size: 0.9rem; color: {THEME.text_primary}; margin-top: 4px; line-height: 1.5;">
                I am connected directly to your computed portfolio metrics, anomaly detector, and prescriptive action engine. 
                My answers are <strong>strictly grounded in verified evidence</strong> with zero fabricated values.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---------------------------------------------------------
    # Quick Executive Inquiries
    # ---------------------------------------------------------
    render_section_title("Suggested Executive Questions")
    q_col1, q_col2 = st.columns(2)
    q_col3, q_col4 = st.columns(2)

    quick_query = None
    with q_col1:
        if st.button("📊 Summarize overall portfolio health and risk highlights", use_container_width=True):
            quick_query = "Summarize overall portfolio health and risk highlights"
    with q_col2:
        if st.button("⚠️ What are the top statistical anomalies and root causes?", use_container_width=True):
            quick_query = "What are the top statistical anomalies and root causes?"
    with q_col3:
        if st.button("🏢 Which branches show the highest credit stress?", use_container_width=True):
            quick_query = "Which branches show the highest credit stress?"
    with q_col4:
        if st.button("📋 What are the primary recommended policy actions?", use_container_width=True):
            quick_query = "What are the primary recommended policy actions?"

    # ---------------------------------------------------------
    # Custom Query Input
    # ---------------------------------------------------------
    render_section_title("Ask a Custom Question")
    user_query = st.text_input(
        "Enter your question regarding portfolio risk, DPD buckets, or branch metrics:",
        value=quick_query or "",
        placeholder="e.g. Why is PAR30 elevated in certain segments?",
    )

    if user_query:
        resp = analyst.answer_query(user_query)

        st.write("")
        st.markdown(
            f"""
            <div class="cp-card" style="border-left: 4px solid {THEME.primary_navy}; padding: 1.25rem;">
                <div style="font-size: 0.8rem; font-weight: 700; color: {THEME.accent_teal}; text-transform: uppercase;">AI Analyst Response</div>
                <div style="font-size: 1.15rem; font-weight: 700; color: {THEME.primary_navy}; margin-top: 6px;">
                    {resp.headline_answer}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.write("")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(
                f"""
                <div class="cp-panel" style="height: 100%;">
                    <strong style="color: {THEME.primary_navy};">Detailed Metrics & Observations:</strong>
                    <ul style="font-size: 0.88rem; margin-top: 6px;">
                        {''.join(f'<li>{d}</li>' for d in resp.detailed_findings)}
                    </ul>
                    <div style="font-size: 0.8rem; color: {THEME.text_muted}; margin-top: 8px;">
                        <strong>Evidence Citations:</strong><br>
                        {'<br>'.join(f'&bull; {c}' for c in resp.evidence_citations)}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with c2:
            st.markdown(
                f"""
                <div class="cp-panel" style="height: 100%;">
                    <strong style="color: {THEME.primary_navy};">Prescribed Strategic Actions:</strong>
                    <ul style="font-size: 0.88rem; margin-top: 6px;">
                        {''.join(f'<li>{a}</li>' for a in resp.suggested_actions)}
                    </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )

    render_footer()


if __name__ == "__main__":
    main()
