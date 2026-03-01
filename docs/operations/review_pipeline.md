# Farm Review Pipeline

Status: Active  
Last updated: 2026-03-01

## Purpose

Define a deterministic review pipeline that produces one clear human decision point.

- `verify` checks objective merge readiness.
- `review` performs quality assessment and remediation on the integration branch.
- Parent issue moves to `In Review` only after pipeline pass.

## Lifecycle

1. Gather completed child tasks for a parent issue.
2. Build/update integration branch and parent PR.
3. Run `verify` gates.
4. Run reviewer pass on the integration diff.
5. Apply fixes directly on integration branch when blockers are found.
6. Re-run `verify`.
7. Publish summary for human review.
8. Move parent issue to `In Review` on pass.

## Verify Gates

All must pass:

1. Parent PR exists and points to integration branch.
2. Branch is up to date with base.
3. Required CI checks are green.
4. Required evidence is present:
   - screenshots for UI changes,
   - reproduction notes for bug fixes (when applicable),
   - test commands and outcomes.

## Review Behavior

Reviewer acts on the integration branch:

1. Identify blocking findings (`critical`, `high`).
2. Patch code directly in integration branch.
3. Commit and push remediation.
4. Re-run verification.
5. Repeat until:
   - pass, or
   - max remediation loops reached.

If max loops is reached, status is `needs_fix` and parent does not move to `In Review`.

## Outcome States

1. `pass`:
   - parent PR ready for human review,
   - parent Linear issue moved to `In Review`.
2. `needs_fix`:
   - unresolved blockers or failed gates,
   - parent remains pre-review state.
3. `blocked`:
   - merge conflict, infra/auth outage, or missing prerequisite.

## Required Review Summary (PM + CTO)

Every review cycle must produce this structure in PR comment and parent issue note:

```md
## 1) Feature Purpose (PM Context)
- Problem this solves:
- Who it’s for:
- Intended outcome:
- Business reason / priority now:

## 2) Scope and Boundaries
- In scope:
- Out of scope:
- Non-goals:

## 3) Technical Implementation Overview (CTO Context)
- Architecture touchpoints:
- End-to-end flow:
- Key design decisions:
- Alternatives considered:
- Operational considerations:
- Failure modes + mitigations:
- Compatibility/migration:

## 4) What Was Implemented
- Concrete behavior changes (before -> after):
- Major files/components touched:
- Linked child tasks/issues:

## 5) Validation and Evidence
- CI/checks status:
- Tests run + outcomes:
- Manual verification:
- UI artifacts/screenshots (if relevant):

## 6) Risks and Follow-ups
- Remaining risks:
- Deferred items:
- Recommended next steps:

## 7) Decision Request
- Recommendation: Ready for Review | Needs Fix
- Human reviewer focus areas (top 3):
```

## Operating Notes

1. Keep planning/business logic in skills and docs, not runtime orchestration code.
2. Keep runtime code focused on deterministic orchestration and API/CLI operations.
3. Prefer explicit failure over silent fallback for review gates.
