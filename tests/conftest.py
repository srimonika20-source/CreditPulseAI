"""Shared pytest fixtures for CreditPulse AI."""

from __future__ import annotations

from pathlib import Path

import pytest

from config.settings import BASE_DIR


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Absolute path to the project root."""
    return BASE_DIR
