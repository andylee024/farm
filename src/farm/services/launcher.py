"""Execution launcher for worktree + tmux + agent runtime."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from farm.adapters.git import run_git
from farm.adapters.storage import RegistryStore
from farm.adapters.tmux import run_tmux
from farm.config import FarmConfig
from farm.core.events import info_event, transition_event
from farm.core.models import AgentKind, LaunchResult, TaskRecord, TaskState
from farm.core.state_machine import transition


GitRunner = Callable[[str | Path, list[str]], str]
TmuxRunner = Callable[[list[str]], str]


class Launcher:
    """Starts a single task execution environment."""

    def __init__(
        self,
        *,
        store: RegistryStore,
        config: FarmConfig,
        git_runner: GitRunner = run_git,
        tmux_runner: TmuxRunner = run_tmux,
        pr_number_provider: Callable[[TaskRecord], int | None] | None = None,
    ):
        self.store = store
        self.config = config
        self.git_runner = git_runner
        self.tmux_runner = tmux_runner
        self.pr_number_provider = pr_number_provider or (lambda _: None)

    def launch_task(self, task_id: str) -> LaunchResult:
        with self.store.lock_task(task_id):
            task = self.store.get_task(task_id)
            if task.state != TaskState.QUEUED:
                return LaunchResult(
                    started=False,
                    message=f"Task {task_id} is not launchable from state={task.state.value}",
                    task_id=task.task_id,
                )

            repo_config = self.config.repos.get(task.repo)
            if repo_config is None:
                return LaunchResult(
                    started=False,
                    message=f"No repo configuration found for repo={task.repo}",
                    task_id=task.task_id,
                )

            worktree_path = self._worktree_path(task)
            worktree_path.parent.mkdir(parents=True, exist_ok=True)
            branch_name = self._branch_name(task)
            tmux_session = self._session_name(task)
            startup_command = self._agent_startup_command(task)

            self.git_runner(
                repo_config.path,
                [
                    "worktree",
                    "add",
                    str(worktree_path),
                    "-b",
                    branch_name,
                    repo_config.default_branch,
                ],
            )
            self.tmux_runner(
                [
                    "new-session",
                    "-d",
                    "-s",
                    tmux_session,
                    "-c",
                    str(worktree_path),
                    startup_command,
                ]
            )

            task.worktree_path = str(worktree_path)
            task.branch = branch_name
            task.tmux_session = tmux_session

            self._persist_transition(task, TaskState.RUNNING, "Launcher started task runtime")

            task.pr_number = self.pr_number_provider(task)
            self._persist_transition(task, TaskState.PR_OPEN, "Task launch completed; awaiting verification")

            self.store.append_event(
                task.task_id,
                info_event(
                    task_id=task.task_id,
                    message="Launch artifacts recorded",
                    payload={
                        "worktree_path": task.worktree_path,
                        "branch": task.branch,
                        "tmux_session": task.tmux_session,
                        "agent": task.agent.value,
                    },
                ),
            )
            return LaunchResult(
                started=True,
                message="Task launched",
                task_id=task.task_id,
                pr_number=task.pr_number,
            )

    def _persist_transition(self, task: TaskRecord, to_state: TaskState, message: str) -> None:
        from_state, _ = transition(task, to_state)
        self.store.save_task(task)
        self.store.append_event(
            task.task_id,
            transition_event(
                task_id=task.task_id,
                from_state=from_state,
                to_state=to_state,
                message=message,
            ),
        )

    def _worktree_path(self, task: TaskRecord) -> Path:
        root = Path(self.config.worktree_root)
        return root / task.repo / task.task_id

    def _branch_name(self, task: TaskRecord) -> str:
        return f"farm/{self._slug(task.task_id)}-attempt-{task.attempt}"

    def _session_name(self, task: TaskRecord) -> str:
        return f"farm-{self._slug(task.task_id)}"

    def _agent_startup_command(self, task: TaskRecord) -> str:
        model = self._resolve_model(task.agent)
        return (
            "printf '%s\\n' "
            f"'farm launch task={task.task_id} agent={task.agent.value} model={model}'"
        )

    def _resolve_model(self, agent: AgentKind) -> str:
        if agent == AgentKind.CLAUDE:
            return self.config.agent_defaults.claude_model
        return self.config.agent_defaults.codex_model

    @staticmethod
    def _slug(value: str) -> str:
        return re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-").lower()
