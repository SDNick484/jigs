# Worker brief

Each runnable issue gets one worker, on the model your harness file (`harnesses/`) gives for the issue's tier. The orchestrator creates the worktree and venv first (git operations one at a time), so the worker never clones or pushes.

The brief is in two parts. What every worker in the run shares is written once to `<clone>/.worktrees/shared-rules.md`; each worker is sent only the path to it and the lines about its own issue. In one run of seven workers the shared rules were about sixty lines repeated seven times.

## Part 1: the run's shared rules (one file, written once to `<clone>/.worktrees/shared-rules.md`)

```text
Rules for every worker in this run of <OWNER/REPO>. Read all of this before starting.

Repo rules (from CLAUDE.md, AGENTS.md, GEMINI.md, CONTRIBUTING.md; they win over this file):
- Gate: <exact commands>
- Do not edit: <shared/generated files>. If your issue seems to need it, stop and report.
- Changes together with a feature: <README row, CHANGELOG [Unreleased], TOOL_NAMES, ...>
- <any other rule that bears on the work>

Your workspace is your worktree and nothing else:
- Run every command with the worktree's own virtualenv, as <worktree>/.venv/bin/python -m ..., never a
  bare `python` or `pytest`: the system Python may have another checkout installed and would test that.
- Anything you write outside git (gate logs, notes, PR_BODY.md) goes under <worktree>/.queue/, which is
  already excluded from git. Never write to a folder another worker could share.
<the lines your harness file lists under "Add to the shared rules", if it lists any>

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

The harness lines are copied in only for the harness the run is on. A rule that keeps one harness from stalling can be impossible in another: "read files with your file tools, not the shell" suits a harness that asks a person to approve shell commands, and cannot be followed in one that reads files through its shell.

## Part 2: one worker's brief

```text
You are implementing issue #<N> in <OWNER/REPO>: "<title>".
First read the run's rules at <clone>/.worktrees/shared-rules.md, then the issue body, in full, at
<clone>/.worktrees/<slug>/.queue/ISSUE.md (saved for you: there is no need to fetch it).

- Worktree: <clone>/.worktrees/<slug>, branch <branch>, based on <main | branch-of-#M (same lane: #M's
  commits are below yours; don't touch #M's changes)>.
- Assigned by the queue (use these, not the numbers in the issue): <HARDWARE_VALIDATION step 14>
- <anything that applies to this issue only>
```

## Orchestrator setup per worker

Place every worktree inside the repository at `<clone>/.worktrees/<slug>` (where `<slug>` is a short kebab-case name for the issue, e.g. `issue-12-rate-limit` or `rate-limit`). Some harnesses confine a worker to the workspace, and a worktree beside the clone is outside it.

```sh
# once per run, exclude .worktrees/ from git in the main checkout
mkdir -p <clone>/.worktrees
EXCLUDE="$(git -C <clone> rev-parse --path-format=absolute --git-path info/exclude)"
grep -qxF ".worktrees/" "$EXCLUDE" || echo ".worktrees/" >> "$EXCLUDE"
grep -qxF ".queue/" "$EXCLUDE" || echo ".queue/" >> "$EXCLUDE"       # every worktree shares this file

# one worker at a time (<path> is <clone>/.worktrees/<slug>)
git -C <clone> fetch --depth=50 origin main
git -C <clone> worktree add -b <branch> <path> origin/main          # or <base-branch> when stacked
python3 -m venv <path>/.venv
<path>/.venv/bin/pip install -q <what the repo's CI installs>               # see below
<path>/.venv/bin/python -c "import <pkg>, sys; print(<pkg>.__file__)"   # must print a path under <path>
mkdir -p <path>/.queue
gh api repos/<OWNER/REPO>/issues/<N> -q .body > <path>/.queue/ISSUE.md
```

`--path-format=absolute` matters: without it git prints `.git/info/exclude` relative to `<clone>`, and from any other directory the two lines after it read and write a different file (or another repository's). The exclude file is shared by every worktree of the clone, so both entries are written once.

Saving the issue body during setup means no worker calls the API: one fewer command per worker, and one fewer thing to hit the proxy's limit.

Install what the repo's CI job installs, read from its workflow or CONTRIBUTING.md: `-e "<path>[dev]"` for a package with a `pyproject.toml`, `-r requirements.txt -r requirements-dev.txt` for an app that has only requirements files. Guessing `-e ".[dev]"` fails on the second kind.

The last line is the check that the venv tests this worktree's code and not another checkout's; it applies when the repo is an installable package. If it prints any other path, the editable install went to the wrong place; fix it before starting the worker. For an app run from its directory there is nothing to import-check: run the gate from `<path>`.

Branch names: `<prefix>/<repo-short>-<slug>`, with the prefix from your harness file (the hand run used `claude/harmony-sleep-timer`), where `<repo-short>` is the repository name without a common prefix like `mcp-server-`, or the full repo name if none, unless the repo's rules say otherwise.

## The queue ledger (`<clone>/.worktrees/queue-state.md`)

A long run can lose its context to compaction or a new session while workers are out, or while it waits for the owner to merge. The ledger holds what cannot be worked out again from git and GitHub: which lane each issue is in, what it started from, which worker has it, the merge order and the numbers handed out. Write it before the first worker starts (step 1d) and update it at every dispatch, hand-back, push and merge.

```markdown
# Queue state for <OWNER/REPO>

- Planned merge order: #<N1> → #<N2> → #<N3>
- Numbers handed out: <slot assignments or "none">

| Issue | Lane | Worktree | Branch | Started from | Worker | PR | Stage |
|---|---|---|---|---|---|---|---|
| #12 | A (1/2) | `.worktrees/rate-limit` | `<prefix>/app-rate-limit` | `main` | `<worker id>` | #34 | PR open |
| #13 | A (2/2) | `.worktrees/rate-limit-ui` | `<prefix>/app-rate-limit-ui` | `<prefix>/app-rate-limit` | `<worker id>` | - | dispatched |
```

Stage is one of: `dispatched`, `handed back`, `checked` (the pre-push check passed), `pushed`, `PR open`, `merged`.

Not in the ledger: commit SHAs and CI state. Read those from `git` and `ci_state.py` each time. A SHA copied into a table is wrong after the first restack, and a "green" written down an hour ago is an agent's word about CI.

On resuming (a compacted context, a new session, or the owner saying "merged"), read the ledger, then `git worktree list` and the open PRs. Where the ledger and git or GitHub disagree, they are right: correct the ledger and say what differed. Never dispatch an issue again when its branch has commits past where it started, or it has an open PR.

## Pre-push check (step 1e, before pushing a branch or building on it)

```sh
python3 <skill-dir>/scripts/prepush_check.py <path> --base <started from> --issue <N> \
    --forbid '<pattern>' --other-lane '<pattern>' --require '<pattern>'
```

- `--base`: the row's "Started from" (`origin/main`, or the branch below it in the lane).
- `--forbid`: the shared and generated files from step 0, one option per pattern (`'shared/*'`).
- `--other-lane`: files the plan gave to a parallel lane and to no one else. Leave out every file both lanes are meant to add to. In the hand run, four parallel branches had fifteen files in common, all planned (a tool registration, a README row, a changelog bullet each); listing those would have failed all four.
- `--require`: what step 0 says changes together with this kind of work (`CHANGELOG.md`, `'tests/*'`), where it applies to this issue.

It fails on a forbidden or out-of-lane file, a required file missing from the diff, uncommitted work, a branch with no commits, and a `PR_BODY.md` that is missing or does not open with `Closes #<N>`. On `FAIL`, resume the worker with the output; it fixes the commit and runs the gate again before you push.

The check works on file names. It cannot see two lanes changing the same function in a file both may touch; that is what the lane plan in step 1c is for.

A `read:` line means the PR description never uses the word for decisions, deviations or what is unverified. A repo's PR template may word those differently, so read the description and decide. For a stacked branch, also check that it says what it sits on.

## Opening the PR

Always against the default branch, also for a branch that was started from another PR's branch:

```sh
gh api repos/<OWNER/REPO>/pulls -f head=<branch> -f base=<default branch> -f title=... -F body=@<path>/.queue/PR_BODY.md
```

A PR whose base is another PR's branch is merged into that branch, not into the default one. GitHub moves such a PR to the default branch only if the branch below it is deleted when it merges, which depends on a repository setting (delete branches on merge) that many repositories leave off. The skill does not rely on it and does not change it; if the owner turns it on, merged branches are tidied away and nothing else here changes.

## Why the worker doesn't push

On 2026-11-12 four agents each cloned and pushed, and the git proxy's two-operations-per-repo limit returned HTTP 429. Centralising git in the orchestrator also means the orchestrator holds every branch and can restack them, and the PR is opened by the session that will read its CI.
