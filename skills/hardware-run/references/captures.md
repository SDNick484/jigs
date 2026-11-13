# Captures

A capture is what a real device returned, saved so the tests can replay it: a configuration dump, a list reply, a recorded message. It is the best evidence a run produces and the only file in the PR that nobody wrote, so it is the one that leaks.

## The sequence

1. **Take it with the repo's own tool** (its diagnostic command's dump option, or whatever the repo's `CLAUDE.md` names). That tool scrubs on the way out. Do not save raw responses by other means.
2. **Write it outside the tracked tree first** (a scratch directory), not into the fixtures directory. A file that is already where the tests look gets committed by the next `git add`.
3. **Scan it.**
   ```sh
   python3 scripts/scan_capture.py SCRATCH_DIR --deny FILE
   ```
   `--deny FILE` is a list the person writes, one term per line: their own name, household and room names, network names, hostnames, the vendor account's display name. No pattern can know these. Keep the file out of the repo.
4. **Deal with every finding** (below).
5. **Copy it into the fixtures directory, run the replay test, and look at the diff once yourself** for anything a person would recognise.
6. **Scan the fixtures directory once more** before committing, so what is checked is what is staged.

## A "must fix" finding

It means the repo's scrubber does not know this field. The fix is in the scrubber, not in the capture:

1. Add the key or the pattern to the scrubber. Prefer a rule by shape (any value containing an address) over a longer key list where one is possible: firmware adds keys.
2. Add a test with a made-up value of the same shape, in the same position (mid-string, nested, inside a JSON string).
3. Commit the scrubber and its test on their own, before the capture exists in git. History is public for good; a capture committed and then cleaned is still in the first commit.
4. Take the capture again, or run the existing file back through the fixed scrubber if the repo's tool can. Scan again.

Do not edit the capture by hand to pass. It is clean once, the scrubber is still wrong, and the next person's dump leaks the same field into an issue.

If the value is somewhere the scrubber cannot reach without breaking the replay (an identifier the parser needs), mask it with a stable placeholder of the same shape and say so in the capture's metadata and in the PR.

## The "look at" list

These are not failures. Each is a question for the person:

- **Identity keys with a value** (a serial, a session id, a location, a time zone, a host name): is this unique to their setup? Mask unless they say it is fine.
- **Partly masked values** (the last part of an address left visible): enough to tell devices apart in a test, and usually enough to say so in the PR and move on. The person decides.
- **Opaque tokens**: a hash can embed an account name. If nobody knows what it is, mask it.
- **Names of devices, rooms and activities**: a capture is not much use without them, and the repo may accept them. That is the repo's rule; in a public repo, ask once and write the answer into the repo's `CLAUDE.md`.

Record what was accepted in the PR description, so the reviewer sees it was a decision.

## What is never committed

- A debug or verbose log. Those are unredacted by design. If a step needs one, it stays on the person's machine and the note quotes the two lines that matter.
- A capture from someone else's device sent in for a bug report, without their say-so.
- Credentials, in any file, including a checklist's "before you start".

## After the captures are in

- The replay test's docstring and any list of recorded devices.
- Any assumption whose step says "if the replay test passes": this is the evidence it was waiting for, even if that step was not part of today's run.
- The capture's own metadata: when it was taken and with which versions. A replay that fails next year needs to know.
