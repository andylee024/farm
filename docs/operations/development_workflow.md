# Farm Development Workflow

Status: Active  
Last updated: 2026-03-01

## Purpose

Define how coding work is expected to run across all projects through Farm.

Farm is the single entrypoint for coding task orchestration into Linear.

For copy/paste command setup, start with [quickstart.md](./quickstart.md).

## Scope

Applies to any repository key configured in:

- `/Users/andylee/Projects/farm/config.yaml` -> `repos.<repo-key>`

Examples are optional; workflow is repo-agnostic.

## Roles

1. Human
- sets priorities,
- approves scope,
- reviews/merges integration PRs.

2. Farm
- manages issue lifecycle,
- launches/manages execution environments,
- tracks runtime + board state,
- runs review/verification pipeline.

3. Coding Agents
- implement scoped child tasks,
- run tests,
- produce PR-ready changes/evidence.

## Required Lifecycle

1. Intake
- Create parent issue for the outcome.
- Create child issues for atomic execution units.

2. Scope/Approval
- Keep child tasks atomic and testable.
- Move to `Approved` only after acceptance checks are explicit.

3. Execution
- Launch via `farm run` from queued tasks.
- Track via `farm pulse` / `farm watch`.

4. Review + Verify
- Follow [review_pipeline.md](./review_pipeline.md).
- Parent moves to `In Review` only after review/verify pass.

5. Human Decision
- Human reviews integration PR summary and evidence.
- Human approves/requests changes/merges.

## Status Policy

Child statuses:

1. `Backlog`
2. `Approved`
3. `Coding`
4. `Completed`
5. `Canceled`

Parent review stage:

- `In Review` (after integration PR + successful review pipeline)

See full policy in [linear_style_guide.md](./linear_style_guide.md).

## Operational Rules

1. Use Farm CLI for coding task lifecycle operations.
2. Do not use direct Linear MCP operations for coding lifecycle changes.
3. Keep planning/decomposition logic in skills and docs.
4. Keep runtime code deterministic and thin.
5. Prefer explicit gate failures over implicit assumptions.

## Minimal Command Pattern

```bash
# Parent
farm intake --repo <repo-key> --title "<parent>" --description "<outcome>" --status backlog

# Child
farm intake --repo <repo-key> --parent-id <parent-id> --title "<child>" --description "<scope + checks>" --status backlog

# Approve child
farm decide --issue <child-id> --approve --repo <repo-key>

# Execute
farm run --repo <repo-key>

# Monitor
farm pulse
```

## Integration + Parent Handoff

Use the integration review skill to:

1. consolidate child branches,
2. run review/verification,
3. publish PM+CTO summary,
4. move parent to `In Review`.

Reference:

- `/Users/andylee/Projects/farm/skills/farm-integration-review/SKILL.md`
