"""
Tests for Phase 4 Analytics Engines (Delinquency, Vintage, Roll Rate).
"""

from __future__ import annotations

import pandas as pd
import pytest

from config.settings import RAW_DATA_DIR
from src.data.io import datasets_exist, load_portfolio
from src.metrics.delinquency import (
    calculate_first_payment_default,
    dpd_bucket_summary,
    monthly_historical_par_trend,
    segment_delinquency_breakdown,
)
from src.metrics.roll_rate import calculate_transition_matrix
from src.metrics.vintage import compare_cohort_vintage_curves, generate_mob_matrix


@pytest.fixture(scope="module")
def sample_portfolio():
    if not datasets_exist(RAW_DATA_DIR):
        pytest.skip("Generated datasets not found")
    return load_portfolio(RAW_DATA_DIR)


def test_dpd_bucket_summary(sample_portfolio) -> None:
    summary = dpd_bucket_summary(sample_portfolio.loans)
    assert len(summary) == 5
    assert "accounts" in summary.columns
    assert "outstanding_inr" in summary.columns
    assert summary["accounts"].sum() == (sample_portfolio.loans["loan_status"] == "Active").sum()


def test_segment_delinquency_breakdown(sample_portfolio) -> None:
    prod_breakdown = segment_delinquency_breakdown(sample_portfolio.loans, "product_type")
    assert len(prod_breakdown) == 5
    assert "par30_%" in prod_breakdown.columns
    assert "par90_%" in prod_breakdown.columns


def test_first_payment_default(sample_portfolio) -> None:
    fpd_res = calculate_first_payment_default(sample_portfolio.loans, sample_portfolio.repayments)
    assert "overall_rate_%" in fpd_res
    assert 0.0 <= fpd_res["overall_rate_%"] <= 100.0
    assert not fpd_res["by_product"].empty
    assert not fpd_res["by_cohort"].empty


def test_historical_par_trend(sample_portfolio) -> None:
    trend = monthly_historical_par_trend(sample_portfolio.repayments, sample_portfolio.loans)
    assert not trend.empty
    assert "par30_rate_%" in trend.columns
    assert "par90_rate_%" in trend.columns


def test_vintage_mob_matrix(sample_portfolio) -> None:
    matrix = generate_mob_matrix(sample_portfolio.loans, sample_portfolio.repayments, dpd_threshold=30, cohort_freq="Q")
    assert not matrix.empty
    assert "MOB 1" in matrix.columns
    tidy = compare_cohort_vintage_curves(matrix)
    assert not tidy.empty
    assert "MOB_num" in tidy.columns


def test_roll_rate_transition_matrix(sample_portfolio) -> None:
    res = calculate_transition_matrix(sample_portfolio.repayments)
    assert "rate_matrix" in res
    assert "roll_forward_rates" in res
    assert "cure_rates" in res
    rate_mat = res["rate_matrix"]
    assert rate_mat.shape == (5, 5)
