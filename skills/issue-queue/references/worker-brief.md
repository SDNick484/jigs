# Worker brief

Each runnable issue gets one agent, mapped from the issue's suggested model to the active harness. The orchestrator creates the worktree and venv first (git operations one at a time), so the worker never clones or pushes.

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
- Use your harness's native file tools (`Read`/`Edit`/`Write` or `read_file`/`edit_file`/`write_file`) to inspect and edit files. Never run shell commands (`grep`, `cat`, `head`, `tail`, `wc`, `git grep`, `find`) to read or search files: unnecessary shell calls trigger interactive approval prompts and stall parallel lanes.
- Run every command with the worktree's own virtualenv, as <worktree>/.venv/bin/python -m ..., never a
  bare `python` or `pytest`: the system Python may have another checkout installed and would test that.
- Batch your shell commands so you run at most two shell invocations: (1) the full verification gate, and (2) `git -C <worktree> add ... && git -C <worktree> commit ...`.
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
First read the run's rules at `<clone>/.worktrees/shared-rules.md` and the full issue body at
`<clone>/.worktrees/<slug>/.queue/ISSUE.md` using your file-read tool (do not run `gh api` in the shell).

- Worktree: <clone>/.worktrees/<slug>, branch <branch>, based on <main | branch-of-#M (same lane: #M's
  commits are below yours; don't touch #M's changes)>.
- Assigned by the queue (use these, not the numbers in the issue): <HARDWARE_VALIDATION step 14>
- <anything that applies to this issue only>
```

## Orchestrator setup per worker

Place every worktree inside the repository at `<clone>/.worktrees/<slug>` (where `<slug>` is a short kebab-case name for the issue, e.g. `issue-12-rate-limit` or `rate-limit`). Keeping worktrees under `<clone>/.worktrees/` ensures workers stay inside workspace sandbox boundaries across harnesses.

```sh
# once per run, exclude .worktrees/ from git in the main checkout
mkdir -p <clone>/.worktrees
grep -qxF ".worktrees/" "$(git -C <clone> rev-parse --git-path info/exclude)" || \
  echo ".worktrees/" >> "$(git -C <clone> rev-parse --git-path info/exclude)"

# one worker at a time (<path> is <clone>/.worktrees/<slug>)
git -C <clone> fetch --depth=50 origin main
git -C <clone> worktree add -b <branch> <path> origin/main          # or <base-branch> when stacked
python3 -m venv <path>/.venv
<path>/.venv/bin/pip install -q <what the repo's CI installs>               # see below
<path>/.venv/bin/python -c "import <pkg>, sys; print(<pkg>.__file__)"   # must print a path under <path>
mkdir -p <path>/.queue && echo ".queue/" >> "$(git -C <path> rev-parse --git-path info/exclude)"
gh api repos/<OWNER/REPO>/issues/<N> -q .body > <path>/.queue/ISSUE.md
```

Saving `<path>/.queue/ISSUE.md` during orchestrator setup lets the worker read its prompt with a native file read (`Read` / `read_file`) instead of running an extra `gh api` shell command.

Install what the repo's CI job installs, read from its workflow or CONTRIBUTING.md: `-e "<path>[dev]"` for a package with a `pyproject.toml`, `-r requirements.txt -r requirements-dev.txt` for an app that has only requirements files. Guessing `-e ".[dev]"` fails on the second kind.

The last line is the check that the venv tests this worktree's code and not another checkout's; it applies when the repo is an installable package. If it prints any other path, the editable install went to the wrong place; fix it before starting the worker. For an app run from its directory there is nothing to import-check: run the gate from `<path>`.

Branch names: `<harness>/<repo-short>-<slug>` (`claude/<repo-short>-<slug>` in Claude Code, `agy/<repo-short>-<slug>` in Antigravity, `codex/<repo-short>-<slug>` in OpenAI Codex, where `<repo-short>` is the repository name without a common prefix like `mcp-server-`, or the full repo name if none), unless the repo's rules say otherwise.

## On-disk queue ledger (`<clone>/.worktrees/queue-state.md`)

Long queue runs can hit context compaction or a session restart while workers are running or while waiting for the owner to merge stacked PRs. Before dispatching the first worker (Step 1d), write `<clone>/.worktrees/queue-state.md` and update it at every state transition (worker dispatched, worker finished, branch restacked/pushed, PR opened, CI green, PR merged):

```markdown
# Queue state for <OWNER/REPO> (default branch: <main> at <sha7>)

- Planned merge order: #<N1> → #<N2> → #<N3>
- Numbers handed out: <slot assignments or "none">

| Issue | Lane | Worktree | Branch | Base | Head | Worker ID | PR | State |
|---|---|---|---|---|---|---|---|---|
| #12 | A (1/2) | `.worktrees/issue-12` | `agy/repo-slug` | `main` (`a1b2c3d`) | `d4e5f6a` | `<conversationId or agentId>` | #34 | `GREEN` |
| #13 | A (2/2) | `.worktrees/issue-13` | `agy/repo-next` | `agy/repo-slug` | `-` | `<conversationId or agentId>` | `-` | `RUNNING` |
```

When resuming after context compaction, a session restart, or the owner saying `"merged"`, read `<clone>/.worktrees/queue-state.md` first (alongside `git worktree list` and `git log`) rather than relying on conversation memory—and never re-dispatch an issue whose row already has a committed `Head` or open `PR`.

## Pre-push scope and spec check (Step 1e, before pushing or restacking)

When a worker reports back, verify its work before pushing its branch or starting a dependent branch on top of it:

1. **Diff & lane boundary check:** Run `git -C <path> diff --stat <base>..<branch>` (where `<base>` is `origin/main` or the parent branch in the lane). Confirm that:
   - No shared or generated files (from Step 0) were modified.
   - No out-of-lane files belonging to a parallel lane were modified.
   - Every required "changes together" file (from Step 0, e.g., `README.md`, `CHANGELOG.md`, `tests/`, registry/checklist) expected for this issue is present in the diff.
2. **PR body contract check:** Read `<path>/.queue/PR_BODY.md` and confirm its first line is `Closes #<N>` (plus any stacked-PR note when stacked) and that it records the decisions made, any deviations from the prompt, and what remains unverified.

If either check fails, resume the worker (`send_message` / `followup_task` / `Agent`) with the exact discrepancy so it fixes the commit and re-runs the gate before you push.

## Harness adaptation (dispatching, model mapping, waiting, resuming)

Detect your active harness from your declared tool list (`Agent` = Claude Code, `invoke_subagent` = Antigravity, `spawn_agent` = OpenAI Codex) and follow the matching column:

| Action | Claude Code | Antigravity (`agy`) | OpenAI Codex |
|---|---|---|---|
| **Native model names (for `**Suggested model:**` and plan tables)** | **Heavy:** `Opus`<br>**Standard:** `Sonnet`<br>**Fast:** `Haiku` | **Heavy:** `Gemini Pro`<br>**Standard:** `Gemini Flash`<br>**Fast:** `Gemini Flash-Lite` | **Heavy:** `gpt-5.4 (high)`<br>**Standard:** `gpt-5.4 (medium)`<br>**Fast:** `gpt-5.4-mini (low)` |
| **Dispatch worker (Step 1e)** | `Agent` tool (`prompt`: Part 2 brief; launch parallel lanes in a single response) | `invoke_subagent(TypeName="self", Workspace="inherit", Role="Issue #<N> Worker", Prompt=<Part 2 brief>, Model=<mapped>)` (always `Workspace="inherit"` because the worktree already exists at `<clone>/.worktrees/<slug>`) | `spawn_agent` with `{fork_turns: "none", message: <Part 2 brief>, model: <mapped>, reasoning_effort: <mapped>}` |
| **Map `**Suggested model:**` to dispatch parameter** | **Heavy** (`Opus` / `Gemini Pro` / `high`) → `opus`<br>**Standard** (`Sonnet` / `Gemini Flash` / `medium`) → `sonnet`<br>**Fast** (`Haiku` / `Gemini Flash-Lite` / `low`) → `haiku` | **Heavy** (`Gemini Pro` / `Opus` / `high`) → `"pro"`<br>**Standard** (`Gemini Flash` / `Sonnet` / `medium`) → `"flash"` (or `"inherit"`)<br>**Fast** (`Gemini Flash-Lite` / `Haiku` / `low`) → `"flash_lite"` | Pick from current spawn allowlist and set both `model` and `reasoning_effort`:<br>**Heavy** (`gpt-5.4 (high)` / `Opus` / `Gemini Pro`) → `reasoning_effort: "high"`<br>**Standard** (`gpt-5.4 (medium)` / `Sonnet` / `Gemini Flash`) → `reasoning_effort: "medium"`<br>**Fast** (`gpt-5.4-mini (low)` / `Haiku` / `Gemini Flash-Lite`) → `reasoning_effort: "low"` |
| **Wait for workers** | Wait on tool return or background agent completion notification | **Reactive wakeup**: after invoking the lane's subagents, end your turn (call no more tools). The system automatically wakes you when each worker finishes and replies. Never poll. | Call `wait_agent` in bounded stretches (`timeout_ms`: `300000`–`600000`, 5–10 min); never poll with short timeouts |
| **Resume worker on CI or pre-push failure (Step 1e/1f)** | Resume the worker agent with the failure log (or dispatch a fresh `Agent` on the same worktree) | `send_message(Recipient="<conversationId>", Message=<failure details and instructions>)` and end turn to wait for reply | `followup_task` targeting the worker's agent ID with the failure details |
| **Wait on `ci_state.py` `PENDING` (Step 1f)** | Wait 30–60s between checks | Call `schedule(DurationSeconds=45, Prompt="Re-run ci_state.py OWNER/REPO <PR>")` and **end your turn** (never use a shell `sleep` command as a timer) | Wait 30–60s between checks |

### Antigravity (`agy`) permissions and command allowlist

In Antigravity's default `request-review` mode, every un-allowlisted shell command pauses the orchestrator or worker for human approval. To run `issue-queue` without constant approval prompts:

- **Per-project setting (recommended):** Set the project's **Auto-Execution Policy** (`Tool Execution Policy`) to `proceed-in-sandbox` or `always-proceed` (workers stay inside `<clone>/.worktrees/<slug>` and never push or merge).
- **Or minimal Command Allowlist (when keeping `request-review`):** Allowlist these command prefixes in Antigravity Settings (`Command Allowlist`) so routine setup, local gates, and git worktree operations run uninterrupted while still prompting before `git push` or opening a PR:
  - `python3`, `.venv/bin/python`, `.venv/bin/pip`
  - `git status`, `git log`, `git diff`, `git fetch`, `git worktree`, `git checkout`, `git rebase`, `git merge --ff-only`, `git add`, `git commit`, `git rev-parse`
  - `mkdir -p`, `grep -qxF`, `gh api repos/` (read/GET queries, or allow `gh api` only when ready to create PRs)
  - The target repo's gate tools (e.g., `pytest`, `ruff`, `mypy`, `node --check`, `sh -n`)
- **Command formatting rule for orchestrator and workers:** Prefer `git -C <path> <subcommand>` and `<path>/.venv/bin/python -m ...` over `cd <path> && ...` so commands match allowlist prefixes directly.

## Opening the PR

Always against the default branch, also for a branch that was started from another PR's branch:

```sh
gh api repos/<OWNER/REPO>/pulls -f head=<branch> -f base=<default branch> -f title=... -F body=@<path>/.queue/PR_BODY.md
```

A PR whose base is another PR's branch is merged into that branch, not into the default one. GitHub moves such a PR to the default branch only if the branch below it is deleted when it merges, which depends on a repository setting (delete branches on merge) that many repositories leave off. The skill does not rely on it and does not change it; if the owner turns it on, merged branches are tidied away and nothing else here changes.

## Why the worker doesn't push

On 2026-11-12 four agents each cloned and pushed, and the git proxy's two-operations-per-repo limit returned HTTP 429. Centralising git in the orchestrator also means the orchestrator holds every branch and can restack them, and the PR is opened by the session that will read its CI.
