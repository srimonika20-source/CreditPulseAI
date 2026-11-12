"""
Display formatting helpers for Indian financial figures.

Uses the Indian numbering system (lakh = 1,00,000; crore = 1,00,00,000),
which is how NBFC management reports are usually presented.
"""

from __future__ import annotations

import math

LAKH: int = 100_000
CRORE: int = 10_000_000


def format_indian_number(value: float, decimals: int = 0) -> str:
    """Format a number with Indian digit grouping (e.g. 12,34,567).

    Args:
        value: Number to format.
        decimals: Number of decimal places to keep.

    Returns:
        The formatted string, e.g. ``"12,34,567"`` or ``"-1,00,000.50"``.
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "–"
    sign = "-" if value < 0 else ""
    formatted = f"{abs(value):.{decimals}f}"
    integer_part, _, fraction = formatted.partition(".")

    # Last three digits, then groups of two (Indian system).
    if len(integer_part) > 3:
        head, tail = integer_part[:-3], integer_part[-3:]
        groups: list[str] = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        integer_part = ",".join(groups + [tail])

    return f"{sign}{integer_part}" + (f".{fraction}" if fraction else "")


def format_inr(value: float, compact: bool = True, decimals: int = 2) -> str:
    """Format a rupee amount, optionally in lakh / crore units.

    Args:
        value: Amount in rupees.
        compact: If True, scale to ``Cr`` or ``L`` when the amount is large enough.
        decimals: Decimal places for compact output.

    Returns:
        Formatted string, e.g. ``"₹12.50 Cr"``, ``"₹4.20 L"`` or ``"₹85,000"``.
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "–"
    sign = "-" if value < 0 else ""
    magnitude = abs(value)
    if compact and magnitude >= CRORE:
        return f"{sign}₹{magnitude / CRORE:.{decimals}f} Cr"
    if compact and magnitude >= LAKH:
        return f"{sign}₹{magnitude / LAKH:.{decimals}f} L"
    return f"{sign}₹{format_indian_number(magnitude)}"


def format_percent(value: float, decimals: int = 2, is_ratio: bool = True) -> str:
    """Format a value as a percentage.

    Args:
        value: The value to format.
        decimals: Decimal places.
        is_ratio: If True, ``value`` is a ratio (0.052 → 5.20%). If False, it is
            already a percentage (5.2 → 5.20%).

    Returns:
        Formatted percentage string.
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "–"
    pct = value * 100 if is_ratio else value
    return f"{pct:.{decimals}f}%"
