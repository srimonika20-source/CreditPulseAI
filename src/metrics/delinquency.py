"""
Delinquency Analytics Engine for CreditPulse AI.

Provides deep-dive delinquency analytics:
- DPD bucket distribution (count, outstanding balance, share %)
- Product-wise delinquency
- Branch-wise delinquency
- Monthly PAR trends (PAR30, PAR60, PAR90 historical trajectory)
- First Payment Default (FPD30) rate and cohort breakdown
- Non-Performing Asset (NPA / PAR90) analysis
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.data.schema import DPD_BUCKET_LABELS, STATUS_ACTIVE, assign_dpd_bucket


def dpd_bucket_summary(loans: pd.DataFrame) -> pd.DataFrame:
    """Summarise active portfolio exposure by DPD bucket."""
    active = loans[loans["loan_status"] == STATUS_ACTIVE].copy()
    total_pos = active["outstanding_principal"].sum()
    total_accs = len(active)

    grouped = active.groupby("dpd_bucket")
    res = grouped.agg(
        accounts=("loan_id", "count"),
        outstanding_inr=("outstanding_principal", "sum"),
        avg_balance_inr=("outstanding_principal", "mean"),
    ).reindex(list(DPD_BUCKET_LABELS), fill_value=0)

    res["account_share_%"] = (res["accounts"] / total_accs * 100.0) if total_accs > 0 else 0.0
    res["pos_share_%"] = (res["outstanding_inr"] / total_pos * 100.0) if total_pos > 0 else 0.0

    return res.reset_index()


def segment_delinquency_breakdown(loans: pd.DataFrame, segment_col: str) -> pd.DataFrame:
    """Break down delinquency and PAR metrics across a specified segment/dimension."""
    active = loans[loans["loan_status"] == STATUS_ACTIVE].copy()

    grouped = active.groupby(segment_col)
    res = grouped.agg(
        active_loans=("loan_id", "count"),
        total_pos_inr=("outstanding_principal", "sum"),
    )

    for threshold in (30, 60, 90):
        par_mask = active["dpd"] >= threshold
        par_amt = active[par_mask].groupby(segment_col)["outstanding_principal"].sum()
        res[f"par{threshold}_inr"] = par_amt.reindex(res.index, fill_value=0.0)
        res[f"par{threshold}_%"] = (res[f"par{threshold}_inr"] / res["total_pos_inr"] * 100.0).fillna(0.0)

    return res.reset_index().sort_values("total_pos_inr", ascending=False).reset_index(drop=True)


def calculate_first_payment_default(loans: pd.DataFrame, repayments: pd.DataFrame) -> dict[str, any]:
    """Calculate First Payment Default (FPD 30+ DPD on first scheduled EMI).

    Returns:
        dict containing overall FPD rate, count, and cohort/product breakdown tables.
    """
    # Find the earliest due date for each loan in repayments
    first_repayments = repayments.sort_values(["loan_id", "due_date"]).groupby("loan_id").first().reset_index()
    merged = loans.merge(
        first_repayments[["loan_id", "days_past_due", "payment_status"]],
        on="loan_id",
        how="inner",
    )

    merged["is_fpd30"] = merged["days_past_due"] >= 30
    total_eligible = len(merged)
    fpd_count = int(merged["is_fpd30"].sum())
    fpd_rate = (fpd_count / total_eligible * 100.0) if total_eligible > 0 else 0.0

    # By Product
    prod_fpd = (
        merged.groupby("product_type")
        .agg(
            total_loans=("loan_id", "count"),
            fpd_loans=("is_fpd30", "sum"),
        )
        .reset_index()
    )
    prod_fpd["fpd_rate_%"] = (prod_fpd["fpd_loans"] / prod_fpd["total_loans"] * 100.0).round(2)

    # By Disbursement Month Cohort
    merged["cohort_month"] = pd.to_datetime(merged["disbursement_date"]).dt.to_period("M").dt.to_timestamp()
    cohort_fpd = (
        merged.groupby("cohort_month")
        .agg(
            total_loans=("loan_id", "count"),
            fpd_loans=("is_fpd30", "sum"),
        )
        .reset_index()
    )
    cohort_fpd["fpd_rate_%"] = (cohort_fpd["fpd_loans"] / cohort_fpd["total_loans"] * 100.0).round(2)

    return {
        "overall_rate_%": fpd_rate,
        "fpd_count": fpd_count,
        "total_evaluated": total_eligible,
        "by_product": prod_fpd.sort_values("fpd_rate_%", ascending=False).reset_index(drop=True),
        "by_cohort": cohort_fpd.sort_values("cohort_month").reset_index(drop=True),
    }


def monthly_historical_par_trend(repayments: pd.DataFrame, loans: pd.DataFrame) -> pd.DataFrame:
    """Reconstruct monthly historical delinquency trend from repayment transaction cycles.

    Returns:
        DataFrame with ['month', 'total_due', 'par30_due', 'par90_due', 'delinquency_rate_%']
    """
    df = repayments.copy()
    df["month"] = pd.to_datetime(df["due_date"]).dt.to_period("M").dt.to_timestamp()

    grouped = df.groupby("month")
    res = grouped.agg(
        total_due=("emi_due", "sum"),
        total_paid=("amount_paid", "sum"),
        overdue_due=("emi_due", lambda s: s[df.loc[s.index, "days_past_due"] > 0].sum()),
        par30_due=("emi_due", lambda s: s[df.loc[s.index, "days_past_due"] >= 30].sum()),
        par90_due=("emi_due", lambda s: s[df.loc[s.index, "days_past_due"] >= 90].sum()),
    ).reset_index()

    res["delinquency_rate_%"] = (res["overdue_due"] / res["total_due"] * 100.0).round(2)
    res["par30_rate_%"] = (res["par30_due"] / res["total_due"] * 100.0).round(2)
    res["par90_rate_%"] = (res["par90_due"] / res["total_due"] * 100.0).round(2)

    return res.sort_values("month").reset_index(drop=True)
