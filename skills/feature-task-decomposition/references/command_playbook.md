# Farm Planning + Execution Playbook (Simple)

## 1) Decompose In Chat First

Before execution:

- Define parent outcome.
- Define atomic child issues.
- For each child, include:
  - `Context To Read First` (docs + file paths)
  - objective `Acceptance Criteria` checklist
  - explicit `Evidence Required` checklist

## 2) Approve One Child In Linear

Set target child issue state to `Approved`.

## 3) Execute One Child

```bash
farm run --config config.yaml --repo <repo-key> --issue <child-issue-id>
```

## 4) Observe While Running

```bash
farm watch --config config.yaml --repo <repo-key>
```

## 5) Optional Progress Updates

```bash
farm update --config config.yaml --repo <repo-key> --issue <child-issue-id> --phase running --summary "..."
```

## 6) Finish

```bash
farm finish --config config.yaml --repo <repo-key> --issue <child-issue-id> --outcome completed --summary "..." --pr-url "<optional-pr-url>"
# or canceled
farm finish --config config.yaml --repo <repo-key> --issue <child-issue-id> --outcome canceled --summary "..."
```

## 7) Check Snapshot

```bash
farm status --config config.yaml --repo <repo-key> --issue <child-issue-id>
```
