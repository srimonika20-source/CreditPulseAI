"""
Vintage Analysis Dashboard.

Month-on-Book (MOB) performance tracking:
- Vintage Delinquency Curves (MOB 1 to 36)
- Heatmap / Matrix view of Vintage Degradation
- Cohort comparison across origination quarters
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from components.layout import render_footer, render_header, render_section_title
from config.settings import RAW_DATA_DIR, THEME
from src.data.io import datasets_exist, load_portfolio
from src.metrics.vintage import compare_cohort_vintage_curves, generate_mob_matrix


def main() -> None:
    render_header(
        title="Vintage Analysis",
        subtitle="Tracking credit deterioration by cohort and Month-on-Book (MOB) to evaluate underwriting quality across cycles.",
        eyebrow="Portfolio Analytics",
    )

    if not datasets_exist(RAW_DATA_DIR):
        st.warning("Data not generated yet. Please run `python -m src.data.pipeline`.")
        render_footer()
        return

    @st.cache_data(show_spinner="Computing vintage curves...")
    def _load():
        return load_portfolio(RAW_DATA_DIR)

    portfolio = _load()
    loans = portfolio.loans
    repayments = portfolio.repayments

    # Controls
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1:
        threshold = st.selectbox("Delinquency Threshold", [30, 60, 90], index=0, format_func=lambda x: f"{x}+ DPD")
    with f_col2:
        freq = st.selectbox("Cohort Granularity", ["Quarterly (Q)", "Monthly (M)"], index=0)
        freq_code = "Q" if "Quarterly" in freq else "M"
    with f_col3:
        products = ["All Products"] + sorted(loans["product_type"].unique().tolist())
        selected_prod = st.selectbox("Product Filter", products)

    # Filter by product if selected
    if selected_prod != "All Products":
        target_loans = loans[loans["product_type"] == selected_prod]
        loan_ids = set(target_loans["loan_id"])
        target_repayments = repayments[repayments["loan_id"].isin(loan_ids)]
    else:
        target_loans = loans
        target_repayments = repayments

    mob_matrix = generate_mob_matrix(target_loans, target_repayments, dpd_threshold=threshold, cohort_freq=freq_code)

    # ---------------------------------------------------------
    # Vintage Curves (Plotly)
    # ---------------------------------------------------------
    render_section_title(f"Vintage Delinquency Curves ({threshold}+ DPD % by MOB)")
    tidy_curves = compare_cohort_vintage_curves(mob_matrix)

    if not tidy_curves.empty:
        fig_curves = px.line(
            tidy_curves,
            x="MOB_num",
            y="Delinquency_%",
            color="cohort",
            markers=True,
            title="",
        )
        fig_curves.update_layout(
            paper_bgcolor="white",
            plot_bgcolor=THEME.secondary_background,
            margin=dict(l=10, r=10, t=10, b=10),
            height=380,
            xaxis=dict(showgrid=True, gridcolor=THEME.border, title="Month on Book (MOB)"),
            yaxis=dict(showgrid=True, gridcolor=THEME.border, title=f"Cumulative {threshold}+ DPD (%)"),
            legend=dict(title="Cohort", orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig_curves, use_container_width=True)

    # ---------------------------------------------------------
    # Vintage Heatmap Matrix
    # ---------------------------------------------------------
    render_section_title("Month-On-Book (MOB) Matrix Table")
    st.markdown(
        f"Shows the cumulative percentage of accounts in each disbursement cohort that have ever breached the **{threshold}+ DPD** threshold by each Month-on-Book."
    )

    if not mob_matrix.empty:
        # Format table
        display_matrix = mob_matrix.copy()
        formatted_matrix = display_matrix.map(lambda v: f"{v:.2f}%" if pd.notnull(v) else "-")
        st.dataframe(formatted_matrix, use_container_width=True)

    render_footer()


if __name__ == "__main__":
    main()
