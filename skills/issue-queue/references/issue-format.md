# The prompt issue format (the queue's contract)

A prompt issue is read twice: by a planner deciding what can run, and by a fresh session doing the work. The prose serves the session; three header lines serve the planner.

## Why add header lines (and not only labels)

Planning #30 to #33 from prose alone showed two failures a planner can't be trusted to avoid:

- **The dependency was written in the other issue.** #30 (`harmony_fix_device`) never mentions #31. #31 says "If `fixit` is missing ... the fix-a-device issue needs rethinking before anyone builds it", naming #30 by description, not number. A planner reading #30 alone would start it.
- **"Owner" is not a gate.** #30 says "the owner's 4.15.600 hubs" and "the owner also runs webOS" and needs nothing from them. #31 says "It needs the owner at home with the remotes". A keyword match can't tell them apart; a line that says `Needs the owner: no` can.

Labels were the other option. They are good for filtering but carry no reason and no issue number, and the reasons are what the plan shows the owner. Header lines next to the existing `**Suggested model:**` line keep everything in the one place the writer already edits. Labels stay optional.

## Template

```markdown
This issue is a prompt for a new Claude session. Paste it, or say "work the issue queue in <repo>".

**Suggested model:** <model>. <one-line reason>
**Runs after:** <none | #N (why: what it must settle first)>
**Needs the owner:** <no | before starting: why | at the end: what step, e.g. pushing the tag>
**Reserves:** <none | HARDWARE_VALIDATION step 14, ...>   (a suggestion; the queue run assigns the final numbers)

## Goal
<one paragraph; ends with "One PR against `main`, CI green.">

## Why
<the problem, concretely>

## What is already on `main` to build on
<only when it builds on recent work; cite the PRs>

## What to build
<the design, decisions already made, refusal cases>

## Tests and docs
<what to test; which docs change, per the repo's CLAUDE.md>

## Done when
The PR is open with the verification gate and CI green, and its description lists the decisions made, any deviation from this prompt, and what is unverified on hardware.
```

Rules for the header:

- `Runs after` names issues by number with the reason, and is written on **both** sides: if #31 can overturn #30, #31 also says so in prose ("If X, #30 needs rethinking") so a reader of either finds the other.
- `Needs the owner: at the end` means the session can run to the PR and stop there (for example a release PR whose tag push needs the owner). `before starting` means the queue holds it.
- Model choice: Opus for a new subsystem, safety-relevant refusals or tricky concurrency; Sonnet for well-bounded work, checklists and mechanical releases; Haiku only for small edits a test proves. Name one model first; an alternative after "or".

## Changes to #30 to #33 under this format

Only header lines are added; the prose stays.

| Issue | Add |
|---|---|
| #30 fix a device | `**Runs after:** #31 (H-FIXIT must be checked on the real hubs; if fixit is missing or shaped differently on 4.15.600, this prompt is rewritten first)` · `**Needs the owner:** no` · `**Reserves:** HARDWARE_VALIDATION step 14` |
| #31 hardware validation | `**Runs after:** none` · `**Needs the owner:** before starting: at home with the remotes, does the physical steps, and decides the two questions under "Decisions to bring back"` · and in its prose, "#30" instead of "the fix-a-device issue" |
| #32 history noise | `**Runs after:** none` · `**Needs the owner:** no` |
| #33 release 0.4.0 | `**Runs after:** #31, #30, #32 (the owner decides which must land first)` · `**Needs the owner:** before starting (which issues to wait for) and at the end (pushing the v0.4.0 tag publishes to PyPI)` |

The opening line of each changes from "Paste it, or say 'do issue #N in mcp-server-harmony'" to "... or say 'work the issue queue in mcp-server-harmony'". "Do issue #N" would trigger the single-issue skill, which stops for approval before committing; a prompt issue is already the approval to reach a PR.
