from __future__ import annotations

import datetime as dt
import uuid
from enum import Enum
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Base(DeclarativeBase):
    pass


class RunStatus(str, Enum):
    running = "running"
    completed = "completed"
    failed = "failed"
    waiting_signal = "waiting_signal"
    paused = "paused"
    canceled = "canceled"


def _run_id() -> str:
    return f"run_{uuid.uuid4().hex}"


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_run_id)
    org_id: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, index=True
    )
    deployment_id: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, index=True
    )
    goal: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[RunStatus] = mapped_column(
        String(32), default=RunStatus.running.value, index=True
    )
    parent_run_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    events: Mapped[list["WorkflowEvent"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    tasks: Mapped[list["WorkflowTask"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class WorkflowEvent(Base):
    __tablename__ = "workflow_events"
    __table_args__ = (
        UniqueConstraint("run_id", "idx", name="uq_workflow_events_run_idx"),
        Index("ix_workflow_events_run_created", "run_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("workflow_runs.id", ondelete="CASCADE"), index=True
    )
    idx: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )

    run: Mapped["WorkflowRun"] = relationship(back_populates="events")


class WorkflowTask(Base):
    __tablename__ = "workflow_tasks"
    __table_args__ = (
        Index("ix_workflow_tasks_run", "run_id", "execute_at"),
        Index("ix_workflow_tasks_due", "execute_at", "priority"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("workflow_runs.id", ondelete="CASCADE"), index=True
    )
    execute_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    priority: Mapped[int] = mapped_column(Integer, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    worker_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    lease_expires_at: Mapped[Optional[dt.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )

    run: Mapped["WorkflowRun"] = relationship(back_populates="tasks")


class WorkflowSignal(Base):
    __tablename__ = "workflow_signals"
    __table_args__ = (
        Index("ix_workflow_signals_run", "run_id", "name"),
        Index("ix_workflow_signals_consumed", "consumed_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("workflow_runs.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    consumed_at: Mapped[Optional[dt.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class IdempotencyKey(Base):
    __tablename__ = "idempotency_cache"
    __table_args__ = (Index("ix_idempotency_expires", "expires_at"),)

    effect_key: Mapped[str] = mapped_column(String(256), primary_key=True)
    effect_hash: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    expires_at: Mapped[Optional[dt.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
