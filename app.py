"""
CreditPulse AI: application entry point.

Run with:
    streamlit run app.py

This script is the router. It sets page configuration, applies the global
theme, and builds grouped sidebar navigation from the module registry in
``config.settings``. Page content lives in ``pages/``.
"""

from __future__ import annotations

from collections import defaultdict

import streamlit as st

from components.theme import apply_theme
from config.settings import APP, MODULES
from src.utils.logger import get_logger

logger = get_logger(__name__)


def build_navigation() -> dict[str, list[st.Page]]:
    """Build grouped navigation from the module registry.

    Returns:
        Mapping of sidebar section name to an ordered list of ``st.Page``.
    """
    sections: dict[str, list[st.Page]] = defaultdict(list)
    sections["Home"].append(
        st.Page("pages/home.py", title="Home", icon=":material/home:", default=True)
    )
    for module in MODULES:
        sections[module.section].append(
            st.Page(module.page, title=module.title, icon=module.icon, url_path=module.key)
        )
    return dict(sections)


def render_sidebar_footer() -> None:
    """Render product identity and build information in the sidebar."""
    with st.sidebar:
        st.markdown(f"**{APP.app_name}**")
        st.caption(f"Version {APP.version} · Phase {APP.current_phase} of 8")
        st.caption("Synthetic data only. No real borrower information.")


def ensure_data_ready() -> None:
    """Ensure synthetic data is ready; auto-generate on cloud boot if missing."""
    from config.settings import RAW_DATA_DIR
    from src.data.io import datasets_exist

    if not datasets_exist(RAW_DATA_DIR):
        logger.info("Datasets not found in %s; generating initial synthetic portfolio...", RAW_DATA_DIR)
        from src.data.pipeline import run_pipeline
        run_pipeline(load_sqlite=False)


def main() -> None:
    """Configure and launch the Streamlit application."""
    st.set_page_config(
        page_title=APP.app_name,
        page_icon=":material/monitoring:",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    apply_theme()
    ensure_data_ready()
    navigation = st.navigation(build_navigation())
    render_sidebar_footer()
    logger.debug("Rendering page: %s", navigation.title)
    navigation.run()


if __name__ == "__main__":
    main()
