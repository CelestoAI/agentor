from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from agents import Runner
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from agentor.durable.models import (
    RunStatus,
    WorkflowEvent,
    WorkflowRun,
    WorkflowTask,
    utcnow,
)
from agentor.tools.registry import CelestoConfig

logger = logging.getLogger(__name__)

TERMINAL_STATUSES: set[str] = {
    RunStatus.completed.value,
    RunStatus.failed.value,
    RunStatus.canceled.value,
}


def _is_postgres(engine: AsyncEngine) -> bool:
    return engine.url.get_backend_name().startswith("postgres")


@dataclass
class DurableRunHandle:
    """User-facing run handle with async + sync helpers."""

    run_id: str
    session_factory: async_sessionmaker[AsyncSession]

    async def status(self) -> str:
        async with self.session_factory() as session:
            run = await session.get(WorkflowRun, self.run_id)
            if run is None:
                raise RuntimeError(f"Run {self.run_id} not found")
            return run.status

    async def events(self) -> list[WorkflowEvent]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(WorkflowEvent)
                .where(WorkflowEvent.run_id == self.run_id)
                .order_by(WorkflowEvent.idx)
            )
            return list(result.scalars().all())

    async def wait(self, poll_interval: float = 0.5, timeout: Optional[float] = None):
        started = time.monotonic()
        while True:
            current_status = await self.status()
            if current_status in TERMINAL_STATUSES:
                return current_status
            if timeout and (time.monotonic() - started) > timeout:
                raise TimeoutError(f"Timed out waiting for run {self.run_id}")
            await asyncio.sleep(poll_interval)

    async def result(self) -> Any:
        events = await self.events()
        for event in reversed(events):
            if event.type == "run_completed":
                return event.data.get("output")
        raise RuntimeError(f"Run {self.run_id} has not completed")

    # Sync helpers ---------------------------------------------------------
    def wait_sync(self, poll_interval: float = 0.5, timeout: Optional[float] = None):
        return asyncio.run(self.wait(poll_interval=poll_interval, timeout=timeout))

    def result_sync(self) -> Any:
        return asyncio.run(self.result())

    def events_sync(self) -> list[WorkflowEvent]:
        return asyncio.run(self.events())


class DurableAgentRunner:
    """Durable execution harness for Agentor."""

    def __init__(
        self,
        agent: Any,
        engine: AsyncEngine,
        session_factory: Optional[async_sessionmaker[AsyncSession]] = None,
        org_id: Optional[str] = None,
        deployment_id: Optional[str] = None,
        lease_seconds: int = 30,
        max_attempts: int = 10,
    ) -> None:
        self.agent = agent
        self.engine = engine
        self.session_factory = session_factory or async_sessionmaker(
            engine, expire_on_commit=False
        )
        self.org_id = org_id
        self.deployment_id = deployment_id
        self.lease_duration = timedelta(seconds=lease_seconds)
        self.max_attempts = max_attempts
        self.worker_id = f"worker_{uuid.uuid4().hex}"
        self.supports_skip_locked = _is_postgres(engine)

    async def start_run(
        self,
        goal: str,
        inline: bool = True,
        parent_run_id: Optional[str] = None,
    ) -> DurableRunHandle:
        """Create a run + initial task; optionally process inline."""
        async with self.session_factory() as session:
            run = WorkflowRun(
                goal=goal,
                status=RunStatus.running.value,
                org_id=self.org_id,
                deployment_id=self.deployment_id,
                parent_run_id=parent_run_id,
            )
            session.add(run)
            await session.flush()

            initial_event = WorkflowEvent(
                run_id=run.id,
                idx=0,
                type="user_message",
                data={"text": goal},
            )
            initial_task = WorkflowTask(
                run_id=run.id,
                execute_at=utcnow(),
                payload={"type": "agent_step", "input": goal},
            )
            session.add_all([initial_event, initial_task])
            await session.commit()

        handle = DurableRunHandle(run_id=run.id, session_factory=self.session_factory)

        if inline:
            await self.process_pending(run_id=run.id)

        return handle

    def start_run_sync(
        self, goal: str, inline: bool = True, parent_run_id: Optional[str] = None
    ) -> DurableRunHandle:
        return asyncio.run(
            self.start_run(goal=goal, inline=inline, parent_run_id=parent_run_id)
        )

    async def process_pending(self, run_id: Optional[str] = None) -> None:
        """Process tasks for a specific run (or all runs if run_id is None)."""
        while True:
            task = await self._dequeue_task(run_id=run_id)
            if task is None:
                break
            await self._execute_task(task)

    async def _dequeue_task(
        self, run_id: Optional[str] = None
    ) -> Optional[WorkflowTask]:
        now = datetime.now(timezone.utc)
        async with self.session_factory() as session:
            query: Select[tuple[WorkflowTask]] = (
                select(WorkflowTask)
                .where(
                    WorkflowTask.execute_at <= now,
                    # Either no lease or lease expired
                    or_(
                        WorkflowTask.lease_expires_at.is_(None),
                        WorkflowTask.lease_expires_at < now,
                    ),
                )
                .order_by(
                    WorkflowTask.execute_at,
                    WorkflowTask.priority,
                    WorkflowTask.id,
                )
                .limit(1)
            )
            if run_id:
                query = query.where(WorkflowTask.run_id == run_id)

            if self.supports_skip_locked:
                query = query.with_for_update(skip_locked=True)

            result = await session.execute(query)
            task = result.scalars().first()
            if task is None:
                return None

            task.worker_id = self.worker_id
            task.lease_expires_at = now + self.lease_duration
            await session.commit()
            return task

    async def _execute_task(self, task: WorkflowTask) -> None:
        async with self.session_factory() as session:
            # Reload with a lock when supported to avoid double processing
            locked_task = await session.get(
                WorkflowTask,
                task.id,
                with_for_update=self.supports_skip_locked,
                options=[selectinload(WorkflowTask.run)],
            )
            if locked_task is None:
                return

            run = locked_task.run
            if run is None:
                await session.delete(locked_task)
                await session.commit()
                return

            next_idx = await self._next_event_idx(session, run.id)

            try:
                agent_result = await asyncio.to_thread(
                    Runner.run_sync, self.agent, run.goal, context=CelestoConfig()
                )
                final_output = getattr(agent_result, "final_output", agent_result)

                events: list[WorkflowEvent] = [
                    WorkflowEvent(
                        run_id=run.id,
                        idx=next_idx,
                        type="assistant_message",
                        data={"output": final_output},
                    ),
                    WorkflowEvent(
                        run_id=run.id,
                        idx=next_idx + 1,
                        type="run_completed",
                        data={"output": final_output},
                    ),
                ]

                run.status = RunStatus.completed.value
                session.add_all(events)
                await session.delete(locked_task)
                await session.commit()
            except Exception as exc:  # noqa: BLE001
                locked_task.attempts += 1
                run.status = RunStatus.failed.value

                failure_event = WorkflowEvent(
                    run_id=run.id,
                    idx=next_idx,
                    type="run_failed",
                    data={"error": str(exc)},
                )
                session.add(failure_event)

                await session.delete(locked_task)
                await session.commit()

                logger.exception("Durable run %s failed: %s", run.id, exc)

                if locked_task.attempts >= self.max_attempts:
                    return
                raise

    async def _next_event_idx(self, session: AsyncSession, run_id: str) -> int:
        result = await session.execute(
            select(func.max(WorkflowEvent.idx)).where(WorkflowEvent.run_id == run_id)
        )
        current = result.scalar()
        return 0 if current is None else int(current) + 1
