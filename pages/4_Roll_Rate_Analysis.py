"""
Roll Rate Analysis Dashboard.

Analysis of DPD bucket transitions month-over-month:
- Transition Matrix between consecutive monthly cycles
- Roll Forward Rate (slippage to higher DPD buckets)
- Cure Rate (recovery back to 0 DPD / Current)
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from components.layout import render_footer, render_header, render_section_title
from config.settings import RAW_DATA_DIR, THEME
from src.data.io import datasets_exist, load_portfolio
from src.metrics.roll_rate import calculate_transition_matrix


def main() -> None:
    render_header(
        title="Roll Rate Analysis",
        subtitle="Tracking migration dynamics between delinquency buckets to observe cure rates and worsening flow rates.",
        eyebrow="Portfolio Analytics",
    )

    if not datasets_exist(RAW_DATA_DIR):
        st.warning("Data not generated yet. Please run `python -m src.data.pipeline`.")
        render_footer()
        return

    @st.cache_data(show_spinner="Computing roll rate transitions...")
    def _load():
        return load_portfolio(RAW_DATA_DIR)

    portfolio = _load()
    repayments = portfolio.repayments

    # Available months in repayments
    all_months = sorted(repayments["due_date"].dt.to_period("M").unique().astype(str).tolist())
    if len(all_months) < 2:
        st.info("Insufficient monthly history for transition calculation.")
        render_footer()
        return

    col1, col2 = st.columns(2)
    with col1:
        from_m = st.selectbox("Base Month (t)", all_months[:-1], index=len(all_months) - 2)
    with col2:
        idx_to = all_months.index(from_m) + 1 if (all_months.index(from_m) + 1) < len(all_months) else len(all_months) - 1
        to_m = st.selectbox("Comparison Month (t+1)", all_months[1:], index=idx_to - 1)

    trans_data = calculate_transition_matrix(repayments, from_month=from_m, to_month=to_m)
    if not trans_data:
        st.warning("Could not calculate transitions for selected months.")
        render_footer()
        return

    # ---------------------------------------------------------
    # Transition Rates Matrix Table
    # ---------------------------------------------------------
    render_section_title(f"Bucket Transition Probability Matrix ({from_m} → {to_m})")
    st.markdown("Rows represent the **originating DPD bucket** at time *t*; columns represent where those accounts moved at time *t+1*.")

    rate_matrix = trans_data["rate_matrix"]
    formatted_rate = rate_matrix.map(lambda v: f"{v:.2f}%" if pd.notnull(v) else "-")
    st.dataframe(formatted_rate, use_container_width=True)

    # ---------------------------------------------------------
    # Roll Forward & Cure Rates Bar Charts
    # ---------------------------------------------------------
    render_section_title("Roll Forward & Cure Rates by Bucket")
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("**Roll Forward Rate (%)** *(Accounts rolling into deeper arrears)*")
        rf_df = trans_data["roll_forward_rates"].reset_index()
        rf_df.columns = ["Bucket", "Roll_Forward_%"]
        # Exclude 90+ DPD (cannot roll forward past terminal bucket)
        rf_df = rf_df[rf_df["Bucket"] != "90+ DPD"]
        fig_rf = px.bar(
            rf_df,
            x="Bucket",
            y="Roll_Forward_%",
            text="Roll_Forward_%",
            color_discrete_sequence=[THEME.danger],
        )
        fig_rf.update_traces(texttemplate="%{y:.2f}%", textposition="outside")
        fig_rf.update_layout(
            paper_bgcolor="white",
            plot_bgcolor=THEME.secondary_background,
            margin=dict(l=10, r=10, t=10, b=10),
            height=280,
            xaxis_title="",
            yaxis_title="Roll Forward Rate (%)",
        )
        st.plotly_chart(fig_rf, use_container_width=True)

    with c2:
        st.markdown("**Cure Rate (%)** *(Delinquent accounts curing back to 0 DPD)*")
        cure_df = trans_data["cure_rates"].reset_index()
        cure_df.columns = ["Bucket", "Cure_Rate_%"]
        # Only show delinquent buckets
        cure_df = cure_df[cure_df["Bucket"] != "0 DPD"]
        fig_cure = px.bar(
            cure_df,
            x="Bucket",
            y="Cure_Rate_%",
            text="Cure_Rate_%",
            color_discrete_sequence=[THEME.success],
        )
        fig_cure.update_traces(texttemplate="%{y:.2f}%", textposition="outside")
        fig_cure.update_layout(
            paper_bgcolor="white",
            plot_bgcolor=THEME.secondary_background,
            margin=dict(l=10, r=10, t=10, b=10),
            height=280,
            xaxis_title="",
            yaxis_title="Cure Rate (%)",
        )
        st.plotly_chart(fig_cure, use_container_width=True)

    # ---------------------------------------------------------
    # Transition Counts
    # ---------------------------------------------------------
    with st.expander("View Raw Loan Transition Counts"):
        st.dataframe(trans_data["count_matrix"], use_container_width=True)

    render_footer()


if __name__ == "__main__":
    main()
