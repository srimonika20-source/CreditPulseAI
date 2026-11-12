"""
Data contract for the CreditPulse AI synthetic portfolio.

Defines dataset columns, categorical values, the DPD bucketing rule, the
amortisation maths shared by the generator and the validator, and the
``PortfolioData`` container.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from config.settings import RISK

# --------------------------------------------------------------------------- #
# Columns (order is the on-disk order)
# --------------------------------------------------------------------------- #
BRANCH_COLUMNS: list[str] = ["branch_id", "branch_name", "city", "state", "region", "tier"]

CUSTOMER_COLUMNS: list[str] = [
    "customer_id",
    "customer_segment",
    "customer_city",
    "customer_age_band",
    "monthly_income_band",
    "employment_type",
]

LOAN_COLUMNS: list[str] = [
    "loan_id",
    "customer_id",
    "product_type",
    "branch_id",
    "branch_name",
    "disbursement_date",
    "loan_amount",
    "interest_rate",
    "tenure_months",
    "emi_amount",
    "loan_status",
    "outstanding_principal",
    "dpd",
    "dpd_bucket",
    "first_emi_due_date",
    "last_payment_date",
    "maturity_date",
]

REPAYMENT_COLUMNS: list[str] = [
    "repayment_id",
    "loan_id",
    "due_date",
    "emi_due",
    "amount_paid",
    "payment_date",
    "days_past_due",
    "payment_status",
]

TABLE_COLUMNS: dict[str, list[str]] = {
    "branches": BRANCH_COLUMNS,
    "customers": CUSTOMER_COLUMNS,
    "loans": LOAN_COLUMNS,
    "repayments": REPAYMENT_COLUMNS,
}

DATE_COLUMNS: dict[str, list[str]] = {
    "branches": [],
    "customers": [],
    "loans": ["disbursement_date", "first_emi_due_date", "last_payment_date", "maturity_date"],
    "repayments": ["due_date", "payment_date"],
}

# Columns allowed to be null (everything else is mandatory).
NULLABLE_COLUMNS: dict[str, set[str]] = {
    "branches": set(),
    "customers": set(),
    "loans": {"last_payment_date"},  # no payment received yet
    "repayments": {"payment_date"},  # nothing paid against the instalment
}

# --------------------------------------------------------------------------- #
# Categorical values
# --------------------------------------------------------------------------- #
STATUS_ACTIVE = "Active"
STATUS_CLOSED = "Closed"
LOAN_STATUSES: tuple[str, ...] = (STATUS_ACTIVE, STATUS_CLOSED)

PAID_ON_TIME = "Paid On Time"
PAID_LATE = "Paid Late"
PARTIALLY_PAID = "Partially Paid"
UNPAID = "Unpaid"
PAYMENT_STATUSES: tuple[str, ...] = (PAID_ON_TIME, PAID_LATE, PARTIALLY_PAID, UNPAID)

DPD_BUCKET_LABELS: tuple[str, ...] = tuple(label for label, _, _ in RISK.dpd_buckets)


# --------------------------------------------------------------------------- #
# Rules shared by the generator and the validator
# --------------------------------------------------------------------------- #
def assign_dpd_bucket(dpd: pd.Series | np.ndarray | list[int]) -> pd.Series:
    """Map days past due to the configured DPD bucket labels.

    Args:
        dpd: Non-negative days-past-due values.

    Returns:
        A string Series of bucket labels aligned with the input.
    """
    values = pd.Series(dpd).astype("int64")
    labels = pd.Series(DPD_BUCKET_LABELS[-1], index=values.index, dtype="object")
    for label, lower, upper in RISK.dpd_buckets:
        upper_bound = np.inf if upper is None else upper
        labels[(values >= lower) & (values <= upper_bound)] = label
    return labels


def calculate_emi(principal: float, annual_rate_pct: float, tenure_months: int) -> float:
    """Calculate the equated monthly instalment on a reducing balance.

    EMI = P * r * (1 + r)^n / ((1 + r)^n - 1), where r is the monthly rate.

    Args:
        principal: Loan amount in INR.
        annual_rate_pct: Annual interest rate in percent (e.g. 18.5).
        tenure_months: Number of monthly instalments.

    Returns:
        The EMI in INR (unrounded).
    """
    r = annual_rate_pct / 1200.0
    if r == 0:
        return principal / tenure_months
    growth = (1.0 + r) ** tenure_months
    return principal * r * growth / (growth - 1.0)


def principal_schedule(principal: float, annual_rate_pct: float, tenure_months: int) -> np.ndarray:
    """Return the principal component of each instalment.

    The components sum exactly to ``principal``. The final instalment absorbs
    any floating-point residue.

    Args:
        principal: Loan amount in INR.
        annual_rate_pct: Annual interest rate in percent.
        tenure_months: Number of monthly instalments.

    Returns:
        Array of length ``tenure_months`` with the principal repaid per instalment.
    """
    r = annual_rate_pct / 1200.0
    emi = calculate_emi(principal, annual_rate_pct, tenure_months)
    k = np.arange(tenure_months)
    if r == 0:
        components = np.full(tenure_months, principal / tenure_months)
    else:
        # Opening balance before instalment k (closed-form reducing balance).
        opening = principal * (1 + r) ** k - emi * ((1 + r) ** k - 1) / r
        components = emi - opening * r
    components[-1] = principal - components[:-1].sum()
    return components


def add_months(d: date, months: int) -> date:
    """Add calendar months to a date whose day is at most 28.

    Args:
        d: Starting date (day <= 28, so every month has that day).
        months: Number of months to add.

    Returns:
        The shifted date.
    """
    total = d.year * 12 + (d.month - 1) + months
    return date(total // 12, total % 12 + 1, d.day)


def history_start(reporting_date: date, history_months: int) -> date:
    """First day of the history window ending at ``reporting_date``.

    A 36-month window ending 31-Oct-2026 starts on 01-Nov-2023.

    Args:
        reporting_date: Last day of the window.
        history_months: Window length in calendar months.

    Returns:
        The first day of the earliest month in the window.
    """
    return add_months(date(reporting_date.year, reporting_date.month, 1), -(history_months - 1))


# --------------------------------------------------------------------------- #
# Container
# --------------------------------------------------------------------------- #
@dataclass
class PortfolioData:
    """The four synthetic datasets plus the reporting date and window they describe."""

    branches: pd.DataFrame
    customers: pd.DataFrame
    loans: pd.DataFrame
    repayments: pd.DataFrame
    reporting_date: date
    history_months: int

    def tables(self) -> dict[str, pd.DataFrame]:
        """Return the datasets keyed by table name."""
        return {
            "branches": self.branches,
            "customers": self.customers,
            "loans": self.loans,
            "repayments": self.repayments,
        }
