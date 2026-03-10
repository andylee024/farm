from __future__ import annotations

from pathlib import Path

from farm.adapters.linear import LinearIssue
from farm.runtime.daemon import FarmDaemon
from farm.runtime.models import Agent
from farm.support.config import FarmConfig


class FakeLinearClient:
    def __init__(self, issues_by_project: dict[str, list[LinearIssue]]) -> None:
        self.issues_by_project = issues_by_project
        self.moved: list[tuple[str, str]] = []
        self._state_ids = {"approved": "state-approved", "coding": "state-coding"}

    def get_issue(self, issue_id: str) -> LinearIssue:
        for issues in self.issues_by_project.values():
            for issue in issues:
                if issue.id == issue_id or issue.identifier == issue_id:
                    return issue
        raise ValueError(f"Issue not found: {issue_id}")

    def get_state_id(self, state_name: str) -> str:
        return self._state_ids[state_name.lower()]

    def list_issues_by_state(self, *, state_name: str, project_name: str) -> list[LinearIssue]:
        _ = state_name
        return self.issues_by_project.get(project_name, [])

    def move_issue_to_status(self, issue_id: str, status_name: str) -> None:
        self.moved.append((issue_id, status_name))


def _make_issue(issue_id: str, identifier: str, project: str = "farm") -> LinearIssue:
    return LinearIssue(
        id=issue_id,
        identifier=identifier,
        title=f"Task {identifier}",
        description="desc",
        parent_id=None,
        state_name="Approved",
        project_name=project,
    )


def _build_config(tmp_path: Path) -> FarmConfig:
    repo_root = tmp_path / "repos" / "farm"
    repo_root.mkdir(parents=True, exist_ok=True)
    return FarmConfig.model_validate(
        {
            "repos": {
                "farm": {
                    "path": str(repo_root),
                    "default_branch": "main",
                    "test_command": "pytest -q",
                }
            },
            "worktree_root": str(tmp_path / "worktrees"),
        }
    )


def test_poll_cycle_launches_approved_issue(tmp_path: Path) -> None:
    cfg = _build_config(tmp_path)
    issue = _make_issue("uuid-1", "FARM-1")
    linear = FakeLinearClient({"farm": [issue]})

    git_calls: list[list[str]] = []
    tmux_calls: list[list[str]] = []

    def fake_git(repo_path, args):
        _ = repo_path
        git_calls.append(args)
        return ""

    def fake_tmux(args):
        tmux_calls.append(args)
        if args[:2] == ["has-session", "-t"]:
            raise RuntimeError("no session")
        return ""

    from farm.runtime.runner import TaskRunner

    runner = TaskRunner(config=cfg, linear_client=linear, git_runner=fake_git, tmux_runner=fake_tmux)

    daemon = FarmDaemon(
        config=cfg,
        linear_client=linear,
        poll_interval=1.0,
        max_concurrent=1,
        default_agent=Agent.CODEX,
        repos=["farm"],
    )
    daemon._runner = runner  # noqa: SLF001

    daemon._poll_cycle()  # noqa: SLF001

    assert linear.moved == [("uuid-1", "Coding")]
    assert any("worktree" in c for c in git_calls)
    assert any("new-session" in c for c in tmux_calls)


def test_poll_cycle_skips_existing_worktree(tmp_path: Path) -> None:
    cfg = _build_config(tmp_path)
    issue = _make_issue("uuid-1", "FARM-1")
    linear = FakeLinearClient({"farm": [issue]})

    # Pre-create the worktree directory to simulate already-running task
    worktree = Path(cfg.worktree_root) / "farm" / "uuid-1"
    worktree.mkdir(parents=True, exist_ok=True)

    def fake_tmux(args):
        if args[:2] == ["has-session", "-t"]:
            raise RuntimeError("no session")
        return ""

    from farm.runtime.runner import TaskRunner

    runner = TaskRunner(config=cfg, linear_client=linear, tmux_runner=fake_tmux)

    daemon = FarmDaemon(
        config=cfg,
        linear_client=linear,
        poll_interval=1.0,
        max_concurrent=1,
        default_agent=Agent.CODEX,
        repos=["farm"],
    )
    daemon._runner = runner  # noqa: SLF001

    daemon._poll_cycle()  # noqa: SLF001

    # Should not have tried to move or launch anything
    assert linear.moved == []


def test_poll_cycle_respects_max_concurrent(tmp_path: Path) -> None:
    cfg = _build_config(tmp_path)
    issues = [
        _make_issue("uuid-1", "FARM-1"),
        _make_issue("uuid-2", "FARM-2"),
    ]
    linear = FakeLinearClient({"farm": issues})

    launched_sessions: list[str] = []

    def fake_git(repo_path, args):
        _ = repo_path
        return ""

    def fake_tmux(args):
        if args[:2] == ["has-session", "-t"]:
            raise RuntimeError("no session")
        if args[0] == "new-session":
            session_idx = args.index("-s") + 1
            launched_sessions.append(args[session_idx])
        return ""

    from farm.runtime.runner import TaskRunner

    runner = TaskRunner(config=cfg, linear_client=linear, git_runner=fake_git, tmux_runner=fake_tmux)

    daemon = FarmDaemon(
        config=cfg,
        linear_client=linear,
        poll_interval=1.0,
        max_concurrent=1,
        default_agent=Agent.CODEX,
        repos=["farm"],
    )
    daemon._runner = runner  # noqa: SLF001

    daemon._poll_cycle()  # noqa: SLF001

    # Only one should have launched due to max_concurrent=1
    assert len(launched_sessions) == 1


def test_active_sessions_counts_live_tmux(tmp_path: Path) -> None:
    cfg = _build_config(tmp_path)
    linear = FakeLinearClient({})

    # Create a task directory with artifacts so pulse discovers it
    task_dir = Path(cfg.worktree_root) / "farm" / "uuid-1" / ".farm"
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "task_updates.jsonl").write_text(
        '{"schema_version":1,"ts":"2026-01-01T00:00:00Z","issue_id":"uuid-1","repo":"farm","phase":"running","summary":"x"}\n'
    )

    # Make get_issue work for pulse
    linear.issues_by_project["farm"] = [_make_issue("uuid-1", "FARM-1")]

    def fake_tmux(args):
        if args[:2] == ["has-session", "-t"]:
            return ""  # session alive
        return ""

    from farm.runtime.runner import TaskRunner

    runner = TaskRunner(config=cfg, linear_client=linear, tmux_runner=fake_tmux)

    daemon = FarmDaemon(
        config=cfg,
        linear_client=linear,
        poll_interval=1.0,
        max_concurrent=2,
        default_agent=Agent.CODEX,
        repos=["farm"],
    )
    daemon._runner = runner  # noqa: SLF001

    active = daemon._active_sessions()  # noqa: SLF001
    assert len(active) == 1


def test_signal_sets_shutdown_flag() -> None:
    cfg = FarmConfig.model_validate(
        {
            "repos": {},
            "worktree_root": "/tmp/worktrees",
        }
    )
    linear = FakeLinearClient({})

    daemon = FarmDaemon(
        config=cfg,
        linear_client=linear,
        poll_interval=1.0,
        max_concurrent=1,
        default_agent=Agent.CODEX,
    )

    assert daemon._shutdown is False  # noqa: SLF001
    daemon._handle_signal(2, None)  # noqa: SLF001
    assert daemon._shutdown is True  # noqa: SLF001
