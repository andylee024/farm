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
from farm.runtime.runner import TaskRunner
from farm.support.config import FarmConfig

logger = logging.getLogger("farm.daemon")


class FarmDaemon:
    """Polls Linear for Approved issues and launches them via TaskRunner."""

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
    ):
        self.config = config
        self.linear_client = linear_client
        self.config_path = config_path
        self.poll_interval = poll_interval
        self.max_concurrent = max_concurrent
        self.default_agent = default_agent
        self.repos = repos or list(config.repos.keys())
        self._runner = TaskRunner(
            config=config,
            linear_client=linear_client,
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
        active = self._active_sessions()
        active_count = len(active)
        logger.info("daemon: poll active=%d/%d", active_count, self.max_concurrent)

        if active_count >= self.max_concurrent:
            return

        for repo in self.repos:
            if active_count >= self.max_concurrent:
                break
            launched = self._poll_repo(repo, active)
            active_count += launched

    def _poll_repo(self, repo: str, active_sessions: set[str]) -> int:
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
            if len(active_sessions) + launched >= self.max_concurrent:
                break

            paths = task_paths(config=self.config, repo=repo, issue_id=issue.id)
            if paths.worktree.exists():
                logger.debug(
                    "daemon: skip %s (worktree exists)", issue.identifier or issue.id
                )
                continue

            try:
                result = self._runner.run(
                    issue_id=issue.id, repo=repo, agent=self.default_agent
                )
                logger.info(
                    "daemon: launched %s repo=%s session=%s",
                    issue.identifier or issue.id,
                    repo,
                    result["session"],
                )
                launched += 1
            except Exception:
                logger.exception(
                    "daemon: failed to launch %s", issue.identifier or issue.id
                )

        return launched

    def _active_sessions(self) -> set[str]:
        active: set[str] = set()
        for repo in self.repos:
            for snapshot in self._runner.pulse(repo=repo):
                if snapshot.get("session_alive"):
                    session = snapshot.get("session")
                    if isinstance(session, str):
                        active.add(session)
        return active

    def _handle_signal(self, signum: int, frame: Any) -> None:
        logger.info("daemon: received signal %d, shutting down", signum)
        self._shutdown = True
