# Worker brief

Each runnable issue gets one agent, on the issue's suggested model, with this brief filled in. The orchestrator creates the worktree and venv first (git operations one at a time), so the worker never clones or pushes.

```text
You are implementing issue #<N> in <OWNER/REPO>: "<title>". The issue body is your prompt; read it in full:
  gh api repos/<OWNER/REPO>/issues/<N> -q .body

Workspace (already set up for you; use nothing else):
- Worktree: <path>, branch <branch>, based on <main | branch-of-#M (stacked)>.
- Virtualenv: <path>/.venv. Run every command as <path>/.venv/bin/python -m ..., never a bare `python` or `pytest`:
  the system Python has a different checkout installed editable and would test the wrong code.

Repo rules (from CLAUDE.md, CONTRIBUTING.md; they win over this brief):
- Gate: <exact commands>
- Do not edit: <shared/generated files>. If the issue seems to need it, stop and report.
- Changes together with this work: <README row, CHANGELOG [Unreleased], TOOL_NAMES, ...>
- <any other rule that bears on this issue>

Assigned by the queue (use these, not the numbers in the issue):
- <HARDWARE_VALIDATION step 14>
- <stacked: "Your branch sits on #M's. Don't touch #M's changes.">

Do:
1. Implement the issue as written; where you deviate, note why.
2. Run the full gate in the venv. Fix until it passes. Never skip or loosen a test.
3. Commit on <branch> with the repo's commit style. Do NOT push, open a PR or touch other branches;
   the orchestrator does that (the git proxy allows two concurrent operations per repo).
4. Write the PR description to <path>/PR_BODY.md (outside git: add it to .git/info/exclude), following
   the repo's PR template or, if none, the issue's "Done when": What, decisions, deviations, tests,
   unverified on hardware. First line "Closes #<N>".
5. Reply with: branch, commit SHA(s), the gate's exact summary lines (e.g. "441 passed, 1 skipped"),
   and anything you could not do. Do not say "CI is green": you have not seen CI.
```

## Orchestrator setup per worker

```sh
# one at a time
git -C <clone> fetch --depth=50 origin main
git -C <clone> worktree add -b <branch> <path> origin/main          # or <base-branch> when stacked
python3 -m venv <path>/.venv
<path>/.venv/bin/pip install -q <what the repo's CI installs>               # see below
<path>/.venv/bin/python -c "import <pkg>, sys; print(<pkg>.__file__)"   # must print a path under <path>
```

Install what the repo's CI job installs, read from its workflow or CONTRIBUTING.md: `-e "<path>[dev]"` for a package with a `pyproject.toml`, `-r requirements.txt -r requirements-dev.txt` for an app that has only requirements files. Guessing `-e ".[dev]"` fails on the second kind.

The last line is the check that the venv tests this worktree's code and not another checkout's; it applies when the repo is an installable package. If it prints any other path, the editable install went to the wrong place; fix it before starting the worker. For an app run from its directory there is nothing to import-check: run the gate from `<path>`.

Branch names: `claude/<repo-short>-<slug>` (the hand run used `claude/harmony-sleep-timer`), unless the repo's rules say otherwise.

## Why the worker doesn't push

On 2026-11-12 four agents each cloned and pushed, and the git proxy's two-operations-per-repo limit returned HTTP 429. Centralising git in the orchestrator also means the orchestrator holds every branch and can restack them, and the PR is opened by the session that will read its CI.
