# Worker brief

Each runnable issue gets one agent, on the issue's suggested model. The orchestrator creates the worktree and venv first (git operations one at a time), so the worker never clones or pushes.

The brief is in two parts. What every worker in the run shares is written once to a file; each worker is sent only the path to it and the lines about its own issue. In one run of seven workers the shared rules were about sixty lines repeated seven times.

## Part 1: the run's shared rules (one file, written once)

```text
Rules for every worker in this run of <OWNER/REPO>. Read all of this before starting.

Repo rules (from CLAUDE.md, CONTRIBUTING.md; they win over this file):
- Gate: <exact commands>
- Do not edit: <shared/generated files>. If your issue seems to need it, stop and report.
- Changes together with a feature: <README row, CHANGELOG [Unreleased], TOOL_NAMES, ...>
- <any other rule that bears on the work>

Your workspace is your worktree and nothing else:
- Run every command with the worktree's own virtualenv, as <worktree>/.venv/bin/python -m ..., never a
  bare `python` or `pytest`: the system Python may have another checkout installed and would test that.
- Anything you write outside git (gate logs, notes, PR_BODY.md) goes under <worktree>/.queue/, which is
  already excluded from git. Never write to a folder another worker could share.

Do:
1. Implement the issue as written; where you deviate, note why.
2. Run the full gate. Fix until it passes. Never skip or loosen a test. If a test is skipped because a
   tool is missing, that is not a pass: report it.
3. Commit on your branch with the repo's commit style. Do NOT push, open a PR or touch other branches.
4. Write the PR description to <worktree>/.queue/PR_BODY.md, following the repo's PR template or, if
   none, the issue's "Done when": What, decisions, deviations, tests, unverified. First line
   "Closes #<N>". The detail goes here, not in your reply.
5. Reply in at most 15 lines: branch, commit SHA(s), the gate's exact summary lines (e.g. "441 passed,
   1 skipped"), the decisions a reviewer should check (one line each), and anything you could not do.
   Do not say "CI is green": you have not seen CI.
```

## Part 2: one worker's brief

```text
You are implementing issue #<N> in <OWNER/REPO>: "<title>".
First read the run's rules: <path to the shared file>. Then the issue body, in full:
  gh api repos/<OWNER/REPO>/issues/<N> -q .body

- Worktree: <path>, branch <branch>, based on <main | branch-of-#M (same lane: #M's commits are below
  yours; don't touch #M's changes)>.
- Assigned by the queue (use these, not the numbers in the issue): <HARDWARE_VALIDATION step 14>
- <anything that applies to this issue only>
```

## Orchestrator setup per worker

```sh
# one at a time
git -C <clone> fetch --depth=50 origin main
git -C <clone> worktree add -b <branch> <path> origin/main          # or <base-branch> when stacked
python3 -m venv <path>/.venv
<path>/.venv/bin/pip install -q <what the repo's CI installs>               # see below
<path>/.venv/bin/python -c "import <pkg>, sys; print(<pkg>.__file__)"   # must print a path under <path>
mkdir -p <path>/.queue && echo ".queue/" >> "$(git -C <path> rev-parse --git-path info/exclude)"
```

Install what the repo's CI job installs, read from its workflow or CONTRIBUTING.md: `-e "<path>[dev]"` for a package with a `pyproject.toml`, `-r requirements.txt -r requirements-dev.txt` for an app that has only requirements files. Guessing `-e ".[dev]"` fails on the second kind.

The last line is the check that the venv tests this worktree's code and not another checkout's; it applies when the repo is an installable package. If it prints any other path, the editable install went to the wrong place; fix it before starting the worker. For an app run from its directory there is nothing to import-check: run the gate from `<path>`.

Branch names: `claude/<repo-short>-<slug>` (the hand run used `claude/harmony-sleep-timer`), unless the repo's rules say otherwise.

## Opening the PR

Always against the default branch, also for a branch that was started from another PR's branch:

```sh
gh api repos/<OWNER/REPO>/pulls -f head=<branch> -f base=<default branch> -f title=... -F body=@<path>/.queue/PR_BODY.md
```

A PR whose base is another PR's branch is merged into that branch, not into the default one. GitHub moves such a PR to the default branch only if the branch below it is deleted when it merges, which depends on a repository setting (delete branches on merge) that many repositories leave off. The skill does not rely on it and does not change it; if the owner turns it on, merged branches are tidied away and nothing else here changes.

## Why the worker doesn't push

On 2026-11-12 four agents each cloned and pushed, and the git proxy's two-operations-per-repo limit returned HTTP 429. Centralising git in the orchestrator also means the orchestrator holds every branch and can restack them, and the PR is opened by the session that will read its CI.
