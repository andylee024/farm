from __future__ import annotations

from pathlib import Path

from farm.adapters.storage_json import JsonRegistryStore
from farm.config import FarmConfig
from farm.core.models import AgentKind, TaskRecord, TaskState
from farm.services.launcher import Launcher
from farm.services.orchestrator import Orchestrator
from farm.services.scheduler import Scheduler


def build_config(tmp_path: Path) -> FarmConfig:
    repo_root = tmp_path / "repos"
    repo_root.mkdir(parents=True, exist_ok=True)
    scout_repo = repo_root / "scout"
    scout_repo.mkdir(parents=True, exist_ok=True)

    repos: dict[str, dict[str, str]] = {
        "scout": {
            "path": str(scout_repo),
            "default_branch": "main",
            "test_command": "pytest -q",
        }
    }
    return FarmConfig.model_validate(
        {
            "repos": repos,
            "worktree_root": str(tmp_path / "worktrees"),
            "agent_defaults": {
                "codex_model": "gpt-5.3-codex",
                "claude_model": "claude-opus-4.5",
            },
        }
    )


def make_queued_task() -> TaskRecord:
    return TaskRecord(
        task_id="TASK-QUEUED-1",
        repo="scout",
        linear_issue_id="LIN-1",
        state=TaskState.QUEUED,
        agent=AgentKind.CLAUDE,
    )


def test_scheduler_returns_oldest_queued_task(tmp_path: Path) -> None:
    store = JsonRegistryStore(tmp_path / "registry.json")
    first = TaskRecord(task_id="TASK-1", repo="scout", linear_issue_id="LIN-1", state=TaskState.QUEUED)
    second = TaskRecord(task_id="TASK-2", repo="scout", linear_issue_id="LIN-2", state=TaskState.QUEUED)
    store.save_task(first)
    store.save_task(second)

    scheduler = Scheduler(store)
    selected = scheduler.next_queued_task()

    assert selected is not None
    assert selected.task_id == "TASK-1"


def test_run_cycle_launches_task_to_pr_open(tmp_path: Path) -> None:
    store = JsonRegistryStore(tmp_path / "registry.json")
    config = build_config(tmp_path)
    task = make_queued_task()
    store.save_task(task)

    git_calls: list[tuple[str, list[str]]] = []
    tmux_calls: list[list[str]] = []

    def fake_git_runner(repo_path: str | Path, args: list[str]) -> str:
        git_calls.append((str(repo_path), args))
        return ""

    def fake_tmux_runner(args: list[str]) -> str:
        tmux_calls.append(args)
        return ""

    launcher = Launcher(
        store=store,
        config=config,
        git_runner=fake_git_runner,
        tmux_runner=fake_tmux_runner,
        pr_number_provider=lambda _: 456,
    )
    orchestrator = Orchestrator(store=store, config=config, launcher=launcher)

    result = orchestrator.run_cycle()

    assert result is not None
    assert result.started is True
    assert result.task_id == task.task_id
    assert result.pr_number == 456
    final_task = store.get_task(task.task_id)
    assert final_task.state == TaskState.PR_OPEN
    assert final_task.pr_number == 456
    assert final_task.branch is not None
    assert final_task.worktree_path is not None
    assert final_task.tmux_session is not None
    assert len(git_calls) == 1
    assert "worktree" in git_calls[0][1]
    assert len(tmux_calls) == 1
    assert "new-session" in tmux_calls[0]


def test_run_cycle_no_queued_tasks_returns_none(tmp_path: Path) -> None:
    store = JsonRegistryStore(tmp_path / "registry.json")
    config = build_config(tmp_path)
    orchestrator = Orchestrator(store=store, config=config)

    result = orchestrator.run_cycle()

    assert result is None
