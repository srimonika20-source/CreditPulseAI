"""
Portfolio Metrics Engine for CreditPulse AI.

Pure Python & pandas analytics engine (no UI dependencies).
Calculates headline KPIs and breakdowns from the loan and repayment datasets:
- Total disbursement
- Outstanding portfolio (POS)
- Active loan accounts
- Average ticket size
- Portfolio at Risk (PAR30, PAR60, PAR90)
- Collection efficiency
- Monthly disbursement trends
- Product-wise portfolio distribution
- Branch-level portfolio performance
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from src.data.schema import STATUS_ACTIVE, STATUS_CLOSED, PortfolioData


@dataclass(frozen=True)
class ExecutiveKPIs:
    """Headline executive portfolio KPIs at a given reporting date."""

    total_disbursement: float
    total_loans: int
    outstanding_portfolio: float
    active_loans: int
    closed_loans: int
    average_ticket_size: float
    weighted_avg_interest_rate: float
    par30_amount: float
    par30_pct: float
    par60_amount: float
    par60_pct: float
    par90_amount: float
    par90_pct: float
    collection_efficiency_pct: float
    total_due_inr: float
    total_collected_inr: float


def calculate_executive_kpis(
    loans: pd.DataFrame,
    repayments: pd.DataFrame,
    as_of: date | None = None,
) -> ExecutiveKPIs:
    """Calculate aggregate headline KPIs for the portfolio.

    Args:
        loans: Loan master DataFrame.
        repayments: Repayment transactions DataFrame.
        as_of: Optional cutoff date. If omitted, uses current dataset state.

    Returns:
        ExecutiveKPIs dataclass instance with calculated metrics.
    """
    if loans.empty:
        return ExecutiveKPIs(
            total_disbursement=0.0,
            total_loans=0,
            outstanding_portfolio=0.0,
            active_loans=0,
            closed_loans=0,
            average_ticket_size=0.0,
            weighted_avg_interest_rate=0.0,
            par30_amount=0.0,
            par30_pct=0.0,
            par60_amount=0.0,
            par60_pct=0.0,
            par90_amount=0.0,
            par90_pct=0.0,
            collection_efficiency_pct=0.0,
            total_due_inr=0.0,
            total_collected_inr=0.0,
        )

    # Filter by date if specified
    if as_of is not None:
        as_of_ts = pd.Timestamp(as_of)
        l_df = loans[loans["disbursement_date"] <= as_of_ts]
        r_df = repayments[repayments["due_date"] <= as_of_ts]
    else:
        l_df = loans
        r_df = repayments

    total_disb = float(l_df["loan_amount"].sum())
    total_count = int(len(l_df))
    avg_ticket = total_disb / total_count if total_count > 0 else 0.0

    active_mask = l_df["loan_status"] == STATUS_ACTIVE
    active_df = l_df[active_mask]
    active_count = int(len(active_df))
    closed_count = int(len(l_df[l_df["loan_status"] == STATUS_CLOSED]))

    total_pos = float(active_df["outstanding_principal"].sum())

    # Weighted average interest rate on active portfolio
    if total_pos > 0:
        w_rate = float((active_df["interest_rate"] * active_df["outstanding_principal"]).sum() / total_pos)
    else:
        w_rate = float(l_df["interest_rate"].mean()) if not l_df.empty else 0.0

    # PAR calculations: POS of loans with DPD >= threshold / Total POS
    def _par(threshold: int) -> tuple[float, float]:
        if total_pos <= 0:
            return 0.0, 0.0
        amount = float(active_df.loc[active_df["dpd"] >= threshold, "outstanding_principal"].sum())
        pct = (amount / total_pos) * 100.0
        return amount, pct

    par30_amt, par30_pct = _par(30)
    par60_amt, par60_pct = _par(60)
    par90_amt, par90_pct = _par(90)

    # Collection efficiency = Amount Collected / Amount Due
    if not r_df.empty:
        tot_due = float(r_df["emi_due"].sum())
        tot_coll = float(r_df["amount_paid"].sum())
        coll_eff = (tot_coll / tot_due * 100.0) if tot_due > 0 else 0.0
    else:
        tot_due, tot_coll, coll_eff = 0.0, 0.0, 0.0

    return ExecutiveKPIs(
        total_disbursement=total_disb,
        total_loans=total_count,
        outstanding_portfolio=total_pos,
        active_loans=active_count,
        closed_loans=closed_count,
        average_ticket_size=avg_ticket,
        weighted_avg_interest_rate=w_rate,
        par30_amount=par30_amt,
        par30_pct=par30_pct,
        par60_amount=par60_amt,
        par60_pct=par60_pct,
        par90_amount=par90_amt,
        par90_pct=par90_pct,
        collection_efficiency_pct=coll_eff,
        total_due_inr=tot_due,
        total_collected_inr=tot_coll,
    )


def monthly_disbursement_trend(loans: pd.DataFrame) -> pd.DataFrame:
    """Aggregate monthly disbursement volumes and average loan sizes.

    Returns:
        DataFrame with columns: ['month', 'disbursement_amount', 'loan_count', 'avg_ticket']
    """
    df = loans.copy()
    df["month"] = pd.to_datetime(df["disbursement_date"]).dt.to_period("M").dt.to_timestamp()
    trend = (
        df.groupby("month")
        .agg(
            disbursement_amount=("loan_amount", "sum"),
            loan_count=("loan_id", "count"),
        )
        .reset_index()
    )
    trend["avg_ticket"] = trend["disbursement_amount"] / trend["loan_count"]
    return trend.sort_values("month").reset_index(drop=True)


def monthly_collection_trend(repayments: pd.DataFrame) -> pd.DataFrame:
    """Aggregate monthly due vs collected amounts and collection efficiency.

    Returns:
        DataFrame with columns: ['month', 'amount_due', 'amount_paid', 'collection_efficiency_%']
    """
    df = repayments.copy()
    df["month"] = pd.to_datetime(df["due_date"]).dt.to_period("M").dt.to_timestamp()
    trend = (
        df.groupby("month")
        .agg(
            amount_due=("emi_due", "sum"),
            amount_paid=("amount_paid", "sum"),
        )
        .reset_index()
    )
    trend["collection_efficiency_%"] = (trend["amount_paid"] / trend["amount_due"] * 100.0).round(2)
    return trend.sort_values("month").reset_index(drop=True)


def product_portfolio_distribution(loans: pd.DataFrame) -> pd.DataFrame:
    """Calculate portfolio mix by product type: disbursement, POS, active count, and PAR30."""
    active_df = loans[loans["loan_status"] == STATUS_ACTIVE]
    total_pos = active_df["outstanding_principal"].sum()

    grouped = loans.groupby("product_type")
    res = grouped.agg(
        total_loans=("loan_id", "count"),
        disbursed_inr=("loan_amount", "sum"),
        avg_rate_pct=("interest_rate", "mean"),
    )

    # Active POS and PAR30 by product
    active_grouped = active_df.groupby("product_type")
    res["outstanding_inr"] = active_grouped["outstanding_principal"].sum().fillna(0.0)
    res["active_loans"] = active_grouped["loan_id"].count().fillna(0)
    
    par30_active = active_df[active_df["dpd"] >= 30].groupby("product_type")["outstanding_principal"].sum()
    res["par30_inr"] = par30_active.reindex(res.index, fill_value=0.0)
    
    res["pos_share_%"] = (res["outstanding_inr"] / total_pos * 100.0) if total_pos > 0 else 0.0
    res["par30_%"] = (res["par30_inr"] / res["outstanding_inr"] * 100.0).fillna(0.0)

    return res.reset_index()


def branch_portfolio_performance(loans: pd.DataFrame) -> pd.DataFrame:
    """Calculate portfolio performance at branch level.

    Returns:
        DataFrame with columns:
        ['branch_id', 'branch_name', 'total_loans', 'active_loans', 'disbursed_inr',
         'outstanding_inr', 'pos_share_%', 'par30_inr', 'par30_%', 'par90_%']
    """
    active_df = loans[loans["loan_status"] == STATUS_ACTIVE]
    total_pos = active_df["outstanding_principal"].sum()

    grouped = loans.groupby(["branch_id", "branch_name"])
    res = grouped.agg(
        total_loans=("loan_id", "count"),
        disbursed_inr=("loan_amount", "sum"),
    )

    active_grouped = active_df.groupby(["branch_id", "branch_name"])
    res["outstanding_inr"] = active_grouped["outstanding_principal"].sum().fillna(0.0)
    res["active_loans"] = active_grouped["loan_id"].count().fillna(0)

    par30_active = active_df[active_df["dpd"] >= 30].groupby(["branch_id", "branch_name"])["outstanding_principal"].sum()
    par90_active = active_df[active_df["dpd"] >= 90].groupby(["branch_id", "branch_name"])["outstanding_principal"].sum()

    res["par30_inr"] = par30_active.reindex(res.index, fill_value=0.0)
    res["par90_inr"] = par90_active.reindex(res.index, fill_value=0.0)

    res["pos_share_%"] = (res["outstanding_inr"] / total_pos * 100.0) if total_pos > 0 else 0.0
    res["par30_%"] = (res["par30_inr"] / res["outstanding_inr"] * 100.0).fillna(0.0)
    res["par90_%"] = (res["par90_inr"] / res["outstanding_inr"] * 100.0).fillna(0.0)

    return res.reset_index().sort_values("outstanding_inr", ascending=False).reset_index(drop=True)
