"""Tests for shared utilities and the database connection layer."""

from __future__ import annotations

import pytest

from database.connection import check_connection, create_db_engine, get_session
from src.utils.formatting import format_indian_number, format_inr, format_percent


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, "0"),
        (999, "999"),
        (1_000, "1,000"),
        (100_000, "1,00,000"),
        (1_234_567, "12,34,567"),
        (123_456_789, "12,34,56,789"),
        (-100_000, "-1,00,000"),
    ],
)
def test_format_indian_number(value: float, expected: str) -> None:
    assert format_indian_number(value) == expected


def test_format_indian_number_decimals() -> None:
    assert format_indian_number(1_234_567.891, decimals=2) == "12,34,567.89"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (85_000, "₹85,000"),
        (420_000, "₹4.20 L"),
        (125_000_000, "₹12.50 Cr"),
        (-420_000, "-₹4.20 L"),
    ],
)
def test_format_inr(value: float, expected: str) -> None:
    assert format_inr(value) == expected


def test_format_inr_non_compact() -> None:
    assert format_inr(125_000_000, compact=False) == "₹12,50,00,000"


def test_format_percent() -> None:
    assert format_percent(0.0523) == "5.23%"
    assert format_percent(5.23, is_ratio=False) == "5.23%"
    assert format_percent(float("nan")) == "–"


def test_in_memory_database_connection() -> None:
    engine = create_db_engine("sqlite:///:memory:")
    assert check_connection(engine)
    with get_session(engine) as session:
        assert session.bind is engine
