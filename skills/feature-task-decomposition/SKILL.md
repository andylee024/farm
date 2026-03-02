---
name: feature-task-decomposition
description: Plan and decompose work into parent/child Linear issues, then execute one approved child at a time with the Farm single-task runner.
---

# Feature Task Decomposition

## Workflow

1. Read `docs/operations/operations.md`.
2. Decompose user intent into one parent plus atomic child issues.
3. Ensure each child has deterministic acceptance checks.
4. Move one child to `Approved` in Linear.
5. Run one child via Farm `run/update/finish/status` commands.

## Operating Rules

- Farm runtime is execution-only; planning stays in skill output and issue descriptions.
- Keep one active child task per run invocation.
- Track progress through `task_updates.jsonl` and final outcome through `task_result.json`.

## Command Playbook

Read [references/command_playbook.md](references/command_playbook.md).
