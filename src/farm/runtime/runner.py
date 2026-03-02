"""Single-task runtime execution kernel."""

from __future__ import annotations

import json
import shlex
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from farm.adapters.git import run_git
from farm.adapters.linear import LinearClient, LinearIssue, normalize_state_name
from farm.adapters.tmux import run_tmux
from farm.runtime.models import AgentKind, TaskResult, TaskUpdate
from farm.runtime.paths import task_paths
from farm.support.config import FarmConfig

GitRunner = Callable[[str | Path, list[str]], str]
TmuxRunner = Callable[[list[str]], str]



def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class TaskRunner:
    """Minimal orchestration for run/update/finish/status task lifecycle."""

    def __init__(
        self,
        *,
        config: FarmConfig,
        linear_client: LinearClient,
        git_runner: GitRunner = run_git,
        tmux_runner: TmuxRunner = run_tmux,
    ):
        self.config = config
        self.linear_client = linear_client
        self.git_runner = git_runner
        self.tmux_runner = tmux_runner

    def run(self, *, issue_id: str, repo: str, agent: AgentKind) -> dict[str, str]:
        repo_cfg = self._repo_cfg(repo)
        issue = self.linear_client.get_issue(issue_id)
        self._require_run_allowed(issue)
        self._require_issue_repo(issue, repo)

        paths = task_paths(config=self.config, repo=repo, issue_id=issue_id)
        worktree = paths.worktree
        updates_path = paths.updates
        branch = paths.branch
        session = paths.session

        if worktree.exists():
            raise ValueError(f"Task worktree already exists: {worktree}")
        worktree.parent.mkdir(parents=True, exist_ok=True)

        self._create_worktree(
            repo_path=repo_cfg.path,
            worktree=worktree,
            branch=branch,
            base_branch=repo_cfg.default_branch,
        )
        self._start_agent_session(
            session=session,
            worktree=worktree,
            startup_command=self._startup_command(issue_id=issue_id, agent=agent),
        )

        self.linear_client.move_issue_to_status(issue_id, "Coding")
        self._append_update(
            updates_path,
            TaskUpdate(
                issue_id=issue_id,
                repo=repo,
                phase="starting",
                summary="Created worktree and started session",
                ts=_now_iso(),
            ),
        )

        return {
            "issue_id": issue_id,
            "repo": repo,
            "worktree": str(worktree),
            "branch": branch,
            "session": session,
            "updates": str(updates_path),
            "result": str(paths.result),
            "agent": agent.value,
        }

    def update(self, *, issue_id: str, repo: str, phase: str, summary: str) -> str:
        _ = self._repo_cfg(repo)
        issue = self.linear_client.get_issue(issue_id)
        self._require_issue_repo(issue, repo)
        paths = task_paths(config=self.config, repo=repo, issue_id=issue_id)
        updates_path = paths.updates
        self._append_update(
            updates_path,
            TaskUpdate(
                issue_id=issue_id,
                repo=repo,
                phase=phase,
                summary=summary,
                ts=_now_iso(),
            ),
        )
        return str(updates_path)

    def finish(
        self,
        *,
        issue_id: str,
        repo: str,
        outcome: str,
        summary: str,
        pr_url: str | None,
    ) -> str:
        _ = self._repo_cfg(repo)
        issue = self.linear_client.get_issue(issue_id)
        self._require_issue_repo(issue, repo)
        state = normalize_state_name(issue.state_name)
        if state not in {"coding", "done", "canceled"}:
            raise ValueError(
                f"Issue {issue.identifier or issue.id} must be Coding/Done/Canceled before finish. "
                f"Current state: {issue.state_name or 'unknown'}"
            )

        normalized_outcome = outcome.strip().lower()
        if normalized_outcome not in {"completed", "canceled", "blocked", "failed"}:
            raise ValueError("`outcome` must be one of: completed, canceled, blocked, failed")

        target_status = "Done" if normalized_outcome == "completed" else "Canceled"
        self.linear_client.move_issue_to_status(issue_id, target_status)

        paths = task_paths(config=self.config, repo=repo, issue_id=issue_id)
        updates_path = paths.updates
        result_path = paths.result

        terminal_phase = "completed" if normalized_outcome == "completed" else "canceled"
        self._append_update(
            updates_path,
            TaskUpdate(
                issue_id=issue_id,
                repo=repo,
                phase=terminal_phase,
                summary=summary,
                ts=_now_iso(),
            ),
        )

        started_at = self._first_update_ts(updates_path) or _now_iso()
        result = TaskResult(
            issue_id=issue_id,
            repo=repo,
            outcome=normalized_outcome,
            summary=summary,
            started_at=started_at,
            ended_at=_now_iso(),
            pr_url=pr_url,
        )
        self._write_result(result_path, result)
        return str(result_path)

    def status(self, *, issue_id: str, repo: str) -> dict[str, Any]:
        _ = self._repo_cfg(repo)
        issue = self.linear_client.get_issue(issue_id)
        self._require_issue_repo(issue, repo)

        paths = task_paths(config=self.config, repo=repo, issue_id=issue_id)
        updates_path = paths.updates
        result_path = paths.result

        latest_update = self._latest_update(updates_path)
        task_result = self._load_result(result_path)

        return {
            "issue_id": issue_id,
            "repo": repo,
            "linear_state": issue.state_name,
            "update_phase": latest_update.phase if latest_update else None,
            "update_ts": latest_update.ts if latest_update else None,
            "update_summary": latest_update.summary if latest_update else None,
            "outcome": task_result.outcome if task_result else None,
            "result_summary": task_result.summary if task_result else None,
            "result_ended_at": task_result.ended_at if task_result else None,
            "updates": str(updates_path),
            "result": str(result_path),
        }

    def _repo_cfg(self, repo: str):
        repo_cfg = self.config.repos.get(repo)
        if repo_cfg is None:
            available = ", ".join(sorted(self.config.repos.keys()))
            raise ValueError(f"Unknown repo `{repo}`. Available: {available}")
        return repo_cfg

    @staticmethod
    def _require_run_allowed(issue: LinearIssue) -> None:
        state = normalize_state_name(issue.state_name)
        if state != "approved":
            raise ValueError(
                f"Issue {issue.identifier or issue.id} must be in Approved before run. "
                f"Current state: {issue.state_name or 'unknown'}"
            )

    @staticmethod
    def _require_issue_repo(issue: LinearIssue, repo: str) -> None:
        if issue.project_name is None:
            return
        project = issue.project_name.strip().lower()
        if project != repo.strip().lower():
            raise ValueError(f"Issue project `{issue.project_name}` does not match --repo `{repo}`")

    def _create_worktree(self, *, repo_path: str, worktree: Path, branch: str, base_branch: str) -> None:
        self.git_runner(
            repo_path,
            [
                "worktree",
                "add",
                str(worktree),
                "-b",
                branch,
                base_branch,
            ],
        )

    def _start_agent_session(self, *, session: str, worktree: Path, startup_command: str) -> None:
        self.tmux_runner(
            [
                "new-session",
                "-d",
                "-s",
                session,
                "-c",
                str(worktree),
                startup_command,
            ]
        )

    def _startup_command(self, *, issue_id: str, agent: AgentKind) -> str:
        args = self._agent_launch_args(issue_id=issue_id, agent=agent)
        return shlex.join(args)

    def _agent_launch_args(self, *, issue_id: str, agent: AgentKind) -> list[str]:
        model = self._agent_model(agent)
        prompt = (
            f"Work on Linear issue {issue_id}. "
            "Read AGENTS.md and docs/operations/operations.md first, then execute the scoped task."
        )
        if agent == AgentKind.CLAUDE:
            args = ["claude", "--model", model]
            if self.config.agent_defaults.dangerous_bypass_permissions:
                args.append("--dangerously-skip-permissions")
            return [*args, prompt]
        args = ["codex", "--model", model]
        if self.config.agent_defaults.dangerous_bypass_permissions:
            args.append("--dangerously-bypass-approvals-and-sandbox")
        return [*args, prompt]

    def _agent_model(self, agent: AgentKind) -> str:
        if agent == AgentKind.CLAUDE:
            return self.config.agent_defaults.claude_model
        return self.config.agent_defaults.codex_model

    @staticmethod
    def _append_update(path: Path, update: TaskUpdate) -> None:
        payload = {
            "schema_version": 1,
            "ts": update.ts,
            "issue_id": update.issue_id,
            "repo": update.repo,
            "phase": update.phase,
            "summary": update.summary,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")

    @staticmethod
    def _iter_json_lines(path: Path) -> list[dict[str, object]]:
        if not path.exists():
            return []
        rows: list[dict[str, object]] = []
        try:
            with path.open("r", encoding="utf-8") as handle:
                for raw in handle:
                    line = raw.strip()
                    if not line:
                        continue
                    try:
                        decoded = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(decoded, dict):
                        rows.append(decoded)
        except OSError:
            return []
        return rows

    def _first_update_ts(self, path: Path) -> str | None:
        rows = self._iter_json_lines(path)
        if not rows:
            return None
        value = rows[0].get("ts")
        return value if isinstance(value, str) else None

    def _latest_update(self, path: Path) -> TaskUpdate | None:
        rows = self._iter_json_lines(path)
        if not rows:
            return None
        row = rows[-1]
        issue_id = row.get("issue_id")
        repo = row.get("repo")
        phase = row.get("phase")
        summary = row.get("summary")
        ts = row.get("ts")
        if not all(isinstance(v, str) for v in (issue_id, repo, phase, summary, ts)):
            return None
        return TaskUpdate(issue_id=issue_id, repo=repo, phase=phase, summary=summary, ts=ts)

    @staticmethod
    def _write_result(path: Path, result: TaskResult) -> None:
        payload = {
            "schema_version": 1,
            "issue_id": result.issue_id,
            "repo": result.repo,
            "outcome": result.outcome,
            "summary": result.summary,
            "started_at": result.started_at,
            "ended_at": result.ended_at,
            "pr_url": result.pr_url,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp_path.replace(path)

    @staticmethod
    def _load_result(path: Path) -> TaskResult | None:
        if not path.exists():
            return None
        try:
            decoded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(decoded, dict):
            return None
        issue_id = decoded.get("issue_id")
        repo = decoded.get("repo")
        outcome = decoded.get("outcome")
        summary = decoded.get("summary")
        started_at = decoded.get("started_at")
        ended_at = decoded.get("ended_at")
        pr_url = decoded.get("pr_url")
        if not all(
            isinstance(value, str)
            for value in (issue_id, repo, outcome, summary, started_at, ended_at)
        ):
            return None
        if pr_url is not None and not isinstance(pr_url, str):
            pr_url = None
        return TaskResult(
            issue_id=issue_id,
            repo=repo,
            outcome=outcome,
            summary=summary,
            started_at=started_at,
            ended_at=ended_at,
            pr_url=pr_url,
        )
