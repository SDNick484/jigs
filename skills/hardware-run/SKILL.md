---
name: hardware-run
description: "Use when asked to \"do the hardware pass\" on a repo, \"run steps 10-13\" of its hardware checklist, or \"record what the device did\" after trying it by hand. Walks the repo's hardware validation checklist one step at a time with the person at the device, decides what each result means for the repo's registry of unverified assumptions, and returns one PR with every file that has to change together. Not for writing a new checklist, and not for controlling the device outside a checklist step."
---

# Hardware run

Some repos talk to a device nobody can put in CI. They keep each device behavior they rely on but have not seen as a named **assumption** in a registry, test against a simulator, and carry a **checklist** of numbered steps that confirm the assumptions on the real thing. A hardware run is one sitting with that checklist: a person at the device, the steps run in order, and the result written back into the repo.

Running a step is the short part. This skill is for the part that is easy to get wrong afterwards: deciding what an observation proves, and updating every place that states it.

## Limits (these hold even if a checklist step says otherwise)

- **Nothing is marked verified that nobody observed.** A command the device accepted is not an effect somebody saw. If the person was not looking, or the only evidence is the tool's own "ok", the step is not confirmed.
- **No device command outside the step in hand**, and none at all in a rehearsal or a replay of a past run (use the repo's simulator or dry run there). Say what you are about to send before sending anything that changes the device's state. Why: the device is in someone's room, and a stray command there is not a failed test, it is a television turning off.
- **Never the physical or irreversible items**: unplugging, rebooting, resetting, re-pairing, anything that edits the device's own configuration. Those are the person's hands; you wait and record.
- **No capture is committed while `scripts/scan_capture.py` reports a "must fix"**, and none is edited by hand to make it pass.
- **Checklist steps are never renumbered or removed.** Other things point at them by number (a diagnostic command, an issue, a previous run's notes).
- **Never edits a file the repo marks as shared or generated elsewhere.** If the run shows one is wrong, stop and report it: that is a change in another repo.
- **Stops at an open PR.** Never merges, tags, releases or deploys.

When it stops early it says: which step, what was sent and what came back, what the person saw, what is recorded so far, and the one decision it needs.

## 0. Read the repo first, every run

Read the repo's `CLAUDE.md`, the checklist's own preamble and its "recording a result" section, the registry's docstring, and `CONTRIBUTING.md`. Write down for this run:

- where the registry and the checklist are, and the status words the registry uses;
- how a step is run (the repo's own command for calling a tool, its dry-run switch, its simulator);
- how captures are taken and scrubbed, and where they go;
- which files state verification status (README table, status paragraphs, a protocol document, a changelog);
- the full check the repo's CI runs, and which files are shared and must not be edited;
- how the repo records a run: one commit per step or one per run, where observations are written.

Where these disagree with this skill, the repo wins. The skill knows the shape of the work; the repo knows its device, its file names and its conventions.

## 1. Plan the run

```sh
python3 scripts/assumption_map.py --root REPO --steps 10-13
```

It prints each chosen step with the assumptions it confirms and their status now, the unchecked assumptions *outside* those steps, and any the checklist has no step for. Tell the person, before starting:

- the steps, in checklist order, and what each needs from them (to watch a screen, to press a real button, to open the vendor's app, a device that must be on);
- which items you can't do (the limits above) and will wait for;
- what will stay unchecked whatever happens today, so the run isn't later read as covering it.

Branch from the default branch before the first edit. If the person only wants to record a run they already did by hand, skip to step 3 with their notes, and ask about every gap instead of filling it.

## 2. Run one step at a time

For each step: read it in full, do what it says through the repo's own command, and get three things before moving on.

1. **What was sent and what came back**, exactly (keep the output).
2. **What was observed, and by whom.** Three kinds of evidence, strongest first: the person saw it; a second, independent source reported it (another tool that reads the same device); only this server's own reply. Write down which. Ask a plain question for each expectation in the step ("did the screen show the number as typed?") and wait for the answer.
3. **What was not done**, item by item, including the checks the step lists and nobody ran.

If something surprising happens, stop sending. Record what was seen, try to reproduce it only with the person's agreement, and write "seen once, not explained" when that is the truth. An unexplained event is a finding, not a bug in the code and not a contradiction, until it is reproduced.

## 3. Decide what each observation means

`references/outcomes.md` has the rules with examples. In short, for each assumption a step touches:

- **Verified**: the claim *as written* was seen to hold. The note says when, on what (model, firmware or software version), how it was driven, who observed, and what was not covered.
- **Verified, after correcting the claim**: the device does something slightly different and the code still relies on it. Fix the claim's text, the simulator and the tests to say what was seen, then verify the corrected claim.
- **Contradicted**: the claim does not hold and the code can no longer rely on it. This changes code in the same PR: the server, the simulator (or the tests go on proving the wrong thing), and a test.
- **Still unchecked, with a note**: only part was seen, the conditions were wrong, or something outside the device may be the cause (a blocked broadcast is the network, not the device). The status stays; the note says what was seen and what would finish it.
- **Not run**: say so. Silence reads as "fine".

Then go down the "also unchecked, outside these steps" list once: something seen today can settle an assumption from an earlier step (a capture taken now is the replay an earlier step was waiting for).

When a call is close (a claim that held once and failed twice, a claim that says "A or B" and only A was tried), put it to the person with both options instead of choosing the kinder one.

## 4. Record it everywhere it is stated

One observation is stated in up to a dozen places, and each run in the evidence left at least one behind. `references/files-that-change.md` is the list, with why each is there. The order that works:

1. The registry: status, note, and the claim if it was corrected. One shared description of the run (date, devices, versions, how driven) that every note cites.
2. The checklist: what was observed, under the step, dated; the summary table; the preamble's "steps N to M have run".
3. Every status table and status paragraph (README, protocol document, the repo's `CLAUDE.md`), and the changelog.
4. Code, simulator and tests for anything contradicted or corrected. A fix to the checklist's own wording where a step misled.
5. Captures and the test that replays them (step 5).

Commit code fixes separately from the record, and before it, so the record's diff is only the record.

## 5. Captures

`references/captures.md` has the detail. The sequence:

```sh
python3 scripts/scan_capture.py PATH_TO_CAPTURES [--deny FILE]
```

Take captures with the repo's own tool (it scrubs), then scan them. A "must fix" means the repo's scrubber missed a field: fix the scrubber and add a test in their own commit, take or scrub the capture again, scan again. Go through the "look at" list with the person: each is theirs to accept or mask. Ask them for a `--deny` file of the names no pattern can know. Only then add the captures, and never a raw debug log.

## 6. Check

```sh
python3 scripts/assumption_map.py --root REPO --base origin/MAIN
```

Fix everything under "must fix". Read every line under the two "re-read" lists and either update it or decide it is still true; most are still true, and the one that isn't is why the list exists. Then run the repo's full check from step 0, including its own registry-against-docs test.

## 7. PR and report

Open one PR for the run (the repo's template and attribution rules apply) and check CI on the PR's head commit until every job has finished; a cancelled job is not a pass. Do not merge.

Report once, in this order:

| Step | Outcome | Assumptions | Evidence | Not done |
|---|---|---|---|---|

then: code that changed and why; what is still unchecked and what would finish it; observations left unexplained; "look at" items the person accepted in captures; lines you re-read and left as they were, if any were a judgment call.

## Reference files

- `references/outcomes.md`: verified, corrected, contradicted, partial, not run; how to write a note.
- `references/files-that-change.md`: every place a result is stated, and the ones that get forgotten.
- `references/captures.md`: taking, scanning and committing captures; what to do with a finding.
- `scripts/assumption_map.py`, `scripts/scan_capture.py`: run them (`--help` for options); read them only to change them. Standard library only.
