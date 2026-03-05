---
name: feature-task-decomposition
description: Plan and decompose work into parent/child Linear issues, then execute one approved child at a time with the Farm single-task runner.
---

# Feature Task Decomposition

## Goal

Create short, clear, objective Linear tasks that are easy for coding agents to execute correctly.

## Workflow

1. Read `docs/operations/operations.md`.
2. Decompose user intent into one parent plus atomic child issues.
3. Write each child issue using the Child Spec Contract below.
4. Move one child to `Approved` in Linear.
5. Run one child via Farm `run/update/finish/status/watch` commands.

## Operating Rules

- Farm runtime is execution-only; planning stays in skill output and issue descriptions.
- Keep one active child task per run invocation.
- Track progress through `task_updates.jsonl` and final outcome through `task_result.json`.
- Keep task specs short; avoid long PRD-style prose inside child tasks.

## Child Spec Contract (Required)

Each child issue description should be concise and include five sections:

1. `Goal` (2-4 lines): what outcome must be true when done.
2. `Context To Read First` (paths): docs + likely code files to inspect before coding.
3. `Scope` (in/out): what to change and what not to change.
4. `Acceptance Criteria` (checklist): objective, verifiable checks only.
5. `Evidence Required` (checklist): exact proof the agent must provide on completion.

### Child Spec Template

Use this template when drafting child issues:

```md
## Goal
<2-4 lines, concrete outcome>

## Context To Read First
- AGENTS.md
- docs/operations/operations.md
- <relevant file/path 1>
- <relevant file/path 2>

## Scope
- In: <allowed changes>
- Out: <explicitly out of scope>

## Acceptance Criteria
- [ ] <objective check 1>
- [ ] <objective check 2>
- [ ] <objective check 3>

## Evidence Required
- [ ] `git diff --name-only` list matches intended scope
- [ ] Required test/lint command output is provided
- [ ] Brief mapping from each acceptance criterion to evidence
- [ ] `farm status --issue <id> --repo <repo>` snapshot at completion
```

## Prompting Guidance For Child Tasks

When writing child issue text, explicitly instruct the task agent to:

1. Read listed docs and code paths before coding.
2. Summarize understanding briefly before making changes.
3. Keep implementation minimal and within declared scope.
4. Return evidence that maps directly to acceptance criteria.

## Command Playbook

Read [references/command_playbook.md](references/command_playbook.md).
