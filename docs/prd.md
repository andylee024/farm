# Farm: Product Requirements Document (PRD)

**Status:** Draft  
**Last Updated:** 2026-02-28  
**Product Type:** Local orchestration control plane for autonomous coding  
**Primary Stack:** Farm + NanoClaw + Agent Deck + Scout + Linear  
**Implementation Strategy:** Rewrite Farm runtime from scratch for V0

---

## 1) Product Goal

Farm should let one developer operate like a small engineering team by turning natural-language intent into safely merged code with minimal coordination overhead.

Farm is the control plane that:
- translates intent into structured tickets,
- launches and supervises coding agents,
- enforces deterministic quality gates,
- escalates only when human judgment is required.

---

## 2) Problem Statement

Current workflows fragment across chat, planning, execution, and review tools. This creates four recurring failures:

1. **Planning drift:** intent is not converted into stable, testable work units.
2. **Execution drift:** agents run without consistent constraints and boundaries.
3. **Verification drift:** PR quality varies because completion criteria are inconsistent.
4. **Integration drift:** parallel branches merge late and break at integration time.

Farm exists to remove these failures with a single orchestrated lifecycle from request to merge.

---

## 3) Target User And Jobs To Be Done

**Primary user:** solo technical founder (or very small engineering team) shipping quickly across multiple repos.

**Jobs to be done:**
- capture feature/bug intent in chat,
- create structured Linear tickets with acceptance criteria,
- execute tickets in parallel with isolated agents,
- review only PRs that already passed hard gates,
- merge with confidence into an integration branch and then main.

---

## 4) Product Principles

1. **Linear-first system of record:** tickets, states, and evidence are traceable.
2. **State machine over ad hoc scripts:** every task has an explicit lifecycle.
3. **Least privilege by default:** orchestrator and coding agents have different permissions.
4. **Task-scoped context:** agents receive only what is needed for one ticket.
5. **Deterministic done criteria:** no task is "ready" without objective checks.
6. **Human decisions at high-leverage points only:** scope approval, retry policy, final merge.

---

## 5) Architecture Overview

### 5.1 Control Plane (Farm)
- intake from NanoClaw/chat and local docs,
- ticket decomposition and routing,
- task orchestration and retries,
- final readiness signaling.

### 5.2 Ticket Plane (Linear via Direct API)
- canonical task objects,
- approval and state transitions,
- evidence links (PRs, CI, screenshots, review summaries).

### 5.3 Execution Plane (Agent Deck + Worktrees)
- one ticket -> one worktree -> one tmux session -> one agent run,
- model assignment by task type and risk profile.

### 5.4 Verification Plane
- tests-only quality gate for V0,
- CI test status aggregation and failure classification,
- AI review as advisory signal only (non-blocking).

### 5.5 Integration Plane
- PRs land to a persistent `integration` branch,
- scheduled `integration -> main` PR for final human review,
- automated follow-up tickets when integration breaks.

### 5.6 Architecture Sketch (ASCII)
```text
                           +----------------------+
                           |   You / NanoClaw     |
                           |  (intent + approve)  |
                           +----------+-----------+
                                      |
                                      v
                          +-----------+------------+
                          | Farm Control Plane     |
                          | - parse intent         |
                          | - decompose tickets    |
                          | - route model          |
                          +-----------+------------+
                                      |
                           create/update Linear issues
                                      |
                                      v
+--------------------+      poll "Ready"      +-----------------------+
| Linear (source of  |<---------------------->| Farm Scheduler         |
| truth for tickets) |                       | - queue + concurrency   |
+---------+----------+                       | - retries (max 2)       |
          |                                  +-----------+------------+
          |                                              |
          | writes state/evidence                        | launch
          v                                              v
+---------+----------------------------------------------+-------------+
|                    Task Runtime                                       |
|  worktree + tmux + agent (Codex/Claude) per ticket                   |
+---------+----------------------------------------------+-------------+
          |                                              |
          | PR to integration branch                     | write run state
          v                                              v
+---------+----------+                          +--------+-------------+
| GitHub PR + CI     |                          | data/registry.json    |
| (tests-only gate)  |                          | (runtime registry)    |
+---------+----------+                          +-----------------------+
          |
          | AI review (advisory comment only)
          v
+---------+------------------+
| Farm Gatekeeper            |
| tests pass -> ready        |
| tests fail + retries < 2   |
|   -> retry with new prompt |
| else -> blocked            |
+---------+------------------+
          |
          v
+---------+------------------+
| Notify You                |
| ready_for_review/blocked  |
+---------------------------+
```

---

## 6) Main Architectural Considerations

1. **Canonical state model**  
Task states must be explicit and deterministic:
`drafted -> queued -> running -> pr_open -> tests_failed|ready_for_review`
`tests_failed -> retrying (attempt 1..2) -> running`
`tests_failed at attempt 2 -> blocked_needs_human`
`ready_for_review -> merged|changes_requested`

2. **Context partitioning**  
Farm keeps business context and history. Coding agents get only ticket scope, local code context, and constraints.

3. **Security boundaries**  
Farm may access sensitive systems if needed. Coding agents should never hold production credentials or broad external access.

4. **Isolation and reproducibility**  
Every execution run must be reproducible from ticket ID, branch/worktree, prompt pack, and commit history.

5. **Deterministic completion gates**  
`ready_for_review` is set only when required checks pass. PR creation alone is never "done."

6. **Adaptive retries**  
Retries must include diagnosis and revised guidance. Blind reruns are disallowed.

7. **Operational observability**  
Central registry and event log must answer: what ran, why it failed, what changed, and what is blocked.

8. **Resource constraints**  
Parallelism must be throttled by CPU/RAM limits, especially for TypeScript-heavy repos.

---

## 7) V0 Scope

### In scope
- Chat-to-ticket decomposition into Linear parent + child issues.
- Ticket-to-agent launcher with worktree and tmux session creation.
- Task registry with runtime states and retry metadata.
- Monitor loop for session health, PR creation, and CI status.
- Tests-only quality gate and `ready_for_review` notification.
- Integration branch workflow (`feature -> integration -> main`).
- Max retry count of `2` before moving to `blocked_needs_human`.
- AI review capture as advisory evidence only.
- JSON registry backend with a defined migration path to SQLite.

### Out of scope
- Full autonomous product management across all repos.
- Automatic deploys and auto-merge to production.
- Complex multi-agent collaborative swarms on one ticket.
- Rich memory platform integration beyond local artifacts.
- Blocking AI review policies.

---

## 8) V0 Implementation Plan (Light)

### Phase 1: Contracts and state
- Define task schema and status enum.
- Define Linear field/state mapping.
- Create local JSON registry (`data/registry.json`) and versioned schema.

### Phase 2: Core orchestration loop
- Implement `intent -> ticket graph` command.
- Implement `ticket -> execution` launcher (worktree + tmux + model routing).
- Implement monitor loop and failure classification.
- Enforce retry policy (`max_retries=2`) with transition to `blocked_needs_human`.

### Phase 3: Verification and integration
- Add CI test aggregation (tests-only gate in V0).
- Add advisory AI review summary capture.
- Add integration branch manager and daily cleanup.

### Phase 4: Operator UX
- Add concise notifications (blocked, retry decision needed, ready for review).
- Add run summaries for quick merge decisions.

### Phase 5: Storage migration path
- Implement `RegistryStore` interface with JSON adapter first.
- Add SQLite adapter with equivalent schema and operations.
- Build one-time migration command (`json_to_sqlite`) with validation.
- Run dual-write validation window, then move reads to SQLite.

---

## 9) Success Metrics

- **Cycle time:** median time from ticket creation to ready-for-review.
- **Autonomy rate:** percentage of tickets completed without manual intervention.
- **Merge confidence:** percentage of agent PRs merged without post-merge rollback.
- **Review load:** average human review time per ready PR.
- **Failure visibility:** percentage of failed runs with clear machine-readable reason.

---

## 10) Extensibility Strategy

1. **Adapter interfaces**  
Keep integrations pluggable: ticketing, agent providers, CI providers, notifications.

2. **Policy as configuration**  
Route selection, done criteria, and retry limits should live in config, not hardcoded branches.

3. **Event-driven core**  
Emit normalized events (`task_started`, `ci_failed`, `review_ready`) so new capabilities can subscribe without changing orchestration core.

4. **Schema versioning**  
Version prompt packs, task records, and run artifacts so workflow upgrades do not break historical runs.

5. **Capability routing**  
Use task metadata to route backend, frontend, infra, and docs work to different agent profiles.

6. **Learning loop**  
Store retry outcomes and useful prompt patterns as reusable playbooks tied to task type.

7. **Storage abstraction**  
Keep storage behind a stable interface so JSON, SQLite, or remote stores can be swapped without changing orchestration logic.

---

## 11) Risks And Mitigations

- **Over-automation risk:** require explicit human checkpoints for scope and merge.
- **False confidence from AI review:** keep hard CI gates and treat AI review as additive.
- **Resource exhaustion:** implement queue concurrency limits and backoff.
- **Prompt/context drift:** use structured prompt templates with required sections.
- **Rewrite regression risk:** phase rollout by running new runtime on a small ticket subset first.

---

## 12) Open Questions

- What is the first notification channel: Telegram, WhatsApp, or both?
- At what milestone should we promote from tests-only to full gate set (lint, types, screenshots)?
- What ticket categories should bypass integration and go directly to main, if any?

---

## 13) V0 Decisions Locked (Approved)

- AI review is advisory only (non-blocking).
- Registry backend starts with JSON.
- Migration plan to SQLite is required as part of V0 design.
- Max retries per ticket is `2`.
- V0 `ready_for_review` gate is tests-only.
- Farm runtime can be rewritten from scratch.
