from __future__ import annotations

from pathlib import Path

from farm.adapters.linear import LinearIssue
from farm.runtime.daemon import FarmDaemon
from farm.runtime.models import Agent
from farm.runtime.task_service import TaskService
from farm.runtime.tmux_task_runtime import TmuxTaskRuntime
from farm.support.config import FarmConfig


class FakeLinearClient:
    def __init__(self, issues_by_project: dict[str, list[LinearIssue]]) -> None:
        self.issues_by_project = issues_by_project
        self.moved: list[tuple[str, str]] = []

    def get_issue(self, issue_id: str) -> LinearIssue:
        for issues in self.issues_by_project.values():
            for issue in issues:
                if issue.id == issue_id or issue.identifier == issue_id:
                    return issue
        raise ValueError(f"Issue not found: {issue_id}")

    def list_issues_by_state(self, *, state_name: str, project_name: str) -> list[LinearIssue]:
        _ = state_name
        return self.issues_by_project.get(project_name, [])

    def move_issue_to_status(self, issue_id: str, status_name: str) -> None:
        self.moved.append((issue_id, status_name))


class FailingMoveLinearClient(FakeLinearClient):
    def __init__(self, issues_by_project: dict[str, list[LinearIssue]], failing_issue_id: str) -> None:
        super().__init__(issues_by_project)
        self.failing_issue_id = failing_issue_id

    def move_issue_to_status(self, issue_id: str, status_name: str) -> None:
        super().move_issue_to_status(issue_id, status_name)
        if issue_id == self.failing_issue_id:
            raise RuntimeError("simulated move failure")


def _make_issue(
    issue_id: str,
    identifier: str,
    *,
    project: str = "farm",
    parent_id: str | None = "parent-1",
) -> LinearIssue:
    return LinearIssue(
        id=issue_id,
        identifier=identifier,
        title=f"Task {identifier}",
        description="desc",
        parent_id=parent_id,
        state_name="Approved",
        project_name=project,
    )


def _build_config(tmp_path: Path) -> FarmConfig:
    farm_repo_root = tmp_path / "repos" / "farm"
    scout_repo_root = tmp_path / "repos" / "scout"
    farm_repo_root.mkdir(parents=True, exist_ok=True)
    scout_repo_root.mkdir(parents=True, exist_ok=True)
    return FarmConfig.model_validate(
        {
            "repos": {
                "farm": {
                    "path": str(farm_repo_root),
                    "default_branch": "main",
                    "test_command": "pytest -q",
                },
                "scout": {
                    "path": str(scout_repo_root),
                    "default_branch": "main",
                    "test_command": "pytest -q",
                },
            },
            "worktree_root": str(tmp_path / "worktrees"),
        }
    )


def _build_service(
    *,
    cfg: FarmConfig,
    linear: FakeLinearClient,
    git_runner=None,
    tmux_runner=None,
) -> TaskService:
    return TaskService(
        config=cfg,
        linear_client=linear,
        task_runtime=TmuxTaskRuntime(
            git_runner=git_runner or (lambda repo_path, args: ""),
            tmux_runner=tmux_runner or (lambda args: ""),
        ),
    )


def test_poll_cycle_launches_approved_child_issue(tmp_path: Path) -> None:
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

    service = _build_service(
        cfg=cfg,
        linear=linear,
        git_runner=fake_git,
        tmux_runner=fake_tmux,
    )
    daemon = FarmDaemon(
        config=cfg,
        linear_client=linear,
        poll_interval=1.0,
        max_concurrent=1,
        default_agent=Agent.CODEX,
        repos=["farm"],
        task_service=service,
    )

    daemon._poll_cycle()  # noqa: SLF001

    assert linear.moved == [("uuid-1", "Coding")]
    assert any("worktree" in call for call in git_calls)
    assert any("new-session" in call for call in tmux_calls)


def test_poll_cycle_skips_parent_issue(tmp_path: Path) -> None:
    cfg = _build_config(tmp_path)
    parent_issue = _make_issue("uuid-1", "FARM-1", parent_id=None)
    linear = FakeLinearClient({"farm": [parent_issue]})
    service = _build_service(cfg=cfg, linear=linear)

    daemon = FarmDaemon(
        config=cfg,
        linear_client=linear,
        poll_interval=1.0,
        max_concurrent=1,
        default_agent=Agent.CODEX,
        repos=["farm"],
        task_service=service,
    )

    daemon._poll_cycle()  # noqa: SLF001

    assert linear.moved == []


def test_poll_cycle_skips_existing_task_dir(tmp_path: Path) -> None:
    cfg = _build_config(tmp_path)
    issue = _make_issue("uuid-1", "FARM-1")
    linear = FakeLinearClient({"farm": [issue]})

    task_dir = Path(cfg.worktree_root) / "farm" / "uuid-1"
    task_dir.mkdir(parents=True, exist_ok=True)

    def fake_tmux(args):
        if args[:2] == ["has-session", "-t"]:
            raise RuntimeError("no session")
        return ""

    service = _build_service(cfg=cfg, linear=linear, tmux_runner=fake_tmux)
    daemon = FarmDaemon(
        config=cfg,
        linear_client=linear,
        poll_interval=1.0,
        max_concurrent=1,
        default_agent=Agent.CODEX,
        repos=["farm"],
        task_service=service,
    )

    daemon._poll_cycle()  # noqa: SLF001

    assert linear.moved == []


def test_poll_cycle_respects_max_concurrent_across_repos(tmp_path: Path) -> None:
    cfg = _build_config(tmp_path)
    linear = FakeLinearClient(
        {
            "farm": [_make_issue("uuid-1", "FARM-1", project="farm")],
            "scout": [
                _make_issue("uuid-2", "SCOUT-1", project="scout"),
                _make_issue("uuid-3", "SCOUT-2", project="scout"),
            ],
        }
    )

    launched_sessions: list[str] = []

    def fake_tmux(args):
        if args[:2] == ["has-session", "-t"]:
            raise RuntimeError("no session")
        if args[0] == "new-session":
            launched_sessions.append(args[args.index("-s") + 1])
        return ""

    service = _build_service(cfg=cfg, linear=linear, tmux_runner=fake_tmux)
    daemon = FarmDaemon(
        config=cfg,
        linear_client=linear,
        poll_interval=1.0,
        max_concurrent=2,
        default_agent=Agent.CODEX,
        repos=["farm", "scout"],
        task_service=service,
    )

    daemon._poll_cycle()  # noqa: SLF001

    assert len(launched_sessions) == 2


def test_active_task_count_counts_live_runtime(tmp_path: Path) -> None:
    cfg = _build_config(tmp_path)
    linear = FakeLinearClient({})

    task_dir = Path(cfg.worktree_root) / "farm" / "uuid-1" / ".farm"
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "task_updates.jsonl").write_text(
        '{"schema_version":1,"ts":"2026-01-01T00:00:00Z","issue_id":"uuid-1","repo":"farm","phase":"running","summary":"x"}\n',
        encoding="utf-8",
    )

    linear.issues_by_project["farm"] = [_make_issue("uuid-1", "FARM-1")]

    def fake_tmux(args):
        if args[:2] == ["has-session", "-t"]:
            return ""
        return ""

    service = _build_service(cfg=cfg, linear=linear, tmux_runner=fake_tmux)
    daemon = FarmDaemon(
        config=cfg,
        linear_client=linear,
        poll_interval=1.0,
        max_concurrent=2,
        default_agent=Agent.CODEX,
        repos=["farm"],
        task_service=service,
    )

    active = daemon._active_task_count()  # noqa: SLF001
    assert active == 1


def test_poll_cycle_reserves_capacity_for_partial_launch(tmp_path: Path) -> None:
    cfg = _build_config(tmp_path)
    linear = FailingMoveLinearClient(
        {
            "farm": [
                _make_issue("uuid-1", "FARM-1", project="farm"),
                _make_issue("uuid-2", "FARM-2", project="farm"),
            ]
        },
        failing_issue_id="uuid-1",
    )
    launched_sessions: list[str] = []

    def fake_git(repo_path, args):
        _ = repo_path
        task_dir = Path(args[2])
        task_dir.mkdir(parents=True, exist_ok=True)
        return ""

    def fake_tmux(args):
        if args[:2] == ["has-session", "-t"]:
            raise RuntimeError("no session")
        if args[0] == "new-session":
            launched_sessions.append(args[args.index("-s") + 1])
        return ""

    service = _build_service(
        cfg=cfg,
        linear=linear,
        git_runner=fake_git,
        tmux_runner=fake_tmux,
    )
    daemon = FarmDaemon(
        config=cfg,
        linear_client=linear,
        poll_interval=1.0,
        max_concurrent=1,
        default_agent=Agent.CODEX,
        repos=["farm"],
        task_service=service,
    )

    daemon._poll_cycle()  # noqa: SLF001

    assert launched_sessions == ["farm-uuid-1"]


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
