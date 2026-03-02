#!/usr/bin/env python3
"""Append PR metadata to a Linear issue description and optionally move status."""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from farm.adapters.linear import LinearClient
from farm.support.config import FarmConfig, load_config, load_dotenv_file
from farm.support.errors import LinearApiError

ISSUE_UPDATE_MUTATION = """
mutation IssueUpdate($id: String!, $input: IssueUpdateInput!) {
  issueUpdate(id: $id, input: $input) {
    success
    issue {
      id
    }
  }
}
"""


def _resolve_config(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute() and candidate.exists():
        return candidate
    search_roots = [Path.cwd(), *Path.cwd().parents, REPO_ROOT]
    for root in search_roots:
        resolved = root / candidate
        if resolved.exists():
            return resolved
    raise FileNotFoundError(f"Config file not found: {path}")


def _build_client(cfg: FarmConfig) -> LinearClient:
    if cfg.linear is None:
        raise ValueError("Linear config missing in config.yaml")
    return LinearClient.from_settings(
        api_url=cfg.linear.api_url,
        api_key=cfg.linear.api_key,
        api_key_env=cfg.linear.api_key_env,
        team_id=cfg.linear.team_id,
        team_id_env=cfg.linear.team_id_env,
    )


def _update_description(client: LinearClient, issue_id: str, description: str) -> None:
    data = client._execute(  # pylint: disable=protected-access
        ISSUE_UPDATE_MUTATION,
        {
            "id": issue_id,
            "input": {"description": description},
        },
    )
    payload = data.get("issueUpdate")
    if not isinstance(payload, dict) or payload.get("success") is not True:
        raise LinearApiError("Linear issueUpdate(description) returned success=false.")


def _build_block(*, pr_url: str | None, notes: list[str]) -> str:
    timestamp = dt.datetime.now(dt.UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = ["## Integration Review", f"- Updated: {timestamp}"]
    if pr_url:
        lines.append(f"- Parent PR: {pr_url}")
    for note in notes:
        text = note.strip()
        if text:
            lines.append(f"- {text}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--issue", required=True, help="Linear issue id (parent)")
    parser.add_argument("--pr-url", default=None, help="Integration PR URL")
    parser.add_argument("--note", action="append", default=[], help="Additional note line")
    parser.add_argument("--status", default=None, help="Target Linear status name (e.g. In Review)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config_path = _resolve_config(args.config)
    load_dotenv_file(config_path.parent / ".env")
    cfg = load_config(config_path)
    client = _build_client(cfg)

    issue = client.get_issue(args.issue)
    original_description = issue.description or ""
    update_block = _build_block(pr_url=args.pr_url, notes=args.note)

    if args.pr_url and args.pr_url in original_description:
        merged_description = original_description
    elif "## Integration Review" in original_description:
        merged_description = original_description + "\n\n" + update_block
    elif original_description.strip():
        merged_description = original_description.rstrip() + "\n\n" + update_block
    else:
        merged_description = update_block

    print(f"issue={issue.identifier or issue.id}")

    if args.dry_run:
        print("dry-run: description update preview")
        print("---")
        print(update_block)
        print("---")
    else:
        if merged_description != original_description:
            _update_description(client, args.issue, merged_description)
            print("description: updated")
        else:
            print("description: unchanged")

    if args.status:
        if args.dry_run:
            print(f"dry-run: would move status -> {args.status}")
        else:
            client.move_issue_to_status(args.issue, args.status)
            print(f"status: moved -> {args.status}")


if __name__ == "__main__":
    main()
