"""Task lifecycle orchestration independent from the execution runtime."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from farm.adapters.linear import LinearClient, LinearIssue, normalize_state_name
from farm.runtime.models import Agent, TaskResult, TaskUpdate
from farm.runtime.paths import task_paths
from farm.runtime.task_runtime import TaskRuntime, TaskRuntimeLaunchRequest
from farm.support.config import FarmConfig


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class TaskService:
    """Lifecycle service for run/update/finish/status/pulse/watch."""

    def __init__(
        self,
        *,
        config: FarmConfig,
        linear_client: LinearClient,
        task_runtime: TaskRuntime,
        config_path: Path | None = None,
    ):
        self.config = config
        self.linear_client = linear_client
        self.task_runtime = task_runtime
        self.config_path = config_path

    def run(self, *, issue_id: str, repo: str, agent: Agent) -> dict[str, str]:
        repo_cfg = self._repo_cfg(repo)
        issue = self.linear_client.get_issue(issue_id)
        resolved_issue_id = issue.id
        self._require_run_allowed(issue)
        self._require_child_issue(issue)
        self._require_issue_repo(issue, repo)

        paths = task_paths(config=self.config, repo=repo, issue_id=resolved_issue_id)
        metadata = self.task_runtime.start(
            TaskRuntimeLaunchRequest(
                issue_id=resolved_issue_id,
                repo=repo,
                repo_path=repo_cfg.path,
                default_branch=repo_cfg.default_branch,
                task_dir=paths.task_dir,
                startup_command=self._startup_command(
                    issue_id=resolved_issue_id,
                    repo=repo,
                    agent=agent,
                ),
            )
        )

        self.linear_client.move_issue_to_status(resolved_issue_id, "Coding")
        self._append_update(
            paths.updates,
            TaskUpdate(
                issue_id=resolved_issue_id,
                repo=repo,
                phase="starting",
                summary="Created task runtime and started execution",
                ts=_now_iso(),
            ),
        )

        result = {
            "issue_id": resolved_issue_id,
            "repo": repo,
            "task_dir": str(paths.task_dir),
            "runtime": metadata.runtime,
            "updates": str(paths.updates),
            "result": str(paths.result),
            "agent": agent.value,
        }
        if metadata.workspace is not None:
            result["runtime_workspace"] = metadata.workspace
        if metadata.branch is not None:
            result["runtime_branch"] = metadata.branch
        if metadata.handle is not None:
            result["runtime_handle"] = metadata.handle
        return result

    def update(self, *, issue_id: str, repo: str, phase: str, summary: str) -> str:
        _ = self._repo_cfg(repo)
        issue = self.linear_client.get_issue(issue_id)
        resolved_issue_id = issue.id
        self._require_issue_repo(issue, repo)
        paths = task_paths(config=self.config, repo=repo, issue_id=resolved_issue_id)
        self._append_update(
            paths.updates,
            TaskUpdate(
                issue_id=resolved_issue_id,
                repo=repo,
                phase=phase,
                summary=summary,
                ts=_now_iso(),
            ),
        )
        return str(paths.updates)

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
        resolved_issue_id = issue.id
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
        self.linear_client.move_issue_to_status(resolved_issue_id, target_status)

        paths = task_paths(config=self.config, repo=repo, issue_id=resolved_issue_id)
        terminal_phase = "completed" if normalized_outcome == "completed" else "canceled"
        self._append_update(
            paths.updates,
            TaskUpdate(
                issue_id=resolved_issue_id,
                repo=repo,
                phase=terminal_phase,
                summary=summary,
                ts=_now_iso(),
            ),
        )

        started_at = self._first_update_ts(paths.updates) or _now_iso()
        result = TaskResult(
            issue_id=resolved_issue_id,
            repo=repo,
            outcome=normalized_outcome,
            summary=summary,
            started_at=started_at,
            ended_at=_now_iso(),
            pr_url=pr_url,
        )
        self._write_result(paths.result, result)
        return str(paths.result)

    def status(self, *, issue_id: str, repo: str) -> dict[str, Any]:
        _ = self._repo_cfg(repo)
        issue = self.linear_client.get_issue(issue_id)
        resolved_issue_id = issue.id
        self._require_issue_repo(issue, repo)

        paths = task_paths(config=self.config, repo=repo, issue_id=resolved_issue_id)
        latest_update = self._latest_update(paths.updates)
        task_result = self._load_result(paths.result)
        runtime_metadata = self.task_runtime.describe(
            issue_id=resolved_issue_id,
            repo=repo,
            task_dir=paths.task_dir,
        )

        return {
            "issue_id": resolved_issue_id,
            "repo": repo,
            "linear_state": issue.state_name,
            "runtime": runtime_metadata.runtime,
            "runtime_workspace": runtime_metadata.workspace,
            "runtime_branch": runtime_metadata.branch,
            "runtime_handle": runtime_metadata.handle,
            "update_phase": latest_update.phase if latest_update else None,
            "update_ts": latest_update.ts if latest_update else None,
            "update_summary": latest_update.summary if latest_update else None,
            "outcome": task_result.outcome if task_result else None,
            "result_summary": task_result.summary if task_result else None,
            "result_ended_at": task_result.ended_at if task_result else None,
            "updates": str(paths.updates),
            "result": str(paths.result),
        }

    def pulse(self, *, repo: str) -> list[dict[str, Any]]:
        _ = self._repo_cfg(repo)
        snapshots: list[dict[str, Any]] = []
        for issue_id in self._task_issue_ids(repo):
            paths = task_paths(config=self.config, repo=repo, issue_id=issue_id)
            latest_update = self._latest_update(paths.updates)
            task_result = self._load_result(paths.result)
            runtime_metadata = self.task_runtime.describe(
                issue_id=issue_id,
                repo=repo,
                task_dir=paths.task_dir,
            )

            issue_identifier: str | None = None
            linear_state: str | None = None
            try:
                linear_issue = self.linear_client.get_issue(issue_id)
                issue_identifier = linear_issue.identifier
                linear_state = linear_issue.state_name
            except Exception:  # noqa: BLE001
                linear_state = None

            snapshots.append(
                {
                    "issue_id": issue_id,
                    "issue_identifier": issue_identifier,
                    "repo": repo,
                    "linear_state": linear_state,
                    "runtime": runtime_metadata.runtime,
                    "runtime_workspace": runtime_metadata.workspace,
                    "runtime_branch": runtime_metadata.branch,
                    "runtime_handle": runtime_metadata.handle,
                    "runtime_alive": self.task_runtime.is_alive(
                        issue_id=issue_id,
                        repo=repo,
                        task_dir=paths.task_dir,
                    ),
                    "update_phase": latest_update.phase if latest_update else None,
                    "update_ts": latest_update.ts if latest_update else None,
                    "outcome": task_result.outcome if task_result else None,
                    "updates": str(paths.updates),
                    "result": str(paths.result),
                }
            )
        return snapshots

    def watch(self, *, repo: str, tail_lines: int = 4) -> list[dict[str, Any]]:
        rows = self.pulse(repo=repo)
        enriched: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            tail: list[str] = []
            if bool(row.get("runtime_alive")):
                paths = task_paths(config=self.config, repo=repo, issue_id=row["issue_id"])
                tail = self.task_runtime.tail(
                    issue_id=row["issue_id"],
                    repo=repo,
                    task_dir=paths.task_dir,
                    lines=tail_lines,
                )
            item["tail_lines"] = tail
            enriched.append(item)
        return enriched

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

    @staticmethod
    def _require_child_issue(issue: LinearIssue) -> None:
        if issue.parent_id is None:
            raise ValueError(
                f"Issue {issue.identifier or issue.id} must be a child issue before run."
            )

    def _startup_command(self, *, issue_id: str, repo: str, agent: Agent) -> str:
        agent_command = shlex.join(self._agent_launch_args(issue_id=issue_id, agent=agent))
        finish_success = shlex.join(
            self._finish_launch_args(
                issue_id=issue_id,
                repo=repo,
                outcome="completed",
                summary=f"Agent session ended successfully ({agent.value}).",
            )
        )
        finish_failure = shlex.join(
            self._finish_launch_args(
                issue_id=issue_id,
                repo=repo,
                outcome="failed",
                summary=f"Agent session exited non-zero ({agent.value}).",
            )
        )
        script = (
            f"{agent_command}; "
            "__farm_exit=$?; "
            f"if [ $__farm_exit -eq 0 ]; then {finish_success}; else {finish_failure}; fi; "
            "exit $__farm_exit"
        )
        return shlex.join(["bash", "-lc", script])

    def _agent_launch_args(self, *, issue_id: str, agent: Agent) -> list[str]:
        binary = self._agent_binary(agent)
        model = self._agent_model(agent)
        prompt = (
            f"Work on Linear issue {issue_id}. "
            "Read AGENTS.md and docs/operations/operations.md first, then execute the scoped task."
        )
        if agent == Agent.CLAUDE:
            args = [binary, "--model", model, "--print"]
            if self.config.agent_defaults.dangerous_bypass_permissions:
                args.append("--dangerously-skip-permissions")
            return [*args, prompt]
        args = [binary, "exec", "--model", model]
        if self.config.agent_defaults.dangerous_bypass_permissions:
            args.append("--dangerously-bypass-approvals-and-sandbox")
        return [*args, prompt]

    def _agent_model(self, agent: Agent) -> str:
        if agent == Agent.CLAUDE:
            return self.config.agent_defaults.claude_model
        return self.config.agent_defaults.codex_model

    @staticmethod
    def _agent_binary(agent: Agent) -> str:
        resolved = shutil.which(agent.value)
        return resolved or agent.value

    def _finish_launch_args(self, *, issue_id: str, repo: str, outcome: str, summary: str) -> list[str]:
        config_path = self._resolved_config_path_for_subprocess()
        return [
            sys.executable,
            "-m",
            "farm.cli.commands",
            "finish",
            "--config",
            config_path,
            "--issue",
            issue_id,
            "--repo",
            repo,
            "--outcome",
            outcome,
            "--summary",
            summary,
        ]

    def _resolved_config_path_for_subprocess(self) -> str:
        if self.config_path is not None:
            return str(self.config_path.resolve())
        env_path = os.getenv("FARM_CONFIG")
        if env_path:
            return str(Path(env_path).resolve())
        return str(Path("config.yaml").resolve())

    def _task_issue_ids(self, repo: str) -> list[str]:
        repo_root = Path(self.config.worktree_root) / repo
        if not repo_root.exists():
            return []
        issue_ids: list[str] = []
        for child in sorted(repo_root.iterdir()):
            if not child.is_dir():
                continue
            farm_dir = child / ".farm"
            if (farm_dir / "task_updates.jsonl").exists() or (farm_dir / "task_result.json").exists():
                issue_ids.append(child.name)
        return issue_ids

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
