"""
TRACK Stage: Action Tracker Service and Database Model for CreditPulse AI.

Provides SQLite persistence for operationalizing recommendations:
- Record recommended actions from the PRESCRIBE engine or user input.
- Assign action owners, priorities, and target due dates.
- Track lifecycle status: Planned -> In Progress -> Under Review -> Completed.
- Log measurable business outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import Column, Date, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config.settings import APP
from database.connection import get_engine
from src.intelligence.recommendations import Recommendation


class Base(DeclarativeBase):
    pass


class ActionModel(Base):
    """SQLAlchemy model for tracked operational credit actions."""

    __tablename__ = "actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rec_id = Column(String(50), nullable=True)
    finding_id = Column(String(50), nullable=True)
    title = Column(String(200), nullable=False)
    pillar = Column(String(50), nullable=False, default="Policy")
    priority = Column(String(50), nullable=False, default="P2 - High")
    owner = Column(String(100), nullable=False)
    due_date = Column(Date, nullable=False)
    status = Column(String(50), nullable=False, default="Planned")
    action_summary = Column(Text, nullable=False)
    expected_impact = Column(Text, nullable=True)
    outcome_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


@dataclass
class ActionItem:
    """In-memory domain model for an Action."""

    id: int | None
    rec_id: str | None
    finding_id: str | None
    title: str
    pillar: str
    priority: str
    owner: str
    due_date: date
    status: str
    action_summary: str
    expected_impact: str | None
    outcome_notes: str | None = None
    created_at: datetime | None = None


def init_action_table() -> None:
    """Ensure the actions table exists in the SQLite database."""
    engine = get_engine()
    Base.metadata.create_all(engine)


def list_actions() -> list[ActionItem]:
    """Retrieve all tracked action items ordered by priority and due date."""
    init_action_table()
    engine = get_engine()
    with Session(engine) as session:
        records = session.query(ActionModel).order_by(ActionModel.id.asc()).all()
        return [
            ActionItem(
                id=r.id,
                rec_id=r.rec_id,
                finding_id=r.finding_id,
                title=r.title,
                pillar=r.pillar,
                priority=r.priority,
                owner=r.owner,
                due_date=r.due_date,
                status=r.status,
                action_summary=r.action_summary,
                expected_impact=r.expected_impact,
                outcome_notes=r.outcome_notes,
                created_at=r.created_at,
            )
            for r in records
        ]


def create_action(
    title: str,
    owner: str,
    due_date: date,
    pillar: str = "Policy",
    priority: str = "P2 - High",
    action_summary: str = "",
    expected_impact: str = "",
    rec_id: str | None = None,
    finding_id: str | None = None,
) -> ActionItem:
    """Create and persist a new action item."""
    init_action_table()
    engine = get_engine()
    with Session(engine) as session:
        record = ActionModel(
            rec_id=rec_id,
            finding_id=finding_id,
            title=title,
            pillar=pillar,
            priority=priority,
            owner=owner,
            due_date=due_date,
            status="Planned",
            action_summary=action_summary,
            expected_impact=expected_impact,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return ActionItem(
            id=record.id,
            rec_id=record.rec_id,
            finding_id=record.finding_id,
            title=record.title,
            pillar=record.pillar,
            priority=record.priority,
            owner=record.owner,
            due_date=record.due_date,
            status=record.status,
            action_summary=record.action_summary,
            expected_impact=record.expected_impact,
            created_at=record.created_at,
        )


def update_action_status(action_id: int, new_status: str, outcome_notes: str | None = None) -> bool:
    """Update status and optional outcome notes for an action item."""
    init_action_table()
    engine = get_engine()
    with Session(engine) as session:
        record = session.query(ActionModel).filter(ActionModel.id == action_id).first()
        if not record:
            return False
        record.status = new_status
        if outcome_notes is not None:
            record.outcome_notes = outcome_notes
        record.updated_at = datetime.utcnow()
        session.commit()
        return True


def sync_recommendations_to_tracker(recommendations: list[Recommendation]) -> int:
    """Seed the action tracker with recommendations from the PRESCRIBE engine if not already tracked."""
    init_action_table()
    engine = get_engine()
    added_count = 0
    with Session(engine) as session:
        existing_recs = {r.rec_id for r in session.query(ActionModel.rec_id).all() if r.rec_id}
        for rec in recommendations:
            if rec.rec_id not in existing_recs:
                record = ActionModel(
                    rec_id=rec.rec_id,
                    finding_id=rec.finding_id,
                    title=rec.title,
                    pillar=rec.pillar,
                    priority=rec.priority,
                    owner=rec.suggested_owner,
                    due_date=date(2026, 12, 31),
                    status="Planned",
                    action_summary=rec.action_summary,
                    expected_impact=rec.expected_impact,
                )
                session.add(record)
                added_count += 1
        if added_count > 0:
            session.commit()
    return added_count
