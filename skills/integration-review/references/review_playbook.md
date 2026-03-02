# Farm Integration Review Playbook (Simple)

## 0) Set Variables

```bash
PARENT_ID="<linear-parent-issue-id>"
REPO="<repo-key>"
BASE="main"
REPO_ROOT="<absolute-repo-path>"
INTEGRATION_BRANCH="farm/${REPO}/parent-${PARENT_ID:0:8}-integration-$(date +%Y%m%d-%H%M)"
```

## 1) Choose Child Branches

Use Linear to list child issues under parent and pick those in `Completed`.

## 2) Review Per Child

```bash
git -C "$REPO_ROOT" fetch origin
BRANCH="farm/<child-issue-id>"
git -C "$REPO_ROOT" log --oneline --no-merges "origin/$BASE..$BRANCH"
git -C "$REPO_ROOT" diff --stat "origin/$BASE...$BRANCH"
```

## 3) Build Integration Branch

```bash
git -C "$REPO_ROOT" switch -c "$INTEGRATION_BRANCH" "origin/$BASE"
BRANCH="farm/<child-issue-id>"
git -C "$REPO_ROOT" merge --no-ff --no-edit "$BRANCH"
```

Resolve conflicts explicitly if needed.

## 4) Validate

```bash
cd "$REPO_ROOT"
pytest -q
codex review --base "origin/$BASE" "Review for regressions and missing tests."
```

## 5) Open Parent PR

```bash
git -C "$REPO_ROOT" push -u origin "$INTEGRATION_BRANCH"
```

## 6) Update Parent Linear Issue

```bash
python3 skills/farm-integration-review/scripts/update_parent_issue.py \
  --config config.yaml \
  --issue "$PARENT_ID" \
  --pr-url "<opened-pr-url>" \
  --note "Integrated completed child branches"
```

## 7) Publish Review Summary

```md
## Review Summary
- Parent:
- Integrated branches:
- Tests:
- Risks:
- Decision: Ready for Review | Needs Fix
```
