from __future__ import annotations

import pytest

from farm.core.errors import InvalidTransitionError
from farm.core.models import TaskRecord, TaskState
from farm.core.state_machine import can_transition, transition


def make_task(*, state: TaskState = TaskState.DRAFTED, attempt: int = 0) -> TaskRecord:
    return TaskRecord(
        task_id="TASK-1",
        repo="scout",
        linear_issue_id="LIN-1",
        state=state,
        attempt=attempt,
    )


def test_happy_path_with_one_retry() -> None:
    task = make_task()

    for target in [
        TaskState.QUEUED,
        TaskState.RUNNING,
        TaskState.PR_OPEN,
        TaskState.TESTS_FAILED,
        TaskState.RETRYING,
        TaskState.RUNNING,
        TaskState.PR_OPEN,
        TaskState.TESTS_PASSED,
        TaskState.READY_FOR_REVIEW,
    ]:
        transition(task, target)

    assert task.state == TaskState.READY_FOR_REVIEW
    assert task.attempt == 1


def test_invalid_transition_raises() -> None:
    task = make_task()
    with pytest.raises(InvalidTransitionError):
        transition(task, TaskState.RUNNING)


def test_retry_increments_attempt() -> None:
    task = make_task(state=TaskState.TESTS_FAILED)
    transition(task, TaskState.RETRYING)
    assert task.attempt == 1
    assert task.state == TaskState.RETRYING


def test_retry_beyond_cap_raises() -> None:
    task = make_task(state=TaskState.TESTS_FAILED, attempt=2)
    with pytest.raises(InvalidTransitionError):
        transition(task, TaskState.RETRYING)


def test_can_transition_matrix_basics() -> None:
    assert can_transition(TaskState.DRAFTED, TaskState.QUEUED)
    assert can_transition(TaskState.DRAFTED, TaskState.CANCELED)
    assert not can_transition(TaskState.DRAFTED, TaskState.RUNNING)


def test_cancel_transition_from_queued() -> None:
    task = make_task(state=TaskState.QUEUED)
    transition(task, TaskState.CANCELED)
    assert task.state == TaskState.CANCELED
