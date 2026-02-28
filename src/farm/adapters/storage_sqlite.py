"""SQLite registry adapter placeholder for migration phase."""

from __future__ import annotations

from contextlib import contextmanager

from farm.adapters.storage import RegistryStore, TaskFilter
from farm.core.errors import StorageError
from farm.core.models import RegistryData, TaskEvent, TaskRecord


class SqliteRegistryStore(RegistryStore):
    """Stub adapter kept for the planned JSON -> SQLite migration path."""

    def __init__(self, path: str):
        self.path = path

    def _not_implemented(self) -> None:
        raise StorageError(
            "SQLite adapter is not implemented yet. Use JsonRegistryStore for V0."
        )

    def read_registry(self) -> RegistryData:
        self._not_implemented()

    def write_registry(self, registry: RegistryData) -> None:
        self._not_implemented()

    def get_task(self, task_id: str) -> TaskRecord:
        self._not_implemented()

    def save_task(self, task: TaskRecord) -> None:
        self._not_implemented()

    def list_tasks(self, task_filter: TaskFilter | None = None) -> list[TaskRecord]:
        self._not_implemented()

    def append_event(self, task_id: str, event: TaskEvent) -> None:
        self._not_implemented()

    @contextmanager
    def lock_task(self, task_id: str):
        self._not_implemented()
        yield
