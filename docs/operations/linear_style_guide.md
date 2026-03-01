# Farm Linear Style Guide (Lean)

Status: Active
Last updated: 2026-03-01
Applies to: Farm orchestration work across all repo keys configured in `config.yaml`

## 1) Purpose

Keep Linear lightweight while still giving Farm enough structure to:
- decompose intent into atomic tasks,
- run tasks with agents,
- verify via checks/review,
- hand final PR approval to you.

This guide intentionally uses minimal statuses and fields.

## 2) Required Workflow (5 child statuses)

Use exactly these issue statuses:

1. `Backlog`
2. `Approved`
3. `Coding`
4. `Completed`
5. `Canceled`

Definitions:
- `Backlog`: idea captured, not yet scoped into executable units.
- `Approved`: scoped, atomic, and ready for Farm execution.
- `Coding`: Farm/agent execution in progress (including PR open, checks, retries, fixes).
- `Completed`: ready for your PR approval on integration path, or approved/merged.
- `Canceled`: dropped, duplicate, or no longer relevant.

Parent review stage:
- Parent issues may move to `In Review` after the integration PR is opened and linked.
- `In Review` is parent-only and does not change child status policy.

## 3) Required Fields (minimal)

Use only:
- `Project` (must match a configured repo key in Farm config)
- `Parent/Sub-issue` (parent = intent, children = atomic tasks)

Optional:
- label `blocked` for tickets needing human intervention while in `Coding`.

Do not require milestone, priority, or extra custom fields.

## 4) Parent/Child Rules

Parent issue:
- captures the intent/outcome.
- should not be directly executed by an agent.
- moves to `In Review` when the parent integration PR is ready for human review.

Child issue:
- is the execution unit for Farm.
- must be atomic: one clear outcome, one main change thread, independently testable.
- moves through statuses and produces evidence.

## 5) Agent Context Standard

Every child issue must include a short `Context Pack` section with:
- repo context (`<repo-key>` from Farm config),
- relevant local file paths,
- links to [PRD](../prd.md) and [V0 Technical Plan](../feature/v0/technical_plan.md),
- any constraints needed for safe execution.

Goal: enough context to execute well, not full-repo brain dump.

## 6) Child Issue Template

Use this exact section order in each child issue description:

1. `Context`
2. `Scope`
3. `Out of Scope`
4. `Acceptance Checks`
5. `Agent Startup Instructions`
6. `Context Pack`
7. `Evidence Required`

Required `Agent Startup Instructions` content:

```md
## Agent Startup Instructions
- Before making changes, read this repository to understand full project context (architecture, conventions, and constraints).
- Then implement only the scoped task in this issue.
```

Minimum quality bar:
- `Acceptance Checks` must be deterministic (exact command, check, or observable condition).
- `Evidence Required` must include PR link + checks/review result summary.

## 7) State Compression For Farm Runtime

Linear is intentionally coarse; Farm runtime stays detailed internally.

Mapping:
- `drafted` -> `Backlog`
- `queued` -> `Approved`
- `running`, `pr_open`, `tests_failed`, `retrying`, `changes_requested`, `blocked_needs_human` -> `Coding`
- `ready_for_review`, `merged` -> `Completed`

This keeps board management simple while preserving full internal orchestration state.

## 8) Execution Policy

- Only move to `Approved` when a child issue is atomic and testable.
- Farm runs `Approved` items and manages branch/check/retry flow in `Coding`.
- Human action is primarily at PR approval time before final merge decisions.
- If retries exhaust or scope ambiguity appears, mark `blocked` and keep in `Coding` until resolved.

## 9) Definition Of Done

A child issue is `Completed` only when:
- integration-target PR exists with required evidence,
- checks/review have run,
- task is ready for your approve/merge decision.

PR opened alone is not done.

## 10) Review Process

Parent review flow, gates, and summary format are defined in [review_pipeline.md](./review_pipeline.md).
