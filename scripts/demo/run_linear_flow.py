#!/usr/bin/env python3
"""Run one Linear child issue through farm run/update/finish/status."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _base_command() -> list[str]:
    return [sys.executable, "-m", "farm.cli.commands"]


def _run_command(args: list[str], *, env: dict[str, str]) -> None:
    cmd = _base_command() + args
    print("$", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=str(REPO_ROOT), env=env, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--issue", required=True, help="Linear child issue id (UUID).")
    parser.add_argument("--agent", choices=["codex", "claude"], default="codex")
    parser.add_argument(
        "--outcome",
        choices=["completed", "canceled", "blocked", "failed"],
        default="completed",
        help="Final outcome passed to `farm finish`.",
    )
    parser.add_argument("--pr-url", default=None)
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    args = parser.parse_args()

    env = os.environ.copy()
    existing_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + (os.pathsep + existing_path if existing_path else "")

    _run_command(
        [
            "run",
            "--config",
            args.config,
            "--repo",
            args.repo,
            "--issue",
            args.issue,
            "--agent",
            args.agent,
        ],
        env=env,
    )
    if args.sleep_seconds > 0:
        time.sleep(args.sleep_seconds)

    _run_command(
        [
            "update",
            "--config",
            args.config,
            "--repo",
            args.repo,
            "--issue",
            args.issue,
            "--phase",
            "running",
            "--summary",
            "Executing sample step 1",
        ],
        env=env,
    )
    if args.sleep_seconds > 0:
        time.sleep(args.sleep_seconds)

    _run_command(
        [
            "update",
            "--config",
            args.config,
            "--repo",
            args.repo,
            "--issue",
            args.issue,
            "--phase",
            "running",
            "--summary",
            "Executing sample step 2",
        ],
        env=env,
    )
    if args.sleep_seconds > 0:
        time.sleep(args.sleep_seconds)

    finish_cmd = [
        "finish",
        "--config",
        args.config,
        "--repo",
        args.repo,
        "--issue",
        args.issue,
        "--outcome",
        args.outcome,
        "--summary",
        f"Sample flow finished with outcome={args.outcome}",
    ]
    if args.pr_url:
        finish_cmd.extend(["--pr-url", args.pr_url])
    _run_command(finish_cmd, env=env)

    _run_command(
        [
            "status",
            "--config",
            args.config,
            "--repo",
            args.repo,
            "--issue",
            args.issue,
        ],
        env=env,
    )


if __name__ == "__main__":
    main()
