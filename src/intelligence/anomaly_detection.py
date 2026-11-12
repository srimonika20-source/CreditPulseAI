"""
DETECT Stage: Automated Anomaly Detection Engine for CreditPulse AI.

Implements automated detection of statistically and operationally significant
deviations in credit risk and portfolio metrics:
- KPI Deviations: Z-score & threshold outlier detection on time-series metrics.
- Segment Anomalies: Branch, product, and customer segment delinquency spikes.
- Vintage Anomalies: Cohorts exhibiting significantly higher deterioration at key MOBs.
- Structured Finding model ensuring evidence-first logging (finding IDs, observed values, benchmarks).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from src.metrics.delinquency import segment_delinquency_breakdown
from src.metrics.vintage import generate_mob_matrix


@dataclass(frozen=True)
class Finding:
    """A verified, statistically grounded risk observation.

    Distinguishes verifiable mathematical findings from subjective hypotheses.
    """

    finding_id: str
    stage: str  # "DETECT"
    category: str  # "KPI", "Branch", "Product", "Vintage"
    severity: str  # "HIGH", "MEDIUM", "LOW"
    title: str
    dimension: str
    dimension_value: str
    metric_name: str
    observed_value: float
    benchmark_value: float
    deviation_pct: float
    evidence: str
    metadata: dict[str, Any] = field(default_factory=dict)


def detect_kpi_deviations(
    historical_metrics: pd.DataFrame,
    metric_col: str,
    date_col: str = "month",
    z_threshold: float = 2.0,
) -> list[Finding]:
    """Detect statistical outliers in a monthly metric series using rolling Z-scores.

    Args:
        historical_metrics: Time-series DataFrame.
        metric_col: Column to test for outliers.
        date_col: Timestamp/Period column.
        z_threshold: Number of standard deviations to trigger anomaly.

    Returns:
        List of Finding instances.
    """
    findings: list[Finding] = []
    if len(historical_metrics) < 4:
        return findings

    df = historical_metrics.sort_values(date_col).copy()
    series = df[metric_col].astype(float)
    mean = series.mean()
    std = series.std(ddof=1)

    if std <= 1e-6:
        return findings

    z_scores = (series - mean) / std

    # Check latest observation and any historical spike
    for idx, z in z_scores.items():
        if abs(z) >= z_threshold:
            val = float(series.loc[idx])
            dev = ((val - mean) / mean * 100.0) if mean != 0 else 0.0
            month_str = str(df.loc[idx, date_col])[:7]
            f_id = f"FND-KPI-{metric_col[:3].upper()}-{month_str.replace('-', '')}"
            severity = "HIGH" if abs(z) >= 2.5 else "MEDIUM"

            findings.append(
                Finding(
                    finding_id=f_id,
                    stage="DETECT",
                    category="KPI",
                    severity=severity,
                    title=f"Statistical anomaly in {metric_col} during {month_str}",
                    dimension="Timeline",
                    dimension_value=month_str,
                    metric_name=metric_col,
                    observed_value=val,
                    benchmark_value=mean,
                    deviation_pct=dev,
                    evidence=f"Observed {val:.2f} vs portfolio historical mean {mean:.2f} (Z-score: {z:.2f})",
                    metadata={"z_score": round(z, 2), "std": round(std, 3)},
                )
            )

    return findings


def detect_segment_anomalies(
    loans: pd.DataFrame,
    segment_col: str,
    par_col: str = "par30_%",
    relative_threshold: float = 1.35,  # 35% worse than portfolio average
) -> list[Finding]:
    """Detect branches, products, or segments whose delinquency significantly exceeds benchmark.

    Args:
        loans: Loan master dataframe.
        segment_col: Dimension column (e.g., 'branch_name', 'product_type').
        par_col: Target risk metric column.
        relative_threshold: Multiplier threshold above overall average.

    Returns:
        List of Finding instances.
    """
    findings: list[Finding] = []
    df = segment_delinquency_breakdown(loans, segment_col)
    if df.empty:
        return findings

    # Overall portfolio benchmark
    active_loans = loans[loans["loan_status"] == "Active"]
    tot_pos = active_loans["outstanding_principal"].sum()
    if tot_pos <= 0:
        return findings

    target_thresh = int(par_col.replace("par", "").replace("_%", ""))
    tot_par = active_loans.loc[active_loans["dpd"] >= target_thresh, "outstanding_principal"].sum()
    portfolio_par_rate = (tot_par / tot_pos * 100.0)

    for _, row in df.iterrows():
        observed_rate = float(row[par_col])
        pos_amt = float(row["total_pos_inr"])

        # Skip immaterial segments (< 1% of total POS)
        if pos_amt / tot_pos < 0.01:
            continue

        if observed_rate >= portfolio_par_rate * relative_threshold and observed_rate > 3.0:
            dev = ((observed_rate - portfolio_par_rate) / portfolio_par_rate * 100.0)
            seg_val = str(row[segment_col])
            cat_name = "Branch" if "branch" in segment_col.lower() else "Product"
            f_id = f"FND-{cat_name.upper()[:3]}-{abs(hash(seg_val)) % 10000:04d}"
            severity = "HIGH" if observed_rate >= portfolio_par_rate * 1.6 else "MEDIUM"

            findings.append(
                Finding(
                    finding_id=f_id,
                    stage="DETECT",
                    category=cat_name,
                    severity=severity,
                    title=f"Elevated {par_col.upper()} in {cat_name}: {seg_val}",
                    dimension=cat_name,
                    dimension_value=seg_val,
                    metric_name=par_col,
                    observed_value=observed_rate,
                    benchmark_value=portfolio_par_rate,
                    deviation_pct=dev,
                    evidence=(
                        f"{seg_val} {par_col} is {observed_rate:.2f}% vs portfolio average of {portfolio_par_rate:.2f}% "
                        f"(+{dev:.1f}% higher relative risk, active POS ₹{pos_amt/1e7:.2f} Cr)"
                    ),
                    metadata={"outstanding_pos": pos_amt, "active_count": int(row["active_loans"])},
                )
            )

    return findings


def detect_vintage_anomalies(
    loans: pd.DataFrame,
    repayments: pd.DataFrame,
    target_mob: int = 6,
    dpd_threshold: int = 30,
    multiplier_threshold: float = 1.4,
) -> list[Finding]:
    """Detect underwriting cohorts showing abnormal vintage delinquency at target Month-on-Book.

    Args:
        loans: Loan master.
        repayments: Repayment transactions.
        target_mob: Specific maturity milestone (e.g., MOB 6 or MOB 12).
        dpd_threshold: Default hurdle (e.g. 30 DPD).
        multiplier_threshold: Multiplier above cross-cohort median.

    Returns:
        List of Finding instances.
    """
    findings: list[Finding] = []
    matrix = generate_mob_matrix(loans, repayments, dpd_threshold=dpd_threshold, cohort_freq="Q")
    mob_col = f"MOB {target_mob}"

    if mob_col not in matrix.columns:
        return findings

    series = matrix[mob_col].dropna()
    if len(series) < 3:
        return findings

    median_val = float(series.median())
    if median_val <= 0.05:
        return findings

    for cohort, val in series.items():
        if val >= median_val * multiplier_threshold and val > 1.5:
            dev = ((val - median_val) / median_val * 100.0)
            f_id = f"FND-VNT-{cohort.replace('Q', '')}-{target_mob}"
            findings.append(
                Finding(
                    finding_id=f_id,
                    stage="DETECT",
                    category="Vintage",
                    severity="HIGH" if val >= median_val * 1.7 else "MEDIUM",
                    title=f"Vintage underwriting deterioration in cohort {cohort}",
                    dimension="Disbursement Cohort",
                    dimension_value=str(cohort),
                    metric_name=f"{dpd_threshold}+ DPD at MOB {target_mob}",
                    observed_value=float(val),
                    benchmark_value=median_val,
                    deviation_pct=dev,
                    evidence=(
                        f"Cohort {cohort} reached {val:.2f}% delinquency at MOB {target_mob} "
                        f"compared to cross-cohort benchmark median of {median_val:.2f}% (+{dev:.1f}% deviation)"
                    ),
                    metadata={"target_mob": target_mob, "cohort": cohort},
                )
            )

    return findings


def run_full_anomaly_scan(loans: pd.DataFrame, repayments: pd.DataFrame) -> list[Finding]:
    """Run an exhaustive multi-dimensional anomaly detection sweep across the portfolio."""
    all_findings: list[Finding] = []

    # 1. Product level anomalies
    all_findings.extend(detect_segment_anomalies(loans, "product_type", "par30_%"))

    # 2. Branch level anomalies
    all_findings.extend(detect_segment_anomalies(loans, "branch_name", "par30_%"))

    # 3. Vintage deterioration at MOB 6 & MOB 12
    all_findings.extend(detect_vintage_anomalies(loans, repayments, target_mob=6))
    all_findings.extend(detect_vintage_anomalies(loans, repayments, target_mob=12))

    return all_findings
