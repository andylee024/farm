# Farm V0: Technical Implementation Plan

**Status:** Draft for review (no implementation yet)  
**Date:** 2026-02-28  
**Scope:** Clean-slate rewrite of Farm runtime with incremental rollout

---

## 1) Purpose

This plan defines how Farm V0 will be implemented from scratch, starting with repository cleanup, then a framework skeleton, then incremental vertical slices. No implementation work starts until this plan is approved.

---

## 2) Locked V0 Decisions

- AI review is advisory only (non-blocking).
- Registry starts as JSON.
- JSON -> SQLite migration path is required.
- Max retries per ticket is `2`.
- `ready_for_review` gate is tests-only for V0.
- Farm runtime is rewritten from scratch.

---

## 3) Recommended Stack

- Language: `Python 3.12`
- CLI framework: `Typer`
- Data contracts: `pydantic v2`
- Config: `PyYAML` + typed config models
- Runtime/process control: `asyncio` + `subprocess`
- Test framework: `pytest`
- Storage:
  - V0: JSON store at `data/registry.json`
  - V1: SQLite store behind same storage interface

Rationale: this is orchestration-heavy local automation; Python gives fastest iteration and strongest fit for shell/worktree/tmux orchestration.

---

## 4) Target Repository Layout (Post-Cleanup)

```text
farm/
  docs/
    prd.md
    feature/
      v0/
        technical_plan.md
  data/
    registry.json
  src/farm/
    __init__.py
    cli.py
    core/
      models.py
      state_machine.py
      events.py
      errors.py
    services/
      orchestrator.py
      scheduler.py
      launcher.py
      verifier.py
      gatekeeper.py
      notifier.py
    adapters/
      linear_api.py
      git.py
      tmux.py
      ci.py
      storage_json.py
      storage_sqlite.py   # stub in V0
    prompts/
      templates.py
    config.py
  tests/
    unit/
    integration/
```

---

## 5) Phase 0: Repository Cleanup (Fresh Start)

Goal: remove legacy runtime implementation and old tests so V0 starts from a clean baseline.

### 5.1 Cleanup scope

Remove legacy implementation files under:
- `src/farm/*.py` (except optional temporary `__init__.py` placeholder)
- `tests/test_*.py` tied to legacy modules
- all `__pycache__/` artifacts
- `.pytest_cache/`

Keep:
- `docs/prd.md`
- `docs/feature/v0/technical_plan.md`
- `pyproject.toml` (to be updated, not deleted)
- `config.yaml.example` (may be rewritten)
- `data/` and `logs/` directories

### 5.2 Safety procedure

1. Capture full pre-cleanup snapshot with `git status` + file inventory.
2. Create a dedicated rewrite branch.
3. Commit snapshot before deletion.
4. Delete legacy runtime/test files in one explicit commit.
5. Verify package still installs and CLI entrypoint resolves.

Deliverable: empty but valid skeleton package, no legacy behavior retained.

---

## 6) Core Contracts (Implement before business logic)

### 6.1 Task state machine

```text
drafted -> queued -> running -> pr_open
pr_open -> tests_passed -> ready_for_review
pr_open -> tests_failed -> retrying (attempt 1..2) -> running
pr_open -> tests_failed at attempt 2 -> blocked_needs_human
ready_for_review -> merged | changes_requested
changes_requested -> queued
```

### 6.2 Task record schema (JSON V0)

Each task record includes:
- `task_id`
- `repo`
- `linear_issue_id`
- `state`
- `attempt`
- `max_retries` (default `2`)
- `agent` (`codex` or `claude`)
- `worktree_path`
- `branch`
- `tmux_session`
- `pr_number` (nullable)
- `test_status` (`unknown|pass|fail`)
- `created_at`, `updated_at`
- `last_error` (nullable structured object)
- `schema_version`

### 6.3 Storage interface

Define `RegistryStore` interface now:
- `get_task(task_id)`
- `save_task(task)`
- `list_tasks(filter)`
- `append_event(task_id, event)`
- `lock_task(task_id)`

Implement JSON adapter first; keep SQLite adapter stubbed but interface-compliant.

---

## 7) Incremental Implementation Phases

## Phase 1: Framework Skeleton

- Build package layout.
- Implement typed models + state transition guards.
- Implement JSON storage adapter.
- Implement minimal CLI scaffolding.

Exit criteria:
- `farm --help` works.
- Unit tests validate allowed/disallowed state transitions.

## Phase 2: First Vertical Slice (Single Task E2E)

- `intent -> Linear parent/child ticket creation`
- scheduler picks one `Ready` task
- launcher creates worktree + tmux + agent run
- registry updates from `queued -> running -> pr_open`

Exit criteria:
- one real ticket can be launched and tracked in registry.

## Phase 3: Verification + Retry Policy

- attach CI test result polling
- enforce tests-only ready gate
- implement retry loop with cap `2`
- transition to `blocked_needs_human` at retry exhaustion

Exit criteria:
- test fail/passing paths produce correct state transitions.

## Phase 4: Integration + Operator Loop

- enforce PR target branch as `integration`
- add notifications: `ready_for_review`, `blocked_needs_human`
- add run summary output for human merge review

Exit criteria:
- autonomous loop runs without manual polling for one repo.

## Phase 5: SQLite Migration Readiness

- implement `storage_sqlite.py`
- add `json_to_sqlite` migration command
- run temporary dual-write validation

Exit criteria:
- JSON and SQLite produce identical read views for sampled tasks.

---

## 8) CLI Surface (Planned)

- `farm intake` - create one Linear issue (parent or child) with explicit fields
- `farm decide` - apply human approve/cancel decision for one issue
- `farm run` - execute one scheduler + launcher cycle from locally queued tasks
- `farm status` - print concise board + local runtime summary

---

## 9) Testing Strategy

- Unit tests:
  - state machine transitions
  - retry boundaries (`attempt <= 2`)
  - JSON store reads/writes and schema version handling
- Integration tests:
  - mocked Linear + mocked tmux + mocked CI flow
  - end-to-end task lifecycle happy/fail paths
- Smoke tests:
  - one real ticket on one repo in canary mode

---

## 10) Rollout Strategy

- Stage 1: canary on low-risk tickets only
- Stage 2: expand to medium-risk backend tasks
- Stage 3: broaden to multi-ticket daily queue

Operational controls:
- concurrency cap (start at `1`)
- hard retry cap (`2`)
- immediate pause switch if repeated failure pattern detected

---

## 11) Risks And Mitigations

- Rewrite churn risk -> freeze scope to V0 states/gates until first stable loop.
- State divergence risk -> single state authority in registry and idempotent transition handlers.
- Resource pressure risk -> scheduler enforces queue backpressure and concurrency limits.
- Hidden failures risk -> structured event logging per state transition.

---

## 12) Review Checklist (Before Implementation)

- Confirm cleanup file deletion scope.
- Confirm target package layout.
- Confirm CLI command names.
- Confirm state machine and retry policy.
- Confirm JSON schema fields.
- Confirm canary rollout criteria.

After approval, implementation starts with Phase 0 cleanup commit.
