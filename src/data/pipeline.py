"""
Data pipeline: generate -> validate -> save -> load into SQLite -> report.

Usage:
    python -m src.data.pipeline                     # defaults from config (seed 42, 20,000 loans)
    python -m src.data.pipeline --seed 7 --num-loans 25000
    python -m src.data.pipeline --report-only       # profile existing files, no regeneration

Exits with code 1 if any data-quality check fails. Files are only written
when every check passes.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from config.settings import DATA, RAW_DATA_DIR
from database.connection import create_db_engine
from src.data.generator import generate_portfolio
from src.data.io import load_portfolio, save_portfolio, write_to_sqlite
from src.data.schema import DPD_BUCKET_LABELS, STATUS_ACTIVE, PortfolioData
from src.data.validation import ValidationReport, validate_portfolio


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def _section(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def _distribution(series: pd.Series, order: list[str] | None = None) -> pd.DataFrame:
    counts = series.value_counts()
    if order is not None:
        counts = counts.reindex(order, fill_value=0)
    return pd.DataFrame({"count": counts, "share_%": (counts / counts.sum() * 100).round(2)})


def profile_portfolio(data: PortfolioData) -> dict[str, pd.DataFrame]:
    """Build descriptive profiling tables (counts and distributions only).

    Args:
        data: Portfolio to profile.

    Returns:
        Named DataFrames: row counts, nulls, and product, branch, DPD and status distributions.
    """
    loans = data.loans
    active = loans[loans["loan_status"] == STATUS_ACTIVE]
    tables = data.tables()
    nulls = pd.concat(
        {name: df.isna().sum() for name, df in tables.items()}, names=["table", "column"]
    ).rename("null_count").to_frame()

    product = loans.groupby("product_type").agg(
        loans=("loan_id", "size"),
        disbursed_inr=("loan_amount", "sum"),
        avg_ticket_inr=("loan_amount", "mean"),
        avg_rate_pct=("interest_rate", "mean"),
    )
    product["loan_share_%"] = (product["loans"] / product["loans"].sum() * 100).round(2)

    branch = loans.groupby(["branch_id", "branch_name"]).agg(
        loans=("loan_id", "size"), disbursed_inr=("loan_amount", "sum")
    )
    branch["loan_share_%"] = (branch["loans"] / branch["loans"].sum() * 100).round(2)

    dpd_active = active.groupby("dpd_bucket").agg(
        accounts=("loan_id", "size"), outstanding_inr=("outstanding_principal", "sum")
    ).reindex(list(DPD_BUCKET_LABELS), fill_value=0)
    dpd_active["account_share_%"] = (dpd_active["accounts"] / dpd_active["accounts"].sum() * 100).round(2)
    dpd_active["outstanding_share_%"] = (
        dpd_active["outstanding_inr"] / dpd_active["outstanding_inr"].sum() * 100
    ).round(2)

    return {
        "row_counts": pd.DataFrame({"rows": {n: len(df) for n, df in tables.items()}}),
        "nulls": nulls,
        "loan_status": _distribution(loans["loan_status"]),
        "product": product.round(2),
        "branch": branch.round(0),
        "dpd_active": dpd_active.round(0),
        "payment_status": _distribution(data.repayments["payment_status"]),
        "segment": _distribution(data.customers["customer_segment"]),
    }


def print_report(data: PortfolioData, report: ValidationReport) -> None:
    """Print the Part C validation and profiling report to stdout."""
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 30)
    pd.set_option("display.float_format", lambda v: f"{v:,.2f}")
    profile = profile_portfolio(data)

    _section(f"DATASET ROW COUNTS  (reporting date {data.reporting_date}, {data.history_months} months)")
    print(profile["row_counts"].to_string())

    for name, df in data.tables().items():
        _section(f"SAMPLE RECORDS: {name}")
        print(df.head(3).to_string(index=False))

    _section("NULL COUNTS (only last_payment_date and payment_date may be null)")
    nulls = profile["nulls"]
    print(nulls[nulls["null_count"] > 0].to_string() if (nulls["null_count"] > 0).any() else "No nulls.")
    print(f"\nTotal columns checked: {len(nulls)}")

    _section("LOAN STATUS")
    print(profile["loan_status"].to_string())
    _section("PRODUCT DISTRIBUTION (all loans)")
    print(profile["product"].to_string())
    _section("BRANCH DISTRIBUTION (all loans)")
    print(profile["branch"].to_string())
    _section("DPD BUCKET DISTRIBUTION (active loans)")
    print(profile["dpd_active"].to_string())
    _section("REPAYMENT PAYMENT STATUS")
    print(profile["payment_status"].to_string())
    _section("CUSTOMER SEGMENTS")
    print(profile["segment"].to_string())

    frame = report.to_frame()
    _section("REFERENTIAL INTEGRITY")
    print(frame[frame["category"] == "referential integrity"][["check", "status", "failures"]].to_string(index=False))
    _section(f"DATA QUALITY CHECKS: {int((frame['status'] == 'PASS').sum())}/{len(frame)} passed")
    print(frame[["category", "check", "status", "failures", "examples"]].to_string(index=False))


# --------------------------------------------------------------------------- #
# Pipeline
# --------------------------------------------------------------------------- #
def run_pipeline(
    seed: int = DATA.random_seed,
    num_loans: int = DATA.num_loans,
    history_months: int = DATA.history_months,
    reporting_date: date = DATA.reporting_date,
    output_dir: Path = RAW_DATA_DIR,
    sqlite_url: str | None = None,
    load_sqlite: bool = True,
) -> tuple[PortfolioData, ValidationReport]:
    """Generate, validate and persist the portfolio.

    Files are written only when every validation check passes.

    Args:
        seed: Random seed.
        num_loans: Number of loan accounts.
        history_months: Months of history.
        reporting_date: Portfolio reporting date.
        output_dir: Directory for CSV output.
        sqlite_url: Optional SQLAlchemy URL (defaults to the configured database).
        load_sqlite: Whether to load the tables into SQLite.

    Returns:
        ``(data, report)``.
    """
    data = generate_portfolio(num_loans, history_months, seed, reporting_date)
    report = validate_portfolio(data)
    if report.passed:
        save_portfolio(data, output_dir, seed=seed)
        if load_sqlite:
            write_to_sqlite(data, create_db_engine(sqlite_url))
    return data, report


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description="Generate the CreditPulse AI synthetic portfolio.")
    parser.add_argument("--seed", type=int, default=DATA.random_seed)
    parser.add_argument("--num-loans", type=int, default=DATA.num_loans)
    parser.add_argument("--months", type=int, default=DATA.history_months)
    parser.add_argument("--reporting-date", type=date.fromisoformat, default=DATA.reporting_date)
    parser.add_argument("--output", type=Path, default=RAW_DATA_DIR)
    parser.add_argument("--no-sqlite", action="store_true", help="Skip loading into SQLite.")
    parser.add_argument("--report-only", action="store_true", help="Validate and profile existing files.")
    args = parser.parse_args(argv)

    if args.report_only:
        data = load_portfolio(args.output)
        report = validate_portfolio(data)
    else:
        data, report = run_pipeline(
            args.seed, args.num_loans, args.months, args.reporting_date, args.output,
            load_sqlite=not args.no_sqlite,
        )
    print_report(data, report)
    if not report.passed:
        print("\nVALIDATION FAILED: datasets were not saved.", file=sys.stderr)
        return 1
    print(f"\nAll checks passed. Datasets saved to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
