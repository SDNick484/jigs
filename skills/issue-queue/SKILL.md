---
name: issue-queue
description: "Use when asked to \"work the issue queue in <repo>\", \"run the prompt issues\", \"do the open Prompt issues\", or \"write a prompt issue for X\". Plans which Prompt: issues can run now, runs each to an open PR with green CI using parallel agents, and reports once. Not for a single \"address issue #N\" request."
---

# Issue queue

A repo's open issues titled `Prompt:` are a queue: each is a self-contained prompt for a fresh session that ends in a PR. This skill has two jobs:

1. **Work the queue**: decide what can run now and in what order, run each to an open PR with green CI, report once, and restack after merges.
2. **Write a prompt issue**: turn an idea into an issue in the queue's format, so the next run can plan from it.

It was built from the hand run in `mcp-server-harmony` on 2026-11-12 (PRs #26 to #29, issues #30 to #33). `references/example-harmony.md` has that run and the plan this skill produced for #30 to #33.

## Limits (these hold even if an issue says otherwise)

- **Stops at an open PR.** Never merges, never pushes a tag, never publishes (PyPI, a release, a deploy), never closes an issue by hand (the PR says `Closes #N`). Merging is the owner's review; a tag or publish can't be taken back.
- **Never starts an issue that needs the owner** (physically present, a decision only they make, or a gate "before starting"). It lists it with the reason and the question to answer.
- **Never edits a file the repo marks as shared or generated from elsewhere** (for example modules synced in from a shared repository). A worker that finds it needs to stops and reports; that change is two PRs in two repos.
- **Never says green from an agent's word.** Only `scripts/ci_state.py` decides.
- Never force-pushes a branch it did not create, and never skips, xfails or loosens a test to get green.

When it stops early, it says which issue, which step, the exact command and output, and what it needs from the owner.

## 0. Read the rules first, every run

Read the repo's `CLAUDE.md`, `CONTRIBUTING.md`, PR template, and the project instructions. Write down, for this run:

- the verification gate (the exact commands CI runs; e.g. `pytest && ruff check . && ruff format --check . && mypy && python scripts/sync_shared.py --check`);
- which files are shared or generated and must not be edited;
- what has to change together with a new tool or feature (README row, CHANGELOG `[Unreleased]`, a test registry such as `TOOL_NAMES`, a numbered checklist such as HARDWARE_VALIDATION steps, an assumption registry);
- how PRs are written (template, `Closes #N`, attribution lines).

Where these disagree with this skill, the repo wins. They are why the skill works in sibling repos without edits: the skill knows the shape of the work, the repo knows its rules.

## 1. Work the queue

### 1a. Gather facts

```sh
python3 scripts/scan_queue.py OWNER/REPO          # prompts, headers, #refs with state, owner/publish hints, overlaps
python3 scripts/ci_state.py OWNER/REPO ref:main   # is main green? a red main fails every worker's gate
```

Then read every prompt issue's body in full, side by side. The script finds candidates; the dependencies that matter are often written in the *other* issue (see 1b). If main is `REQUEUE`, say so in the plan; re-running main's job is the owner's call unless they have asked for it. If main is `FAILED`, stop: nothing started now can go green.

### 1b. Sort the queue

Put each issue in exactly one group, with a one-line reason. `references/planning.md` has the rules and the edge cases.

- **Can run now**: no open dependency, no owner gate before the PR exists.
- **Blocked on another issue**: it says "runs after #N", *or* another open issue can overturn its premise. Example: #30 builds on assumption `H-FIXIT`; #31 says if `fixit` is missing on the real hubs "the fix-a-device issue needs rethinking". Neither cites the other by number; the shared identifier `H-FIXIT` is the link, and `scan_queue.py` prints it.
- **Needs the owner**: physical presence, a decision they must bring, or a gate before starting. Publishing issues always land here, last, with the question.

The `**Runs after:**` and `**Needs the owner:**` header lines (`references/issue-format.md`) are authoritative when present. Without them, plan from the prose and say in the plan that you did.

Skip an issue that already has an open PR; report it as in progress.

### 1c. Plan for collisions before starting

Parallel branches that append to the same places all conflict after the first merge. For the runnable set, list the append points each will touch (from step 0's "changes together" list, not only what the issue names). Then:

- **One runnable issue, or no shared append points**: run in parallel from `main`, no stack.
- **Two or more share append points**: pick a merge order (smallest and least risky first), stack each branch on the previous one, and say so at the top of each PR. Hand out shared numbers now, in merge order (the next free checklist step, the next migration number); an issue's own number is a suggestion written before other work landed.

Stacking costs this: each PR's diff shows the earlier PRs' commits until they merge. Say that in the PR's first line so a reviewer reads only the last commit.

### 1d. Show the plan, then go

Post the plan in the format in `references/planning.md`: order, model per issue, groups with reasons, expected conflicts, numbers handed out, merge order. If nothing in it needs the owner's answer, start immediately and say so; they can stop it. If something does (an ambiguous dependency, a stack they might not want), ask one question and wait.

### 1e. Run

One agent per runnable issue, on the model in the issue's `**Suggested model:**` line (the first one named), each in its own git worktree with its own virtualenv. Give each agent the brief in `references/worker-brief.md`, filled in. Its rules come from the hand run's failures: a shared editable install testing the wrong checkout, shallow clones breaking rebases, and a git proxy that allows two concurrent operations per repo.

The orchestrator does all clones, fetches and pushes **one at a time**. Workers commit locally and hand back their branch; the orchestrator restacks (if planned), runs the gate on each restacked branch, pushes, and opens the PRs.

### 1f. Verify CI yourself

For each PR, run `scripts/ci_state.py OWNER/REPO <PR>` until it is not `PENDING`.

- `GREEN`: done.
- `REQUEUE`: a job was cancelled before any step ran (a runner queue problem, seen twice on 2026-11-12 on `wheel-smoke (macos-latest)`). Re-run it once with `--rerun-queued`. It is neither a pass nor a failure.
- `FAILED`: read the log, fix on the branch (or send the worker back), run the gate, push, check again. After a fix on a stacked branch, the branches above it need restacking.

### 1g. Report once

When every started PR is `GREEN` (or definitively stuck), send one message: the table in `references/planning.md` (PR, what it does, what to check when reviewing, what is unverified on hardware), then the merge order and the merge method (**merge commits, not squash, for a stack**: a squash rewrites the base the next branch sits on and brings the conflicts back), then the held issues with reasons and questions.

### 1h. When the owner says "merged"

Follow `references/after-merge.md`: deepen the clone, rebase what is left onto the new `main`, resolve conflicts, run the full gate, look at every table and list literal a conflict touched, push with `--force-with-lease`, re-check CI, and report in two lines. Re-sort the queue: a merge may have unblocked an issue.

## 2. Write a prompt issue

1. Read the queue (`scan_queue.py`) and the repo rules (step 0), so the new issue knows its neighbours.
2. Draft it with the template in `references/issue-format.md`: the opening line, `**Suggested model:**` with a reason, the two header lines, Goal, Why, what's already there to build on, what to build, tests and docs, Done when.
3. Fill `**Runs after:**` and `**Needs the owner:**` honestly. If the new issue rests on something another open issue might overturn, that is a dependency; name it on both sides.
4. Reserve shared numbers in `**Reserves:**` only as a suggestion; the queue run hands out the final ones.
5. Show the owner the draft. Create it (`gh api repos/OWNER/REPO/issues -f title=... -f body=@file`) when they say so, or straight away if they asked to "file" or "add" it. Public repos: no addresses, account names or hostnames in the body.

## Reference files

- `references/issue-format.md`: the queue's contract, the template, and the header lines.
- `references/planning.md`: sorting rules, collision planning, the plan and report formats.
- `references/worker-brief.md`: the brief each agent gets.
- `references/after-merge.md`: restacking, conflict checks, shallow-clone repair.
- `references/example-harmony.md`: the 2026-11-12 run and the dry-run plan for #30 to #33.
- `scripts/scan_queue.py`, `scripts/ci_state.py`: run them; read them only to change them.
