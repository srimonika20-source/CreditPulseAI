"""
Roll Rate Analytics Engine for CreditPulse AI.

Provides DPD bucket transition dynamics across monthly cycles:
- Transition Matrix (From Bucket t to Bucket t+1)
- Roll Forward Rate (accounts or balance rolling to worse delinquency)
- Roll Backward / Cure Rate (accounts improving or returning to 0 DPD)
- Flow Rate tracking across consecutive months
"""

from __future__ import annotations

import pandas as pd

from src.data.schema import DPD_BUCKET_LABELS, assign_dpd_bucket


def calculate_transition_matrix(
    repayments: pd.DataFrame,
    from_month: str | pd.Timestamp | None = None,
    to_month: str | pd.Timestamp | None = None,
) -> dict[str, pd.DataFrame]:
    """Calculate bucket-to-bucket transition matrix between two consecutive observation months.

    Returns:
        dict with:
        - 'count_matrix': Loan count transition table
        - 'rate_matrix': Percentage transition matrix (rows sum to 100%)
        - 'roll_forward_rates': Summary of roll forward rate per bucket
        - 'cure_rates': Summary of cure rate per bucket
    """
    df = repayments.copy()
    df["cycle_month"] = pd.to_datetime(df["due_date"]).dt.to_period("M")
    df["bucket"] = assign_dpd_bucket(df["days_past_due"])

    # If months not specified, select the latest two consecutive months available
    unique_months = sorted(df["cycle_month"].unique())
    if len(unique_months) < 2:
        return {}

    if from_month is None or to_month is None:
        m_from = unique_months[-2]
        m_to = unique_months[-1]
    else:
        m_from = pd.Period(from_month, freq="M")
        m_to = pd.Period(to_month, freq="M")

    df_from = df[df["cycle_month"] == m_from][["loan_id", "bucket"]].rename(columns={"bucket": "From_Bucket"})
    df_to = df[df["cycle_month"] == m_to][["loan_id", "bucket"]].rename(columns={"bucket": "To_Bucket"})

    # Merge on loan_id
    transitions = df_from.merge(df_to, on="loan_id", how="inner")

    bucket_order = list(DPD_BUCKET_LABELS)

    # Contingency table
    count_matrix = pd.crosstab(
        transitions["From_Bucket"],
        transitions["To_Bucket"],
        dropna=False,
    ).reindex(index=bucket_order, columns=bucket_order, fill_value=0)

    # Percentage transition matrix
    row_sums = count_matrix.sum(axis=1)
    rate_matrix = count_matrix.div(row_sums, axis=0).fillna(0.0).mul(100.0).round(2)

    # Roll forward definition: transitioning to any bucket strictly higher in order
    roll_forward = {}
    cure_rates = {}
    for i, b_from in enumerate(bucket_order):
        if row_sums[b_from] > 0:
            # rolling forward to higher index
            rf_count = count_matrix.iloc[i, i + 1 :].sum()
            roll_forward[b_from] = round(rf_count / row_sums[b_from] * 100.0, 2)
            # curing back to '0 DPD' (for buckets > 0 DPD)
            if i > 0:
                cure_count = count_matrix.loc[b_from, "0 DPD"]
                cure_rates[b_from] = round(cure_count / row_sums[b_from] * 100.0, 2)
            else:
                cure_rates[b_from] = 100.0
        else:
            roll_forward[b_from] = 0.0
            cure_rates[b_from] = 0.0

    return {
        "from_month": str(m_from),
        "to_month": str(m_to),
        "count_matrix": count_matrix,
        "rate_matrix": rate_matrix,
        "roll_forward_rates": pd.Series(roll_forward, name="Roll_Forward_%"),
        "cure_rates": pd.Series(cure_rates, name="Cure_Rate_%"),
    }
