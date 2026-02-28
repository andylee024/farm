from __future__ import annotations

import json
from pathlib import Path

import pytest

from farm.adapters.storage import TaskFilter
from farm.adapters.storage_json import JsonRegistryStore
from farm.core.errors import StorageError, TaskNotFoundError
from farm.core.events import info_event
from farm.core.models import TaskRecord, TaskState


def make_task(
    *,
    task_id: str,
    repo: str = "scout",
    state: TaskState = TaskState.DRAFTED,
) -> TaskRecord:
    return TaskRecord(task_id=task_id, repo=repo, linear_issue_id=f"LIN-{task_id}", state=state)


def test_store_bootstraps_registry_file(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.json"
    store = JsonRegistryStore(registry_path)

    registry = store.read_registry()

    assert registry_path.exists()
    assert registry.tasks == {}
    assert registry.events == []


def test_save_get_and_filter_tasks(tmp_path: Path) -> None:
    store = JsonRegistryStore(tmp_path / "registry.json")
    task_1 = make_task(task_id="TASK-1", state=TaskState.QUEUED)
    task_2 = make_task(task_id="TASK-2", repo="farm", state=TaskState.RUNNING)
    store.save_task(task_1)
    store.save_task(task_2)

    fetched = store.get_task("TASK-1")
    assert fetched.task_id == "TASK-1"

    queued = store.list_tasks(TaskFilter(state=TaskState.QUEUED))
    assert [task.task_id for task in queued] == ["TASK-1"]

    by_repo = store.list_tasks(TaskFilter(repo="farm"))
    assert [task.task_id for task in by_repo] == ["TASK-2"]


def test_get_missing_task_raises(tmp_path: Path) -> None:
    store = JsonRegistryStore(tmp_path / "registry.json")
    with pytest.raises(TaskNotFoundError):
        store.get_task("TASK-404")


def test_append_event_validates_task_identity(tmp_path: Path) -> None:
    store = JsonRegistryStore(tmp_path / "registry.json")
    task = make_task(task_id="TASK-1")
    store.save_task(task)

    event = info_event(task_id="TASK-1", message="hello")
    store.append_event("TASK-1", event)
    assert len(store.read_registry().events) == 1

    with pytest.raises(StorageError):
        store.append_event("TASK-1", info_event(task_id="TASK-2", message="bad"))

    with pytest.raises(TaskNotFoundError):
        store.append_event("TASK-404", info_event(task_id="TASK-404", message="missing"))


def test_legacy_runs_shape_is_accepted_as_empty_registry(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps({"runs": []}), encoding="utf-8")

    store = JsonRegistryStore(registry_path)
    registry = store.read_registry()

    assert registry.tasks == {}
    assert registry.events == []


def test_missing_tasks_field_is_not_treated_as_legacy_shape(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(
        json.dumps({"schema_version": 1, "events": []}),
        encoding="utf-8",
    )
    store = JsonRegistryStore(registry_path)

    with pytest.raises(StorageError):
        store.read_registry()


def test_schema_version_mismatch_raises(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": 999,
                "tasks": {},
                "events": [],
                "updated_at": "2026-01-01T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    store = JsonRegistryStore(registry_path)

    with pytest.raises(StorageError):
        store.read_registry()
