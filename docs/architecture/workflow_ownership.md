# Farm Workflow Ownership Architecture

Status: Draft  
Last updated: 2026-03-01

## Purpose

Define a single ownership model so Farm stays simple:

1. Skills own planning/review reasoning.
2. Runtime code owns deterministic execution.
3. Domain models own lifecycle invariants.

This prevents business logic from leaking into CLI glue, scripts, or adapter code.

## Design Principles

1. One workflow owner per lifecycle stage (`intake`, `execute`, `review`, `monitor`).
2. Skills are guidance assets, not side-effect executors.
3. Adapters are pure side-effect boundaries (Linear/git/tmux/gh/ci/storage).
4. CLI is a thin interface over workflows.
5. State transitions are domain-enforced and testable.

## Layer Model

```text
Human -> CLI -> Workflows -> Domain Policies -> Adapters
                        |
                        +-> Skill Runtime -> Skill Assets (SKILL.md/references/agents)
```

### 1) Interface Layer (`farm` CLI)

- Parse flags and args.
- Call workflow entrypoints.
- Render concise output.
- No lifecycle decision logic.

### 2) Workflow Layer

Own lifecycle orchestration:

- `IntakeWorkflow`
- `ExecutionWorkflow`
- `ReviewWorkflow`
- `MonitorWorkflow`

Each workflow:
- receives typed input,
- calls domain policy checks,
- invokes adapters for side effects,
- returns typed result (status/messages/actions taken).

### 3) Domain Layer

Owns:
- task models,
- state transitions,
- invariants (valid transitions, retry bounds, completion rules),
- policy checks (what can move to `Completed`, when parent can move to `In Review`).

### 4) Adapter Layer

Owns external I/O only:
- Linear API adapter
- git adapter
- tmux adapter
- CI/GH adapters
- registry storage adapter

Adapters do not contain planning logic or status policy.

### 5) Skills Layer

Owns reasoning assets and playbooks:
- `feature-task-decomposition`
- `farm-integration-review`

Skills can recommend actions and produce summaries, but workflow code decides what to execute.

## Skill Runtime Contract

Workflows call skills through a runtime boundary:

```text
run_skill(skill_name, context) -> SkillResult
```

Minimum `SkillResult` shape:

```json
{
  "status": "ok|needs_input|blocked",
  "summary": "human-readable concise output",
  "recommended_actions": [
    {"kind": "create_child_issue", "payload": {}}
  ]
}
```

Rules:
- Workflows may execute actions only after domain/policy checks.
- No critical workflow state transitions may depend on parsing freeform prose.

## Command-to-Workflow Ownership

1. `farm intake` -> `IntakeWorkflow`
2. `farm decide` + `farm run` -> `ExecutionWorkflow`
3. `farm review run` (target) -> `ReviewWorkflow`
4. `farm watch` + `farm pulse` -> `MonitorWorkflow`

## Where Planning Lives

Planning and decomposition are done by skill + operator flow:

- Chat and skill outputs define task breakdown.
- Runtime code performs deterministic issue creation/moves only.

Runtime code must never embed fixed decomposition templates or business-priority logic.

## Migration Plan

1. Extract existing `_cmd_*` logic from `src/farm/cli.py` into workflow modules.
2. Keep behavior identical during extraction (no policy changes in this step).
3. Introduce `SkillRuntime` abstraction and wire workflow invocation points.
4. Add workflow-level tests for each lifecycle path.
5. Reduce CLI to argument parsing + workflow dispatch only.

## Definition Of Done For This Architecture

1. All lifecycle decisions live in workflow/domain modules.
2. CLI has no duplicated lifecycle logic.
3. Skills are the only place for planning/review reasoning instructions.
4. Side effects happen only through adapters.
5. Workflow tests cover happy path + key failure paths.
