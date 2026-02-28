"""State transition rules for task lifecycle."""

from __future__ import annotations

from farm.core.errors import InvalidTransitionError
from farm.core.models import TaskRecord, TaskState

ALLOWED_TRANSITIONS: dict[TaskState, set[TaskState]] = {
    TaskState.DRAFTED: {TaskState.QUEUED, TaskState.CANCELED},
    TaskState.QUEUED: {TaskState.RUNNING, TaskState.CANCELED},
    TaskState.RUNNING: {TaskState.PR_OPEN, TaskState.CANCELED},
    TaskState.PR_OPEN: {TaskState.TESTS_PASSED, TaskState.TESTS_FAILED, TaskState.CANCELED},
    TaskState.TESTS_PASSED: {TaskState.READY_FOR_REVIEW, TaskState.CANCELED},
    TaskState.TESTS_FAILED: {TaskState.RETRYING, TaskState.BLOCKED_NEEDS_HUMAN, TaskState.CANCELED},
    TaskState.RETRYING: {TaskState.RUNNING},
    TaskState.READY_FOR_REVIEW: {TaskState.MERGED, TaskState.CHANGES_REQUESTED, TaskState.CANCELED},
    TaskState.CHANGES_REQUESTED: {TaskState.QUEUED, TaskState.CANCELED},
    TaskState.MERGED: set(),
    TaskState.BLOCKED_NEEDS_HUMAN: set(),
    TaskState.CANCELED: set(),
}


def can_transition(from_state: TaskState, to_state: TaskState) -> bool:
    return to_state in ALLOWED_TRANSITIONS[from_state]


def transition(task: TaskRecord, to_state: TaskState) -> tuple[TaskState, TaskState]:
    """Transition a task to a new valid state and update counters."""
    from_state = task.state
    if not can_transition(from_state, to_state):
        raise InvalidTransitionError(
            f"Invalid transition for task={task.task_id}: {from_state.value} -> {to_state.value}"
        )

    if to_state == TaskState.RETRYING:
        if task.attempt >= task.max_retries:
            raise InvalidTransitionError(
                f"Task {task.task_id} exhausted retries: attempt={task.attempt}, max={task.max_retries}"
            )
        task.attempt += 1

    task.state = to_state
    task.touch()
    return from_state, to_state
