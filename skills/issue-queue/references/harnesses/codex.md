# Harness: OpenAI Codex

You are here if your tool list has `spawn_agent`. That tool exists only when Codex's multi-agent feature is turned on in its configuration; without it, use the "no such tool" path in `SKILL.md` step 0 and tell the owner the feature would let lanes run at the same time. Trust your actual tool list over this file where they disagree, and say what differed in the report.

| Action in the skill | Here |
|---|---|
| Dispatch a worker | `spawn_agent` with `{fork_turns: "none", message: <Part 2 brief>, model: <...>, reasoning_effort: <...>}`. `fork_turns: "none"` gives the worker a clean context; the default copies your whole transcript into it. |
| Model for each tier | Choose `model` from your current spawn allowlist, never from a name written in a skill or an issue, and always set `reasoning_effort` with it: heavy `"high"`, standard `"medium"`, fast `"low"` (on the smallest model the allowlist offers). Setting `model` alone resets the effort to that model's default. |
| Wait for workers | While you have work of your own, don't wait: a finished worker's answer arrives with your next turn. When idle, `wait_agent` with `timeout_ms` of 300000 to 600000. It wakes as soon as a worker reports, so shorter timeouts only add calls. |
| Resume a worker | `followup_task` to the worker's agent id with the failure and what to do. |
| Wait between CI checks | 30 to 60 seconds between runs of `ci_state.py`. |
| Branch prefix | `codex/` |
| Rules file | `AGENTS.md` |

**Add to the shared rules:** nothing. Codex reads and searches files through its shell, so a rule against shell reads cannot be followed here.

The spawning and waiting notes follow the Codex reference in the Superpowers plugin.
