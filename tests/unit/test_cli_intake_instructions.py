from __future__ import annotations

from farm.workflows.intake_workflow import CHILD_REPO_CONTEXT_MARKER
from farm.workflows.intake_workflow import ensure_child_repo_context_instruction


def test_ensure_child_repo_context_instruction_appends_block_when_missing() -> None:
    description = "## Context\n- Add retry handling for upload worker."

    output = ensure_child_repo_context_instruction(description)

    assert output.startswith(description)
    assert CHILD_REPO_CONTEXT_MARKER in output
    assert "read this repository to understand full project context" in output


def test_ensure_child_repo_context_instruction_is_idempotent() -> None:
    description = (
        "## Context\n- Add retry handling for upload worker.\n\n"
        "## Agent Startup Instructions\n"
        "- Before making changes, read this repository first."
    )

    output = ensure_child_repo_context_instruction(description)

    assert output == description
