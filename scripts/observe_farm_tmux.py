#!/usr/bin/env python3
"""Stream farm tmux pane output with task-number labels."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict


TASK_RE = re.compile(r"\b([A-Z]{1,6}\d*-\d+)\b")
UUID_RE = re.compile(
    r"\b([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b",
    re.IGNORECASE,
)


@dataclass
class PaneWatch:
    session_name: str
    pane_ref: str
    pane_id: str
    task_label: str
    log_path: Path
    offset: int = 0


def _run_tmux(tmux_bin: str, args: list[str]) -> str:
    proc = subprocess.run(
        [tmux_bin, *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        raise RuntimeError(stderr or f"tmux command failed: {' '.join(args)}")
    return proc.stdout


def _detect_task_label(tmux_bin: str, pane_id: str, session_name: str) -> str:
    try:
        content = _run_tmux(tmux_bin, ["capture-pane", "-p", "-t", pane_id, "-S", "-120"])
    except Exception:
        content = ""

    matches = TASK_RE.findall(content)
    if matches:
        return matches[-1]

    uuid_match = UUID_RE.search(content)
    if uuid_match:
        return uuid_match.group(1)

    if session_name.startswith("farm-"):
        return session_name[len("farm-") :]
    return session_name


def _discover_farm_panes(tmux_bin: str, session_prefix: str) -> list[tuple[str, str, str]]:
    rows = _run_tmux(
        tmux_bin,
        ["list-panes", "-a", "-F", "#{session_name}\t#{window_index}.#{pane_index}\t#{pane_id}"],
    )
    panes: list[tuple[str, str, str]] = []
    for row in rows.splitlines():
        parts = row.split("\t")
        if len(parts) != 3:
            continue
        session_name, pane_ref, pane_id = parts
        if not session_name.startswith(session_prefix):
            continue
        panes.append((session_name, pane_ref, pane_id))
    return panes


def _attach_logging(tmux_bin: str, pane_id: str, log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.touch(exist_ok=True)
    _run_tmux(tmux_bin, ["pipe-pane", "-o", "-t", pane_id, f"cat >> {log_path}"])


def _read_new_lines(watch: PaneWatch) -> list[str]:
    if not watch.log_path.exists():
        return []
    size = watch.log_path.stat().st_size
    if size < watch.offset:
        watch.offset = 0
    if size == watch.offset:
        return []
    with watch.log_path.open("r", encoding="utf-8", errors="replace") as handle:
        handle.seek(watch.offset)
        chunk = handle.read()
        watch.offset = handle.tell()
    return chunk.splitlines()


def _add_new_watches(
    tmux_bin: str,
    watches: Dict[str, PaneWatch],
    logs_dir: Path,
    session_prefix: str,
    follow_from_start: bool,
) -> None:
    for session_name, pane_ref, pane_id in _discover_farm_panes(tmux_bin, session_prefix):
        if pane_id in watches:
            continue
        safe_name = f"{session_name}_{pane_ref}".replace(":", "_").replace(".", "_")
        log_path = logs_dir / f"{safe_name}.log"
        _attach_logging(tmux_bin, pane_id, log_path)
        task_label = _detect_task_label(tmux_bin, pane_id, session_name)
        offset = 0
        if not follow_from_start and log_path.exists():
            offset = log_path.stat().st_size
        watch = PaneWatch(
            session_name=session_name,
            pane_ref=pane_ref,
            pane_id=pane_id,
            task_label=task_label,
            log_path=log_path,
            offset=offset,
        )
        watches[pane_id] = watch
        print(
            f"[observe] attached {pane_ref} ({session_name}) as task={task_label} -> {log_path}",
            flush=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tmux-bin", default=os.getenv("TMUX_BIN", "tmux"))
    parser.add_argument("--session-prefix", default="farm-")
    parser.add_argument("--logs-dir", default="/tmp/farm-tmux-logs")
    parser.add_argument("--poll-seconds", type=float, default=0.7)
    parser.add_argument("--discover-every", type=float, default=5.0)
    parser.add_argument("--duration", type=float, default=0.0, help="0 means run forever")
    parser.add_argument(
        "--from-start",
        action="store_true",
        help="Stream from beginning of existing logs (default is new lines only).",
    )
    args = parser.parse_args()

    logs_dir = Path(args.logs_dir)
    watches: Dict[str, PaneWatch] = {}
    started = time.time()
    last_discover = 0.0

    try:
        while True:
            now = time.time()
            if now - last_discover >= args.discover_every:
                _add_new_watches(
                    tmux_bin=args.tmux_bin,
                    watches=watches,
                    logs_dir=logs_dir,
                    session_prefix=args.session_prefix,
                    follow_from_start=args.from_start,
                )
                last_discover = now

            for watch in list(watches.values()):
                for line in _read_new_lines(watch):
                    print(f"[{watch.task_label}] {line}", flush=True)

            if args.duration > 0 and (time.time() - started) >= args.duration:
                break
            time.sleep(args.poll_seconds)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
