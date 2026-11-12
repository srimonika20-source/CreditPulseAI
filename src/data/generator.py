"""
Synthetic Indian NBFC loan portfolio generator.

Produces four linked datasets: branch master, customer master, loan master
and instalment-level repayment transactions. All values come from the
simulation profile in ``config.simulation`` and a single seeded NumPy random
generator, so a given ``(seed, num_loans, history_months, reporting_date)``
always yields identical data.

How the simulation works
------------------------
1. **Customers** get a segment, age band, income band and employment type,
   plus a home branch (customer city = branch city).
2. **Loans** are originated over the history window. Volume grows over
   time with festive and year-end seasonality. Product mix is tilted by
   branch tier, and amount, rate and tenure come from product profiles.
3. **Repayments** are simulated month by month for each instalment due on
   or before the reporting date. A borrower who is current may miss an EMI
   with a loan-specific probability. Once in arrears, they cure, pay one
   instalment, or roll forward. Payments clear the oldest dues first
   (FIFO). Payments dated after the reporting date are not recorded.
4. **The loan snapshot** (status, outstanding principal, DPD, bucket, last
   payment) is derived from the repayment records, so the loan master and
   the transactions always agree.

Latent risk drivers are used only inside the simulation and are never
written to the output.
"""

from __future__ import annotations

import calendar
import math
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

from config.settings import DATA
from config.simulation import (
    AGE_BANDS,
    BEHAVIOUR,
    BRANCHES,
    COLLECTION_STRESS,
    CUSTOMER_SEGMENTS,
    EMI_DAYS,
    EMPLOYMENT_TYPES,
    INCOME_BANDS,
    MIN_DAYS_TO_FIRST_EMI,
    MONTHLY_GROWTH_RATE,
    PRODUCTS,
    REPEAT_CUSTOMER_LOAN_SHARE,
    SEASONALITY,
    TIER_PRODUCT_TILT,
    VINTAGE_STRESS,
    BehaviourProfile,
    Category,
)
from src.data.schema import (
    BRANCH_COLUMNS,
    CUSTOMER_COLUMNS,
    LOAN_COLUMNS,
    PAID_LATE,
    PAID_ON_TIME,
    PARTIALLY_PAID,
    REPAYMENT_COLUMNS,
    STATUS_ACTIVE,
    STATUS_CLOSED,
    UNPAID,
    PortfolioData,
    add_months,
    assign_dpd_bucket,
    calculate_emi,
    history_start,
    principal_schedule,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

__all__ = [
    "generate_branches",
    "generate_customers",
    "generate_loan_originations",
    "simulate_repayments",
    "generate_portfolio",
]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _weights(categories: tuple[Category, ...]) -> np.ndarray:
    """Normalised sampling weights for a tuple of categories."""
    w = np.array([c.weight for c in categories], dtype=float)
    return w / w.sum()


def _sample_index(rng: np.random.Generator, categories: tuple[Category, ...], size: int) -> np.ndarray:
    """Sample category indices according to their weights."""
    return rng.choice(len(categories), size=size, p=_weights(categories))


def _income_probabilities(segment: str) -> np.ndarray:
    """Income-band probabilities tilted by customer segment.

    Prime customers skew to higher incomes and Sub Prime to lower incomes,
    which gives a realistic correlation between the attributes.
    """
    base = _weights(INCOME_BANDS)
    position = np.linspace(-1.0, 1.0, len(INCOME_BANDS))  # low income -> high income
    tilt = {"Prime": 0.6, "Sub Prime": -0.5, "New to Credit": -0.2}.get(segment, 0.0)
    adjusted = base * np.exp(tilt * position)
    return adjusted / adjusted.sum()


# --------------------------------------------------------------------------- #
# Branches
# --------------------------------------------------------------------------- #
def generate_branches() -> pd.DataFrame:
    """Build the fictional branch master.

    Returns:
        DataFrame with ``BRANCH_COLUMNS`` (one row per branch).
    """
    rows = [
        (b.branch_id, b.branch_name, b.city, b.state, b.region, b.tier) for b in BRANCHES
    ]
    return pd.DataFrame(rows, columns=BRANCH_COLUMNS)


# --------------------------------------------------------------------------- #
# Customers
# --------------------------------------------------------------------------- #
@dataclass
class _CustomerLatent:
    """Simulation-only attributes of customers (never exported)."""

    home_branch: np.ndarray  # index into BRANCHES
    risk: np.ndarray  # combined customer risk multiplier
    segment_idx: np.ndarray
    income_idx: np.ndarray


def generate_customers(
    n_customers: int, rng: np.random.Generator
) -> tuple[pd.DataFrame, _CustomerLatent]:
    """Generate the customer master.

    Args:
        n_customers: Number of unique customers.
        rng: Seeded random generator.

    Returns:
        ``(customers, latent)``: the exported customer master and the
        simulation-only attributes used to originate loans.
    """
    branch_w = np.array([b.size_weight for b in BRANCHES], dtype=float)
    home_branch = rng.choice(len(BRANCHES), size=n_customers, p=branch_w / branch_w.sum())

    segment_idx = _sample_index(rng, CUSTOMER_SEGMENTS, n_customers)
    age_idx = _sample_index(rng, AGE_BANDS, n_customers)
    employment_idx = _sample_index(rng, EMPLOYMENT_TYPES, n_customers)
    income_idx = np.empty(n_customers, dtype=int)
    for s, segment in enumerate(CUSTOMER_SEGMENTS):
        mask = segment_idx == s
        income_idx[mask] = rng.choice(
            len(INCOME_BANDS), size=int(mask.sum()), p=_income_probabilities(segment.name)
        )

    def risk_of(cats: tuple[Category, ...], idx: np.ndarray) -> np.ndarray:
        return np.array([c.risk_mult for c in cats])[idx]

    risk = (
        risk_of(CUSTOMER_SEGMENTS, segment_idx)
        * risk_of(AGE_BANDS, age_idx)
        * risk_of(EMPLOYMENT_TYPES, employment_idx)
        * risk_of(INCOME_BANDS, income_idx)
    )

    customers = pd.DataFrame(
        {
            "customer_id": [f"CUST{i:06d}" for i in range(1, n_customers + 1)],
            "customer_segment": np.array([c.name for c in CUSTOMER_SEGMENTS])[segment_idx],
            "customer_city": np.array([b.city for b in BRANCHES])[home_branch],
            "customer_age_band": np.array([c.name for c in AGE_BANDS])[age_idx],
            "monthly_income_band": np.array([c.name for c in INCOME_BANDS])[income_idx],
            "employment_type": np.array([c.name for c in EMPLOYMENT_TYPES])[employment_idx],
        },
        columns=CUSTOMER_COLUMNS,
    )
    return customers, _CustomerLatent(home_branch, risk, segment_idx, income_idx)


# --------------------------------------------------------------------------- #
# Loan originations
# --------------------------------------------------------------------------- #
def _disbursement_month_weights(start: date, history_months: int) -> np.ndarray:
    """Relative disbursement volume per month: growth trend times seasonality."""
    weights = []
    for m in range(history_months):
        month = add_months(start, m).month
        weights.append((1 + MONTHLY_GROWTH_RATE) ** m * SEASONALITY.get(month, 1.0))
    w = np.array(weights)
    return w / w.sum()


def _first_emi_due_date(disbursed: date, emi_day: int) -> date:
    """First EMI date: the EMI day in the next month, at least N days after disbursal."""
    candidate = add_months(date(disbursed.year, disbursed.month, emi_day), 1)
    if (candidate - disbursed).days < MIN_DAYS_TO_FIRST_EMI:
        candidate = add_months(candidate, 1)
    return candidate


def generate_loan_originations(
    customers: pd.DataFrame,
    latent: _CustomerLatent,
    num_loans: int,
    reporting_date: date,
    history_months: int,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Originate loans with static terms (no repayment behaviour yet).

    Every customer receives at least one loan. The remaining loans go to
    randomly chosen repeat customers. Loan IDs are assigned in disbursement
    order.

    Args:
        customers: Customer master.
        latent: Simulation-only customer attributes.
        num_loans: Total number of loans to originate.
        reporting_date: Portfolio reporting date (no loan is disbursed after it).
        history_months: Length of the disbursement window in months.
        rng: Seeded random generator.

    Returns:
        DataFrame of originations. It includes the private column ``_risk``
        (relative risk multiplier), which ``simulate_repayments`` consumes and
        removes.
    """
    n_customers = len(customers)
    extra = rng.integers(0, n_customers, size=num_loans - n_customers)
    cust_idx = np.concatenate([np.arange(n_customers), extra])
    branch_idx = latent.home_branch[cust_idx]

    # Product choice, tilted by branch tier.
    product_names = [p.name for p in PRODUCTS]
    base_mix = np.array([p.mix_weight for p in PRODUCTS])
    product_idx = np.empty(num_loans, dtype=int)
    for tier, tilt in TIER_PRODUCT_TILT.items():
        mask = np.array([BRANCHES[b].tier == tier for b in branch_idx])
        probs = base_mix * np.array([tilt.get(name, 1.0) for name in product_names])
        product_idx[mask] = rng.choice(len(PRODUCTS), size=int(mask.sum()), p=probs / probs.sum())

    # Disbursement dates within the history window.
    start = history_start(reporting_date, history_months)
    month_offsets = rng.choice(history_months, size=num_loans, p=_disbursement_month_weights(start, history_months))
    disbursement_dates: list[date] = []
    for offset in month_offsets:
        month_start = add_months(start, int(offset))
        last_day = calendar.monthrange(month_start.year, month_start.month)[1]
        if (month_start.year, month_start.month) == (reporting_date.year, reporting_date.month):
            last_day = reporting_date.day
        day = int(rng.integers(1, last_day + 1))
        disbursement_dates.append(date(month_start.year, month_start.month, day))

    income_factor = np.array([c.amount_factor for c in INCOME_BANDS])[latent.income_idx[cust_idx]]
    rate_adjust = np.array([c.rate_adjust for c in CUSTOMER_SEGMENTS])[latent.segment_idx[cust_idx]]
    idiosyncratic = rng.lognormal(
        mean=-(BEHAVIOUR.idiosyncratic_sigma**2) / 2, sigma=BEHAVIOUR.idiosyncratic_sigma, size=num_loans
    )
    emi_days = rng.choice(EMI_DAYS, size=num_loans)

    amounts = np.empty(num_loans)
    rates = np.empty(num_loans)
    tenures = np.empty(num_loans, dtype=int)
    for p, product in enumerate(PRODUCTS):
        mask = product_idx == p
        n = int(mask.sum())
        raw = rng.lognormal(np.log(product.amount_median), product.amount_sigma, size=n) * income_factor[mask]
        clipped = np.clip(raw, product.amount_min, product.amount_max)
        amounts[mask] = np.round(clipped / product.amount_rounding) * product.amount_rounding
        raw_rate = rng.uniform(product.rate_min, product.rate_max, size=n) + rate_adjust[mask]
        rates[mask] = np.round(np.clip(raw_rate, product.rate_min - 1.0, product.rate_max + 3.0) * 4) / 4
        w = np.array(product.tenure_weights)
        tenures[mask] = rng.choice(product.tenures, size=n, p=w / w.sum())

    # Relative risk: customer x branch x idiosyncratic (x vintage stress).
    branch_risk = np.array([b.risk_factor for b in BRANCHES])[branch_idx]
    relative_risk = latent.risk[cust_idx] * branch_risk * idiosyncratic

    loans = pd.DataFrame(
        {
            "customer_id": customers["customer_id"].to_numpy()[cust_idx],
            "product_type": np.array(product_names)[product_idx],
            "branch_id": np.array([b.branch_id for b in BRANCHES])[branch_idx],
            "branch_name": np.array([b.branch_name for b in BRANCHES])[branch_idx],
            "disbursement_date": disbursement_dates,
            "loan_amount": amounts,
            "interest_rate": rates,
            "tenure_months": tenures,
            "_emi_day": emi_days,
            "_risk": relative_risk,
        }
    )

    if VINTAGE_STRESS.enabled:
        stressed = (
            (loans["product_type"] == VINTAGE_STRESS.product)
            & loans["branch_id"].isin(VINTAGE_STRESS.branch_ids)
            & (loans["disbursement_date"] >= date.fromisoformat(VINTAGE_STRESS.disbursed_from))
            & (loans["disbursement_date"] <= date.fromisoformat(VINTAGE_STRESS.disbursed_to))
        )
        loans.loc[stressed, "_risk"] *= VINTAGE_STRESS.risk_multiplier

    # Assign IDs in disbursement order (ties broken deterministically).
    loans = loans.sort_values(["disbursement_date", "customer_id", "product_type"], kind="mergesort")
    loans = loans.reset_index(drop=True)
    loans.insert(0, "loan_id", [f"LN{i:07d}" for i in range(1, num_loans + 1)])
    loans["emi_amount"] = [
        round(calculate_emi(a, r, int(t)), 2)
        for a, r, t in zip(loans["loan_amount"], loans["interest_rate"], loans["tenure_months"])
    ]
    loans["first_emi_due_date"] = [
        _first_emi_due_date(d, int(e)) for d, e in zip(loans["disbursement_date"], loans["_emi_day"])
    ]
    loans["maturity_date"] = [
        add_months(f, int(t) - 1) for f, t in zip(loans["first_emi_due_date"], loans["tenure_months"])
    ]
    return loans.drop(columns="_emi_day")


# --------------------------------------------------------------------------- #
# Repayment simulation
# --------------------------------------------------------------------------- #
@dataclass
class _LoanOutcome:
    """Snapshot of one loan at the reporting date."""

    status: str
    outstanding: float
    dpd: int
    last_payment: date | None


class _RepaymentSimulator:
    """Simulates the monthly repayment behaviour of individual loans."""

    def __init__(self, rng: np.random.Generator, reporting_date: date, behaviour: BehaviourProfile = BEHAVIOUR):
        self.rng = rng
        self.reporting_date = reporting_date
        self.b = behaviour
        self.base_miss = {p.name: p.base_miss_prob for p in PRODUCTS}
        self.stress_from = date.fromisoformat(COLLECTION_STRESS.due_from)
        self.stress_to = date.fromisoformat(COLLECTION_STRESS.due_to)

    def _calendar_stress(self, product: str, due: date) -> float:
        """Collection-stress multiplier for an instalment due on ``due``."""
        if (
            COLLECTION_STRESS.enabled
            and product == COLLECTION_STRESS.product
            and self.stress_from <= due <= self.stress_to
        ):
            return COLLECTION_STRESS.risk_multiplier
        return 1.0

    def _arrears_probs(self, arrears: int, risk: float) -> tuple[float, float]:
        """(cure, pay-one) probabilities for an account ``arrears`` instalments behind."""
        cure, pay_one = self.b.arrears_transitions[min(arrears, len(self.b.arrears_transitions)) - 1]
        cure = cure / math.sqrt(risk)
        if cure + pay_one > 0.95:
            cure = max(0.0, 0.95 - pay_one)
        return cure, pay_one

    def _days(self, low: int, high: int) -> timedelta:
        return timedelta(days=int(self.rng.integers(low, high + 1)))

    def simulate(self, loan: pd.Series, rows: list[tuple]) -> _LoanOutcome:
        """Simulate one loan, append its instalment rows to ``rows`` and return its snapshot."""
        rd = self.reporting_date
        tenure = int(loan["tenure_months"])
        emi = float(loan["emi_amount"])
        first_due: date = loan["first_emi_due_date"]
        product: str = loan["product_type"]
        risk = float(loan["_risk"])

        due_dates = [add_months(first_due, k) for k in range(tenure)]
        n_due = sum(1 for d in due_dates if d <= rd)
        paid = [0.0] * n_due
        paid_on: list[date | None] = [None] * n_due
        head = 0  # oldest instalment not fully paid (FIFO appropriation)

        def settle(i: int, when: date) -> None:
            paid[i] = emi
            paid_on[i] = when

        def maybe_partial(i: int, earliest: date) -> None:
            if paid[i] == 0.0 and self.rng.random() < self.b.partial_payment_prob:
                when = earliest + self._days(0, 15)
                if when <= rd:
                    paid[i] = round(emi * self.rng.uniform(*self.b.partial_payment_range), 2)
                    paid_on[i] = when

        # Instalment-by-instalment behaviour up to the reporting date.
        for k in range(n_due):
            due = due_dates[k]
            stress = self._calendar_stress(product, due)
            arrears = k - head
            if arrears == 0:
                p_miss = min(self.b.max_miss_prob, self.base_miss[product] * risk * stress)
                if self.rng.random() < p_miss:
                    maybe_partial(k, due)
                    continue
                if self.rng.random() < self.b.on_time_share:
                    when = due - self._days(0, self.b.early_payment_max_days)
                else:
                    when = due + self._days(1, self.b.late_payment_max_days)
                if when <= rd:
                    settle(k, when)
                    head = k + 1
            else:
                cure, pay_one = self._arrears_probs(arrears, risk * stress)
                u = self.rng.random()
                when = due + self._days(0, self.b.arrears_payment_max_days)
                if when > rd:
                    continue
                if u < cure:
                    for i in range(head, k + 1):
                        settle(i, when)
                    head = k + 1
                elif u < cure + pay_one:
                    settle(head, when)
                    head += 1
                else:
                    maybe_partial(head, due)

        # Post-maturity collection cycles for loans still in arrears.
        if n_due == tenure and head < tenure:
            cycle = 1
            cycle_date = add_months(due_dates[-1], cycle)
            while cycle_date <= rd and head < tenure:
                cure, pay_one = self._arrears_probs(tenure - head, risk)
                u = self.rng.random()
                when = cycle_date + self._days(0, self.b.arrears_payment_max_days)
                if when <= rd:
                    if u < cure:
                        for i in range(head, tenure):
                            settle(i, when)
                        head = tenure
                    elif u < cure + pay_one:
                        settle(head, when)
                        head += 1
                cycle += 1
                cycle_date = add_months(due_dates[-1], cycle)

        # Emit instalment rows.
        loan_id = loan["loan_id"]
        for i in range(n_due):
            due = due_dates[i]
            amount = paid[i]
            when = paid_on[i]
            if amount >= emi:
                dpd_i = max(0, (when - due).days)
                status = PAID_ON_TIME if dpd_i == 0 else PAID_LATE
            else:
                dpd_i = (rd - due).days
                status = PARTIALLY_PAID if amount > 0 else UNPAID
            rows.append((loan_id, due, emi, amount, when, dpd_i, status))

        # Snapshot at the reporting date.
        fully_repaid = n_due == tenure and head == tenure
        if fully_repaid:
            return _LoanOutcome(STATUS_CLOSED, 0.0, 0, max(d for d in paid_on if d is not None))
        principal = principal_schedule(float(loan["loan_amount"]), float(loan["interest_rate"]), tenure)
        repaid_fraction = np.array(paid) / emi if n_due else np.array([])
        outstanding = float(loan["loan_amount"]) - float(np.dot(repaid_fraction, principal[:n_due]))
        dpd = (rd - due_dates[head]).days if head < n_due else 0
        payments = [d for d in paid_on if d is not None]
        return _LoanOutcome(STATUS_ACTIVE, round(max(outstanding, 0.0), 2), dpd, max(payments) if payments else None)


def simulate_repayments(
    loans: pd.DataFrame, reporting_date: date, rng: np.random.Generator
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Simulate repayments and derive the loan snapshot at the reporting date.

    Args:
        loans: Originations from ``generate_loan_originations`` (with ``_risk``).
        reporting_date: Portfolio reporting date.
        rng: Seeded random generator.

    Returns:
        ``(loans, repayments)``: the completed loan master (``LOAN_COLUMNS``)
        and instalment-level transactions (``REPAYMENT_COLUMNS``).
    """
    simulator = _RepaymentSimulator(rng, reporting_date)
    rows: list[tuple] = []
    outcomes = [simulator.simulate(loan, rows) for _, loan in loans.iterrows()]

    loans = loans.copy()
    loans["loan_status"] = [o.status for o in outcomes]
    loans["outstanding_principal"] = [o.outstanding for o in outcomes]
    loans["dpd"] = np.array([o.dpd for o in outcomes], dtype="int64")
    loans["dpd_bucket"] = assign_dpd_bucket(loans["dpd"]).to_numpy()
    loans["last_payment_date"] = [o.last_payment for o in outcomes]

    repayments = pd.DataFrame(
        rows, columns=["loan_id", "due_date", "emi_due", "amount_paid", "payment_date", "days_past_due", "payment_status"]
    )
    repayments.insert(0, "repayment_id", [f"RP{i:09d}" for i in range(1, len(repayments) + 1)])
    repayments["days_past_due"] = repayments["days_past_due"].astype("int64")
    return _finalise_dates(loans[LOAN_COLUMNS], "loans"), _finalise_dates(repayments[REPAYMENT_COLUMNS], "repayments")


def _finalise_dates(df: pd.DataFrame, table: str) -> pd.DataFrame:
    """Convert Python date columns to pandas datetime64 (nulls become NaT)."""
    from src.data.schema import DATE_COLUMNS

    df = df.copy()
    for col in DATE_COLUMNS[table]:
        df[col] = pd.to_datetime(df[col])
    return df


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def generate_portfolio(
    num_loans: int = DATA.num_loans,
    history_months: int = DATA.history_months,
    seed: int = DATA.random_seed,
    reporting_date: date = DATA.reporting_date,
) -> PortfolioData:
    """Generate the complete synthetic portfolio.

    Args:
        num_loans: Number of unique loan accounts.
        history_months: Months of disbursement history ending at the reporting date.
        seed: Random seed. The same inputs always give identical output.
        reporting_date: Date at which balances, DPD and status are measured.

    Returns:
        A ``PortfolioData`` with branches, customers, loans and repayments.
    """
    if num_loans < 1:
        raise ValueError("num_loans must be positive")
    rng = np.random.default_rng(seed)
    logger.info(
        "Generating portfolio: %s loans, %s months, seed=%s, reporting date %s",
        num_loans, history_months, seed, reporting_date,
    )
    n_customers = max(1, num_loans - round(num_loans * REPEAT_CUSTOMER_LOAN_SHARE))
    branches = generate_branches()
    customers, latent = generate_customers(n_customers, rng)
    originations = generate_loan_originations(customers, latent, num_loans, reporting_date, history_months, rng)
    loans, repayments = simulate_repayments(originations, reporting_date, rng)
    logger.info("Generated %s loans and %s repayment records", len(loans), len(repayments))
    return PortfolioData(branches, customers, loans, repayments, reporting_date, history_months)
