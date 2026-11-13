# Worked example: the shutdown-limit wave, replayed

## The hand run (the evidence)

On 2026-11-10 one change went to nine repositories under the branch `audit/shutdown-retry-and-ci-hardening`: the service file gained `retry="SIGTERM/15/SIGKILL/5"` and a comment, so the process manager waits 15 seconds after SIGTERM before SIGKILL instead of its default 5. Same commit subject in all nine, each referring to one tracking issue.

## The replay

Three of the nine were checked out as they were immediately before that commit, with no later history: `mcp-server-harmony`, `mcp-server-sofabaton`, `mcp-server-misterfpga`. Chosen because the hand-written comments differ most between them.

**Step 1, the three parts.**

- Fixed: the setting line, the comment's first sentence (what the schedule means) and its last (the process manager reads it at start, so the restart that installs it still stops the old way).
- Derived: how long this server's shutdown can take at worst, from its code, and whether 15 seconds covers it.
- Probe: `--anchor 'deploy/alpine/*.initd' --has '^retry='`.

**Step 3, the probe on the three old checkouts:**

```text
mcp-server-harmony     TODO     marker  missing in: deploy/alpine/mcp-server-harmony.initd
mcp-server-misterfpga  TODO     marker  missing in: deploy/alpine/mcp-server-misterfpga-track.initd, deploy/alpine/mcp-server-misterfpga.initd
mcp-server-sofabaton   TODO     marker  missing in: deploy/alpine/mcp-server-sofabaton.initd

3 repositories: 3 TODO, 0 PARTIAL, 0 DONE, 0 N/A, 0 ERROR
```

Two files in one repository, found by the glob.

**Step 6.** One fresh agent per repository, each given `worker-brief.md` filled in: the fixed lines, the derived part as a question, the repository's gate. None had seen the merged commits or each other's work.

## Result against what was merged

| Repository, file | Hand-written worst case | Replayed worst case | Same conclusion? |
|---|---|---|---|
| harmony | at most about 7 s: 2 s drain, then devices disconnect in parallel, 5 s each | about 7 s: 2 s for open requests, then all closed at once, each cut off at 5 s | yes: 15 s is enough |
| sofabaton | usually about 2 s, at worst about 20 s: 2 s drain, then two tasks at 5 s each and a connection up to 8 s, in turn; can still end in SIGKILL | 2 + 5 + 5 + 8 = 20 s if every timeout fires; 15 s is not always enough; the usual slow case is 10 s | yes: not always enough |
| misterfpga, server | at most about 7 s: 2 s drain, then parallel, 5 s each | 2 + 5 = 7 s however many devices | yes: enough |
| misterfpga, tracker | about 2 s plus 5 s per device, one at a time: 12 s for two; three or more can end in SIGKILL | 5 s each + 2 s: 7, 12, 17 s for one, two, three; not always enough from three | yes: not enough from three |

The setting line and the two fixed sentences are byte-identical to the merged ones in all four files. All three repositories' gates passed (383, 471 and 405 tests, plus lint, format, types and the shared-file check).

## Where the replay differed, and why

1. **The comments are longer than the hand-written ones** (three derived lines against two, some over the files' 100-column width, naming source files and constants). The brief asked for working and the workers put it in the comment. The brief now says to write the derived part in the file's own style and width, and to keep the working for the reply and the PR.
2. **A blank line.** In one repository the block was placed without the blank line before it that the merged version has. The brief said "followed by a blank line" and nothing about the line before. The brief's fixed part now includes the blank lines around it.
3. **Two workers added a changelog entry; the hand run added none.** Both repositories keep an `[Unreleased]` section, and their rules require a changelog section per release, not per change, so each worker made its own call, and the third repository has no changelog. Three workers, two answers to the same question. Whether a sweep's change is recorded in changelogs is now decided once, in the plan, for every repository that has one (step 4), and carried in every brief. For the record: both of these repositories were released within a day, and neither changelog mentions this change, though it asks operators to re-run the installer.
4. **The workers reported things the hand run's commits don't mention**, correctly kept out of their diffs:
   - a shared module's docstring and a shared test still describe a 5-second stop window (all three workers; it is still so on the shared repository's default branch);
   - the tracker could stop its devices in parallel, which would make its worst case about 5 s for any number of them;
   - in one repository a 1.5 s publish at shutdown sits under a 1 s re-cancel, so it may be cut short (the worker's reading; not confirmed).
   These are what the report's "also found" line is for. The first is a change for the shared repository (step 2), not for nine siblings.
5. **Commit bodies.** The hand run used one body in every repository, pointing at the comment for the worst case, plus the tracking reference. The replayed bodies each state that repository's own figure. Both are defensible; the commit format in `formats.md` takes the second and keeps the tracking reference.

## What the replay did not test

- Pushing, opening PRs and reading CI (steps 5, 7, 8): nothing was opened in those repositories. `ci_state.py` was run for real against other pull requests.
- The other six repositories, and the CI-hardening commits that travelled on the same branch.
- Whether the process manager honours the setting: neither the hand run's commits nor the replay ran the service.

## The same probe on today's default branches

Run across every checkout of the family, the probe shows the nine swept repositories DONE and a tenth, a service created the day before the wave under a different name, still TODO. With the installer fix's pattern instead (`--anchor 'deploy/alpine/install.sh' --has 'force-reinstall'`), two repositories are TODO: one that had the installer three days before that wave and was not on its list, and the same tenth.
