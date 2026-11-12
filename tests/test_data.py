"""
Tests for Phase 2 Synthetic Data Engine and Data Validation.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from config.settings import DATA, RAW_DATA_DIR
from config.simulation import PRODUCTS
from src.data.generator import (
    generate_branches,
    generate_customers,
    generate_portfolio,
)
from src.data.io import datasets_exist, load_portfolio
from src.data.schema import (
    BRANCH_COLUMNS,
    CUSTOMER_COLUMNS,
    DPD_BUCKET_LABELS,
    LOAN_COLUMNS,
    REPAYMENT_COLUMNS,
    assign_dpd_bucket,
    calculate_emi,
    principal_schedule,
)
from src.data.validation import validate_portfolio


def test_schema_definitions() -> None:
    assert len(BRANCH_COLUMNS) == 6
    assert len(CUSTOMER_COLUMNS) == 6
    assert len(LOAN_COLUMNS) == 17
    assert len(REPAYMENT_COLUMNS) == 8


def test_calculate_emi_and_amortisation() -> None:
    p = 100_000.0
    rate = 12.0
    tenure = 12
    emi = calculate_emi(p, rate, tenure)
    assert round(emi, 2) == 8884.88

    schedule = principal_schedule(p, rate, tenure)
    assert len(schedule) == tenure
    assert np.isclose(schedule.sum(), p)


def test_dpd_bucketing() -> None:
    dpds = pd.Series([0, 1, 15, 30, 31, 60, 61, 90, 91, 150])
    buckets = assign_dpd_bucket(dpds)
    expected = [
        "0 DPD", "1-30 DPD", "1-30 DPD", "1-30 DPD",
        "31-60 DPD", "31-60 DPD", "61-90 DPD", "61-90 DPD",
        "90+ DPD", "90+ DPD"
    ]
    assert list(buckets) == expected


def test_generate_branches() -> None:
    df = generate_branches()
    assert len(df) == 15
    assert list(df.columns) == BRANCH_COLUMNS
    assert df["branch_id"].nunique() == 15


def test_generate_customers() -> None:
    rng = np.random.default_rng(42)
    df, latent = generate_customers(100, rng)
    assert len(df) == 100
    assert list(df.columns) == CUSTOMER_COLUMNS
    assert df["customer_id"].nunique() == 100
    assert len(latent.home_branch) == 100


def test_reproducibility_small_portfolio() -> None:
    p1 = generate_portfolio(num_loans=50, history_months=12, seed=99, reporting_date=date(2026, 10, 31))
    p2 = generate_portfolio(num_loans=50, history_months=12, seed=99, reporting_date=date(2026, 10, 31))
    pd.testing.assert_frame_equal(p1.loans, p2.loans)
    pd.testing.assert_frame_equal(p1.repayments, p2.repayments)


def test_validation_passes_on_synthetic_data() -> None:
    portfolio = generate_portfolio(num_loans=100, history_months=12, seed=123, reporting_date=date(2026, 10, 31))
    report = validate_portfolio(portfolio)
    assert report.passed
    assert len(report.failed()) == 0


def test_saved_datasets_integrity() -> None:
    if datasets_exist(RAW_DATA_DIR):
        portfolio = load_portfolio(RAW_DATA_DIR)
        assert len(portfolio.loans) == DATA.num_loans
        assert len(portfolio.branches) == 15
        assert len(portfolio.customers) > 0
        assert len(portfolio.repayments) > 0
        report = validate_portfolio(portfolio)
        assert report.passed
