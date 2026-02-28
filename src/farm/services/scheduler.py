"""Task selection and queue management."""

from __future__ import annotations

from farm.adapters.storage import RegistryStore, TaskFilter
from farm.core.models import TaskRecord, TaskState


class Scheduler:
    """Picks the next task(s) eligible for execution."""

    def __init__(self, store: RegistryStore):
        self.store = store

    def next_queued_task(self, *, repo: str | None = None) -> TaskRecord | None:
        task_filter = TaskFilter(state=TaskState.QUEUED, repo=repo)
        queued_tasks = self.store.list_tasks(task_filter)
        if not queued_tasks:
            return None
        return queued_tasks[0]
