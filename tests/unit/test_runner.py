from __future__ import annotations

import json
from pathlib import Path

import pytest

from farm.adapters.linear import LinearIssue
from farm.runtime.models import AgentKind
from farm.runtime.runner import TaskRunner
from farm.support.config import FarmConfig


class FakeLinearClient:
    def __init__(self, issue: LinearIssue) -> None:
        self.issue = issue
        self.moved: list[tuple[str, str]] = []

    def get_issue(self, issue_id: str) -> LinearIssue:
        assert issue_id == self.issue.id
        return self.issue

    def move_issue_to_status(self, issue_id: str, status_name: str) -> None:
        self.moved.append((issue_id, status_name))
        self.issue = LinearIssue(
            id=self.issue.id,
            identifier=self.issue.identifier,
            title=self.issue.title,
            description=self.issue.description,
            parent_id=self.issue.parent_id,
            state_name=status_name,
            project_name=self.issue.project_name,
        )



def build_config(tmp_path: Path, *, dangerous_bypass_permissions: bool = True) -> FarmConfig:
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
            "agent_defaults": {
                "codex_model": "gpt-5.3-codex",
                "claude_model": "claude-opus-4.5",
                "dangerous_bypass_permissions": dangerous_bypass_permissions,
            },
        }
    )



def make_issue(*, state: str = "Approved", project: str = "farm") -> LinearIssue:
    return LinearIssue(
        id="FARM-123",
        identifier="FARM-123",
        title="Test",
        description="desc",
        parent_id="PARENT-1",
        state_name=state,
        project_name=project,
    )



def test_run_moves_issue_to_coding_and_writes_update(tmp_path: Path) -> None:
    cfg = build_config(tmp_path)
    linear = FakeLinearClient(make_issue(state="Approved"))
    git_calls: list[list[str]] = []
    tmux_calls: list[list[str]] = []

    def fake_git(repo_path: str | Path, args: list[str]) -> str:
        _ = repo_path
        git_calls.append(args)
        return ""

    def fake_tmux(args: list[str]) -> str:
        tmux_calls.append(args)
        return ""

    runner = TaskRunner(config=cfg, linear_client=linear, git_runner=fake_git, tmux_runner=fake_tmux)

    result = runner.run(issue_id="FARM-123", repo="farm", agent=AgentKind.CODEX)

    assert linear.moved == [("FARM-123", "Coding")]
    assert result["branch"] == "farm/farm-123"
    assert result["session"] == "farm-farm-123"
    assert Path(result["updates"]).exists()
    assert git_calls and "worktree" in git_calls[0]
    assert tmux_calls and "new-session" in tmux_calls[0]



def test_run_requires_approved_state(tmp_path: Path) -> None:
    cfg = build_config(tmp_path)
    linear = FakeLinearClient(make_issue(state="Backlog"))
    runner = TaskRunner(config=cfg, linear_client=linear)

    with pytest.raises(ValueError, match="must be in Approved"):
        runner.run(issue_id="FARM-123", repo="farm", agent=AgentKind.CODEX)



def test_finish_completed_writes_result(tmp_path: Path) -> None:
    cfg = build_config(tmp_path)
    linear = FakeLinearClient(make_issue(state="Coding"))
    runner = TaskRunner(config=cfg, linear_client=linear)

    runner.update(issue_id="FARM-123", repo="farm", phase="running", summary="working")
    result_path = runner.finish(
        issue_id="FARM-123",
        repo="farm",
        outcome="completed",
        summary="implemented",
        pr_url="https://example.com/pr/1",
    )

    assert linear.moved[-1] == ("FARM-123", "Done")
    payload = json.loads(Path(result_path).read_text(encoding="utf-8"))
    assert payload["outcome"] == "completed"
    assert payload["summary"] == "implemented"
    assert payload["pr_url"] == "https://example.com/pr/1"



def test_status_returns_snapshot(tmp_path: Path) -> None:
    cfg = build_config(tmp_path)
    linear = FakeLinearClient(make_issue(state="Coding"))
    runner = TaskRunner(config=cfg, linear_client=linear)

    runner.update(issue_id="FARM-123", repo="farm", phase="running", summary="working")
    snapshot = runner.status(issue_id="FARM-123", repo="farm")

    assert snapshot["issue_id"] == "FARM-123"
    assert snapshot["linear_state"] == "Coding"
    assert snapshot["update_phase"] == "running"
    assert snapshot["update_summary"] == "working"


def test_startup_command_uses_dangerous_flags_by_default(tmp_path: Path) -> None:
    cfg = build_config(tmp_path, dangerous_bypass_permissions=True)
    linear = FakeLinearClient(make_issue(state="Approved"))
    runner = TaskRunner(config=cfg, linear_client=linear)

    codex_cmd = runner._startup_command(issue_id="FARM-123", agent=AgentKind.CODEX)  # noqa: SLF001
    claude_cmd = runner._startup_command(issue_id="FARM-123", agent=AgentKind.CLAUDE)  # noqa: SLF001

    assert codex_cmd.startswith("codex ")
    assert "--dangerously-bypass-approvals-and-sandbox" in codex_cmd
    assert claude_cmd.startswith("claude ")
    assert "--dangerously-skip-permissions" in claude_cmd


def test_startup_command_can_disable_dangerous_flags(tmp_path: Path) -> None:
    cfg = build_config(tmp_path, dangerous_bypass_permissions=False)
    linear = FakeLinearClient(make_issue(state="Approved"))
    runner = TaskRunner(config=cfg, linear_client=linear)

    codex_cmd = runner._startup_command(issue_id="FARM-123", agent=AgentKind.CODEX)  # noqa: SLF001
    claude_cmd = runner._startup_command(issue_id="FARM-123", agent=AgentKind.CLAUDE)  # noqa: SLF001

    assert "--dangerously-bypass-approvals-and-sandbox" not in codex_cmd
    assert "--dangerously-skip-permissions" not in claude_cmd
