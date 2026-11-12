"""
TRACK stage: action tracker service persisted in SQLite.

Status: placeholder, implemented in Phase 7.

Planned interface:
    - create_action(recommendation_id, title, owner, due_date) -> Action
    - update_status(action_id: int, status: ActionStatus) -> Action
    - record_outcome(action_id: int, outcome: str) -> Action
    - list_actions(status: ActionStatus | None = None) -> list[Action]
"""

from __future__ import annotations

__all__: list[str] = []  # populated when implemented in Phase 7
