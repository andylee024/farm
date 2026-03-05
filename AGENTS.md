# AGENTS.md

## Purpose

Canonical operating contract for coding agents in Farm-managed repositories.

If a project-level `AGENTS.md` exists, this file is still the source of truth for orchestration policy.

## Required Reading Order

Before starting coding work, read in this order:

1. `/Users/andylee/Projects/farm/AGENTS.md` (this file)
2. `/Users/andylee/Projects/farm/docs/operations/operations.md`
3. `/Users/andylee/Projects/farm/features/v0/plan.md`

## Non-Negotiable Rules

1. Farm is the entrypoint for coding task orchestration into Linear.
2. Use Farm CLI for coding lifecycle operations.
3. Do not use Linear MCP tools to create/move coding tasks.
4. Keep planning/business logic in skills/docs, not runtime orchestration code.
5. Keep runtime artifacts minimal: `task_updates.jsonl` and `task_result.json` only.
6. Runtime scope is execution and observability only (`run`, `update`, `finish`, `status`, `pulse`, `watch`).
7. For this core repo, Linear coding issues must be assigned/labeled under the `farm` project.

## Scope

This applies to all repo keys configured in:

- `/Users/andylee/Projects/farm/config.yaml` under `repos.<repo-key>`

## Standard Environment

Use these defaults unless the user specifies otherwise:

```bash
export FARM_CONFIG="/Users/andylee/Projects/farm/config.yaml"
export REPO_KEY="farm"
```

## Runtime Reference

All command usage, lifecycle details, and artifact schema are defined in:

- `/Users/andylee/Projects/farm/docs/operations/operations.md`

## How To Apply In Other Repos

Project-level `AGENTS.md` files should include:

1. A Farm-first orchestration note.
2. A link to this file: `/Users/andylee/Projects/farm/AGENTS.md`
3. Any project-specific constraints (schema, test commands, deployment policies).

Reference snippet:

```md
## Farm-Orchestrated Coding (Required)

For any coding task in this repository:
1. Read `/Users/andylee/Projects/farm/AGENTS.md` before starting.
2. Use Farm CLI as the control plane for Linear coding task lifecycle.
3. Do not create or move coding tasks via Linear MCP tools or ad-hoc scripts.
4. Keep planning/business logic in Farm skills/docs, not in repository orchestration scripts.
```
