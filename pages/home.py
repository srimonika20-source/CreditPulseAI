"""
Landing page for CreditPulse AI.

Shows the product overview, the intelligence workflow, the module catalogue
and project delivery status. This page shows no portfolio metrics on purpose.
"""

from __future__ import annotations

import streamlit as st

from components.layout import (
    build_workflow,
    render_footer,
    render_header,
    render_module_grid,
    render_phase_table,
    render_section_title,
)
from config.settings import APP, DATA, MODULES, PHASES

render_header(title=APP.app_name, subtitle=APP.description, eyebrow=APP.tagline)

# --- Product snapshot (descriptive facts about the build, not portfolio KPIs) ---
left, right = st.columns([3, 2], gap="large")
with left:
    render_section_title(
        "Intelligence workflow",
        "Every insight follows the same evidence chain. Findings are kept separate "
        "from possible explanations.",
    )
    st.markdown(build_workflow(), unsafe_allow_html=True)
    st.write("")
    st.markdown(
        "- **Detect**: flag statistically significant KPI deviations\n"
        "- **Diagnose**: quantify which segments contributed to each change\n"
        "- **Predict**: project near-term risk with stated uncertainty\n"
        "- **Prescribe**: recommend actions linked to verified evidence\n"
        "- **Track**: assign owners and measure outcomes"
    )
with right:
    render_section_title("Platform scope", "Planned design parameters for the simulation.")
    st.markdown(
        '<div class="cp-panel">'
        f"<strong>Portfolio type:</strong> Synthetic {DATA.country} NBFC<br>"
        f"<strong>Loan accounts:</strong> ≥ {DATA.min_loans:,} (configurable)<br>"
        f"<strong>History:</strong> {DATA.history_months} months<br>"
        f"<strong>Random seed:</strong> {DATA.random_seed} (reproducible)<br>"
        f"<strong>Currency:</strong> {DATA.currency}<br>"
        "<strong>Data status:</strong> Not yet generated (Phase 2)"
        "</div>",
        unsafe_allow_html=True,
    )

# --- Module catalogue ---
render_section_title(
    "Product modules",
    "Seven modules covering portfolio monitoring, risk analytics, intelligence and execution. "
    "Use the sidebar to open any module.",
)
render_module_grid(MODULES, columns=3)

# --- Project status ---
render_section_title(
    "Project status",
    f"Built incrementally across {len(PHASES)} phases. "
    f"Current phase: {APP.current_phase}.",
)
render_phase_table(PHASES)

render_footer()
