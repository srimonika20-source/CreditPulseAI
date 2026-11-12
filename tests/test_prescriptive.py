"""
Tests for Phase 6 Prescriptive Recommendation and Forecasting Engines.
"""

from __future__ import annotations

import pandas as pd
import pytest

from config.settings import RAW_DATA_DIR
from src.data.io import datasets_exist, load_portfolio
from src.intelligence.anomaly_detection import run_full_anomaly_scan
from src.intelligence.forecasting import RiskForecast, forecast_par_trajectory
from src.intelligence.recommendations import Recommendation, generate_prescriptive_recommendations
from src.metrics.delinquency import monthly_historical_par_trend


@pytest.fixture(scope="module")
def portfolio_data():
    if not datasets_exist(RAW_DATA_DIR):
        pytest.skip("Generated datasets not found")
    p = load_portfolio(RAW_DATA_DIR)
    if "customer_segment" not in p.loans.columns:
        p.loans = p.loans.merge(p.customers[["customer_id", "customer_segment"]], on="customer_id", how="left")
    return p


def test_forecast_par_trajectory(portfolio_data) -> None:
    trend = monthly_historical_par_trend(portfolio_data.repayments, portfolio_data.loans)
    forecast = forecast_par_trajectory(trend, "par30_rate_%", horizon=3)
    assert isinstance(forecast, RiskForecast)
    assert forecast.horizon_months == 3
    assert forecast.expected_value > 0
    assert forecast.lower_bound <= forecast.expected_value <= forecast.upper_bound
    assert len(forecast.trajectory_table) == 3


def test_generate_prescriptive_recommendations(portfolio_data) -> None:
    findings = run_full_anomaly_scan(portfolio_data.loans, portfolio_data.repayments)
    recommendations = generate_prescriptive_recommendations(findings)
    assert isinstance(recommendations, list)
    assert len(recommendations) == len(findings)

    for rec in recommendations:
        assert isinstance(rec, Recommendation)
        assert rec.stage == "PRESCRIBE"
        assert rec.rec_id.startswith("REC-")
        assert rec.priority in ("P1 - Critical", "P2 - High", "P3 - Moderate")
        assert rec.pillar in ("Underwriting", "Collections", "Exposure", "Policy")
        assert rec.finding_id != ""
        assert "Tied to" in rec.evidence_citation
