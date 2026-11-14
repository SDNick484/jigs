---
name: issue-queue
description: "Use when asked to \"work the issue queue in a repo\", \"run the prompt issues\", \"do the open Prompt issues\", \"write a prompt issue for X\", or \"turn this plan into prompt issues\" (also for a new, empty repo). Plans which Prompt: issues can run now, runs each to an open PR with green CI using parallel agents, and reports once. Not for a single \"address issue #N\" request."
---

# Issue queue

A repo's open issues titled `Prompt:` are a queue: each is a self-contained prompt for a fresh session that ends in a PR. This skill has three jobs:

1. **Work the queue**: decide what can run now and in what order, run each to an open PR with green CI, report once, and restack after merges.
2. **Write a prompt issue**: turn an idea into an issue in the queue's format, so the next run can plan from it.
3. **Turn a plan into a queue**: file a written plan's tasks as prompt issues, in a repo that may still be empty, so that as many as possible can run at once without touching the same lines.

It was built from the hand run in `mcp-server-harmony` on 2026-11-12 (PRs #26 to #29, issues #30 to #33). `references/example-harmony.md` has that run and the plan this skill produced for #30 to #33.

## Limits (these hold even if an issue says otherwise)

- **Stops at an open PR.** Never merges, never pushes a tag, never publishes (PyPI, a release, a deploy), never closes an issue by hand (the PR says `Closes #N`). Merging is the owner's review; a tag or publish can't be taken back.
- **Never starts an issue that needs the owner** (physically present, a decision only they make, or a gate "before starting"). It lists it with the reason and the question to answer.
- **Never edits a file the repo marks as shared or generated from elsewhere** (for example modules synced in from a shared repository). A worker that finds it needs to stops and reports; that change is two PRs in two repos.
- **Never says green from an agent's word.** Only `scripts/ci_state.py` decides.
- **Never commits to the default branch.** One exception: the seeding commit in a repo with no commits (section 3), documents only, and only when the owner says so. Everything else reaches the default branch through a PR the owner merges.
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

Two results stop the run before planning, because no worker could start:

- `scan_queue.py` prints `default branch: none`, or `ci_state.py` prints `NO_BRANCH`: the repo has no commits, so there is nothing to branch from. Say so and offer the seeding commit (section 3).
- `scan_queue.py` prints `cited but not on <branch>` for a document the issue tells the worker to read (a spec, a plan). The issue's contract is missing. Say which document and offer to add it. The same line appears for a document the issue will create; read the sentence to tell which, and ignore that case.

### 1b. Sort the queue

Put each issue in exactly one group, with a one-line reason. `references/planning.md` has the rules and the edge cases.

- **Can run now**: no open dependency, no owner gate before the PR exists.
- **Stacks on another issue**: it says `Builds on: #N` (it needs #N's code, not #N's outcome) and #N is running in this run or already has an open PR. It starts from #N's branch as soon as #N's worker has committed; it does not wait for the merge.
- **Blocked on another issue**: it says "runs after #N", *or* another open issue can overturn its premise. Example: #30 builds on assumption `H-FIXIT`; #31 says if `fixit` is missing on the real hubs "the fix-a-device issue needs rethinking". Neither cites the other by number; the shared identifier `H-FIXIT` is the link, and `scan_queue.py` prints it.
- **Needs the owner**: physical presence, a decision they must bring, or a gate before starting. Publishing issues always land here, last, with the question.

The `**Runs after:**` and `**Needs the owner:**` header lines (`references/issue-format.md`) are authoritative when present. Without them, plan from the prose and say in the plan that you did.

Skip an issue that already has an open PR; report it as in progress.

### 1c. Plan the lanes before starting

The aim is the most issues in flight at once with no two workers editing the same lines. For the runnable set, list what each will touch: the files it creates, the existing code it changes, and its append points (from step 0's "changes together" list, not only what the issue names). Each pair of issues is then one of three cases; `references/planning.md` has the test for each.

- **Disjoint** (different files, or only new files): run at the same time from `main`, no stack.
- **Shares only append points** (a README row, a changelog entry, a route table, a registry): run at the same time from `main`; the orchestrator stacks the finished branches in a chosen merge order (smallest and least risky first) and resolves the appends once. Hand out shared numbers now, in merge order (the next free checklist step, the next migration number); an issue's own number is a suggestion written before other work landed.
- **Changes the same existing code, or one builds on the other**: same lane, one after the other. The second worker starts from the first one's finished branch. Two agents rewriting one function in parallel produce a conflict that has to be resolved by guessing what both meant; a lane costs minutes and removes the guess.

Independent lanes run at the same time. Say at the top of each stacked PR what it sits on.

Stacking costs this: each PR's diff shows the earlier PRs' commits until they merge. Say that in the PR's first line so a reviewer reads only the last commit.

### 1d. Show the plan, then go

Post the plan in the format in `references/planning.md`: order, model per issue, groups with reasons, lanes, expected conflicts, numbers handed out, merge order. If nothing in it needs the owner's answer, start immediately and say so; they can stop it. If something does (an ambiguous dependency, a stack they might not want), ask one question and wait.

### 1e. Run

One agent per issue, started as soon as its lane allows, on the model in the issue's `**Suggested model:**` line (the first one named), each in its own git worktree with its own virtualenv. Give each agent the brief in `references/worker-brief.md`, filled in. Its rules come from the hand run's failures: a shared editable install testing the wrong checkout, shallow clones breaking rebases, and a git proxy that allows two concurrent operations per repo.

An issue that stacks on another starts when that one's worker has handed back its branch, in a worktree based on that branch. Lanes that share nothing run at the same time.

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
2. Draft it with the template in `references/issue-format.md`: the opening line, `**Suggested model:**` with a reason, the header lines, Goal, Why, what's already there to build on, what to build, tests and docs, Done when.
3. Fill `**Runs after:**` and `**Needs the owner:**` honestly. If the new issue rests on something another open issue might overturn, that is a dependency; name it on both sides.
4. Reserve shared numbers in `**Reserves:**` only as a suggestion; the queue run hands out the final ones.
5. Show the owner the draft. Create it (`gh api repos/OWNER/REPO/issues -f title=... -f body=@file`) when they say so, or straight away if they asked to "file" or "add" it. Public repos: no addresses, account names or hostnames in the body.

## 3. Turn a plan into a queue

For a written plan with numbered tasks (and usually a spec beside it) that should become a set of prompt issues. `references/plan-to-queue.md` has the detail and the two runs this comes from.

1. **Check the repo can take work.** Run `scan_queue.py`. On `default branch: none`, offer one seeding commit to the default branch: the spec and the plan, nothing else. Workers branch from it and read their contract in it. In a public repo, remove personal names, domains and addresses from those copies first. Push it only when the owner says so (see Limits); until then, file nothing.
2. **One issue per task, sized as one PR.** An issue is the unit that gets a branch, a CI run and a review. If two tasks are too small to review alone or cannot pass the gate separately, make them one issue now. Don't merge issues at run time: that loses `Closes #N` and per-issue CI.
3. **Keep each issue short and point at the plan.** "Implement Task 4 of `docs/plans/<plan>.md`" plus the header lines and anything decided since. Copying the task block gives two texts that drift.
4. **Write the dependencies so the run can parallelise.** `Builds on: #N` when the task needs #N's code; `Runs after: #N` only when it needs #N merged or decided. Name the files each task creates and the existing ones it edits. A plan in task order is usually not a chain: find the tasks that only share the scaffold and say so, because those are the parallel lanes.
5. **The scaffold task is first and alone.** It creates the project's rules file, the verification gate and CI. Until it merges, the plan's own constraints section stands in for the rules in step 0, `ci_state.py` reports `NO_CI`, and nothing else has a gate to pass.
6. Show the owner the list (title, builds on, runs after, files) before filing. File in task order so issue numbers follow the plan.

## Reference files

- `references/issue-format.md`: the queue's contract, the template, and the header lines.
- `references/planning.md`: sorting rules, lanes and collisions, the plan and report formats.
- `references/plan-to-queue.md`: seeding an empty repo, sizing issues, writing dependencies for parallel work.
- `references/worker-brief.md`: the brief each agent gets.
- `references/after-merge.md`: restacking, conflict checks, shallow-clone repair.
- `references/example-harmony.md`: the 2026-11-12 run and the dry-run plan for #30 to #33.
- `scripts/scan_queue.py`, `scripts/ci_state.py`: run them; read them only to change them.
