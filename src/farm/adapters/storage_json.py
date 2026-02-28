"""JSON-backed registry implementation."""

from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from pathlib import Path

from farm.adapters.storage import RegistryStore, TaskFilter
from farm.core.errors import StorageError, TaskNotFoundError
from farm.core.models import REGISTRY_SCHEMA_VERSION, RegistryData, TaskEvent, TaskRecord, utc_now


class JsonRegistryStore(RegistryStore):
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._global_lock = threading.RLock()
        self._task_locks: dict[str, threading.Lock] = {}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.write_registry(RegistryData())

    def read_registry(self) -> RegistryData:
        with self._global_lock:
            if not self.path.exists():
                return RegistryData()

            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise StorageError(f"Registry file contains invalid JSON: {self.path}") from exc

            # Backward compatibility: old shape was {"runs": []}.
            if (
                isinstance(payload, dict)
                and set(payload.keys()) == {"runs"}
                and isinstance(payload["runs"], list)
            ):
                return RegistryData()
            if (
                isinstance(payload, dict)
                and any(key in payload for key in ("schema_version", "events", "updated_at"))
                and "tasks" not in payload
            ):
                raise StorageError("Registry payload is missing required field: tasks")

            try:
                registry = RegistryData.model_validate(payload)
            except Exception as exc:  # pragma: no cover - pydantic error format varies
                raise StorageError(f"Registry schema validation failed: {exc}") from exc

            if registry.schema_version != REGISTRY_SCHEMA_VERSION:
                raise StorageError(
                    "Unsupported registry schema_version="
                    f"{registry.schema_version}; expected={REGISTRY_SCHEMA_VERSION}"
                )
            return registry

    def write_registry(self, registry: RegistryData) -> None:
        with self._global_lock:
            registry.updated_at = utc_now()
            payload = registry.model_dump(mode="json", exclude_none=True)
            tmp_path = self.path.with_suffix(".tmp")
            tmp_path.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            tmp_path.replace(self.path)

    def get_task(self, task_id: str) -> TaskRecord:
        registry = self.read_registry()
        task = registry.tasks.get(task_id)
        if task is None:
            raise TaskNotFoundError(f"Task not found: {task_id}")
        return task

    def save_task(self, task: TaskRecord) -> None:
        with self._global_lock:
            registry = self.read_registry()
            task.touch()
            registry.tasks[task.task_id] = task
            registry.updated_at = task.updated_at
            self.write_registry(registry)

    def list_tasks(self, task_filter: TaskFilter | None = None) -> list[TaskRecord]:
        registry = self.read_registry()
        tasks = list(registry.tasks.values())
        if task_filter is None:
            return sorted(tasks, key=lambda t: t.created_at)
        if task_filter.state is not None:
            tasks = [task for task in tasks if task.state == task_filter.state]
        if task_filter.repo:
            tasks = [task for task in tasks if task.repo == task_filter.repo]
        return sorted(tasks, key=lambda t: t.created_at)

    def append_event(self, task_id: str, event: TaskEvent) -> None:
        with self._global_lock:
            registry = self.read_registry()
            if event.task_id != task_id:
                raise StorageError(
                    f"Event task_id mismatch: event.task_id={event.task_id} expected={task_id}"
                )
            if task_id not in registry.tasks:
                raise TaskNotFoundError(f"Task not found: {task_id}")
            registry.events.append(event)
            registry.updated_at = event.created_at
            self.write_registry(registry)

    @contextmanager
    def lock_task(self, task_id: str):
        with self._global_lock:
            if task_id not in self._task_locks:
                self._task_locks[task_id] = threading.Lock()
            lock = self._task_locks[task_id]
        lock.acquire()
        try:
            yield
        finally:
            lock.release()
