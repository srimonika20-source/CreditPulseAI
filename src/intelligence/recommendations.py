"""
PRESCRIBE Stage: Prescriptive Recommendation Engine.

Translates verified mathematical Findings into actionable, policy-compliant credit interventions:
- Strict evidence-linking: Each recommendation maps directly to one or more finding_ids.
- Multi-pillar categorization: Underwriting Policy, Collection Operations, Exposure Limits, or Product Restructuring.
- Quantified impact projection: Estimated risk reduction and financial balance at stake.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.intelligence.anomaly_detection import Finding


@dataclass(frozen=True)
class Recommendation:
    """Actionable prescriptive intervention tied strictly to verified Findings."""

    rec_id: str
    stage: str  # "PRESCRIBE"
    finding_id: str
    target_dimension: str
    target_value: str
    pillar: str  # "Underwriting", "Collections", "Exposure", "Policy"
    priority: str  # "P1 - Critical", "P2 - High", "P3 - Moderate"
    title: str
    action_summary: str
    evidence_citation: str
    expected_impact: str
    suggested_owner: str
    implementation_timeframe: str


def generate_prescriptive_recommendations(findings: list[Finding]) -> list[Recommendation]:
    """Generate evidence-grounded recommendations from verified portfolio anomalies.

    Args:
        findings: List of Finding instances from the DETECT stage.

    Returns:
        List of Recommendation instances.
    """
    recommendations: list[Recommendation] = []

    for idx, f in enumerate(findings):
        rec_num = idx + 1

        if f.category == "Product":
            p1_rec = Recommendation(
                rec_id=f"REC-{rec_num:03d}-POL",
                stage="PRESCRIBE",
                finding_id=f.finding_id,
                target_dimension=f.dimension,
                target_value=f.dimension_value,
                pillar="Underwriting",
                priority="P1 - Critical" if f.severity == "HIGH" else "P2 - High",
                title=f"Tighten Underwriting Score & LTV Cutoffs for {f.dimension_value}",
                action_summary=(
                    f"Raise minimum credit bureau score by 25 points for new {f.dimension_value} originations. "
                    "Mandate additional income verification and reduce maximum approved ticket size by 15%."
                ),
                evidence_citation=(
                    f"Tied to {f.finding_id}: {f.dimension_value} observed {f.metric_name} of {f.observed_value:.2f}% "
                    f"exceeds benchmark of {f.benchmark_value:.2f}% (+{f.deviation_pct:.1f}% deviation)."
                ),
                expected_impact="Estimated 35-50 bps reduction in 30+ DPD flow rate over subsequent 2 quarterly cohorts.",
                suggested_owner="Chief Risk Officer / Head of Retail Underwriting",
                implementation_timeframe="Immediate (14 days)",
            )
            recommendations.append(p1_rec)

        elif f.category == "Branch":
            branch_rec = Recommendation(
                rec_id=f"REC-{rec_num:03d}-COL",
                stage="PRESCRIBE",
                finding_id=f.finding_id,
                target_dimension=f.dimension,
                target_value=f.dimension_value,
                pillar="Collections",
                priority="P1 - Critical" if f.severity == "HIGH" else "P2 - High",
                title=f"Deploy Field Collection Taskforce & Review Local Sourcing at {f.dimension_value}",
                action_summary=(
                    f"Deploy dedicated feet-on-street recovery taskforce to {f.dimension_value} for accounts in 1-30 DPD. "
                    "Institute an audit of top 3 sourcing channel partners / DSAs in this branch."
                ),
                evidence_citation=(
                    f"Tied to {f.finding_id}: {f.dimension_value} delinquency of {f.observed_value:.2f}% "
                    f"is significantly above portfolio average ({f.benchmark_value:.2f}%)."
                ),
                expected_impact="Improve cure rate by 15-20% and curtail roll forward into 90+ DPD / NPA bucket.",
                suggested_owner="Head of Collections / Regional Credit Head",
                implementation_timeframe="30 days",
            )
            recommendations.append(branch_rec)

        elif f.category == "Vintage":
            vnt_rec = Recommendation(
                rec_id=f"REC-{rec_num:03d}-EXP",
                stage="PRESCRIBE",
                finding_id=f.finding_id,
                target_dimension=f.dimension,
                target_value=f.dimension_value,
                pillar="Exposure",
                priority="P2 - High",
                title=f"Conduct Retrospective Underwriting Audit on Cohort {f.dimension_value}",
                action_summary=(
                    f"Perform loan-level file audit on sample of early defaults in cohort {f.dimension_value}. "
                    "Identify specific policy deviations or fraud patterns during the origination period."
                ),
                evidence_citation=(
                    f"Tied to {f.finding_id}: Cohort {f.dimension_value} breached {f.observed_value:.2f}% delinquency "
                    f"at target MOB compared to peer median of {f.benchmark_value:.2f}%."
                ),
                expected_impact="Isolate root-cause policy leakages and prevent recurrence in prospective underwriting.",
                suggested_owner="Credit Quality Assurance / Head of Credit Policy",
                implementation_timeframe="45 days",
            )
            recommendations.append(vnt_rec)

    return recommendations
