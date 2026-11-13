---
name: sibling-sweep
description: "Use when asked to \"apply this to all the siblings\", \"roll this fix out everywhere\", \"do the same in the other repos\", \"sync shared across the servers\", or \"which repos still need X\". Takes one change across a family of similar repositories: works out which ones need it, applies it per repo (they are never identical), opens one PR per repo with CI verified, and reports once in one table. Not for several issues in one repo (that is issue-queue)."
---

# Sibling sweep

One change, many repositories that look alike and are not. This skill finds every repository the change applies to, splits the change into the part that is the same everywhere and the part that has to be worked out in each repository, runs one repository first, then the rest, and ends with one pull request per repository and one table.

It was built from nine hand-run waves across a family of nine to eleven repositories. `references/lessons.md` has what each wave taught; `references/example-shutdown.md` has one wave replayed with this skill and compared with what was merged by hand.

## Limits (these hold even if the request says otherwise)

- **Stops at open pull requests.** Never merges, tags, publishes, deploys or restarts anything. A sweep's PRs are independent, so merging them is the owner's review of each.
- **Never edits a file a repository marks as shared or generated from elsewhere.** That change is made once, in the repository it comes from, and reaches the others through that repository's own sync tool (step 2).
- **Never touches a repository that is not in the plan the owner saw** (step 4), and never pushes to a default branch.
- **Never says green from an agent's word.** Only `scripts/ci_state.py` decides.
- Never force-pushes a branch it did not create, never closes or supersedes someone else's PR, and never skips, xfails or loosens a test to get green.

When it stops early, it says which repository, which step, the exact command and output, and what it needs from the owner.

## 0. Read the rules first, every run

Read the project instructions, then, **for every candidate repository**, its `CLAUDE.md`, `CONTRIBUTING.md` and PR template. They differ between siblings more than expected; note per repository:

- the verification gate (the exact commands its CI runs);
- which files are shared or generated and where they come from;
- what has to change together with this kind of change (a changelog section, a README table, a test);
- how commits and PRs are written: author identity, attribution lines, template, and, for a public repository, what must never appear in a commit message, branch name or PR text.

Where these disagree with this skill, the repository wins. The skill knows the shape of a sweep; each repository knows its own rules.

## 1. State the change as three things

Before touching anything, write down (`references/reading-the-change.md` has the method and worked cases):

1. **The fixed part**: what must be identical in every repository (a setting, a line, a workflow block).
2. **The derived part**: what must be worked out in each repository from its own code (a number, a justification, a name, which of several files). If the reference change has a comment or message explaining *why*, that explanation is almost always derived: copying it makes a true statement in one repository and a false one in the next.
3. **The probe**: a file glob (the anchor: where the change applies) and a pattern (how to tell the change is there). It must say TODO for the reference repository before its change and DONE after. Check that it does.

If the request is a reference ("what we did in X"), read that commit or PR in full, including its message, to find all three.

## 2. Is it really a change to shared code?

If the fixed part lives in a file some repository marks as shared or generated, stop treating it as a sweep of edits:

1. Make the change in the source repository, by PR, under that repository's rules.
2. After it merges, run **that repository's own sync tool** to open the per-repo PRs. Don't re-implement it.
3. The sweep's job is then the follow-through the tool doesn't do: find family members the tool does not discover (step 3: its discovery rule is usually a name pattern), verify CI on every PR it opened with `ci_state.py`, and report in the one table.

## 3. Find the family by probing, not by remembering

```sh
python3 scripts/sweep_status.py --root <dir with every checkout> \
    --anchor '<glob>' (--has '<regex>' | --lacks '<regex>') [--marker <file that marks membership>]
```

Clone or fetch every repository the owner could mean into one directory first (one git operation at a time), default branch, up to date. Then:

- Every repository gets a row. `TODO` and `PARTIAL` are the work; `DONE` is "already has it"; `N/A` is "nothing to apply it to". A hand-kept list is how a wave reaches five repositories out of six.
- `PARTIAL` means one repository has several files the change applies to and only some have it. Each file is its own piece of work.
- `--marker` shows membership without filtering: a member whose name doesn't fit the usual pattern, and a non-member that has the anchor file, both show up. Whether those are in or out is the owner's decision; put it in the plan as a question.
- A repository with an open PR that already makes this change is in progress, not TODO: `gh api "repos/OWNER/REPO/pulls?state=open"` and look for the sweep's branch name.

Then check each default branch with `python3 scripts/ci_state.py OWNER/REPO ref:<default branch>`. A red default branch fails that repository's PR for a reason that is not the sweep's: hold that repository and say so.

## 4. Plan, show it, then go

Post the plan (`references/formats.md`): the three parts from step 1, the table from step 3 with what will differ per repository where that is already known, the pilot, the branch name, and anything held. Decide here, once for the whole sweep, anything the repositories' rules leave open, such as whether the change gets a changelog entry where a changelog exists: left to each worker, three workers gave two answers. One branch name and one commit subject for the whole sweep, the same in every repository: it is how the wave is found again later, and how step 3 recognises a PR that is already open.

If nothing in the plan needs the owner's answer, start and say so. If something does (a repository that is in or out, a derived part that needs a decision, a red default branch), ask one question and wait.

## 5. Pilot one repository to green

Pick the repository the reference came from if it is TODO, otherwise the most typical one. Apply the change there (step 6), push, open its PR, and wait for `ci_state.py` to say `GREEN`.

Whatever CI caught in the pilot goes into every other repository's brief before they start: a test that names the thing being changed, a formatter, a smoke test, a drift check. One wave skipped this and needed the same "fix CI" follow-up commit in all six repositories.

## 6. Apply per repository

For each TODO or PARTIAL repository: a fresh branch from its up-to-date default branch, then the brief in `references/worker-brief.md`. A change of a few lines can be done inline, one repository at a time; a change that needs each repository's code read closely gets one agent per repository, each in its own checkout, on the model the owner prefers for mechanical work. Either way:

- The fixed part is written exactly; the derived part is worked out from that repository's code and the working is kept for the PR.
- Each element of the change gets one of three answers per repository, in the commit body: applied, **already there** (and so unchanged), or **does not apply here** (and why). A reviewer reading nine similar PRs needs to see the differences, not the sameness.
- If the honest derived answer is that the change is not enough here, say that in the repository (the comment, the PR), don't round it to match the others, and put it in the report.
- The repository's full gate runs before anything is pushed.
- Workers commit locally and never clone, push or open PRs. The orchestrator pushes one repository at a time and opens each PR, so the session that opens a PR is the one that reads its CI.

## 7. Verify CI yourself

For each PR, `python3 scripts/ci_state.py OWNER/REPO <PR>` until it is not `PENDING`.

- `GREEN`: done.
- `REQUEUE`: a job was cancelled before any step ran. Re-run once with `--rerun-queued`; it is neither a pass nor a failure.
- `FAILED`: read the log, fix on that branch, run the gate, push, check again. If the cause is not specific to that repository, the same fix is due in the others: check them before they fail too.
- `NO_CI`: the repository has no CI. Report the local gate's result and say that nothing else checked it.

## 8. Report once

When every PR is `GREEN` or definitively stuck, send one message in the format in `references/formats.md`: the table (repository, PR, what differed there, CI), then repositories not changed and why (already had it, does not apply, held), then anything the change does not do by merging (a restart, a deploy, a follow-up in the shared repository), then what the probe or the workers turned up outside the request (a repository an earlier sweep missed, a stale comment in a shared file, a bug). Those are reported, never fixed in passing.

## 9. When the owner says "merged"

Fetch each default branch and run the step 3 probe again with `--ref origin/<default branch>`. The sweep is finished when it exits 0: every row `DONE` or `N/A`. Report in two lines, naming any repository that is still TODO.

## Reference files

- `references/reading-the-change.md`: fixed, derived and probe, with worked cases; the shared-code test.
- `references/worker-brief.md`: the brief for one repository, and why workers don't push.
- `references/formats.md`: the plan, commit, PR and report formats.
- `references/lessons.md`: the nine waves and the rule each one produced.
- `references/example-shutdown.md`: one wave replayed with this skill against what was merged by hand.
- `scripts/sweep_status.py`, `scripts/ci_state.py`: run them; read them only to change them. `ci_state.py` is the same file `issue-queue` carries.
