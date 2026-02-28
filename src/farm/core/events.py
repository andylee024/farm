"""Event helper constructors."""

from __future__ import annotations

from typing import Any

from farm.core.models import EventType, TaskEvent, TaskState


def transition_event(
    *,
    task_id: str,
    from_state: TaskState,
    to_state: TaskState,
    message: str,
    payload: dict[str, Any] | None = None,
) -> TaskEvent:
    return TaskEvent(
        task_id=task_id,
        event_type=EventType.STATE_TRANSITION,
        message=message,
        from_state=from_state,
        to_state=to_state,
        payload=payload or {},
    )


def info_event(
    *,
    task_id: str,
    message: str,
    payload: dict[str, Any] | None = None,
) -> TaskEvent:
    return TaskEvent(
        task_id=task_id,
        event_type=EventType.INFO,
        message=message,
        payload=payload or {},
    )


def error_event(
    *,
    task_id: str,
    message: str,
    payload: dict[str, Any] | None = None,
) -> TaskEvent:
    return TaskEvent(
        task_id=task_id,
        event_type=EventType.ERROR,
        message=message,
        payload=payload or {},
    )
