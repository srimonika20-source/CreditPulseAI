"""
Global visual theme for CreditPulse AI.

Builds a single CSS block from ``config.settings.THEME`` so colours are defined
once. The look is a clean white enterprise style: navy headings, a teal
accent, light-grey secondary surfaces, subtle borders and minimal shadows.
"""

from __future__ import annotations

import streamlit as st

from config.settings import THEME, ThemeSettings


def build_css(theme: ThemeSettings = THEME) -> str:
    """Build the global stylesheet for the application.

    Kept separate from :func:`apply_theme` so it can be unit-tested without a
    running Streamlit session.

    Args:
        theme: Colour and typography settings.

    Returns:
        A ``<style>`` block as a string.
    """
    return f"""
<style>
    /* ---------- Base ---------- */
    html, body, [class*="css"] {{
        font-family: {theme.font_family};
        color: {theme.text_primary};
    }}
    .stApp {{ background-color: {theme.background}; }}
    .block-container {{ padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1280px; }}

    h1, h2, h3, h4 {{ color: {theme.primary_navy}; font-weight: 600; letter-spacing: -0.01em; }}

    /* ---------- Sidebar ---------- */
    section[data-testid="stSidebar"] {{
        background-color: {theme.secondary_background};
        border-right: 1px solid {theme.border};
    }}

    /* ---------- Header ---------- */
    .cp-header {{
        border-bottom: 1px solid {theme.border};
        padding-bottom: 1.25rem;
        margin-bottom: 1.75rem;
    }}
    .cp-eyebrow {{
        color: {theme.accent_teal};
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 0.35rem;
    }}
    .cp-title {{
        color: {theme.primary_navy};
        font-size: 2.1rem;
        font-weight: 700;
        line-height: 1.2;
        margin: 0;
    }}
    .cp-subtitle {{
        color: {theme.text_muted};
        font-size: 1.02rem;
        margin-top: 0.5rem;
        max-width: 860px;
        line-height: 1.55;
    }}

    /* ---------- Section titles ---------- */
    .cp-section-title {{
        color: {theme.primary_navy};
        font-size: 1.2rem;
        font-weight: 600;
        margin: 2rem 0 0.25rem 0;
    }}
    .cp-section-caption {{
        color: {theme.text_muted};
        font-size: 0.9rem;
        margin-bottom: 1rem;
    }}

    /* ---------- Cards ---------- */
    .cp-card {{
        background: {theme.background};
        border: 1px solid {theme.border};
        border-radius: 8px;
        padding: 1.15rem 1.25rem;
        height: 100%;
        box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
    }}
    .cp-card-title {{
        color: {theme.primary_navy};
        font-size: 1.02rem;
        font-weight: 600;
        margin-bottom: 0.35rem;
    }}
    .cp-card-text {{ color: {theme.text_muted}; font-size: 0.9rem; line-height: 1.5; }}
    .cp-card ul {{ margin: 0.6rem 0 0.2rem 1.1rem; padding: 0; }}
    .cp-card li {{ color: {theme.text_primary}; font-size: 0.85rem; margin-bottom: 0.15rem; }}
    .cp-card-footer {{
        border-top: 1px solid {theme.border};
        margin-top: 0.8rem;
        padding-top: 0.6rem;
        font-size: 0.78rem;
        color: {theme.text_muted};
    }}

    /* ---------- Panels (light grey secondary sections) ---------- */
    .cp-panel {{
        background: {theme.secondary_background};
        border: 1px solid {theme.border};
        border-radius: 8px;
        padding: 1.25rem 1.4rem;
    }}

    /* ---------- Status badges ---------- */
    .cp-badge {{
        display: inline-block;
        font-size: 0.72rem;
        font-weight: 600;
        padding: 0.12rem 0.55rem;
        border-radius: 999px;
        border: 1px solid {theme.border};
        white-space: nowrap;
    }}
    .cp-badge-complete {{ color: {theme.success}; background: #F0FFF4; border-color: #C6F6D5; }}
    .cp-badge-in-progress {{ color: {theme.accent_teal}; background: #E6FFFA; border-color: #B2F5EA; }}
    .cp-badge-planned {{ color: {theme.text_muted}; background: {theme.secondary_background}; }}

    /* ---------- Workflow strip ---------- */
    .cp-workflow {{ display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center; }}
    .cp-step {{
        background: {theme.background};
        border: 1px solid {theme.border};
        border-left: 3px solid {theme.accent_teal};
        border-radius: 6px;
        padding: 0.45rem 0.9rem;
        font-weight: 600;
        color: {theme.primary_navy};
        font-size: 0.9rem;
    }}
    .cp-arrow {{ color: {theme.text_muted}; }}

    /* ---------- Status table ---------- */
    .cp-table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
    .cp-table th {{
        text-align: left;
        color: {theme.text_muted};
        font-weight: 600;
        font-size: 0.76rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        border-bottom: 1px solid {theme.border};
        padding: 0.6rem 0.75rem;
    }}
    .cp-table td {{ border-bottom: 1px solid {theme.border}; padding: 0.65rem 0.75rem; }}
    .cp-table td.cp-phase {{ color: {theme.primary_navy}; font-weight: 600; white-space: nowrap; }}

    /* ---------- Footer ---------- */
    .cp-footer {{
        color: {theme.text_muted};
        font-size: 0.8rem;
        border-top: 1px solid {theme.border};
        margin-top: 2.5rem;
        padding-top: 1rem;
    }}
</style>
"""


def apply_theme(theme: ThemeSettings = THEME) -> None:
    """Inject the global stylesheet into the current Streamlit page.

    Args:
        theme: Colour and typography settings.
    """
    st.markdown(build_css(theme), unsafe_allow_html=True)
