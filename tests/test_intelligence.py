"""
Tests for Phase 5 Anomaly Detection and Root-Cause Contribution Engines.
"""

from __future__ import annotations

import pytest

from config.settings import RAW_DATA_DIR
from src.data.io import datasets_exist, load_portfolio
from src.intelligence.anomaly_detection import (
    Finding,
    detect_kpi_deviations,
    detect_segment_anomalies,
    detect_vintage_anomalies,
    run_full_anomaly_scan,
)
from src.intelligence.root_cause import Diagnosis, decompose_delinquency_contribution
from src.metrics.portfolio import monthly_disbursement_trend


@pytest.fixture(scope="module")
def portfolio_data():
    if not datasets_exist(RAW_DATA_DIR):
        pytest.skip("Generated datasets not found")
    p = load_portfolio(RAW_DATA_DIR)
    if "customer_segment" not in p.loans.columns:
        p.loans = p.loans.merge(p.customers[["customer_id", "customer_segment"]], on="customer_id", how="left")
    return p


def test_detect_segment_anomalies(portfolio_data) -> None:
    findings = detect_segment_anomalies(portfolio_data.loans, "branch_name")
    assert isinstance(findings, list)
    for f in findings:
        assert isinstance(f, Finding)
        assert f.stage == "DETECT"
        assert f.severity in ("HIGH", "MEDIUM")
        assert f.observed_value > f.benchmark_value


def test_detect_vintage_anomalies(portfolio_data) -> None:
    v_findings = detect_vintage_anomalies(portfolio_data.loans, portfolio_data.repayments, target_mob=6)
    assert isinstance(v_findings, list)


def test_run_full_anomaly_scan(portfolio_data) -> None:
    all_findings = run_full_anomaly_scan(portfolio_data.loans, portfolio_data.repayments)
    assert len(all_findings) > 0
    # Embedded stress scenario: Lucknow (BR08) or Bhopal (BR10) or Business Loans should be detected
    found_ids = {f.dimension_value for f in all_findings}
    assert any("Lucknow" in d or "Bhopal" in d or "Business" in d for d in found_ids)


def test_root_cause_decomposition(portfolio_data) -> None:
    findings = run_full_anomaly_scan(portfolio_data.loans, portfolio_data.repayments)
    assert len(findings) > 0
    target_finding = findings[0]
    diagnosis = decompose_delinquency_contribution(portfolio_data.loans, target_finding)
    assert isinstance(diagnosis, Diagnosis)
    assert diagnosis.stage == "DIAGNOSE"
    assert diagnosis.finding_id == target_finding.finding_id
    assert not diagnosis.decomposition_table.empty
    assert len(diagnosis.observed_facts) >= 2
    assert len(diagnosis.hypotheses) >= 2
