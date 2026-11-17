# Harness: Antigravity (`agy`)

You are here if your tool list has `invoke_subagent`. The tool names and parameters below were written down from a queue run in Antigravity in November 2026 and have not been checked against other versions. Trust your actual tool list over this file where they disagree, and say what differed in the report.

| Action in the skill | Here |
|---|---|
| Dispatch a worker | `invoke_subagent(TypeName="self", Workspace="inherit", Role="Issue #<N> worker", Prompt=<Part 2 brief>, Model=<from the tier>)`. `Workspace="inherit"` because the orchestrator already made the worktree. |
| Model for each tier | heavy: `"pro"` · standard: `"flash"` · fast: `"flash_lite"` |
| Wait for workers | After dispatching, end your turn and call no more tools. You are woken when a worker replies. Don't poll. |
| Resume a worker | `send_message(Recipient=<the worker's conversation id>, Message=<the failure and what to do>)`, then end your turn. |
| Wait between CI checks | `schedule(DurationSeconds=45, Prompt="Re-run ci_state.py OWNER/REPO <PR>")`, then end your turn. A shell `sleep` holds the turn open and needs approval. |
| Branch prefix | `agy/` |
| Rules file | `GEMINI.md` or `AGENTS.md` |

## Why the extra rules

Unless the project's execution policy says otherwise, every shell command that is not on the allowlist stops and waits for a person to approve it. A worker waiting for approval holds up its whole lane, and nobody is watching a parallel run. The repository's README says which policy or allowlist the owner can set; these rules keep the number of prompts down either way.

**Add to the shared rules** (Part 1 of `../worker-brief.md`), as written:

```text
- Read, search and edit files with your file tools, not with shell commands such as cat, grep or
  find: here a shell command can stop and wait for a person's approval, and a waiting worker
  holds up its lane.
- Keep shell commands few. Run the whole gate as one command, and stage and commit as one command.
  Run the gate again after every fix.
- Write commands as `git -C <worktree> ...` and `<worktree>/.venv/bin/python -m ...`, not
  `cd <worktree> && ...`: an allowlist matches on how a command starts.
```

The orchestrator follows the same three rules for its own commands.
