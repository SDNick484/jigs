# Planning the queue

## Sorting rules

Apply in this order; the first that matches decides the group.

1. **Already has an open PR** (`scan_queue.py` shows `open_pr`): in progress. Not started again.
2. **Header `Needs the owner: before starting`**, or prose that needs them before any work ("needs the owner at home", "Before starting, check with the owner"): **needs the owner**. Write the question they have to answer, taken from the issue.
3. **Publishes or tags** (PyPI, a release tag, a deploy) even if the prose doesn't say "owner": **needs the owner**, placed last. A publish is irreversible, and what it should contain depends on what else merges first.
4. **Header `Runs after: #N` with #N still open**, or prose "run after #N": **blocked on #N**.
5. **Premise at risk**: another open issue's outcome can invalidate this one's design. Signs: `scan_queue.py` lists a shared identifier (an assumption id, a field name, a tool name) between the two, and the other issue verifies, measures or decides that identifier. Read both passages; if the other issue says this one would need rethinking, it is **blocked on** that issue. If it only adds to the same files, it is a collision (below), not a dependency.
6. Otherwise: **can run now**.

`Needs the owner: at the end` (a gate after the PR exists, such as pushing a tag after merge) does not hold an issue: run it to the PR and put the gated step in the report.

When the header is missing, say "planned from the prose" next to that issue in the plan.

## Collisions

Collect, per runnable issue, the append points it will touch: what the issue names, plus what the repo's rules say changes together (for a new tool in an MCP server, for example: `server.py`, the README tool table, CHANGELOG `[Unreleased]`, the tool-name set in `tests/test_tools.py`, a HARDWARE_VALIDATION step, maybe `assumptions.py`). Two issues sharing any of these conflict after the first merge.

- Stack when two or more runnable issues share an append point. Merge order: the smallest and most independent first, the one most likely to need review rework last (rework low in a stack forces restacking everything above it).
- Hand out numbered slots in merge order: next free checklist step, next migration number. Write them into each worker's brief so no two branches write the same "step 10".
- A single runnable issue needs no stack, but still check its append points against open PRs and against issues that will run later (they tell the owner where the next conflict will be).

## Plan format (posted before starting)

```markdown
**Queue plan for OWNER/REPO** (main is GREEN at abc1234; planned from the prose for #30-#33: no header lines)

| # | Issue | Group | Model | Why |
|---|---|---|---|---|
| 32 | stop `call` adding history noise | run now | Sonnet 5.5 | no dependency, no owner step |
| 31 | hardware validation 10-13 | needs the owner | Sonnet 5.5 | needs you at home with the remotes; brings 2 decisions back |
| 30 | harmony_fix_device | blocked on #31 | Opus 5.5 | rests on H-FIXIT, which #31 checks |
| 33 | release 0.4.0 | needs the owner, last | Sonnet 5.5 | publishes; question below |

**Collisions:** <none among runnable | list of shared append points and the stack order>
**Numbers handed out:** <HARDWARE_VALIDATION step 14 → #30 (when it runs)>
**Merge order:** <...>
**Starting now:** #32. <or: "Waiting for your answer on X before starting.">

**Questions for you:**
- #33: ...
```

## Report format (sent once, when every started PR has finished CI)

```markdown
All N PRs are open with CI green.

| PR | What it does | Check when reviewing | Unverified on hardware |
|---|---|---|---|
| #34 | ... | the decision taken on X (and why) | ... or "nothing: no hub behaviour" |

**Merge order:** #34, then #35 (stacked on #34; use merge commits, not squash). Reply "merged" and I'll restack what's left and re-check CI.
**Still held:** #31 (needs you at home), #30 (after #31 settles H-FIXIT), #33 (your call: ...).
```

"Check when reviewing" is the thing a reviewer can't see from the diff: a decision the worker made, a deviation from the prompt, a test that was scaled down. Take it from the PR description's decisions section.
