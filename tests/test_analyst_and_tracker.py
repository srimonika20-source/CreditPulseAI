"""
Tests for Phase 7 AI Credit Analyst and Action Tracker.
"""

from __future__ import annotations

from datetime import date
import pytest

from config.settings import RAW_DATA_DIR
from src.actions.tracker import ActionItem, create_action, list_actions, update_action_status
from src.analyst.ai_analyst import AICreditAnalyst, AnalystResponse
from src.data.io import datasets_exist, load_portfolio
from src.intelligence.anomaly_detection import run_full_anomaly_scan
from src.intelligence.recommendations import generate_prescriptive_recommendations
from src.metrics.portfolio import calculate_executive_kpis


@pytest.fixture(scope="module")
def analyst_context():
    if not datasets_exist(RAW_DATA_DIR):
        pytest.skip("Generated datasets not found")
    p = load_portfolio(RAW_DATA_DIR)
    kpis = calculate_executive_kpis(p.loans, p.repayments)
    findings = run_full_anomaly_scan(p.loans, p.repayments)
    recommendations = generate_prescriptive_recommendations(findings)
    analyst = AICreditAnalyst(kpis, findings, recommendations, p.loans)
    return analyst


def test_ai_credit_analyst_overview(analyst_context) -> None:
    resp = analyst_context.answer_query("Summarize overall portfolio health")
    assert isinstance(resp, AnalystResponse)
    assert "CreditPulse" in resp.headline_answer
    assert len(resp.detailed_findings) > 0
    assert len(resp.evidence_citations) > 0


def test_ai_credit_analyst_anomalies(analyst_context) -> None:
    resp = analyst_context.answer_query("What are the top anomalies and why?")
    assert isinstance(resp, AnalystResponse)
    assert len(resp.detailed_findings) > 0
    assert len(resp.suggested_actions) > 0


def test_action_tracker_lifecycle() -> None:
    # Create action
    action = create_action(
        title="Test Underwriting Tightening",
        owner="CRO",
        due_date=date(2026, 12, 31),
        pillar="Underwriting",
        priority="P1 - Critical",
        action_summary="Test summary",
    )
    assert isinstance(action, ActionItem)
    assert action.id is not None
    assert action.status == "Planned"

    # Update status
    updated = update_action_status(action.id, "In Progress", outcome_notes="Audit started")
    assert updated is True

    # List actions
    all_actions = list_actions()
    target = next((a for a in all_actions if a.id == action.id), None)
    assert target is not None
    assert target.status == "In Progress"
    assert target.outcome_notes == "Audit started"
