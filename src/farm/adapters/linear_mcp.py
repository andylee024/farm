"""Linear MCP adapter skeleton."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1


@dataclass(slots=True)
class LinearChildIssue:
    id: str
    title: str
    description: str


class LinearMcpClient:
    """Lightweight placeholder used until MCP integration is wired."""

    def create_parent_issue(
        self,
        title: str,
        description: str,
        *,
        project_name: str | None = None,
        state_name: str | None = None,
    ) -> str:
        _ = project_name
        _ = state_name
        digest = sha1(f"{title}\n{description}".encode("utf-8")).hexdigest()[:8]
        return f"PARENT-{digest}"

    def create_child_issue(
        self,
        *,
        parent_issue_id: str,
        title: str,
        description: str,
        project_name: str | None = None,
        state_name: str | None = None,
    ) -> LinearChildIssue:
        _ = project_name
        _ = state_name
        digest = sha1(f"{parent_issue_id}\n{title}".encode("utf-8")).hexdigest()[:10]
        issue_id = f"CHILD-{digest}"
        return LinearChildIssue(id=issue_id, title=title, description=description)
