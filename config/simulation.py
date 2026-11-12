"""
Simulation profile for the synthetic Indian NBFC portfolio.

Every assumption the data generator relies on is declared here: product
terms, fictional branches, customer mix, repayment behaviour and embedded
stress scenarios. The generator code holds no business constants, so the
simulation can be reviewed and tuned in one place.

All entities are fictional. Branch names combine an Indian city with a
generic descriptor and do not refer to any real lender's branches.

Latent risk parameters (``risk_factor``, ``risk_mult``, ``base_miss_prob``)
drive the simulation but are **never written to the output datasets**.
Analytics must discover risk patterns from the observed data, as they would
in a real portfolio.
"""

from __future__ import annotations

from dataclasses import dataclass


# --------------------------------------------------------------------------- #
# Products
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ProductProfile:
    """Origination terms and baseline risk for one lending product."""

    name: str
    mix_weight: float  # share of loan count before branch-tier tilt
    amount_median: float  # INR
    amount_sigma: float  # log-normal dispersion
    amount_min: float
    amount_max: float
    amount_rounding: int  # loan amounts are rounded to this multiple
    rate_min: float  # annual interest rate, %
    rate_max: float
    tenures: tuple[int, ...]  # allowed tenures in months
    tenure_weights: tuple[float, ...]
    base_miss_prob: float  # monthly probability a current account misses an EMI


PRODUCTS: tuple[ProductProfile, ...] = (
    ProductProfile(
        "Personal Loan", 0.25, 200_000, 0.55, 50_000, 1_000_000, 5_000,
        14.0, 24.0, (12, 24, 36, 48, 60), (0.15, 0.30, 0.30, 0.15, 0.10), 0.028,
    ),
    ProductProfile(
        "Business Loan", 0.15, 800_000, 0.60, 200_000, 5_000_000, 10_000,
        16.0, 26.0, (12, 24, 36, 48), (0.15, 0.35, 0.35, 0.15), 0.032,
    ),
    ProductProfile(
        "Consumer Durable Loan", 0.30, 35_000, 0.50, 10_000, 200_000, 500,
        13.0, 22.0, (6, 9, 12, 18, 24), (0.20, 0.20, 0.35, 0.15, 0.10), 0.024,
    ),
    ProductProfile(
        "Two-Wheeler Loan", 0.20, 90_000, 0.35, 40_000, 250_000, 1_000,
        10.0, 18.0, (12, 18, 24, 36), (0.15, 0.20, 0.40, 0.25), 0.026,
    ),
    ProductProfile(
        "Loan Against Property", 0.10, 3_000_000, 0.65, 1_000_000, 15_000_000, 50_000,
        9.0, 14.0, (60, 84, 120, 180), (0.25, 0.30, 0.30, 0.15), 0.010,
    ),
)


# --------------------------------------------------------------------------- #
# Branches (fictional)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class BranchProfile:
    """A fictional NBFC branch."""

    branch_id: str
    branch_name: str
    city: str
    state: str
    region: str
    tier: str  # "Metro", "Tier 1" or "Tier 2"
    size_weight: float  # relative share of customers acquired
    risk_factor: float  # latent credit-quality multiplier (not exported)


BRANCHES: tuple[BranchProfile, ...] = (
    BranchProfile("BR01", "Mumbai Central", "Mumbai", "Maharashtra", "West", "Metro", 1.6, 0.90),
    BranchProfile("BR02", "Pune West", "Pune", "Maharashtra", "West", "Metro", 1.3, 0.85),
    BranchProfile("BR03", "Nagpur City", "Nagpur", "Maharashtra", "West", "Tier 1", 0.9, 1.05),
    BranchProfile("BR04", "Nashik Main", "Nashik", "Maharashtra", "West", "Tier 2", 0.7, 1.15),
    BranchProfile("BR05", "Ahmedabad East", "Ahmedabad", "Gujarat", "West", "Metro", 1.2, 0.80),
    BranchProfile("BR06", "Surat Ring Road", "Surat", "Gujarat", "West", "Tier 1", 0.9, 0.95),
    BranchProfile("BR07", "Jaipur Pink City", "Jaipur", "Rajasthan", "North", "Tier 1", 1.0, 1.10),
    BranchProfile("BR08", "Lucknow Central", "Lucknow", "Uttar Pradesh", "North", "Tier 1", 1.0, 1.25),
    BranchProfile("BR09", "Indore Main", "Indore", "Madhya Pradesh", "Central", "Tier 1", 0.9, 1.00),
    BranchProfile("BR10", "Bhopal Lake View", "Bhopal", "Madhya Pradesh", "Central", "Tier 2", 0.7, 1.20),
    BranchProfile("BR11", "Bengaluru South", "Bengaluru", "Karnataka", "South", "Metro", 1.5, 0.85),
    BranchProfile("BR12", "Hyderabad North", "Hyderabad", "Telangana", "South", "Metro", 1.3, 0.90),
    BranchProfile("BR13", "Chennai Central", "Chennai", "Tamil Nadu", "South", "Metro", 1.2, 0.85),
    BranchProfile("BR14", "Coimbatore Main", "Coimbatore", "Tamil Nadu", "South", "Tier 2", 0.7, 1.00),
    BranchProfile("BR15", "Kolkata East", "Kolkata", "West Bengal", "East", "Metro", 1.1, 1.15),
)

# Product mix tilt by branch tier (multiplies ProductProfile.mix_weight).
TIER_PRODUCT_TILT: dict[str, dict[str, float]] = {
    "Metro": {"Personal Loan": 1.25, "Loan Against Property": 1.30, "Two-Wheeler Loan": 0.75},
    "Tier 1": {},
    "Tier 2": {"Two-Wheeler Loan": 1.40, "Business Loan": 1.20, "Personal Loan": 0.75,
               "Loan Against Property": 0.70},
}


# --------------------------------------------------------------------------- #
# Customer profile distributions: name -> (weight, risk multiplier, ...)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Category:
    """A categorical attribute value with its sampling weight and risk effect."""

    name: str
    weight: float
    risk_mult: float = 1.0
    rate_adjust: float = 0.0  # interest-rate add-on in percentage points
    amount_factor: float = 1.0  # loan-size scaling


CUSTOMER_SEGMENTS: tuple[Category, ...] = (
    Category("Prime", 0.30, risk_mult=0.55, rate_adjust=-1.5),
    Category("Near Prime", 0.35, risk_mult=1.00, rate_adjust=0.0),
    Category("Sub Prime", 0.15, risk_mult=1.80, rate_adjust=2.5),
    Category("New to Credit", 0.20, risk_mult=1.35, rate_adjust=1.5),
)

EMPLOYMENT_TYPES: tuple[Category, ...] = (
    Category("Salaried", 0.48, risk_mult=0.85),
    Category("Self-Employed Professional", 0.14, risk_mult=0.95),
    Category("Self-Employed Business", 0.28, risk_mult=1.15),
    Category("Gig / Contract Worker", 0.10, risk_mult=1.40),
)

INCOME_BANDS: tuple[Category, ...] = (
    Category("Below 25K", 0.22, risk_mult=1.30, amount_factor=0.60),
    Category("25K-50K", 0.34, risk_mult=1.10, amount_factor=0.85),
    Category("50K-1L", 0.26, risk_mult=0.95, amount_factor=1.00),
    Category("1L-2L", 0.13, risk_mult=0.80, amount_factor=1.30),
    Category("Above 2L", 0.05, risk_mult=0.70, amount_factor=1.70),
)

AGE_BANDS: tuple[Category, ...] = (
    Category("21-25", 0.10, risk_mult=1.15),
    Category("26-35", 0.38, risk_mult=1.00),
    Category("36-45", 0.30, risk_mult=0.95),
    Category("46-55", 0.16, risk_mult=0.95),
    Category("56-65", 0.06, risk_mult=1.05),
)

# Share of customers who hold more than one loan.
REPEAT_CUSTOMER_LOAN_SHARE: float = 0.15


# --------------------------------------------------------------------------- #
# Disbursement volume
# --------------------------------------------------------------------------- #
MONTHLY_GROWTH_RATE: float = 0.015  # month-on-month growth in disbursement count
# Calendar-month seasonality (festive season Oct-Nov, financial year-end March).
SEASONALITY: dict[int, float] = {3: 1.10, 10: 1.25, 11: 1.20, 12: 1.05}
EMI_DAYS: tuple[int, ...] = (5, 10, 15)  # EMI due day of month
MIN_DAYS_TO_FIRST_EMI: int = 15


# --------------------------------------------------------------------------- #
# Repayment behaviour
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class BehaviourProfile:
    """Monthly repayment behaviour of the simulated borrower.

    Arrears are counted in missed instalments. Payments are applied to the
    oldest unpaid instalment first (FIFO), in line with RBI guidance on
    appropriation of repayments.
    """

    # Accounts that are current: share of payments made on or before the due date.
    on_time_share: float = 0.86
    late_payment_max_days: int = 20  # late-but-same-cycle payments
    early_payment_max_days: int = 4

    # Accounts in arrears, by arrears count: (cure probability, pay-one probability).
    # The remaining probability is a further missed instalment (roll forward).
    arrears_transitions: tuple[tuple[float, float], ...] = (
        (0.45, 0.20),  # 1 instalment overdue
        (0.25, 0.22),  # 2 instalments overdue
        (0.07, 0.15),  # 3+ instalments overdue
    )
    arrears_payment_max_days: int = 10

    # When an instalment is missed, chance of a partial payment and its size.
    partial_payment_prob: float = 0.35
    partial_payment_range: tuple[float, float] = (0.20, 0.70)

    # Loan-level idiosyncratic risk dispersion (log-normal sigma).
    idiosyncratic_sigma: float = 0.45
    max_miss_prob: float = 0.60


BEHAVIOUR = BehaviourProfile()


# --------------------------------------------------------------------------- #
# Embedded stress scenarios (known ground truth for later phases)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class VintageStress:
    """Elevated risk for loans of one product, at given branches, in a disbursement window."""

    enabled: bool
    product: str
    branch_ids: tuple[str, ...]
    disbursed_from: str  # ISO date, inclusive
    disbursed_to: str  # ISO date, inclusive
    risk_multiplier: float


@dataclass(frozen=True)
class CollectionStress:
    """Higher miss probability for one product on instalments due in a calendar window."""

    enabled: bool
    product: str
    due_from: str
    due_to: str
    risk_multiplier: float


VINTAGE_STRESS = VintageStress(
    enabled=True,
    product="Business Loan",
    branch_ids=("BR08", "BR10"),
    disbursed_from="2025-06-01",
    disbursed_to="2025-09-30",
    risk_multiplier=2.5,
)

COLLECTION_STRESS = CollectionStress(
    enabled=True,
    product="Consumer Durable Loan",
    due_from="2026-07-01",
    due_to="2026-10-31",
    risk_multiplier=1.6,
)
