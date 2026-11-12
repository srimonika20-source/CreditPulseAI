"""
Executive Portfolio Overview page.

Interactive executive dashboard for banks, NBFCs, and credit risk heads.
Features:
- Headline KPI Cards (Total Disbursement, Outstanding POS, Active Accounts, Ticket Size, PAR30/60/90, Collection Efficiency)
- Global Filters (Product, Branch, Customer Segment)
- Monthly Disbursement & Volume Trend Chart
- Monthly Collection Efficiency Chart
- Product-Wise Portfolio Breakdown & Risk Profile
- Branch-Level Performance Table
"""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from components.layout import render_footer, render_header, render_section_title
from config.settings import RAW_DATA_DIR, THEME
from src.data.io import datasets_exist, load_portfolio
from src.metrics.portfolio import (
    branch_portfolio_performance,
    calculate_executive_kpis,
    monthly_collection_trend,
    monthly_disbursement_trend,
    product_portfolio_distribution,
)
from src.utils.formatting import format_indian_number, format_inr, format_percent


def render_kpi_card(
    title: str,
    value: str,
    subtitle: str = "",
    badge_color: str | None = None,
    badge_text: str | None = None,
) -> None:
    """Render a clean white enterprise KPI card."""
    badge_html = (
        f'<span style="background-color: {badge_color or THEME.secondary_background}; '
        f'color: {THEME.primary_navy}; font-size: 0.72rem; font-weight: 600; '
        f'padding: 2px 8px; border-radius: 999px; margin-left: 6px;">{badge_text}</span>'
        if badge_text
        else ""
    )
    subtitle_html = (
        f'<div style="color: {THEME.text_muted}; font-size: 0.8rem; margin-top: 4px;">{subtitle}</div>'
        if subtitle
        else ""
    )
    st.markdown(
        f"""
        <div class="cp-card" style="padding: 1.1rem 1.25rem;">
            <div style="color: {THEME.text_muted}; font-size: 0.82rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em;">
                {title} {badge_html}
            </div>
            <div style="color: {THEME.primary_navy}; font-size: 1.8rem; font-weight: 700; margin-top: 6px; line-height: 1.1;">
                {value}
            </div>
            {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    render_header(
        title="Executive Portfolio Overview",
        subtitle="High-level lending portfolio performance, liquidity exposure, asset quality, and branch-level metrics.",
        eyebrow="Portfolio Analytics",
    )

    if not datasets_exist(RAW_DATA_DIR):
        st.warning(
            "Portfolio datasets not found in `data/raw`. Please run the synthetic data generator first:\n"
            "`python -m src.data.pipeline`"
        )
        render_footer()
        return

    # Load data
    @st.cache_data(show_spinner="Loading portfolio...")
    def _get_data():
        return load_portfolio(RAW_DATA_DIR)

    portfolio = _get_data()
    loans_df = portfolio.loans
    repayments_df = portfolio.repayments
    customers_df = portfolio.customers

    # Merge customer segment for filtering
    if "customer_segment" not in loans_df.columns:
        loans_df = loans_df.merge(customers_df[["customer_id", "customer_segment"]], on="customer_id", how="left")

    # ---------------------------------------------------------
    # Filters Section
    # ---------------------------------------------------------
    with st.expander("Filter Portfolio", expanded=False):
        f_col1, f_col2, f_col3 = st.columns(3)
        with f_col1:
            products = ["All Products"] + sorted(loans_df["product_type"].unique().tolist())
            selected_product = st.selectbox("Product", products)
        with f_col2:
            branches = ["All Branches"] + sorted(loans_df["branch_name"].unique().tolist())
            selected_branch = st.selectbox("Branch", branches)
        with f_col3:
            segments = ["All Segments"] + sorted(loans_df["customer_segment"].dropna().unique().tolist())
            selected_segment = st.selectbox("Customer Segment", segments)

    # Apply filters
    filtered_loans = loans_df.copy()
    if selected_product != "All Products":
        filtered_loans = filtered_loans[filtered_loans["product_type"] == selected_product]
    if selected_branch != "All Branches":
        filtered_loans = filtered_loans[filtered_loans["branch_name"] == selected_branch]
    if selected_segment != "All Segments":
        filtered_loans = filtered_loans[filtered_loans["customer_segment"] == selected_segment]

    filtered_loan_ids = set(filtered_loans["loan_id"])
    filtered_repayments = repayments_df[repayments_df["loan_id"].isin(filtered_loan_ids)]

    # Calculate KPIs
    kpis = calculate_executive_kpis(filtered_loans, filtered_repayments)

    # ---------------------------------------------------------
    # Headline KPI Cards
    # ---------------------------------------------------------
    render_section_title("Key Performance Indicators", f"As of {portfolio.reporting_date.strftime('%d %B %Y')}")

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        render_kpi_card(
            "Total Disbursed",
            format_inr(kpis.total_disbursement),
            subtitle=f"{format_indian_number(kpis.total_loans)} total loans originated",
        )
    with k2:
        render_kpi_card(
            "Outstanding Portfolio (POS)",
            format_inr(kpis.outstanding_portfolio),
            subtitle=f"{format_indian_number(kpis.active_loans)} active loans ({kpis.closed_loans:,} closed)",
        )
    with k3:
        render_kpi_card(
            "Average Ticket Size",
            format_inr(kpis.average_ticket_size, compact=False),
            subtitle=f"Avg Interest Rate: {kpis.weighted_avg_interest_rate:.2f}%",
        )
    with k4:
        render_kpi_card(
            "Collection Efficiency",
            f"{kpis.collection_efficiency_pct:.2f}%",
            subtitle=f"{format_inr(kpis.total_collected_inr)} collected of {format_inr(kpis.total_due_inr)} due",
        )

    st.write("")
    # Asset Quality / Delinquency Row
    q1, q2, q3, q4 = st.columns(4)
    with q1:
        render_kpi_card(
            "PAR 30 (30+ DPD)",
            f"{kpis.par30_pct:.2f}%",
            subtitle=f"{format_inr(kpis.par30_amount)} in risk bucket",
            badge_text="Attention" if kpis.par30_pct > 5 else "Normal",
            badge_color="#FFF3C4" if kpis.par30_pct > 5 else "#E6FFFA",
        )
    with q2:
        render_kpi_card(
            "PAR 60 (60+ DPD)",
            f"{kpis.par60_pct:.2f}%",
            subtitle=f"{format_inr(kpis.par60_amount)} in risk bucket",
        )
    with q3:
        render_kpi_card(
            "PAR 90 (NPA / 90+ DPD)",
            f"{kpis.par90_pct:.2f}%",
            subtitle=f"{format_inr(kpis.par90_amount)} in NPA bucket",
            badge_text="Critical" if kpis.par90_pct > 3 else "Normal",
            badge_color="#FED7D7" if kpis.par90_pct > 3 else "#E6FFFA",
        )
    with q4:
        health_status = "Healthy" if kpis.par90_pct < 4.0 else "Caution"
        render_kpi_card(
            "Asset Health Index",
            health_status,
            subtitle="Based on RBI NPA threshold (< 4.0%)",
            badge_text=health_status,
            badge_color="#E6FFFA" if health_status == "Healthy" else "#FED7D7",
        )

    st.write("")

    # ---------------------------------------------------------
    # Visual Analytics: Trends
    # ---------------------------------------------------------
    render_section_title("Portfolio Growth & Collection Trends")
    t_col1, t_col2 = st.columns(2)

    with t_col1:
        st.markdown("**Monthly Disbursement Volume (₹ Cr)**")
        disb_trend = monthly_disbursement_trend(filtered_loans)
        if not disb_trend.empty:
            disb_trend["disb_cr"] = disb_trend["disbursement_amount"] / 10_000_000.0
            fig_disb = go.Figure()
            fig_disb.add_trace(
                go.Bar(
                    x=disb_trend["month"],
                    y=disb_trend["disb_cr"],
                    name="Disbursed (₹ Cr)",
                    marker_color=THEME.primary_navy,
                )
            )
            fig_disb.update_layout(
                paper_bgcolor="white",
                plot_bgcolor=THEME.secondary_background,
                margin=dict(l=10, r=10, t=10, b=10),
                height=300,
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor=THEME.border, title="Disbursed (₹ Cr)"),
            )
            st.plotly_chart(fig_disb, use_container_width=True)

    with t_col2:
        st.markdown("**Monthly Collection Efficiency (%)**")
        coll_trend = monthly_collection_trend(filtered_repayments)
        if not coll_trend.empty:
            fig_coll = go.Figure()
            fig_coll.add_trace(
                go.Scatter(
                    x=coll_trend["month"],
                    y=coll_trend["collection_efficiency_%"],
                    mode="lines+markers",
                    name="Efficiency %",
                    line=dict(color=THEME.accent_teal, width=2.5),
                    marker=dict(size=5),
                )
            )
            fig_coll.add_hline(y=95.0, line_dash="dot", line_color=THEME.warning, annotation_text="95% Benchmark")
            fig_coll.update_layout(
                paper_bgcolor="white",
                plot_bgcolor=THEME.secondary_background,
                margin=dict(l=10, r=10, t=10, b=10),
                height=300,
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor=THEME.border, range=[80, 102], title="Efficiency %"),
            )
            st.plotly_chart(fig_coll, use_container_width=True)

    # ---------------------------------------------------------
    # Product Distribution Breakdown
    # ---------------------------------------------------------
    render_section_title("Product-Wise Portfolio Distribution")
    p_col1, p_col2 = st.columns([1, 1])

    prod_dist = product_portfolio_distribution(filtered_loans)
    with p_col1:
        st.markdown("**Outstanding Portfolio Share by Product**")
        fig_donut = px.pie(
            prod_dist,
            names="product_type",
            values="outstanding_inr",
            hole=0.55,
            color_discrete_sequence=[THEME.primary_navy, THEME.accent_teal, "#4A5568", "#2F855A", "#CBD5E0"],
        )
        fig_donut.update_layout(
            paper_bgcolor="white",
            margin=dict(l=10, r=10, t=10, b=10),
            height=280,
            showlegend=True,
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    with p_col2:
        st.markdown("**Product Risk & Delinquency Matrix**")
        prod_display = prod_dist.copy()
        prod_display["Total POS"] = prod_display["outstanding_inr"].apply(lambda v: format_inr(v, compact=True))
        prod_display["Active Loans"] = prod_display["active_loans"].apply(lambda v: f"{int(v):,}")
        prod_display["Avg Rate"] = prod_display["avg_rate_pct"].apply(lambda v: f"{v:.2f}%")
        prod_display["PAR 30 %"] = prod_display["par30_%"].apply(lambda v: f"{v:.2f}%")
        prod_display = prod_display[["product_type", "Total POS", "Active Loans", "Avg Rate", "PAR 30 %"]]
        prod_display = prod_display.rename(columns={"product_type": "Product"})
        st.dataframe(prod_display, hide_index=True, use_container_width=True)

    # ---------------------------------------------------------
    # Branch-Level Portfolio Performance Table
    # ---------------------------------------------------------
    render_section_title("Branch Performance & Quality Summary")
    branch_df = branch_portfolio_performance(filtered_loans)
    if not branch_df.empty:
        branch_display = branch_df.copy()
        branch_display["Disbursed"] = branch_display["disbursed_inr"].apply(lambda v: format_inr(v, compact=True))
        branch_display["Outstanding POS"] = branch_display["outstanding_inr"].apply(lambda v: format_inr(v, compact=True))
        branch_display["Active Accounts"] = branch_display["active_loans"].apply(lambda v: f"{int(v):,}")
        branch_display["POS Share"] = branch_display["pos_share_%"].apply(lambda v: f"{v:.1f}%")
        branch_display["PAR 30 %"] = branch_display["par30_%"].apply(lambda v: f"{v:.2f}%")
        branch_display["PAR 90 %"] = branch_display["par90_%"].apply(lambda v: f"{v:.2f}%")
        branch_display = branch_display[
            ["branch_id", "branch_name", "Active Accounts", "Disbursed", "Outstanding POS", "POS Share", "PAR 30 %", "PAR 90 %"]
        ]
        branch_display = branch_display.rename(
            columns={
                "branch_id": "Branch ID",
                "branch_name": "Branch Name",
            }
        )
        st.dataframe(branch_display, hide_index=True, use_container_width=True)

    render_footer()


if __name__ == "__main__":
    main()
