# Worked example: mcp-server-harmony, 2026-11-12

## The hand run (the evidence)

Five feature ideas became five prompts. Four ran in parallel, each in its own worktree on its recommended model:

| PR | Feature | Branch | Notes from the run |
|---|---|---|---|
| #29 | `harmony_describe_activity`, `export`, migration prompt | `claude/harmony-export` | merged first, unstacked; added HARDWARE_VALIDATION step 10 |
| #26 | `harmony_set_sleep_timer` | `claude/harmony-sleep-timer` | also wrote "step 10"; rebased onto main after #29, renumbered to 11 |
| #27 | `harmony_tune_channel` | `claude/harmony-tune-channel` | stacked on #26, step 12; CI attempt 1 had `wheel-smoke (macos-latest)` cancelled before any step, re-run passed |
| #28 | `harmony_get_history` | `claude/harmony-history` | stacked on #26 and #27, step 13; after its merge, main's run 43262638828 had the same macOS cancellation |

All four added a tool to `server.py`, a README tool row, a CHANGELOG bullet, a name in `TOOL_NAMES`, and a "step 10". The stack notes at the top of #26 to #28 are the format `after-merge.md` asks for.

The remaining work became issues #30 to #33.

## Dry run: the plan this skill produced for #30 to #33 (no work started)

Inputs: `scan_queue.py OWNER/mcp-server-harmony` and `ci_state.py OWNER/mcp-server-harmony ref:main`, run 2026-11-12 17:40 UTC, then the four bodies read in full. Repo rules from CLAUDE.md: gate `pytest && ruff check . && ruff format --check . && mypy` plus `sync_shared.py --check`; shared files from mcp-server-shared not edited here; a new tool changes README, CLAUDE.md, CHANGELOG `[Unreleased]`, HARDWARE_VALIDATION and `test_tools.py`.

> **Queue plan for OWNER/mcp-server-harmony** (planned from the prose: none of #30-#33 has the header lines)
>
> main is REQUEUE at 6a36d75: every job passed except `wheel-smoke (macos-latest)`, which was cancelled before any step ran (runner queue). Not a code failure; re-running it is your call.
>
> | # | Issue | Group | Model | Why |
> |---|---|---|---|---|
> | 32 | stop `call` adding `recording_started` noise | **run now** | Sonnet 5.5 | no open dependency, no owner step; builds on #28 (merged) |
> | 31 | hardware validation, steps 10-13 | **needs the owner** | Sonnet 5.5 | "needs the owner at home with the remotes"; brings back two decisions (channel separator fallback; H-FIXIT outcome) |
> | 30 | `harmony_fix_device` | **blocked on #31** | Opus 5.5 | rests on `H-FIXIT` (simulator-only). #31 checks it, and says if `fixit` is missing or differs on 4.15.600 "the fix-a-device issue needs rethinking before anyone builds it" |
> | 33 | release 0.4.0 to PyPI | **needs the owner, last** | Sonnet 5.5 | publishes; "Before starting, check with the owner"; mentions #30, #31, #32 as possible prerequisites |
>
> **Collisions:** none among runnable issues (only #32). For later: #32, #31 and #30 all write CHANGELOG `[Unreleased]` and README; #31 and #30 both write HARDWARE_VALIDATION.md (#31 results under steps 10-13, #30 a new step).
> **Numbers handed out:** HARDWARE_VALIDATION step 14 stays with #30 (#31 adds results, not steps).
> **Merge order:** #32 alone.
> **Starting now:** #32, Sonnet 5.5, worktree `claude/harmony-call-history`.
>
> **Questions for you (#33):**
> - Release before #31's hardware run (release notes then say the four features are simulator-only), or after?
> - Wait for #32 (likely open today) and #30 (blocked on #31)? My suggestion: wait for #32 and #31; #30 can go in 0.4.1.

### Where this differs from the hand-written expectation, and why

The expectation was: hold #31, notice #30 depends on #31's `H-FIXIT` finding, #32 free, #33 last with a question. The plan matches on all four. Differences:

1. **The #30 → #31 dependency came from #31's text, not #30's.** `scan_queue.py` lists #30's mentions as only `#29 (merged)`; a planner reading #30 alone would have started it. It was found by the identifier overlap (`H-FIXIT`, `fixit`, `harmony_describe_activity`) and then by reading #31's "Decisions to bring back". This is the main reason for the `Runs after:` header.
2. **"Owner" is a false signal.** #30 mentions "the owner" three times and needs nothing from them; the scanner's owner-gate patterns correctly skip those, but this is fragile. Second reason for the `Needs the owner:` header.
3. **The plan reports main's CI state.** Not in the expectation. main was not green, for the same runner-queue reason the hand run hit on #27; saying so up front stops a worker from chasing it.
4. **#32's collisions are listed although it runs alone**, so the owner knows the next conflicts (CHANGELOG and README with #31 and #30).
