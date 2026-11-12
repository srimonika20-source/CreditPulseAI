"""
Reusable layout components shared by every page.

Each function renders one self-contained UI element. HTML-building helpers
(prefixed ``build_``) are pure functions so they can be tested without
Streamlit.
"""

from __future__ import annotations

from html import escape

import streamlit as st

from config.settings import (
    APP,
    INTELLIGENCE_WORKFLOW,
    PHASES,
    ModuleInfo,
    PhaseInfo,
    Status,
    phase_status,
)


# --------------------------------------------------------------------------- #
# Pure HTML builders
# --------------------------------------------------------------------------- #
def build_badge(status: Status) -> str:
    """Return an HTML status badge.

    Args:
        status: Delivery status to display.

    Returns:
        HTML ``<span>`` for the badge.
    """
    css_class = "cp-badge-" + status.name.lower().replace("_", "-")
    return f'<span class="cp-badge {css_class}">{escape(status.value)}</span>'


def build_module_card(module: ModuleInfo, current_phase: int) -> str:
    """Return the HTML card describing a product module.

    Args:
        module: Module metadata.
        current_phase: Phase currently under development (sets the badge).

    Returns:
        HTML for the module card.
    """
    features = "".join(f"<li>{escape(f)}</li>" for f in module.features)
    badge = build_badge(phase_status(module.phase, current_phase))
    return (
        '<div class="cp-card">'
        f'<div class="cp-card-title">{escape(module.title)}</div>'
        f'<div class="cp-card-text">{escape(module.summary)}</div>'
        f"<ul>{features}</ul>"
        f'<div class="cp-card-footer">Delivered in Phase {module.phase} &nbsp; {badge}</div>'
        "</div>"
    )


def build_phase_table(phases: tuple[PhaseInfo, ...], current_phase: int) -> str:
    """Return an HTML table of delivery phases and their status.

    Args:
        phases: Phase registry.
        current_phase: Phase currently under development.

    Returns:
        HTML ``<table>`` markup.
    """
    rows = "".join(
        "<tr>"
        f'<td class="cp-phase">Phase {p.number}</td>'
        f"<td><strong>{escape(p.title)}</strong></td>"
        f"<td>{escape(p.scope)}</td>"
        f"<td>{build_badge(phase_status(p.number, current_phase))}</td>"
        "</tr>"
        for p in phases
    )
    return (
        '<table class="cp-table">'
        "<thead><tr><th>Phase</th><th>Milestone</th><th>Scope</th><th>Status</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def build_workflow(steps: tuple[str, ...] = INTELLIGENCE_WORKFLOW) -> str:
    """Return the HTML for the Detect → … → Track workflow strip.

    Args:
        steps: Ordered workflow stage names.

    Returns:
        HTML markup for the workflow strip.
    """
    parts: list[str] = []
    for i, step in enumerate(steps):
        if i:
            parts.append('<span class="cp-arrow">→</span>')
        parts.append(f'<span class="cp-step">{escape(step)}</span>')
    return f'<div class="cp-workflow">{"".join(parts)}</div>'


# --------------------------------------------------------------------------- #
# Streamlit renderers
# --------------------------------------------------------------------------- #
def render_header(title: str, subtitle: str = "", eyebrow: str = APP.app_name) -> None:
    """Render the standard page header.

    Args:
        title: Main page title.
        subtitle: Optional supporting text.
        eyebrow: Small teal label above the title.
    """
    subtitle_html = f'<div class="cp-subtitle">{escape(subtitle)}</div>' if subtitle else ""
    st.markdown(
        '<div class="cp-header">'
        f'<div class="cp-eyebrow">{escape(eyebrow)}</div>'
        f'<h1 class="cp-title">{escape(title)}</h1>'
        f"{subtitle_html}</div>",
        unsafe_allow_html=True,
    )


def render_section_title(title: str, caption: str = "") -> None:
    """Render a section heading with an optional caption.

    Args:
        title: Section title.
        caption: Optional muted supporting text.
    """
    caption_html = f'<div class="cp-section-caption">{escape(caption)}</div>' if caption else ""
    st.markdown(
        f'<div class="cp-section-title">{escape(title)}</div>{caption_html}',
        unsafe_allow_html=True,
    )


def render_module_grid(modules: tuple[ModuleInfo, ...], columns: int = 3) -> None:
    """Render module cards in a responsive grid.

    Args:
        modules: Modules to display.
        columns: Number of cards per row.
    """
    for start in range(0, len(modules), columns):
        cols = st.columns(columns, gap="medium")
        for col, module in zip(cols, modules[start : start + columns]):
            with col:
                st.markdown(build_module_card(module, APP.current_phase), unsafe_allow_html=True)
        st.write("")  # vertical breathing room between rows


def render_phase_table(phases: tuple[PhaseInfo, ...] = PHASES) -> None:
    """Render the project delivery-status table.

    Args:
        phases: Phase registry.
    """
    st.markdown(build_phase_table(phases, APP.current_phase), unsafe_allow_html=True)


def render_module_placeholder(module: ModuleInfo) -> None:
    """Render the standard 'coming soon' page for a module not yet built.

    The page shows only planned scope. It shows no metrics, charts or numbers,
    so nothing on it can be mistaken for real results.

    Args:
        module: Module whose page is being rendered.
    """
    render_header(module.title, module.summary)
    status = phase_status(module.phase, APP.current_phase)
    st.markdown(
        '<div class="cp-panel">'
        f"<strong>Status:</strong> {build_badge(status)} &nbsp; "
        f"Scheduled for <strong>Phase {module.phase}</strong>. "
        "No data or metrics are shown until the underlying analytics engine is "
        "built and validated."
        "</div>",
        unsafe_allow_html=True,
    )
    render_section_title("Planned capabilities")
    st.markdown("\n".join(f"- {feature}" for feature in module.features))
    render_footer()


def render_footer() -> None:
    """Render the standard application footer."""
    st.markdown(
        f'<div class="cp-footer">{escape(APP.app_name)} v{escape(APP.version)} · '
        "Portfolio project · All data in this application is synthetic and fictional.</div>",
        unsafe_allow_html=True,
    )
