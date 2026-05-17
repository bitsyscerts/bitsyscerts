---
description: "Use when running git or gh commands, committing changes, pushing branches, creating PRs, or performing any version control operation. Enforces read-only git access on integration branches (staging, main) and restricts direct commits to PR branches only."
applyTo: "**"
---

# Git Usage Rules

## Interactive vs Headless — The Fundamental Distinction

How much git involvement is appropriate depends on the execution context:

| Context         | Description                                               | Git write operations                                      |
| --------------- | --------------------------------------------------------- | --------------------------------------------------------- |
| **Interactive** | User is present in VS Code chat or terminal               | **Modify files only. Stop there.**                        |
| **Headless**    | GitHub Actions, agent invoked by a PR, automated workflow | Commits and pushes on the current PR branch are permitted |

### Interactive sessions (default)

When a user is actively present in the conversation:

1. **Make file changes only.** Edit, create, or delete files as requested.
2. **Stop. Do not `git add`, `git commit`, `git push`, create branches, or open PRs.**
3. Leave the working tree in a modified state for the user to review and commit at their own pace.

This avoids creating commits, branches, or PRs that the user then has to clean up.
The user owns the git workflow entirely. The agent owns only the file content.

### Headless sessions

When operating without a user present (GitHub Actions, a PR-triggered agent run, etc.),
commits and pushes on the **current PR branch** are permitted. The headless context must be
explicitly clear from the invocation environment — do not assume headless mode during a
normal chat session.

---

## Read Operations — Always Allowed

The following commands are always permitted on any branch in any context:

```bash
git status
git log
git diff [<ref>]
git show [<ref>]
git branch [--list]
git fetch [--dry-run]
git rev-parse --abbrev-ref HEAD
git ls-files
gh pr list
gh pr view
gh pr checks
gh issue list
gh issue view
gh repo view
```

---

## Integration Branches — No Commits, Ever

**`staging` and `main` are integration branches. Do not create commits on them under any circumstances — interactive or headless.**

| Operation                                 | Allowed on `staging`/`main`? |
| ----------------------------------------- | ---------------------------- |
| `git commit`                              | **NEVER**                    |
| `git commit --amend`                      | **NEVER**                    |
| `git push` (direct branch push)           | **NEVER**                    |
| `git merge`                               | **NEVER**                    |
| `git rebase`                              | **NEVER**                    |
| `git reset --hard`                        | **NEVER**                    |
| `git tag`                                 | **NEVER**                    |
| `git push --force` / `--force-with-lease` | **NEVER**                    |

If the current branch is `staging` or `main` and a write operation is needed: stop, tell
the user which branch is active, and ask them to switch. Do not create a branch on their
behalf during an interactive session.

---

## PR Branches — Commits Allowed (Headless Only)

Short-lived feature/fix branches (`feat/`, `fix/`, `chore/`, `docs/`, `refactor/`) are the
only branches where commits and pushes are ever appropriate — and only in headless context.

Examples of valid PR branch names:

- `feat/hostname-search-perf`
- `fix/migration-concurrently`
- `chore/update-dependencies`

---

## Opening Pull Requests

Opening a PR from a feature branch toward `staging` is a headless-only operation.
Opening a PR from `staging` toward `main` is a release operation — confirm with the user first.
**Never open a PR during an interactive session without being explicitly asked to.**

---

## Decision Flowchart

```
any git write operation?
  └─ interactive session?
       ├─ yes → STOP. Make file changes only. Leave git to the user.
       └─ no (headless) → check current branch
                            ├─ staging or main → STOP. Do not commit.
                            └─ PR branch       → proceed
```
