# Farm Planning + Execution Playbook (Simple)

## 1) Decompose In Chat First

Before execution:

- Define parent outcome.
- Define atomic child issues.
- Confirm deterministic checks.

## 2) Approve One Child In Linear

Set target child issue state to `Approved`.

## 3) Execute One Child

```bash
farm run --config config.yaml --repo <repo-key> --issue <child-issue-id>
```

## 4) Optional Progress Updates

```bash
farm update --config config.yaml --repo <repo-key> --issue <child-issue-id> --phase running --summary "..."
```

## 5) Finish

```bash
farm finish --config config.yaml --repo <repo-key> --issue <child-issue-id> --outcome completed --summary "..." --pr-url "<optional-pr-url>"
# or canceled
farm finish --config config.yaml --repo <repo-key> --issue <child-issue-id> --outcome canceled --summary "..."
```

## 6) Check Snapshot

```bash
farm status --config config.yaml --repo <repo-key> --issue <child-issue-id>
```
