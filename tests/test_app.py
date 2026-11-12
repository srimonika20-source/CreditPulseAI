"""UI tests: theme, layout builders, and a headless smoke test of every page."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from components.layout import build_badge, build_module_card, build_phase_table, build_workflow
from components.theme import build_css
from config.settings import INTELLIGENCE_WORKFLOW, MODULES, PHASES, THEME, Status

# --------------------------------------------------------------------------- #
# Pure builders
# --------------------------------------------------------------------------- #


def test_css_uses_theme_palette() -> None:
    css = build_css()
    for colour in (THEME.primary_navy, THEME.accent_teal, THEME.secondary_background, THEME.border):
        assert colour in css


def test_badge_classes() -> None:
    assert "cp-badge-complete" in build_badge(Status.COMPLETE)
    assert "cp-badge-in-progress" in build_badge(Status.IN_PROGRESS)
    assert "cp-badge-planned" in build_badge(Status.PLANNED)


def test_module_card_contains_features() -> None:
    module = MODULES[0]
    html = build_module_card(module, current_phase=1)
    assert module.title in html
    assert all(feature.replace("&", "&amp;") in html for feature in module.features)


def test_phase_table_has_row_per_phase() -> None:
    assert build_phase_table(PHASES, current_phase=1).count("<tr>") == len(PHASES) + 1


def test_workflow_order() -> None:
    html = build_workflow()
    positions = [html.index(step) for step in INTELLIGENCE_WORKFLOW]
    assert positions == sorted(positions)


# --------------------------------------------------------------------------- #
# Headless app smoke tests
# --------------------------------------------------------------------------- #
APP_PATH = str(Path(__file__).resolve().parent.parent / "app.py")


def test_app_home_renders_without_errors() -> None:
    at = AppTest.from_file(APP_PATH, default_timeout=30).run()
    assert not at.exception
    rendered = " ".join(m.value for m in at.markdown)
    assert "CreditPulse AI" in rendered
    assert "Project status" in rendered


def test_home_page_shows_no_fabricated_kpis() -> None:
    """The landing page must not show monetary amounts or PAR/percentage values."""
    at = AppTest.from_file(APP_PATH, default_timeout=30).run()
    rendered = " ".join(m.value for m in at.markdown)
    # Ignore the injected stylesheet: CSS values such as "100%" are not KPIs.
    rendered = re.sub(r"<style>.*?</style>", "", rendered, flags=re.DOTALL)
    assert "₹" not in rendered
    assert not re.search(r"\d+(\.\d+)?\s?%", rendered)
    assert len(at.metric) == 0


@pytest.mark.parametrize("module", MODULES, ids=lambda m: m.key)
def test_module_pages_render(module) -> None:
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    at.switch_page(module.page).run()
    assert not at.exception
    # Placeholder check only applies if a module is in a future unreleased phase.
    if module.phase > 7:
        assert len(at.metric) == 0
