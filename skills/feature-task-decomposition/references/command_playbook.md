# Farm Linear Planning Playbook

## 1) Decompose In Chat First

Before running CLI commands:
- State the parent outcome in one sentence.
- Propose child issues as atomic, independently testable units.
- For each child, define:
  - title
  - scope
  - deterministic acceptance checks
  - startup instruction to read the repository for full context before coding
  - repo (`<repo-key>` from Farm config)

## 2) Create Parent

```bash
farm intake \
  --title "<parent title>" \
  --description "<parent outcome + constraints>" \
  --repo <repo-key> \
  --status backlog
```

Capture parent issue id from CLI output.

## 3) Create Children

Run once per child:

```bash
farm intake \
  --title "<child title>" \
  --description "<child scope + acceptance checks + evidence needed>" \
  --repo <repo-key> \
  --parent-id <parent-issue-id> \
  --status backlog
```

Farm appends a standard `Agent Startup Instructions` block to child issue descriptions automatically.

## 4) Human Decision Gate

Approve:

```bash
farm decide --issue <child-issue-id> --approve --repo <repo-key>
```

Cancel:

```bash
farm decide --issue <child-issue-id> --cancel
```

## 5) Execute

```bash
farm run --repo <repo-key>
```

Run repeatedly as needed.

## 6) Observe

```bash
farm status
```

Use output to decide:
- approve next children,
- unblock/cancel tasks,
- or move to review/merge steps.
