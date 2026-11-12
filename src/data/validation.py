"""
Data-quality validation for the synthetic portfolio.

Each check is a small function that returns a ``CheckResult`` with the
number of offending records and a few example keys. ``validate_portfolio``
runs every check and returns a ``ValidationReport``. Checks are grouped:

* **schema**: columns, nulls, uniqueness, categorical domains
* **values**: ranges and arithmetic (EMI, outstanding)
* **dates**: chronology and the single reporting date
* **business rules**: status, DPD and bucket consistency, history length
* **referential integrity**: foreign keys between datasets
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from config.simulation import PRODUCTS
from src.data.schema import (
    DPD_BUCKET_LABELS,
    LOAN_STATUSES,
    NULLABLE_COLUMNS,
    PAID_LATE,
    PAID_ON_TIME,
    PARTIALLY_PAID,
    PAYMENT_STATUSES,
    STATUS_ACTIVE,
    STATUS_CLOSED,
    TABLE_COLUMNS,
    UNPAID,
    PortfolioData,
    assign_dpd_bucket,
    calculate_emi,
    history_start,
    principal_schedule,
)

__all__ = ["CheckResult", "ValidationReport", "validate_portfolio"]

MONEY_TOLERANCE = 1.0  # INR, for reconciliations involving rounding


@dataclass(frozen=True)
class CheckResult:
    """Outcome of one validation check."""

    category: str
    name: str
    failures: int
    examples: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        """True when no records violate the rule."""
        return self.failures == 0


@dataclass
class ValidationReport:
    """Collection of check results."""

    results: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """True when every check passed."""
        return all(r.passed for r in self.results)

    def failed(self) -> list[CheckResult]:
        """Checks that found at least one violation."""
        return [r for r in self.results if not r.passed]

    def get(self, name: str) -> CheckResult:
        """Return the result of a check by name."""
        for r in self.results:
            if r.name == name:
                return r
        raise KeyError(name)

    def to_frame(self) -> pd.DataFrame:
        """Results as a DataFrame (one row per check)."""
        return pd.DataFrame(
            [
                {
                    "category": r.category,
                    "check": r.name,
                    "status": "PASS" if r.passed else "FAIL",
                    "failures": r.failures,
                    "examples": ", ".join(r.examples),
                }
                for r in self.results
            ]
        )


def _result(category: str, name: str, mask: pd.Series | np.ndarray, keys: pd.Series | None = None) -> CheckResult:
    """Build a ``CheckResult`` from a boolean violation mask."""
    mask = pd.Series(mask).fillna(True).astype(bool).to_numpy()
    failures = int(mask.sum())
    examples: tuple[str, ...] = ()
    if failures and keys is not None:
        examples = tuple(str(k) for k in pd.Series(keys).to_numpy()[mask][:5])
    return CheckResult(category, name, failures, examples)


def _expected_instalments_due(first_emi: pd.Series, tenure: pd.Series, reporting_date: date) -> pd.Series:
    """Instalments whose due date falls on or before the reporting date."""
    rd = pd.Timestamp(reporting_date)
    months = (rd.year - first_emi.dt.year) * 12 + (rd.month - first_emi.dt.month)
    months = months - (first_emi.dt.day > rd.day).astype(int)
    count = (months + 1).clip(lower=0)
    return np.minimum(count, tenure).astype(int)


# --------------------------------------------------------------------------- #
# Check groups
# --------------------------------------------------------------------------- #
def _schema_checks(d: PortfolioData) -> list[CheckResult]:
    out: list[CheckResult] = []
    for table, df in d.tables().items():
        expected = TABLE_COLUMNS[table]
        mismatch = list(df.columns) != expected
        out.append(CheckResult("schema", f"{table}: columns match contract", int(mismatch),
                               (f"got {list(df.columns)}",) if mismatch else ()))
        mandatory = [c for c in expected if c in df.columns and c not in NULLABLE_COLUMNS[table]]
        nulls = df[mandatory].isna().sum()
        bad = nulls[nulls > 0]
        out.append(CheckResult("schema", f"{table}: no nulls in mandatory columns", int(bad.sum()),
                               tuple(f"{c}={n}" for c, n in bad.items())))

    for table, key in (("branches", "branch_id"), ("customers", "customer_id"),
                       ("loans", "loan_id"), ("repayments", "repayment_id")):
        df = d.tables()[table]
        out.append(_result("schema", f"{table}: unique {key}", df[key].duplicated(keep=False), df[key]))
    r = d.repayments
    out.append(_result("schema", "repayments: one row per loan instalment",
                       r.duplicated(["loan_id", "due_date"], keep=False), r["repayment_id"]))

    loans = d.loans
    products = {p.name for p in PRODUCTS}
    out.append(_result("schema", "loans: valid product_type", ~loans["product_type"].isin(products), loans["loan_id"]))
    out.append(_result("schema", "loans: valid loan_status", ~loans["loan_status"].isin(LOAN_STATUSES), loans["loan_id"]))
    out.append(_result("schema", "loans: valid dpd_bucket", ~loans["dpd_bucket"].isin(DPD_BUCKET_LABELS), loans["loan_id"]))
    out.append(_result("schema", "repayments: valid payment_status",
                       ~r["payment_status"].isin(PAYMENT_STATUSES), r["repayment_id"]))
    return out


def _value_checks(d: PortfolioData) -> list[CheckResult]:
    loans, r = d.loans, d.repayments
    key = loans["loan_id"]
    expected_emi = np.array([
        round(calculate_emi(a, i, int(t)), 2)
        for a, i, t in zip(loans["loan_amount"], loans["interest_rate"], loans["tenure_months"])
    ])
    return [
        _result("values", "loans: loan_amount > 0", loans["loan_amount"] <= 0, key),
        _result("values", "loans: interest_rate > 0", loans["interest_rate"] <= 0, key),
        _result("values", "loans: tenure_months > 0", loans["tenure_months"] <= 0, key),
        _result("values", "loans: emi_amount matches amortisation formula",
                np.abs(loans["emi_amount"] - expected_emi) > 0.01, key),
        _result("values", "loans: outstanding_principal >= 0", loans["outstanding_principal"] < 0, key),
        _result("values", "loans: outstanding_principal <= loan_amount",
                loans["outstanding_principal"] > loans["loan_amount"] + 0.01, key),
        _result("values", "loans: dpd >= 0", loans["dpd"] < 0, key),
        _result("values", "repayments: emi_due > 0", r["emi_due"] <= 0, r["repayment_id"]),
        _result("values", "repayments: 0 <= amount_paid <= emi_due",
                (r["amount_paid"] < 0) | (r["amount_paid"] > r["emi_due"] + 0.01), r["repayment_id"]),
        _result("values", "repayments: days_past_due >= 0", r["days_past_due"] < 0, r["repayment_id"]),
    ]


def _date_checks(d: PortfolioData) -> list[CheckResult]:
    loans, r = d.loans, d.repayments
    rd = pd.Timestamp(d.reporting_date)
    window_start = pd.Timestamp(history_start(d.reporting_date, d.history_months))
    key = loans["loan_id"]
    merged = r.merge(loans[["loan_id", "disbursement_date"]], on="loan_id", how="left")
    expected_maturity = [
        f + pd.DateOffset(months=int(t) - 1) for f, t in zip(loans["first_emi_due_date"], loans["tenure_months"])
    ]
    return [
        _result("dates", "loans: disbursement_date within history window",
                (loans["disbursement_date"] < window_start) | (loans["disbursement_date"] > rd), key),
        _result("dates", "loans: first_emi_due_date after disbursement_date",
                loans["first_emi_due_date"] <= loans["disbursement_date"], key),
        _result("dates", "loans: maturity_date = first EMI + tenure - 1 months",
                loans["maturity_date"] != pd.Series(expected_maturity, index=loans.index), key),
        _result("dates", "loans: last_payment_date not after reporting date",
                loans["last_payment_date"] > rd, key),
        _result("dates", "loans: last_payment_date not before disbursement",
                loans["last_payment_date"] < loans["disbursement_date"], key),
        _result("dates", "repayments: due_date after disbursement_date",
                merged["due_date"] <= merged["disbursement_date"], merged["repayment_id"]),
        _result("dates", "repayments: payment_date not before disbursement_date",
                merged["payment_date"] < merged["disbursement_date"], merged["repayment_id"]),
        _result("dates", "repayments: due_date not after reporting date", r["due_date"] > rd, r["repayment_id"]),
        _result("dates", "repayments: payment_date not after reporting date",
                r["payment_date"] > rd, r["repayment_id"]),
    ]


def _business_rule_checks(d: PortfolioData) -> list[CheckResult]:
    loans, r = d.loans, d.repayments
    key = loans["loan_id"]
    closed = loans["loan_status"] == STATUS_CLOSED
    active = loans["loan_status"] == STATUS_ACTIVE

    fully_paid = r["amount_paid"] >= r["emi_due"] - 0.005
    per_loan = r.assign(_unpaid=~fully_paid).groupby("loan_id").agg(
        rows=("repayment_id", "size"),
        unpaid=("_unpaid", "sum"),
        last_payment=("payment_date", "max"),
    )
    unpaid_dpd = r.loc[~fully_paid].groupby("loan_id")["days_past_due"].max()
    snap = loans.set_index("loan_id").join(per_loan).join(unpaid_dpd.rename("max_unpaid_dpd"))
    snap[["rows", "unpaid"]] = snap[["rows", "unpaid"]].fillna(0)
    snap["max_unpaid_dpd"] = snap["max_unpaid_dpd"].fillna(0)

    expected_rows = _expected_instalments_due(snap["first_emi_due_date"], snap["tenure_months"], d.reporting_date)
    closed_s = snap["loan_status"] == STATUS_CLOSED

    status = r["payment_status"]
    paid_amount_ok = (
        ((status == PAID_ON_TIME) | (status == PAID_LATE)) == fully_paid
    )
    on_time_ok = ~((status == PAID_ON_TIME) & (r["days_past_due"] != 0))
    late_ok = ~((status == PAID_LATE) & (r["days_past_due"] <= 0))
    unpaid_ok = ~((status == UNPAID) & ((r["amount_paid"] != 0) | r["payment_date"].notna()))
    partial_ok = ~((status == PARTIALLY_PAID) & ((r["amount_paid"] <= 0) | r["payment_date"].isna()))
    paid_date_ok = ~(fully_paid & r["payment_date"].isna())

    return [
        _result("business rules", "closed loans have zero outstanding",
                closed & (loans["outstanding_principal"] != 0), key),
        _result("business rules", "closed loans have zero DPD", closed & (loans["dpd"] != 0), key),
        _result("business rules", "closed loans have every instalment fully paid",
                closed_s & ((snap["unpaid"] > 0) | (snap["rows"] != snap["tenure_months"])), snap.index),
        _result("business rules", "active loans have outstanding principal > 0",
                active & (loans["outstanding_principal"] <= 0), key),
        _result("business rules", "fully repaid loans are not marked active",
                ~closed_s & (snap["rows"] == snap["tenure_months"]) & (snap["unpaid"] == 0), snap.index),
        _result("business rules", "dpd_bucket agrees with dpd",
                loans["dpd_bucket"].to_numpy() != assign_dpd_bucket(loans["dpd"]).to_numpy(), key),
        _result("business rules", "loan dpd equals oldest unpaid instalment DPD",
                snap["dpd"] != snap["max_unpaid_dpd"], snap.index),
        _result("business rules", "last_payment_date equals latest repayment",
                ~((snap["last_payment_date"] == snap["last_payment"])
                  | (snap["last_payment_date"].isna() & snap["last_payment"].isna())), snap.index),
        _result("business rules", "repayment history length matches loan age",
                snap["rows"] != expected_rows, snap.index),
        _result("business rules", "payment_status consistent with amounts and dates",
                ~(paid_amount_ok & on_time_ok & late_ok & unpaid_ok & partial_ok & paid_date_ok),
                r["repayment_id"]),
        _outstanding_reconciliation(d),
    ]


def _outstanding_reconciliation(d: PortfolioData) -> CheckResult:
    """Outstanding principal must equal loan amount minus principal repaid."""
    loans = d.loans
    paid_by_loan = {k: g["amount_paid"].to_numpy() for k, g in d.repayments.groupby("loan_id", sort=False)}
    mismatched: list[str] = []
    for row in loans.itertuples(index=False):
        if row.loan_status == STATUS_CLOSED:
            continue
        paid = paid_by_loan.get(row.loan_id, np.array([]))
        schedule = principal_schedule(row.loan_amount, row.interest_rate, int(row.tenure_months))
        expected = row.loan_amount - float(np.dot(paid / row.emi_amount, schedule[: len(paid)]))
        if abs(expected - row.outstanding_principal) > MONEY_TOLERANCE:
            mismatched.append(row.loan_id)
    return CheckResult("values", "outstanding reconciles with repayments", len(mismatched), tuple(mismatched[:5]))


def _referential_checks(d: PortfolioData) -> list[CheckResult]:
    loans, r = d.loans, d.repayments
    branch_names = d.branches.set_index("branch_id")["branch_name"]
    return [
        _result("referential integrity", "loans.customer_id -> customers",
                ~loans["customer_id"].isin(d.customers["customer_id"]), loans["loan_id"]),
        _result("referential integrity", "loans.branch_id -> branches",
                ~loans["branch_id"].isin(d.branches["branch_id"]), loans["loan_id"]),
        _result("referential integrity", "loans.branch_name matches branch master",
                loans["branch_name"].to_numpy() != loans["branch_id"].map(branch_names).to_numpy(), loans["loan_id"]),
        _result("referential integrity", "repayments.loan_id -> loans",
                ~r["loan_id"].isin(loans["loan_id"]), r["repayment_id"]),
        _result("referential integrity", "every customer has at least one loan",
                ~d.customers["customer_id"].isin(loans["customer_id"]), d.customers["customer_id"]),
    ]


CHECK_GROUPS: tuple[Callable[[PortfolioData], list[CheckResult]], ...] = (
    _schema_checks,
    _value_checks,
    _date_checks,
    _business_rule_checks,
    _referential_checks,
)


def validate_portfolio(data: PortfolioData) -> ValidationReport:
    """Run every data-quality check on a portfolio.

    Args:
        data: The generated (or loaded) portfolio.

    Returns:
        A ``ValidationReport``. ``report.passed`` is True only if every check passed.
    """
    report = ValidationReport()
    for group in CHECK_GROUPS:
        report.results.extend(group(data))
    return report
