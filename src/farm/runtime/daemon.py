"""Polling daemon that auto-launches approved Linear issues."""

from __future__ import annotations

import logging
import signal
import time
from pathlib import Path
from typing import Any

from farm.adapters.linear import LinearClient
from farm.runtime.models import Agent
from farm.runtime.paths import task_paths
from farm.runtime.runtime_factory import build_task_runtime
from farm.runtime.task_service import TaskService
from farm.support.config import FarmConfig

logger = logging.getLogger("farm.daemon")


class FarmDaemon:
    """Polls Linear for Approved issues and launches them via TaskService."""

    def __init__(
        self,
        *,
        config: FarmConfig,
        linear_client: LinearClient,
        config_path: Path | None = None,
        poll_interval: float = 30.0,
        max_concurrent: int = 1,
        default_agent: Agent = Agent.CODEX,
        repos: list[str] | None = None,
        task_service: TaskService | None = None,
    ):
        self.config = config
        self.linear_client = linear_client
        self.config_path = config_path
        self.poll_interval = poll_interval
        self.max_concurrent = max_concurrent
        self.default_agent = default_agent
        self.repos = repos or list(config.repos.keys())
        self._service = task_service or TaskService(
            config=config,
            linear_client=linear_client,
            task_runtime=build_task_runtime(config),
            config_path=config_path,
        )
        self._shutdown = False

    def run(self) -> None:
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        logger.info(
            "daemon: started repos=%s interval=%.1fs max_concurrent=%d agent=%s",
            ",".join(self.repos),
            self.poll_interval,
            self.max_concurrent,
            self.default_agent.value,
        )

        while not self._shutdown:
            try:
                self._poll_cycle()
            except Exception:
                logger.exception("daemon: poll cycle error")
            if not self._shutdown:
                time.sleep(self.poll_interval)

        logger.info("daemon: stopped")

    def _poll_cycle(self) -> None:
        remaining_capacity = self.max_concurrent - self._active_task_count()
        logger.info(
            "daemon: poll active=%d/%d",
            self.max_concurrent - remaining_capacity,
            self.max_concurrent,
        )

        if remaining_capacity <= 0:
            return

        for repo in self.repos:
            if remaining_capacity <= 0:
                break
            launched = self._poll_repo(repo, remaining_capacity=remaining_capacity)
            remaining_capacity -= launched

    def _poll_repo(self, repo: str, *, remaining_capacity: int) -> int:
        try:
            issues = self.linear_client.list_issues_by_state(
                state_name="Approved", project_name=repo
            )
        except Exception:
            logger.exception("daemon: failed to list approved issues for repo=%s", repo)
            return 0

        launched = 0
        for issue in issues:
            if self._shutdown:
                break
            if launched >= remaining_capacity:
                break

            if issue.parent_id is None:
                logger.debug(
                    "daemon: skip %s (not a child issue)", issue.identifier or issue.id
                )
                continue

            paths = task_paths(config=self.config, repo=repo, issue_id=issue.id)
            if paths.task_dir.exists():
                logger.debug(
                    "daemon: skip %s (task dir exists)", issue.identifier or issue.id
                )
                continue

            try:
                result = self._service.run(
                    issue_id=issue.id, repo=repo, agent=self.default_agent
                )
                logger.info(
                    "daemon: launched %s repo=%s runtime=%s handle=%s",
                    issue.identifier or issue.id,
                    repo,
                    result["runtime"],
                    result.get("runtime_handle", "-"),
                )
                launched += 1
            except Exception:
                if paths.task_dir.exists():
                    logger.exception(
                        "daemon: failed to launch %s after creating task dir; reserving capacity",
                        issue.identifier or issue.id,
                    )
                    launched += 1
                else:
                    logger.exception(
                        "daemon: failed to launch %s", issue.identifier or issue.id
                    )

        return launched

    def _active_task_count(self) -> int:
        active_count = 0
        for repo in self.repos:
            for snapshot in self._service.pulse(repo=repo):
                if snapshot.get("runtime_alive"):
                    active_count += 1
        return active_count

    def _handle_signal(self, signum: int, frame: Any) -> None:
        logger.info("daemon: received signal %d, shutting down", signum)
        self._shutdown = True
