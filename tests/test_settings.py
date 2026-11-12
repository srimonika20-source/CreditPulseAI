"""Tests for the central configuration module."""

from __future__ import annotations

import pytest

from config.settings import (
    APP,
    DATA,
    MODULES,
    PHASES,
    RISK,
    DataSettings,
    Status,
    get_module,
    phase_status,
)


def test_app_identity() -> None:
    assert APP.app_name == "CreditPulse AI"
    assert APP.version
    assert 1 <= APP.current_phase <= len(PHASES)


def test_database_url_is_sqlite() -> None:
    assert APP.database_url.startswith("sqlite:///")


def test_data_settings_meet_requirements() -> None:
    assert DATA.num_loans >= DATA.min_loans >= 20_000
    assert DATA.history_months >= 36
    assert isinstance(DATA.random_seed, int)


def test_seed_is_configurable_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CREDITPULSE_SEED", "2024")
    assert DataSettings().random_seed == 2024


def test_invalid_env_value_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CREDITPULSE_SEED", "not-a-number")
    assert DataSettings().random_seed == 42


def test_dpd_buckets_are_contiguous() -> None:
    buckets = RISK.dpd_buckets
    for (_, _, upper), (_, next_lower, _) in zip(buckets, buckets[1:]):
        assert upper is not None and next_lower == upper + 1
    assert buckets[0][1] == 0
    assert buckets[-1][2] is None  # final bucket is open-ended


def test_npa_threshold_is_90_dpd() -> None:
    assert RISK.npa_dpd_threshold == 90


def test_seven_modules_with_unique_keys() -> None:
    assert len(MODULES) == 7
    assert len({m.key for m in MODULES}) == len(MODULES)


def test_eight_sequential_phases() -> None:
    assert [p.number for p in PHASES] == list(range(1, 9))


def test_every_module_maps_to_a_valid_phase() -> None:
    valid = {p.number for p in PHASES}
    assert all(m.phase in valid for m in MODULES)


def test_get_module() -> None:
    assert get_module("vintage").title == "Vintage Analysis"
    with pytest.raises(KeyError):
        get_module("does_not_exist")


@pytest.mark.parametrize(
    ("phase", "current", "expected"),
    [(1, 2, Status.COMPLETE), (2, 2, Status.IN_PROGRESS), (3, 2, Status.PLANNED)],
)
def test_phase_status(phase: int, current: int, expected: Status) -> None:
    assert phase_status(phase, current) is expected
