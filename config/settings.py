"""
Central configuration for CreditPulse AI.

All tunable values live here: file paths, simulation parameters, credit-risk
definitions, theme colours, and the module and phase registries. The UI, the
analytics layer and the tests read from this module so nothing is defined
twice.

Environment variables (all optional) can override selected values:

    CREDITPULSE_SEED          Random seed for synthetic data (default: 42)
    CREDITPULSE_NUM_LOANS     Number of synthetic loan accounts (default: 20000)
    CREDITPULSE_HISTORY_MONTHS  Months of portfolio history (default: 36)
    CREDITPULSE_REPORTING_DATE  Portfolio reporting date, YYYY-MM-DD (default: 2026-10-31)
    CREDITPULSE_DB_PATH       Path to the SQLite database file
    CREDITPULSE_LOG_LEVEL     Logging level (default: INFO)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
BASE_DIR: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = BASE_DIR / "data"
RAW_DATA_DIR: Path = DATA_DIR / "raw"
PROCESSED_DATA_DIR: Path = DATA_DIR / "processed"
DATABASE_DIR: Path = BASE_DIR / "database"
DOCS_DIR: Path = BASE_DIR / "docs"


def _env_int(name: str, default: int) -> int:
    """Read an integer environment variable, falling back to ``default``.

    Args:
        name: Environment variable name.
        default: Value used when the variable is unset or not a valid integer.

    Returns:
        The parsed integer or the default.
    """
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_date(name: str, default: date) -> date:
    """Read an ISO date (YYYY-MM-DD) environment variable, falling back to ``default``.

    Args:
        name: Environment variable name.
        default: Value used when the variable is unset or not a valid ISO date.

    Returns:
        The parsed date or the default.
    """
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return date.fromisoformat(raw.strip())
    except ValueError:
        return default


# --------------------------------------------------------------------------- #
# Application settings
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class AppSettings:
    """Application-level settings (immutable once loaded)."""

    app_name: str = "CreditPulse AI"
    tagline: str = "Intelligent credit portfolio monitoring and decision support"
    description: str = (
        "An intelligent credit portfolio monitoring and decision-support platform "
        "for banks, NBFCs and lending institutions. CreditPulse AI turns loan-level "
        "data into evidence-backed risk insight through a structured "
        "Detect → Diagnose → Predict → Prescribe → Track workflow."
    )
    version: str = "0.7.0"
    current_phase: int = 7
    log_level: str = field(default_factory=lambda: os.getenv("CREDITPULSE_LOG_LEVEL", "INFO"))
    database_path: Path = field(
        default_factory=lambda: Path(
            os.getenv("CREDITPULSE_DB_PATH", str(DATABASE_DIR / "creditpulse.db"))
        )
    )

    @property
    def database_url(self) -> str:
        """SQLAlchemy connection URL for the SQLite database."""
        return f"sqlite:///{self.database_path.as_posix()}"


@dataclass(frozen=True)
class DataSettings:
    """Parameters for the synthetic portfolio.

    The reporting date is fixed (not "today") so the same seed always
    produces the same portfolio, whenever the generator is run.
    """

    random_seed: int = field(default_factory=lambda: _env_int("CREDITPULSE_SEED", 42))
    num_loans: int = field(default_factory=lambda: _env_int("CREDITPULSE_NUM_LOANS", 20_000))
    history_months: int = field(
        default_factory=lambda: _env_int("CREDITPULSE_HISTORY_MONTHS", 36)
    )
    reporting_date: date = field(
        default_factory=lambda: _env_date("CREDITPULSE_REPORTING_DATE", date(2026, 10, 31))
    )
    min_loans: int = 20_000
    num_branches: int = 15
    num_products: int = 5
    currency: str = "INR"
    country: str = "India"


@dataclass(frozen=True)
class RiskSettings:
    """Credit-risk definitions used across the analytics engines.

    Bucket boundaries follow common Indian NBFC practice: SMA-0/1/2 style
    buckets and NPA at 90+ days past due (RBI IRACP norms).
    """

    # (label, lower DPD inclusive, upper DPD inclusive; None = open-ended)
    dpd_buckets: tuple[tuple[str, int, int | None], ...] = (
        ("0 DPD", 0, 0),
        ("1-30 DPD", 1, 30),
        ("31-60 DPD", 31, 60),
        ("61-90 DPD", 61, 90),
        ("90+ DPD", 91, None),
    )
    par_thresholds: tuple[int, ...] = (30, 60, 90)
    npa_dpd_threshold: int = 90
    first_payment_default_dpd: int = 30


@dataclass(frozen=True)
class ThemeSettings:
    """Enterprise colour palette and typography."""

    primary_navy: str = "#0B2545"
    accent_teal: str = "#0E9F9A"
    background: str = "#FFFFFF"
    secondary_background: str = "#F5F7FA"
    border: str = "#E3E8EF"
    text_primary: str = "#1F2933"
    text_muted: str = "#616E7C"
    success: str = "#2F855A"
    warning: str = "#B7791F"
    danger: str = "#C53030"
    font_family: str = "'Inter', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif"


# --------------------------------------------------------------------------- #
# Module and phase registries
# --------------------------------------------------------------------------- #
class Status(str, Enum):
    """Delivery status for a module or phase."""

    COMPLETE = "Complete"
    IN_PROGRESS = "In progress"
    PLANNED = "Planned"


@dataclass(frozen=True)
class ModuleInfo:
    """Metadata describing one product module."""

    key: str
    title: str
    summary: str
    features: tuple[str, ...]
    page: str  # path relative to BASE_DIR
    icon: str  # Streamlit material icon short-code
    section: str  # navigation group
    phase: int


@dataclass(frozen=True)
class PhaseInfo:
    """Metadata describing one delivery phase."""

    number: int
    title: str
    scope: str


MODULES: tuple[ModuleInfo, ...] = (
    ModuleInfo(
        key="executive_overview",
        title="Executive Portfolio Overview",
        summary="Headline portfolio size, quality and collection performance.",
        features=(
            "Total disbursement & outstanding",
            "Active accounts & average ticket size",
            "PAR30 / PAR60 / PAR90",
            "Collection efficiency",
            "Disbursement trends, product & branch mix",
        ),
        page="pages/1_Executive_Overview.py",
        icon=":material/dashboard:",
        section="Portfolio Analytics",
        phase=3,
    ),
    ModuleInfo(
        key="delinquency",
        title="Delinquency Analytics",
        summary="Where and how fast the portfolio is slipping into arrears.",
        features=(
            "DPD bucket distribution",
            "Product- & branch-wise delinquency",
            "Monthly PAR trends",
            "First payment default",
            "NPA analysis",
        ),
        page="pages/2_Delinquency_Analytics.py",
        icon=":material/warning:",
        section="Portfolio Analytics",
        phase=4,
    ),
    ModuleInfo(
        key="vintage",
        title="Vintage Analysis",
        summary="Cohort-level credit performance by month on book.",
        features=(
            "Month-on-book matrix",
            "Vintage delinquency curves",
            "Cohort comparison",
            "First payment default by cohort",
        ),
        page="pages/3_Vintage_Analysis.py",
        icon=":material/stacked_line_chart:",
        section="Portfolio Analytics",
        phase=4,
    ),
    ModuleInfo(
        key="roll_rate",
        title="Roll Rate Analysis",
        summary="How accounts move between DPD buckets month to month.",
        features=(
            "DPD bucket transition matrix",
            "Roll forward & roll backward",
            "Cure rate",
            "Flow rate",
        ),
        page="pages/4_Roll_Rate_Analysis.py",
        icon=":material/swap_vert:",
        section="Portfolio Analytics",
        phase=4,
    ),
    ModuleInfo(
        key="intelligence",
        title="Intelligence Centre",
        summary="Automated detection, diagnosis and evidence-linked recommendations.",
        features=(
            "KPI deviation & anomaly detection",
            "Branch, product & vintage anomalies",
            "Root-cause contribution analysis",
            "Risk alerts",
            "Prescriptive recommendations",
        ),
        page="pages/5_Intelligence_Centre.py",
        icon=":material/insights:",
        section="Intelligence",
        phase=5,
    ),
    ModuleInfo(
        key="ai_analyst",
        title="AI Credit Analyst",
        summary="Ask portfolio questions in plain language; answers cite their evidence.",
        features=(
            "Natural-language metric queries",
            "Anomaly explanations",
            "Portfolio performance summaries",
            "Evidence-backed insights",
        ),
        page="pages/6_AI_Credit_Analyst.py",
        icon=":material/forum:",
        section="Intelligence",
        phase=7,
    ),
    ModuleInfo(
        key="action_tracker",
        title="Action Tracker",
        summary="Turn recommendations into owned, dated, measurable actions.",
        features=(
            "Record recommended actions",
            "Assign owners & due dates",
            "Track status",
            "Record outcomes",
        ),
        page="pages/7_Action_Tracker.py",
        icon=":material/task_alt:",
        section="Operations",
        phase=7,
    ),
)

PHASES: tuple[PhaseInfo, ...] = (
    PhaseInfo(1, "Foundation", "Architecture, configuration, documentation, application shell"),
    PhaseInfo(2, "Data", "Synthetic loan data generator and data validation"),
    PhaseInfo(3, "Portfolio Metrics", "Metrics engine and executive dashboard"),
    PhaseInfo(4, "Risk Analytics", "Delinquency, vintage and roll-rate analytics"),
    PhaseInfo(5, "Detect & Diagnose", "Anomaly detection and root-cause analysis"),
    PhaseInfo(6, "Prescribe", "Prescriptive recommendation engine"),
    PhaseInfo(7, "Analyst & Track", "AI Credit Analyst and action tracker"),
    PhaseInfo(8, "Release", "Testing, documentation, UI refinement and deployment"),
)

INTELLIGENCE_WORKFLOW: tuple[str, ...] = ("Detect", "Diagnose", "Predict", "Prescribe", "Track")


def phase_status(phase_number: int, current_phase: int) -> Status:
    """Return the delivery status of a phase relative to the current phase.

    A phase is *in progress* while it is the current phase, *complete* once a
    later phase has started, and *planned* otherwise.

    Args:
        phase_number: Phase being evaluated.
        current_phase: Phase currently under development.

    Returns:
        The phase's ``Status``.
    """
    if phase_number < current_phase:
        return Status.COMPLETE
    if phase_number == current_phase:
        return Status.IN_PROGRESS
    return Status.PLANNED


def get_module(key: str) -> ModuleInfo:
    """Look up a module by its key.

    Args:
        key: Module key, e.g. ``"vintage"``.

    Returns:
        The matching ``ModuleInfo``.

    Raises:
        KeyError: If no module has that key.
    """
    for module in MODULES:
        if module.key == key:
            return module
    raise KeyError(f"Unknown module key: {key!r}")


# Singleton instances used throughout the application.
APP = AppSettings()
DATA = DataSettings()
RISK = RiskSettings()
THEME = ThemeSettings()
