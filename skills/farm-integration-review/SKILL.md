---
name: farm-integration-review
description: Consolidate completed Farm child worktrees into one integration PR, run review, and update the parent Linear issue with the PR link and final status. Use when child issues are in Completed/ready_for_review and the user wants one parent-level review PR.
---

# Farm Integration Review

Use this after child execution is done and you want one parent-level integration PR.

## Required Inputs

- `parent_issue_id` (Linear parent issue id)
- `repo` (`<repo-key>` configured in Farm)
- `base_branch` (usually `main`)
- `parent_ready_status` (parent review stage, default `In Review`)

## Workflow

1. Build child candidate list from local registry + Linear parent relation.
2. Review each child branch/worktree quickly for regressions and scope drift.
3. Create one integration branch from base and merge child branches.
4. Run full tests and a `codex review` pass on the integrated diff.
5. Push integration branch and open one PR.
6. Update parent Linear issue with PR link and move it to `In Review` (or your configured parent review stage).

## Rules

- Keep runtime logic thin: use shell/git/codex commands and direct Linear API calls.
- Do not encode decomposition/planning logic in runtime code.
- If merge conflicts appear, resolve explicitly and rerun validation before PR.
- Do not mark parent ready until integrated tests + review pass.
- Always produce the required PM+CTO summary template for the parent PR review handoff.

## Playbook

Read [references/review_playbook.md](references/review_playbook.md) and follow command order exactly.

## Script

Use [scripts/update_parent_issue.py](scripts/update_parent_issue.py) to append PR metadata to the parent issue and move status to `In Review` (or your custom parent review stage).
