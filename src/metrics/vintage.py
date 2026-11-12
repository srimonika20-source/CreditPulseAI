"""
Vintage (Cohort) Analysis Engine for CreditPulse AI.

Provides Month-on-Book (MOB) performance tracking:
- MOB Delinquency Matrix (Vintage matrix tracking cumulative or point-in-time default % across MOB 1..36)
- Vintage Delinquency Curves for visual cohort degradation tracking
- Cohort comparison across disbursement quarters or vintage years
- Vintage First Payment Default analysis
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def generate_mob_matrix(
    loans: pd.DataFrame,
    repayments: pd.DataFrame,
    dpd_threshold: int = 30,
    cohort_freq: str = "Q",  # 'M' for monthly or 'Q' for quarterly cohorts
) -> pd.DataFrame:
    """Generate Month-on-Book (MOB) Delinquency Matrix.

    Calculates the percentage of accounts reaching >= dpd_threshold at each MOB.

    Args:
        loans: Loan master dataframe.
        repayments: Repayments transaction dataframe.
        dpd_threshold: DPD cutoff (e.g. 30 for 30+ DPD vintage).
        cohort_freq: 'Q' for quarterly cohorts (e.g., 2024Q1) or 'M' for monthly cohorts.

    Returns:
        DataFrame indexed by Cohort with columns MOB 1, MOB 2, ... MOB n.
    """
    merged = repayments.merge(
        loans[["loan_id", "disbursement_date"]],
        on="loan_id",
        how="inner",
    )

    merged["disb_dt"] = pd.to_datetime(merged["disbursement_date"])
    merged["due_dt"] = pd.to_datetime(merged["due_date"])

    # Calculate exact Month-On-Book (MOB)
    merged["mob"] = (
        (merged["due_dt"].dt.year - merged["disb_dt"].dt.year) * 12
        + (merged["due_dt"].dt.month - merged["disb_dt"].dt.month)
    )
    # Filter MOB >= 1
    merged = merged[merged["mob"] >= 1].copy()

    # Define cohort period
    if cohort_freq == "Q":
        merged["cohort"] = merged["disb_dt"].dt.to_period("Q").astype(str)
    else:
        merged["cohort"] = merged["disb_dt"].dt.to_period("M").astype(str)

    # Calculate delinquent flag
    merged["is_delinquent"] = merged["days_past_due"] >= dpd_threshold

    # Calculate cohort size at disbursement
    if cohort_freq == "Q":
        loans_cohort = pd.to_datetime(loans["disbursement_date"]).dt.to_period("Q").astype(str)
    else:
        loans_cohort = pd.to_datetime(loans["disbursement_date"]).dt.to_period("M").astype(str)
    
    cohort_sizes = loans_cohort.value_counts().to_dict()

    # Aggregate delinquent loans per cohort and MOB
    mob_agg = (
        merged[merged["is_delinquent"]]
        .groupby(["cohort", "mob"])["loan_id"]
        .nunique()
        .reset_index()
    )

    # Pivot to Matrix
    pivot = mob_agg.pivot(index="cohort", columns="mob", values="loan_id").fillna(0)

    # Convert to percentage of original cohort size
    for cohort in pivot.index:
        size = cohort_sizes.get(cohort, 1)
        pivot.loc[cohort] = (pivot.loc[cohort] / size * 100.0).round(2)

    pivot.columns = [f"MOB {col}" for col in pivot.columns]
    return pivot.sort_index()


def compare_cohort_vintage_curves(mob_matrix: pd.DataFrame) -> pd.DataFrame:
    """Tidy format dataframe of MOB curves ready for Plotly plotting."""
    tidy = mob_matrix.reset_index().melt(id_vars="cohort", var_name="MOB", value_name="Delinquency_%")
    tidy["MOB_num"] = tidy["MOB"].str.replace("MOB ", "").astype(int)
    return tidy.sort_values(["cohort", "MOB_num"]).dropna().reset_index(drop=True)
