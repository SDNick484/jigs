# Harness: Claude Code

You are here if your tool list has an `Agent` tool (older versions name it `Task`). Trust your actual tool list over this file where they disagree, and say what differed in the report.

| Action in the skill | Here |
|---|---|
| Dispatch a worker | The `Agent` tool: the Part 2 brief as `prompt`, `model` from the tier. Send the calls for every worker that can start now in one response, so they run at the same time. |
| Model for each tier | heavy: `opus` · standard: `sonnet` · fast: `haiku` |
| Wait for workers | A foreground call returns when its worker finishes; a background worker sends a completion notice. Don't poll. |
| Resume a worker | Message the same agent with the failure if your tools allow it. Otherwise dispatch a new worker on the same worktree, and tell it its earlier commits are on the branch. |
| Wait between CI checks | 30 to 60 seconds between runs of `ci_state.py`. |
| Branch prefix | `claude/` |
| Rules file | `CLAUDE.md` |

**Add to the shared rules:** nothing.
