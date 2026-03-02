---
name: farm-integration-review
description: Consolidate completed child work into one integration PR and publish final review context for the parent issue.
---

# Farm Integration Review

Use this after child issues are completed.

## Required Inputs

- `parent_issue_id`
- `repo` (`<repo-key>` in config)
- `base_branch` (usually `main`)

## Workflow

1. Identify completed child issues in Linear.
2. Review each child branch/worktree quickly.
3. Build integration branch from base and merge selected child branches.
4. Run repository tests and code review.
5. Open one integration PR.
6. Update parent issue with PR URL and review summary.

## Rules

- Keep runtime logic thin and deterministic.
- Do not move parent to review without passing validation.
- Include PM + technical summary in parent handoff.

## Playbook

Read [references/review_playbook.md](references/review_playbook.md).
