# What an observation means

The registry's status says whether the code may lean on a claim. So the question for each assumption is never "did the step go well" but "was this sentence seen to be true, on this device, by someone".

The repo's registry defines the status words; the usual three are *unchecked* (seen only in a simulator), *verified on hardware*, and *contradicted on hardware*. Use the repo's words.

## The five outcomes

### Verified

The claim as written was seen to hold.

- Read the claim's text again before deciding. A claim often has several clauses ("answers 200, cancels the screensaver, and starts the game a moment later"); each needs its own observation or its own "not covered" in the note.
- "Accepted" is not "happened". A reply of ok, or no error, confirms a claim about the reply. A claim about the effect needs someone to have seen the effect.
- A claim about what is on the wire (a frame's shape, the absence of a reply) needs a log of the wire. Seeing the right effect on screen does not confirm it.

### Verified, after correcting the claim

The device does something a little different from the claim, and the code still depends on that behavior. Examples of the kind: a refused connection where the claim said a 403; a `%` separator where the claim said a comma; a field name that differs from the documentation.

Rewrite the claim to say what was seen, make the simulator answer the same way, update the tests, and then mark the corrected claim verified. The note says the claim was corrected and from what. Leaving the old wording and marking it verified is the mistake: the next reader trusts a sentence nobody saw.

### Contradicted

The claim does not hold and the code can no longer rely on it. Examples of the kind: endpoints the documentation lists that answer 404; a "force" option the device itself refuses.

The rule of thumb between this and the previous outcome: if the fix is to describe the behavior correctly and carry on using it, correct the claim. If the fix is to stop relying on it (remove the feature, add a guard, take another route), it is contradicted.

A contradiction changes code in the same PR:

- the server, so it no longer relies on the claim, and says so where a user would otherwise be misled (an error message, a tool description);
- the simulator, so it behaves as the device did. A simulator that still behaves the old way keeps every test green while proving the wrong thing;
- a test for the new behavior;
- the documents that described the feature as working.

If the right code change is a design decision (drop the feature or work around it), record the observation, leave the PR at that, and ask.

### Still unchecked, with a note

Use this when the status must not move but something was learned:

- only part of the claim was exercised (a reconnect was seen, the re-read after it was not);
- the conditions were not the claim's (the hub was off throughout, so nothing could change while it was away);
- the cause may be outside the device: no answer to a broadcast can be the network; a timeout can be the host;
- the result was inconsistent and nobody knows why;
- the evidence is only this server's own reply.

The note says "partial" up front, then what was seen, then exactly what would finish it. Several runs can each add a partial note before one of them finishes the claim; keep them all, in date order.

### Not run

Recorded as not run, with the reason if there is one (no such device in the house, the optional item, out of time). Include checks the step lists inside itself (a file's permissions, a grep) that nobody did this time.

## Close calls go to the person

Put it to them, with both readings, when:

- the claim held in one try and failed in others;
- the claim says "A or B" and only A was tried (verified with the limit in the note, or left unchecked until B);
- the device matched the claim but a neighbouring fact looked wrong (the configuration says one input and the screen is on another). Ask first what the claim is about. If it is about what the configuration contains, the mismatch is an open observation beside a verified claim, not a contradiction.

Say which way you lean and why. The kinder status is not the default: an assumption wrongly marked verified is never looked at again.

## Writing the note

A note is read months later by someone deciding whether to trust the code on a different device. It carries, in this order:

1. **When and on what**: the date, the device (model), its firmware or software version. Keep this in one shared description per run that every note of the run cites, so the facts of the run are stated once.
2. **How it was driven**: through the server from a model session, by the repo's command line, by hand on the device; from which kind of host.
3. **What was seen, and who saw it**: measured values where there are any (2.4 s, 400 ms, the reply text), and "the person at the screen confirmed" or "a second tool reading the device agreed".
4. **Limits**: which device it was *not* tried on, which variant was skipped, what stayed inconsistent.

Do not put addresses, account names or credentials in a note. Whether device and room names may appear is the repo's rule; in a public repo, check before writing them.

## Things that are not assumptions

A run turns up more than registry results. Each has a place:

- **A step that confirms no assumption** (a feature built on already-verified behavior): still record what happened under the step. It is the only record that the feature was ever tried on a real device.
- **A document that was wrong** (a sensor's real name, a count of messages): fix it in the same PR and say so in the commit.
- **A step that misled or was missing a warning** ("dismiss the dialog before the next item"): fix the step's wording, keeping its number.
- **A behavior nobody had thought to assume**: if the code depends on it, it is a new assumption, entered as verified with its note, cited where the code relies on it, with a checklist step named.
- **Seen once, not explained**: under the step, with the times and what was ruled out. Not a registry change.
