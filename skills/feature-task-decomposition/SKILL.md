---
name: feature-task-decomposition
description: Plan and decompose feature work into parent/child Linear issues without embedding planning logic in runtime code. Use when a user wants to convert intent into atomic, testable tasks and drive execution with `farm intake`, `farm decide`, `farm run`, and `farm status`.
---

# Feature Task Decomposition

## Workflow

1. Read `docs/operations/linear_style_guide.md`.
2. Convert user intent into one parent issue plus atomic child issues in chat first.
3. Ask for approval on the proposed child issue list before creating Linear issues.
4. Execute approved board operations through CLI commands only.
5. Keep planning decisions in chat and skill output, not in runtime code generation.

## Operating Rules

- Treat runtime commands as thin operations:
  - `farm intake` creates one issue at a time.
  - `farm decide` applies approve/cancel decisions.
  - `farm run` executes queued tasks.
  - `farm status` reports board/runtime summary.
- Keep decomposition in the skill workflow; do not rely on static decomposition templates in code.
- Enforce status policy from style guide:
  - `Backlog` for newly captured work.
  - `Approved` only after atomic, testable scope is confirmed.
  - `Coding` and `Completed` are runtime-driven.
  - `Canceled` for dropped work.

## Command Playbook

Read [references/command_playbook.md](references/command_playbook.md) and follow it for:
- parent/child issue creation order,
- approval/cancel transitions,
- run loop cadence,
- suggested prompts/checklists for decomposition quality.

## Handoff

When child issues reach `Completed`/`ready_for_review`, hand off to `farm-integration-review` to:
- review child branches/worktrees,
- create one parent-level integration PR,
- update parent issue with PR link and move it to final review status.
