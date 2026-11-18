# jigs

Agent Skills for recurring engineering work. A jig holds the work so the same cut comes out the
same way every time; each skill here does that for one procedure that was first done by hand,
more than once, and taught something easy to forget.

## Layout

```
skills/
  <name>/
    SKILL.md        when to use it, the procedure, what it never does on its own
    references/     detail the main file points to (optional)
    scripts/        steps that must run identically every time (optional)
    tests/          tests for those scripts (optional)
```

One directory per skill. Each is self-contained and works without the rest of this repo.

## Install

With Node.js and git, from the project you want the skill in:

```sh
npx skills add SDNick484/jigs --skill issue-queue
```

Add `-a claude-code -a codex -a antigravity -y` to choose the agents and skip the prompts, and
`-g` to install for your user instead of the project. `npx skills add SDNick484/jigs --list`
shows every skill here, and `npx skills update` takes later changes. Checked with version 1.9.0
of the installer, which is the open `skills` command line tool and not part of this repo. It
sends install telemetry by default; its documentation says how to turn that off.

Or copy `skills/<name>/` into your skills directory by hand:

| Harness | Skills directory |
|---|---|
| Claude Code | `~/.claude/skills/`, or a project's `.claude/skills/` |
| Antigravity | a workspace's `.agents/skills/` |
| OpenAI Codex | `~/.agents/skills/` |

These paths change between versions; your harness's documentation has the current ones, and the
one for skills shared across all your projects.

To run, `issue-queue` needs Python 3 and the GitHub command line tool (`gh`), signed in.

`issue-queue` runs in all three. Its procedure is written in action words (dispatch a worker,
resume it, wait), and `skills/issue-queue/references/harnesses/` has one short file per harness
saying how each is done there. In a harness with no way to start a subagent it works the queue
one issue at a time. `hardware-run` and `sibling-sweep` have been run in Claude Code only.

## Skills

| Skill | Use it to |
|---|---|
| [`hardware-run`](skills/hardware-run/SKILL.md) | Record a sitting with a real device and a repository's hardware validation checklist: decide what each observation means for the registry of unverified assumptions, and return one pull request that updates every place the result is stated (registry, checklist, status tables and prose, changelog, scanned captures). |
| [`issue-queue`](skills/issue-queue/SKILL.md) | Work a repository's open `Prompt:` issues: decide what can run now and in what order, run each to an open pull request with CI green, report once, and restack after merges. Also writes a prompt issue in the queue's format, and turns a written plan into a queue: seeds an empty repository, and writes the tasks' dependencies so independent ones run at the same time. |
| [`sibling-sweep`](skills/sibling-sweep/SKILL.md) | Take one change across a family of similar repositories: find every repository it applies to with a probe, separate what is identical from what must be worked out per repository, pilot one, then open one pull request per repository with CI verified and report in one table. |

## What to say

A skill loads when a request matches its description, so the wording matters less than naming the
job. These are the requests each one was written for.

| Skill | Say |
|---|---|
| `issue-queue` | "work the issue queue in OWNER/REPO" · "write a prompt issue for <idea>" · "turn `docs/plans/<plan>.md` into prompt issues in OWNER/REPO" · "merged" (after you merge a PR from a run) |
| `hardware-run` | "do the hardware pass on OWNER/REPO" · "run steps 10-13 of the hardware checklist" · "record what the device did" |
| `sibling-sweep` | "apply this to all the siblings" · "roll this fix out everywhere" · "which repos still need X" |

Asking for one numbered issue ("address issue #12") is deliberately not an `issue-queue` request:
that usually means "show me before committing", and a prompt issue is already the approval to
reach a pull request.

### issue-queue: from a plan to merged pull requests

Three requests, in order. Each stops and shows you something before it changes anything.

1. **File the plan.**

   ```
   Turn docs/plans/<plan>.md into prompt issues in OWNER/REPO. The repo is empty.
   Show me the list (title, builds on, runs after, needs the owner, files) before filing.
   ```

   In an empty repository it first offers one commit to the default branch holding the spec and
   the plan, and waits for your word: without it no worker can branch or read the plan. Read the
   list before you approve it. One long chain means either the plan really is sequential or a
   task claims to need more than it does, and that is cheaper to fix in the plan than in ten
   filed issues.

2. **Run it.**

   ```
   Work the issue queue in OWNER/REPO.
   ```

   It posts a plan and starts. The **Lanes** line says what runs at the same time and what waits
   for what; the table says what is held and why. It ends with one report: each pull request,
   what to check when reviewing it, and the merge order.

3. **Merge, then say "merged".** It rebases what is left, re-reads CI and starts anything the
   merge unblocked. Use merge commits for stacked pull requests, not squash.

### issue-queue in Antigravity: approvals

By default Antigravity asks you to approve each shell command that is not on its allowlist, and a
queue run issues many of them from several workers at once. A worker waiting for an approval
holds up its lane. Two ways to let a run through:

- **Set the project's execution policy** to run commands in the sandbox, or to always proceed.
  Workers stay inside `<clone>/.worktrees/` and never push or merge; only the orchestrator pushes
  and opens pull requests.
- **Or keep approvals and allowlist the routine prefixes**, so you are still asked before a push
  or a new pull request:
  - `python3`, `.venv/bin/python`, `.venv/bin/pip`
  - `git status`, `git log`, `git diff`, `git fetch`, `git worktree`, `git checkout`,
    `git rebase`, `git merge --ff-only`, `git add`, `git commit`, `git rev-parse`
  - `mkdir -p`, `grep -qxF`, and `gh api repos/` if you are happy for reads to go unasked
  - the target repository's own gate tools (`pytest`, `ruff`, `mypy` and so on)

The skill writes its commands as `git -C <path> ...` and `<path>/.venv/bin/python -m ...` so
they match by prefix. The setting names are Antigravity's as of November 2026.

You don't write the header lines (`Builds on`, `Runs after`, `Needs the owner`) yourself. The
skill derives them from the plan, so the plan is where to be precise. Per task:

| In the plan | Why |
|---|---|
| The files it creates, and the existing files it edits | Decides what can run at the same time. Two tasks that only create files are independent; two that change the same function are not. |
| What it uses from an earlier task, by name (`Consumes: access.admin_required`) | Becomes `Builds on`: the task starts from the other's branch without waiting for a merge. |
| Anything that must be merged or decided first | Becomes `Runs after`: the task is held. |
| Any step only you can do (at a device, pushing a tag, a deploy) | Becomes `Needs the owner`. |

And once, at the top of the plan:

- **The files every task adds to** (a route table, shared test fixtures, a status line in the
  rules file). Plans tend to leave these out of each task's list; naming them once lets the run
  treat them as append points and not as a reason to serialise.
- **A constraints section** (language and versions, the checks that must pass, what must never be
  committed). Until the first task creates the repository's rules file, this is what workers
  follow.
- **No instruction about ordering**, such as "pull requests stack in task order". It makes one
  chain out of tasks that could have run side by side. Let the dependencies decide.

## Conventions

- **Generic.** Skills carry no hostnames, addresses, names or account details, and use
  placeholders such as `mcp.example.com` and `user@example.com`. Anything specific to one
  repository belongs in that repository's own rules file (`CLAUDE.md`, `AGENTS.md` or `GEMINI.md`), which a skill
  reads when it runs.
- **Limits stated.** Every skill says what it never does without you (merge, tag, publish, send,
  delete, spend) and what it reports when it stops.
- **Self-contained.** A script two skills need is copied into each. CI fails if the copies differ.

## Checks

CI runs three jobs, all standard library Python:

- the repo's tests, `python -m unittest discover -s tests -v`, then each skill's own from
  `skills/<name>/tests/`
- a privacy scan over every tracked file and every commit's author, committer and message:
  `python .github/scripts/privacy_scan.py`. It reports the location and the rule, never the
  matched text. A denylist of terms no pattern can know is read from the `PRIVACY_DENYLIST`
  secret; without it (forks, local runs) only the pattern checks run.
- a copy check: `python .github/scripts/check_script_copies.py`

## License

MIT. See [LICENSE](LICENSE).
