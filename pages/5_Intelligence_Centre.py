"""
Intelligence Centre Dashboard.

Implements the DETECT, DIAGNOSE, PREDICT, and PRESCRIBE workflow:
- Automated Anomaly Detection Feed
- Risk Alerts categorized by Severity (HIGH / MEDIUM)
- Root-Cause & Mathematical Contribution Analysis
- Short-Horizon Risk Forecasting (PREDICT)
- Evidence-Linked Prescriptive Recommendations (PRESCRIBE)
"""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from components.layout import render_footer, render_header, render_section_title
from config.settings import RAW_DATA_DIR, THEME
from src.data.io import datasets_exist, load_portfolio
from src.intelligence.anomaly_detection import Finding, run_full_anomaly_scan
from src.intelligence.forecasting import forecast_par_trajectory
from src.intelligence.recommendations import generate_prescriptive_recommendations
from src.intelligence.root_cause import decompose_delinquency_contribution
from src.metrics.delinquency import monthly_historical_par_trend
from src.utils.formatting import format_inr


def main() -> None:
    render_header(
        title="Intelligence Centre",
        subtitle="Automated statistical anomaly detection, root cause diagnosis, risk projections, and prescriptive policy actions.",
        eyebrow="Intelligence",
    )

    if not datasets_exist(RAW_DATA_DIR):
        st.warning("Data not generated yet. Please run `python -m src.data.pipeline`.")
        render_footer()
        return

    @st.cache_data(show_spinner="Running portfolio intelligence pipeline...")
    def _run_intelligence():
        p = load_portfolio(RAW_DATA_DIR)
        loans = p.loans
        customers = p.customers
        repayments = p.repayments
        if "customer_segment" not in loans.columns:
            loans = loans.merge(customers[["customer_id", "customer_segment"]], on="customer_id", how="left")
        findings = run_full_anomaly_scan(loans, repayments)
        recommendations = generate_prescriptive_recommendations(findings)
        hist_trend = monthly_historical_par_trend(repayments, loans)
        forecast = forecast_par_trajectory(hist_trend, "par30_rate_%", horizon=3)
        return p, loans, repayments, findings, recommendations, forecast, hist_trend

    portfolio, loans, repayments, findings, recommendations, forecast, hist_trend = _run_intelligence()

    # ---------------------------------------------------------
    # Anomaly Summary Metrics
    # ---------------------------------------------------------
    render_section_title("Intelligence Pipeline Overview", "DETECT → DIAGNOSE → PREDICT → PRESCRIBE")

    high_sev = [f for f in findings if f.severity == "HIGH"]
    med_sev = [f for f in findings if f.severity == "MEDIUM"]

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Detected Anomalies", len(findings))
    with k2:
        st.metric("High Severity Alerts", len(high_sev))
    with k3:
        st.metric("Prescribed Actions", len(recommendations))
    with k4:
        st.metric(f"Projected PAR30 ({forecast.horizon_months}M)", f"{forecast.expected_value:.2f}%", delta=f"{forecast.expected_value - forecast.current_value:+.2f}%")

    st.write("")

    # ---------------------------------------------------------
    # PREDICT: Short-Horizon Risk Forecasting
    # ---------------------------------------------------------
    render_section_title("PREDICT: Short-Horizon Risk Trajectory Projection")
    st.markdown(
        f"**Model Projection:** Anticipated 30+ DPD flow over the next **{forecast.horizon_months} months** with 90% confidence uncertainty intervals."
    )

    fc_col1, fc_col2 = st.columns([3, 2])
    with fc_col1:
        if not hist_trend.empty and not forecast.trajectory_table.empty:
            fig_fc = go.Figure()
            # Historical
            fig_fc.add_trace(
                go.Scatter(
                    x=hist_trend["month"],
                    y=hist_trend["par30_rate_%"],
                    name="Observed PAR30 %",
                    line=dict(color=THEME.primary_navy, width=2.5),
                )
            )
            # Forecasted trajectory
            fc_table = forecast.trajectory_table
            fig_fc.add_trace(
                go.Scatter(
                    x=fc_table["month"],
                    y=fc_table["expected_%"],
                    name="Projected Expected PAR30 %",
                    line=dict(color=THEME.danger, width=2.5, dash="dash"),
                    marker=dict(size=6),
                )
            )
            # Upper & Lower Confidence Bounds
            fig_fc.add_trace(
                go.Scatter(
                    x=fc_table["month"],
                    y=fc_table["upper_bound_%"],
                    mode="lines",
                    line=dict(width=0),
                    showlegend=False,
                )
            )
            fig_fc.add_trace(
                go.Scatter(
                    x=fc_table["month"],
                    y=fc_table["lower_bound_%"],
                    mode="lines",
                    line=dict(width=0),
                    fill="tonexty",
                    fillcolor="rgba(197, 48, 48, 0.12)",
                    name="90% Uncertainty Interval",
                )
            )
            fig_fc.update_layout(
                paper_bgcolor="white",
                plot_bgcolor=THEME.secondary_background,
                margin=dict(l=10, r=10, t=10, b=10),
                height=300,
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor=THEME.border, title="PAR30 Rate (%)"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            st.plotly_chart(fig_fc, use_container_width=True)

    with fc_col2:
        st.markdown("**Projection Breakdown Table**")
        disp_fc = forecast.trajectory_table.copy()
        disp_fc.columns = ["Month", "Horizon", "Expected %", "Lower Bound %", "Upper Bound %"]
        st.dataframe(disp_fc, hide_index=True, use_container_width=True)
        st.caption(f"Methodology: {forecast.methodology}")

    # ---------------------------------------------------------
    # PRESCRIBE: Actionable Recommendations
    # ---------------------------------------------------------
    render_section_title("PRESCRIBE: Policy & Operational Recommendations")
    st.markdown("Interventions generated from calculated metrics and verified empirical findings:")

    for rec in recommendations:
        priority_color = THEME.danger if "P1" in rec.priority else THEME.accent_teal
        priority_bg = "#FED7D7" if "P1" in rec.priority else "#E6FFFA"
        st.markdown(
            f"""
            <div class="cp-card" style="margin-bottom: 0.95rem; border-left: 4px solid {priority_color};">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-size: 0.8rem; font-weight: 700; color: {THEME.text_muted};">{rec.rec_id} &bull; {rec.pillar.upper()}</span>
                    <span style="background-color: {priority_bg}; color: {priority_color}; font-size: 0.72rem; font-weight: 700; padding: 2px 8px; border-radius: 999px;">{rec.priority}</span>
                </div>
                <div style="font-size: 1.05rem; font-weight: 700; color: {THEME.primary_navy}; margin-top: 4px;">{rec.title}</div>
                <div style="font-size: 0.9rem; color: {THEME.text_primary}; margin-top: 6px;">
                    <strong>Prescribed Action:</strong> {rec.action_summary}
                </div>
                <div style="font-size: 0.84rem; color: {THEME.text_muted}; margin-top: 4px;">
                    <strong>Evidence Citation:</strong> {rec.evidence_citation}
                </div>
                <div style="display: flex; justify-content: space-between; margin-top: 8px; padding-top: 6px; border-top: 1px solid {THEME.border}; font-size: 0.8rem; color: {THEME.text_muted};">
                    <span><strong>Impact:</strong> {rec.expected_impact}</span>
                    <span><strong>Owner:</strong> {rec.suggested_owner} ({rec.implementation_timeframe})</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ---------------------------------------------------------
    # DIAGNOSE: Root-Cause Contribution Studio
    # ---------------------------------------------------------
    render_section_title("DIAGNOSE: Root-Cause Contribution Studio")
    finding_map = {f"{f.finding_id}: {f.title}": f for f in findings}
    if finding_map:
        selected_key = st.selectbox("Select Anomaly to Diagnose", list(finding_map.keys()))
        selected_finding = finding_map[selected_key]

        d_col1, d_col2 = st.columns([1, 1])
        diagnosis = decompose_delinquency_contribution(loans, selected_finding, secondary_col="customer_segment")

        with d_col1:
            st.markdown(f"**Decomposition by Customer Segment ({selected_finding.dimension_value})**")
            decomp_table = diagnosis.decomposition_table.copy()
            decomp_table["Total POS"] = decomp_table["total_pos_inr"].apply(lambda v: format_inr(v, compact=True))
            decomp_table["PAR30 Amt"] = decomp_table["par30_inr"].apply(lambda v: format_inr(v, compact=True))
            decomp_table["PAR30 %"] = decomp_table["par30_%"].apply(lambda v: f"{v:.2f}%")
            decomp_table["Contribution %"] = decomp_table["contribution_share_%"].apply(lambda v: f"{v:.1f}%")

            st.dataframe(
                decomp_table[["customer_segment", "active_loans", "Total POS", "PAR30 Amt", "PAR30 %", "Contribution %"]].rename(
                    columns={"customer_segment": "Segment", "active_loans": "Accounts"}
                ),
                hide_index=True,
                use_container_width=True,
            )

        with d_col2:
            st.markdown("**Delinquency Contribution Share (%)**")
            fig_share = px.pie(
                diagnosis.decomposition_table,
                names="customer_segment",
                values="par30_inr",
                hole=0.45,
                color_discrete_sequence=[THEME.primary_navy, THEME.accent_teal, "#E53E3E", "#DD6B20", "#718096"],
            )
            fig_share.update_layout(
                paper_bgcolor="white",
                margin=dict(l=10, r=10, t=10, b=10),
                height=260,
                showlegend=True,
            )
            st.plotly_chart(fig_share, use_container_width=True)

        fact_col, hyp_col = st.columns(2)
        with fact_col:
            st.markdown(
                f"""
                <div class="cp-panel" style="border-left: 3px solid {THEME.success};">
                    <strong style="color: {THEME.primary_navy};">Verified Empirical Findings (Facts):</strong>
                    <ul style="margin-top: 6px; font-size: 0.85rem; padding-left: 1.2rem;">
                        {''.join(f'<li>{fact}</li>' for fact in diagnosis.observed_facts)}
                    </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with hyp_col:
            st.markdown(
                f"""
                <div class="cp-panel" style="border-left: 3px solid {THEME.accent_teal};">
                    <strong style="color: {THEME.primary_navy};">Potential Explanations (Hypotheses):</strong>
                    <ul style="margin-top: 6px; font-size: 0.85rem; padding-left: 1.2rem;">
                        {''.join(f'<li>{hyp}</li>' for hyp in diagnosis.hypotheses)}
                    </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )

    render_footer()


if __name__ == "__main__":
    main()
