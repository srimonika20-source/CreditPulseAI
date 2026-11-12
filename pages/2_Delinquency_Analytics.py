"""
Delinquency Analytics Dashboard.

Deep-dive into portfolio delinquency:
- DPD Bucket Distribution (Count, POS, Share)
- Historical Delinquency & PAR Trends
- Product and Branch Delinquency Risk Matrix
- First Payment Default (FPD) Analysis
"""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from components.layout import render_footer, render_header, render_section_title
from config.settings import RAW_DATA_DIR, THEME
from src.data.io import datasets_exist, load_portfolio
from src.metrics.delinquency import (
    calculate_first_payment_default,
    dpd_bucket_summary,
    monthly_historical_par_trend,
    segment_delinquency_breakdown,
)
from src.utils.formatting import format_inr


def main() -> None:
    render_header(
        title="Delinquency Analytics",
        subtitle="Granular analysis of payment slippages, DPD buckets, historical PAR evolution, and early-warning FPD defaults.",
        eyebrow="Portfolio Analytics",
    )

    if not datasets_exist(RAW_DATA_DIR):
        st.warning("Data not generated yet. Please run `python -m src.data.pipeline`.")
        render_footer()
        return

    @st.cache_data(show_spinner="Loading delinquency data...")
    def _load():
        return load_portfolio(RAW_DATA_DIR)

    portfolio = _load()
    loans = portfolio.loans
    repayments = portfolio.repayments

    # ---------------------------------------------------------
    # DPD Bucket Distribution
    # ---------------------------------------------------------
    render_section_title("DPD Bucket Exposure Distribution")
    dpd_df = dpd_bucket_summary(loans)

    c1, c2 = st.columns([1, 1])
    with c1:
        st.markdown("**Outstanding Portfolio by DPD Bucket (₹ Cr)**")
        dpd_df["pos_cr"] = dpd_df["outstanding_inr"] / 10_000_000.0
        fig_bar = px.bar(
            dpd_df,
            x="dpd_bucket",
            y="pos_cr",
            text="pos_cr",
            color="dpd_bucket",
            color_discrete_map={
                "0 DPD": THEME.success,
                "1-30 DPD": THEME.accent_teal,
                "31-60 DPD": "#ECC94B",
                "61-90 DPD": THEME.warning,
                "90+ DPD": THEME.danger,
            },
        )
        fig_bar.update_traces(texttemplate="₹%{y:.1f} Cr", textposition="outside")
        fig_bar.update_layout(
            paper_bgcolor="white",
            plot_bgcolor=THEME.secondary_background,
            margin=dict(l=10, r=10, t=10, b=10),
            height=300,
            showlegend=False,
            xaxis_title="DPD Bucket",
            yaxis_title="Outstanding Balance (₹ Cr)",
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with c2:
        st.markdown("**DPD Bucket Breakdown Table**")
        disp_dpd = dpd_df.copy()
        disp_dpd["Outstanding POS"] = disp_dpd["outstanding_inr"].apply(lambda v: format_inr(v, compact=True))
        disp_dpd["Account Count"] = disp_dpd["accounts"].apply(lambda v: f"{int(v):,}")
        disp_dpd["Account Share"] = disp_dpd["account_share_%"].apply(lambda v: f"{v:.2f}%")
        disp_dpd["POS Share"] = disp_dpd["pos_share_%"].apply(lambda v: f"{v:.2f}%")
        disp_dpd = disp_dpd[["dpd_bucket", "Account Count", "Account Share", "Outstanding POS", "POS Share"]]
        disp_dpd = disp_dpd.rename(columns={"dpd_bucket": "Bucket"})
        st.dataframe(disp_dpd, hide_index=True, use_container_width=True)

    # ---------------------------------------------------------
    # Historical PAR Trajectory
    # ---------------------------------------------------------
    render_section_title("Historical Delinquency & PAR Trend (36 Months)")
    par_trend = monthly_historical_par_trend(repayments, loans)
    if not par_trend.empty:
        fig_par = go.Figure()
        fig_par.add_trace(
            go.Scatter(
                x=par_trend["month"],
                y=par_trend["delinquency_rate_%"],
                name="Overall Delinquency (1+ DPD %)",
                line=dict(color=THEME.primary_navy, width=2.5),
            )
        )
        fig_par.add_trace(
            go.Scatter(
                x=par_trend["month"],
                y=par_trend["par30_rate_%"],
                name="PAR 30 Rate (%)",
                line=dict(color=THEME.warning, width=2, dash="dash"),
            )
        )
        fig_par.add_trace(
            go.Scatter(
                x=par_trend["month"],
                y=par_trend["par90_rate_%"],
                name="PAR 90 / NPA Rate (%)",
                line=dict(color=THEME.danger, width=2, dash="dot"),
            )
        )
        fig_par.update_layout(
            paper_bgcolor="white",
            plot_bgcolor=THEME.secondary_background,
            margin=dict(l=10, r=10, t=10, b=10),
            height=320,
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor=THEME.border, title="Rate %"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig_par, use_container_width=True)

    # ---------------------------------------------------------
    # First Payment Default (FPD)
    # ---------------------------------------------------------
    render_section_title("Early Warning Indicator: First Payment Default (FPD 30)")
    fpd_info = calculate_first_payment_default(loans, repayments)

    k1, k2, k3 = st.columns(3)
    with k1:
        st.metric("Overall FPD 30 Rate", f"{fpd_info['overall_rate_%']:.2f}%")
    with k2:
        st.metric("FPD 30 Loans Count", f"{fpd_info['fpd_count']:,}")
    with k3:
        st.metric("Total Loans Evaluated", f"{fpd_info['total_evaluated']:,}")

    f_col1, f_col2 = st.columns(2)
    with f_col1:
        st.markdown("**FPD 30 Rate by Product Type**")
        fig_prod_fpd = px.bar(
            fpd_info["by_product"],
            x="product_type",
            y="fpd_rate_%",
            text="fpd_rate_%",
            color_discrete_sequence=[THEME.accent_teal],
        )
        fig_prod_fpd.update_traces(texttemplate="%{y:.2f}%", textposition="outside")
        fig_prod_fpd.update_layout(
            paper_bgcolor="white",
            plot_bgcolor=THEME.secondary_background,
            margin=dict(l=10, r=10, t=10, b=10),
            height=280,
            xaxis_title="",
            yaxis_title="FPD 30 Rate (%)",
        )
        st.plotly_chart(fig_prod_fpd, use_container_width=True)

    with f_col2:
        st.markdown("**Disbursement Cohort FPD 30 Trend**")
        fig_cohort_fpd = px.line(
            fpd_info["by_cohort"],
            x="cohort_month",
            y="fpd_rate_%",
            markers=True,
            color_discrete_sequence=[THEME.primary_navy],
        )
        fig_cohort_fpd.update_layout(
            paper_bgcolor="white",
            plot_bgcolor=THEME.secondary_background,
            margin=dict(l=10, r=10, t=10, b=10),
            height=280,
            xaxis_title="",
            yaxis_title="FPD %",
        )
        st.plotly_chart(fig_cohort_fpd, use_container_width=True)

    # ---------------------------------------------------------
    # Product & Branch Delinquency Breakdown
    # ---------------------------------------------------------
    render_section_title("Product & Branch Risk Segmentation")
    tab1, tab2 = st.tabs(["By Product", "By Branch"])
    with tab1:
        prod_delinq = segment_delinquency_breakdown(loans, "product_type")
        prod_delinq["Total POS"] = prod_delinq["total_pos_inr"].apply(lambda v: format_inr(v, compact=True))
        prod_delinq["PAR30 Amt"] = prod_delinq["par30_inr"].apply(lambda v: format_inr(v, compact=True))
        prod_delinq["PAR30 %"] = prod_delinq["par30_%"].apply(lambda v: f"{v:.2f}%")
        prod_delinq["PAR90 %"] = prod_delinq["par90_%"].apply(lambda v: f"{v:.2f}%")
        st.dataframe(
            prod_delinq[["product_type", "active_loans", "Total POS", "PAR30 Amt", "PAR30 %", "PAR90 %"]].rename(
                columns={"product_type": "Product", "active_loans": "Active Loans"}
            ),
            hide_index=True,
            use_container_width=True,
        )

    with tab2:
        branch_delinq = segment_delinquency_breakdown(loans, "branch_name")
        branch_delinq["Total POS"] = branch_delinq["total_pos_inr"].apply(lambda v: format_inr(v, compact=True))
        branch_delinq["PAR30 Amt"] = branch_delinq["par30_inr"].apply(lambda v: format_inr(v, compact=True))
        branch_delinq["PAR30 %"] = branch_delinq["par30_%"].apply(lambda v: f"{v:.2f}%")
        branch_delinq["PAR90 %"] = branch_delinq["par90_%"].apply(lambda v: f"{v:.2f}%")
        st.dataframe(
            branch_delinq[["branch_name", "active_loans", "Total POS", "PAR30 Amt", "PAR30 %", "PAR90 %"]].rename(
                columns={"branch_name": "Branch", "active_loans": "Active Loans"}
            ),
            hide_index=True,
            use_container_width=True,
        )

    render_footer()


if __name__ == "__main__":
    main()
