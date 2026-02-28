"""High-level orchestration entrypoints."""

from __future__ import annotations

from farm.adapters.storage import RegistryStore
from farm.config import FarmConfig
from farm.core.models import LaunchResult
from farm.services.launcher import Launcher
from farm.services.scheduler import Scheduler


class Orchestrator:
    """Coordinates scheduler and launcher runtime execution."""

    def __init__(
        self,
        *,
        store: RegistryStore,
        config: FarmConfig,
        scheduler: Scheduler | None = None,
        launcher: Launcher | None = None,
    ):
        self.store = store
        self.config = config
        self.scheduler = scheduler or Scheduler(store)
        self.launcher = launcher or Launcher(store=store, config=config)

    def run_cycle(self, *, repo: str | None = None) -> LaunchResult | None:
        next_task = self.scheduler.next_queued_task(repo=repo)
        if next_task is None:
            return None
        return self.launcher.launch_task(next_task.task_id)
