"""Storage interfaces and filter models."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol

from farm.core.models import RegistryData, TaskEvent, TaskRecord, TaskState


@dataclass(slots=True)
class TaskFilter:
    state: TaskState | None = None
    repo: str | None = None


class RegistryStore(Protocol):
    def read_registry(self) -> RegistryData: ...

    def write_registry(self, registry: RegistryData) -> None: ...

    def get_task(self, task_id: str) -> TaskRecord: ...

    def save_task(self, task: TaskRecord) -> None: ...

    def list_tasks(self, task_filter: TaskFilter | None = None) -> list[TaskRecord]: ...

    def append_event(self, task_id: str, event: TaskEvent) -> None: ...

    def lock_task(self, task_id: str) -> AbstractContextManager[None]: ...
