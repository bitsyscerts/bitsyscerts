---
description: "Use when running git or gh commands, committing changes, pushing branches, creating PRs, or performing any version control operation. Enforces read-only git access on integration branches (staging, main) and restricts direct commits to PR branches only."
applyTo: "**"
---

# Git Usage Rules

## Read Operations — Always Allowed

The following commands are always permitted on any branch:

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

## Integration Branches — No Commits, Ever

**`staging` and `main` are integration branches. Do not create commits on them under any circumstances.**

This applies to all write operations:

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

If the current branch is `staging` or `main`, stop. Do not proceed with any write git operation. Tell the user which branch you are on and ask them to create a feature branch.

Check the current branch before any write operation:

```bash
git rev-parse --abbrev-ref HEAD
```

## PR Branches — Commits Allowed

Commits, pushes, and branch operations are allowed when operating on a PR branch — a
short-lived feature/fix branch that is not `staging` or `main`, typically named with a
prefix such as `feat/`, `fix/`, `chore/`, `docs/`, `refactor/`.

Examples of valid PR branch names:

- `feat/hostname-search-perf`
- `fix/migration-concurrently`
- `chore/update-dependencies`

When operating autonomously or headless (e.g., inside a GitHub Actions workflow or an
agent invoked by a PR), commits and pushes to the current PR branch are permitted.

## Creating New Branches

Creating a new branch from `staging` is allowed. This is the expected way to begin new work:

```bash
git checkout -b feat/my-feature   # OK — creates a new PR branch
git push -u origin feat/my-feature  # OK — publishes the PR branch
```

## Opening Pull Requests

Opening a PR from a feature branch toward `staging` using `gh pr create` is allowed.
Opening a PR from `staging` toward `main` is a release operation — confirm with the user first.

## Decision Flowchart

```
git write operation requested?
  └─ yes → check current branch
               ├─ staging or main → STOP. Tell user; ask them to switch to a PR branch.
               └─ feature branch  → proceed with the write operation
```
