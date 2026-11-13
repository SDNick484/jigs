# Every place a result is stated

The registry is the source of truth, and most repos have a test that fails when the registry and the README table disagree. That test is why the table is never the thing forgotten. Everything it does not check is.

`scripts/assumption_map.py --base REF` finds the candidates; this is what they are and why each matters. The file names are the usual ones: the repo's `CLAUDE.md` says what it actually has.

## Always

| Place | What changes | Why it gets missed |
|---|---|---|
| The registry | `status`, `note`, the claim if corrected, the shared description of the run | It doesn't. Start here. |
| The registry's own text | The module docstring ("everything here is unchecked"), a `source` that says "unchecked on this firmware" | It is prose inside the file you just edited, above or beside the line you changed. |
| The checklist, under the step | A dated record of what was observed, item by item, with what was not run | Not checked by any test. Write it even for a step that confirms no assumption. |
| The checklist's summary tables | "Which step confirms what", "what's new and unconfirmed" | A second table in the same file, far below the step. |
| The checklist's preamble | "Everything here is simulator-only", "steps 1 to 4 have run" | It is the first paragraph of the file and nobody scrolls up. The most common stale line in the evidence. |
| README status table | The row per assumption | Usually test-enforced. |
| README status paragraph | The "what has run on real hardware, what has not" summary near the top | Prose; the table test does not read it. |
| README feature prose | A sentence beside a feature: "not yet checked on a real device" | It lives in the feature's section, not near any table. Search for the assumption's id. |
| The repo's `CLAUDE.md` | The status section; a facts section headed "not yet verified" | It is the file that tells the next session what to trust, so a stale line here misleads the most. |
| Changelog | A line under the unreleased section: which run, which assumptions moved, what is still untried | A hardware run feels like "no code change". It changes what a user can rely on. |

## When the run touched them

| Place | What changes |
|---|---|
| A protocol or design document | Its own per-claim status column or wording |
| Source docstrings | "Status: verified against the simulator only" at the top of the server module |
| The simulator | Any behavior that was corrected or contradicted |
| Server code | Guards, error messages and tool descriptions that follow from a contradiction |
| Tests | A test for each code change. Also any test that names one particular unchecked assumption as its example: it breaks the day that assumption is verified. Make it take its example from the registry instead of swapping in another id |
| The diagnostic command | Its hints, if a step number or an expected failure changed |
| Captures | New files in the recorded-fixtures directory (see `captures.md`) |
| The replay test | Its docstring ("nothing is recorded yet") and anything listing the captures |
| The scrubber and its test | When the scan found a field it missed, in a commit of their own |

## Step numbers

Never renumber. A diagnostic command prints "see step 3"; an issue says "blocked on step 9"; last month's notes say "step 13.4". When a step is added, give it the next free number, or a suffix (`8a`) when it belongs between two. A closing section that carries a number ("11. Recording results") moves down only if nothing refers to it; better to leave it unnumbered. `assumption_map.py --base` fails on a step whose number changed or disappeared.

## How many commits

Follow the repo. Both shapes appear in the evidence and both work:

- **one commit per step**, made as the run goes ("Hardware results: step 4; an open dialog holds launches"). Good when a step changes code: the fix and its evidence stay together, and a run that is interrupted has lost nothing;
- **one commit for the record**, after the run. Good when the run is driven from a session and written up at the end.

Either way: a code fix that is not specific to one step (the scrubber, a shared helper) goes in its own commit before the record, and the subject line names what was seen, not only "update docs" ("...: five assumptions verified", "...: the device refuses a forced power off").

A commit message for a run says the date, the device and versions, what was verified with one phrase of evidence each, what was contradicted, and what is still open. It is the summary someone reads in the log instead of opening four files.
