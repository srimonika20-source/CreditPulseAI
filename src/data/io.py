"""
Persistence for the synthetic portfolio: CSV files, metadata and SQLite.

CSV files in ``data/raw`` are the canonical, human-readable output.
``metadata.json`` records the parameters that produced them so a dataset can
always be traced back to its seed. The same tables can also be loaded into
SQLite for SQL-based analysis.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import Engine

from config.settings import RAW_DATA_DIR
from src.data.schema import DATE_COLUMNS, TABLE_COLUMNS, PortfolioData

__all__ = ["save_portfolio", "load_portfolio", "write_to_sqlite", "datasets_exist", "read_metadata"]

METADATA_FILE = "metadata.json"


def _csv_path(directory: Path, table: str) -> Path:
    return directory / f"{table}.csv"


def save_portfolio(data: PortfolioData, directory: Path = RAW_DATA_DIR, seed: int | None = None) -> list[Path]:
    """Write all datasets as CSV plus a metadata file.

    Args:
        data: Portfolio to save.
        directory: Output directory (created if missing).
        seed: Seed used to generate the data, recorded in the metadata.

    Returns:
        Paths of the files written.
    """
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for table, df in data.tables().items():
        path = _csv_path(directory, table)
        df.to_csv(path, index=False, date_format="%Y-%m-%d", encoding="utf-8", lineterminator="\n")
        written.append(path)
    metadata = {
        "seed": seed,
        "reporting_date": data.reporting_date.isoformat(),
        "history_months": data.history_months,
        "currency": "INR",
        "row_counts": {table: len(df) for table, df in data.tables().items()},
        "synthetic": True,
    }
    meta_path = directory / METADATA_FILE
    meta_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    written.append(meta_path)
    return written


def read_metadata(directory: Path = RAW_DATA_DIR) -> dict | None:
    """Return the dataset metadata, or None if no dataset has been generated."""
    path = directory / METADATA_FILE
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def datasets_exist(directory: Path = RAW_DATA_DIR) -> bool:
    """True if every dataset file and the metadata are present."""
    return read_metadata(directory) is not None and all(
        _csv_path(directory, t).is_file() for t in TABLE_COLUMNS
    )


def load_portfolio(directory: Path = RAW_DATA_DIR) -> PortfolioData:
    """Load the saved datasets with correct data types.

    Args:
        directory: Directory containing the CSV files and metadata.

    Returns:
        The loaded ``PortfolioData``.

    Raises:
        FileNotFoundError: If the datasets have not been generated yet.
    """
    metadata = read_metadata(directory)
    if metadata is None or not datasets_exist(directory):
        raise FileNotFoundError(
            f"No generated datasets found in {directory}. Run: python -m src.data.pipeline"
        )
    frames: dict[str, pd.DataFrame] = {}
    for table, columns in TABLE_COLUMNS.items():
        df = pd.read_csv(_csv_path(directory, table), dtype={"tenure_months": "int64", "dpd": "int64"})
        for col in DATE_COLUMNS[table]:
            df[col] = pd.to_datetime(df[col], format="%Y-%m-%d")
        frames[table] = df[columns]
    return PortfolioData(
        branches=frames["branches"],
        customers=frames["customers"],
        loans=frames["loans"],
        repayments=frames["repayments"],
        reporting_date=date.fromisoformat(metadata["reporting_date"]),
        history_months=int(metadata["history_months"]),
    )


def write_to_sqlite(data: PortfolioData, engine: Engine) -> dict[str, int]:
    """Load all datasets into SQLite, replacing existing tables.

    Args:
        data: Portfolio to load.
        engine: SQLAlchemy engine (see ``database.connection``).

    Returns:
        Row counts written per table.
    """
    counts: dict[str, int] = {}
    with engine.begin() as conn:
        for table, df in data.tables().items():
            df.to_sql(table, conn, if_exists="replace", index=False, chunksize=10_000)
            counts[table] = len(df)
    return counts
