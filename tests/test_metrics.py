"""
Tests for Phase 3 Portfolio Metrics Engine.
"""

from __future__ import annotations

import pandas as pd
import pytest

from config.settings import RAW_DATA_DIR
from src.data.io import datasets_exist, load_portfolio
from src.metrics.portfolio import (
    ExecutiveKPIs,
    branch_portfolio_performance,
    calculate_executive_kpis,
    monthly_collection_trend,
    monthly_disbursement_trend,
    product_portfolio_distribution,
)


@pytest.fixture(scope="module")
def sample_portfolio():
    if not datasets_exist(RAW_DATA_DIR):
        pytest.skip("Generated datasets not found in data/raw")
    return load_portfolio(RAW_DATA_DIR)


def test_calculate_executive_kpis(sample_portfolio) -> None:
    kpis = calculate_executive_kpis(sample_portfolio.loans, sample_portfolio.repayments)
    assert isinstance(kpis, ExecutiveKPIs)
    assert kpis.total_loans == 20000
    assert kpis.total_disbursement > 0
    assert kpis.outstanding_portfolio > 0
    assert kpis.active_loans + kpis.closed_loans == 20000
    assert 0 < kpis.collection_efficiency_pct <= 100.0
    assert 0 <= kpis.par30_pct <= 100.0
    assert 0 <= kpis.par60_pct <= kpis.par30_pct
    assert 0 <= kpis.par90_pct <= kpis.par60_pct


def test_empty_loans_kpis() -> None:
    empty_loans = pd.DataFrame()
    empty_repayments = pd.DataFrame()
    kpis = calculate_executive_kpis(empty_loans, empty_repayments)
    assert kpis.total_loans == 0
    assert kpis.total_disbursement == 0.0
    assert kpis.outstanding_portfolio == 0.0


def test_monthly_disbursement_trend(sample_portfolio) -> None:
    trend = monthly_disbursement_trend(sample_portfolio.loans)
    assert not trend.empty
    assert "month" in trend.columns
    assert "disbursement_amount" in trend.columns
    assert "loan_count" in trend.columns
    assert trend["loan_count"].sum() == 20000


def test_monthly_collection_trend(sample_portfolio) -> None:
    trend = monthly_collection_trend(sample_portfolio.repayments)
    assert not trend.empty
    assert "amount_due" in trend.columns
    assert "amount_paid" in trend.columns
    assert "collection_efficiency_%" in trend.columns


def test_product_portfolio_distribution(sample_portfolio) -> None:
    dist = product_portfolio_distribution(sample_portfolio.loans)
    assert len(dist) == 5
    assert set(dist["product_type"]) == {
        "Personal Loan", "Business Loan", "Consumer Durable Loan",
        "Two-Wheeler Loan", "Loan Against Property"
    }
    assert dist["total_loans"].sum() == 20000
    assert pytest.approx(dist["pos_share_%"].sum(), 0.1) == 100.0


def test_branch_portfolio_performance(sample_portfolio) -> None:
    branch_perf = branch_portfolio_performance(sample_portfolio.loans)
    assert len(branch_perf) == 15
    assert branch_perf["total_loans"].sum() == 20000
    assert pytest.approx(branch_perf["pos_share_%"].sum(), 0.1) == 100.0
