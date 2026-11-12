"""
Action Tracker Dashboard.

Implements the TRACK stage of the intelligence workflow:
- Tracks operational recommendations to execution.
- Add and assign actions with owners, priorities, and deadlines.
- Lifecycle status tracking: Planned -> In Progress -> Under Review -> Completed.
- Measure and record business outcomes.
"""

from __future__ import annotations

from datetime import date
import pandas as pd
import streamlit as st

from components.layout import render_footer, render_header, render_section_title
from config.settings import RAW_DATA_DIR, THEME
from src.actions.tracker import (
    create_action,
    list_actions,
    sync_recommendations_to_tracker,
    update_action_status,
)
from src.data.io import datasets_exist, load_portfolio
from src.intelligence.anomaly_detection import run_full_anomaly_scan
from src.intelligence.recommendations import generate_prescriptive_recommendations


def main() -> None:
    render_header(
        title="Action Tracker",
        subtitle="Operationalizing credit risk intelligence: track recommended policy changes, assign leads, and monitor measured outcomes.",
        eyebrow="Operations",
    )

    # Auto-sync recommendations from intelligence engine into action tracker
    if datasets_exist(RAW_DATA_DIR):
        p = load_portfolio(RAW_DATA_DIR)
        loans = p.loans
        if "customer_segment" not in loans.columns:
            loans = loans.merge(p.customers[["customer_id", "customer_segment"]], on="customer_id", how="left")
        findings = run_full_anomaly_scan(loans, p.repayments)
        recs = generate_prescriptive_recommendations(findings)
        sync_recommendations_to_tracker(recs)

    actions = list_actions()

    # ---------------------------------------------------------
    # Action Status Overview
    # ---------------------------------------------------------
    render_section_title("Execution Status Overview", "TRACK Stage: Operational Accountability")

    status_counts = {"Planned": 0, "In Progress": 0, "Under Review": 0, "Completed": 0}
    for a in actions:
        if a.status in status_counts:
            status_counts[a.status] += 1

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Planned Actions", status_counts["Planned"])
    with k2:
        st.metric("In Progress", status_counts["In Progress"])
    with k3:
        st.metric("Under Review", status_counts["Under Review"])
    with k4:
        st.metric("Completed", status_counts["Completed"])

    st.write("")

    # ---------------------------------------------------------
    # Actions Table & Quick Status Updater
    # ---------------------------------------------------------
    render_section_title("Tracked Credit Interventions")

    if not actions:
        st.info("No action items currently tracked. Use the form below to create one.")
    else:
        action_rows = []
        for a in actions:
            action_rows.append(
                {
                    "ID": a.id,
                    "Ref": a.rec_id or "Manual",
                    "Pillar": a.pillar,
                    "Priority": a.priority,
                    "Title": a.title,
                    "Owner": a.owner,
                    "Due Date": str(a.due_date),
                    "Status": a.status,
                    "Outcome Notes": a.outcome_notes or "Pending",
                }
            )

        df_actions = pd.DataFrame(action_rows)
        st.dataframe(df_actions, hide_index=True, use_container_width=True)

        st.write("")
        # Action Update Form
        with st.expander("Update Action Status or Record Outcome"):
            up_col1, up_col2, up_col3 = st.columns(3)
            with up_col1:
                action_options = {f"#{a.id}: {a.title} ({a.owner})": a.id for a in actions}
                selected_label = st.selectbox("Select Action to Update", list(action_options.keys()))
                target_id = action_options[selected_label]
            with up_col2:
                new_status = st.selectbox(
                    "New Status",
                    ["Planned", "In Progress", "Under Review", "Completed"],
                    index=1,
                )
            with up_col3:
                notes = st.text_input("Outcome / Progress Notes", placeholder="e.g. Approved by CRO committee.")

            if st.button("Save Action Update"):
                update_action_status(target_id, new_status, outcome_notes=notes if notes else None)
                st.success(f"Action #{target_id} updated to '{new_status}' successfully!")
                st.rerun()

    # ---------------------------------------------------------
    # Add Manual Action
    # ---------------------------------------------------------
    render_section_title("Log New Operational Action")
    with st.expander("Create Custom Action Item"):
        with st.form("new_action_form"):
            f_col1, f_col2 = st.columns(2)
            with f_col1:
                title = st.text_input("Action Title", placeholder="e.g. Conduct Special Branch Recovery Drive")
                owner = st.text_input("Assigned Owner", placeholder="e.g. Regional Credit Lead - West")
                due = st.date_input("Target Due Date", value=date(2026, 12, 31))
            with f_col2:
                pillar = st.selectbox("Pillar", ["Underwriting", "Collections", "Exposure", "Policy", "Audit"])
                priority = st.selectbox("Priority", ["P1 - Critical", "P2 - High", "P3 - Moderate"])
                impact = st.text_input("Expected Impact", placeholder="e.g. Reduce FPD by 20 bps")

            summary = st.text_area("Detailed Action Summary", placeholder="Specify specific operational tasks...")
            submitted = st.form_submit_button("Create Action Item")

            if submitted:
                if not title or not owner:
                    st.error("Action Title and Owner are required.")
                else:
                    create_action(
                        title=title,
                        owner=owner,
                        due_date=due,
                        pillar=pillar,
                        priority=priority,
                        action_summary=summary,
                        expected_impact=impact,
                    )
                    st.success("New operational action item recorded and persisted!")
                    st.rerun()

    render_footer()


if __name__ == "__main__":
    main()
