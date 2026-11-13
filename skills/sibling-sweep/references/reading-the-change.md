# Reading the change: fixed, derived, probe

A sweep goes wrong in two ways: the same text lands where it is not true, or a repository is left out. Splitting the change into three parts before starting prevents both.

## Fixed and derived

Take the reference change (a commit, a PR, or the owner's sentence) and sort every line of it:

- **Fixed**: must be byte-identical everywhere for the change to mean the same thing. A setting and its value, a workflow block, a pinned version.
- **Derived**: correct only for the repository it was written in. Anything that states a fact about that repository's code or behaviour: a number of seconds, a count, a package or file name, a list of what "already" holds, a justification.

The test for derived: *could this sentence be false in another repository?* If yes, it is worked out there, from that repository's code, and the working goes in the PR.

Worked case (see `example-shutdown.md`). The change was one service-file setting giving a server 15 seconds to stop before it is killed, with a comment above it.

- Fixed: the setting line and two sentences of the comment (what the setting means, when it takes effect).
- Derived: the comment's middle, saying how long *this* server's shutdown takes at worst and so whether 15 seconds is enough. Across nine repositories and ten service files the hand-written answers were: about 2 s (five files), at most about 7 s (two), and three that say plainly the limit can still be exceeded (about 20 s at worst in one; a close that isn't time-limited in another; a serial per-device stop in a third). One line was the same in ten places; the truthful explanation beside it took five different forms.

Copying the reference repository's comment would have put "at most about 7 s" on a server whose worst case is 20.

## What "does not apply" and "already there" look like

For a change with several elements (a CI hardening pass: token permissions, concurrency, timeouts, pinned actions, an update bot's config), each repository answers each element separately. In the hand-run wave one repository already had the permissions block and the bot config, and only two of nine had a release workflow to pin. Their commit bodies say so line by line ("permissions: already contents: read", "dependabot.yml: unchanged"). That is the form to keep: a reviewer can then trust that an element missing from the diff was looked at.

## The probe

Two arguments to `scripts/sweep_status.py`:

- `--anchor`: a glob for the files the change applies to. Prefer the pattern over a path: `deploy/*/*.initd` found a repository with two service files where a path naming one file per repository would have found one.
- `--has` (or `--lacks` for a removal): a regular expression that is true only once the change is in. Use the fixed part, anchored to a line start where it can be (`^retry=`), not a word from the comment.

Check the probe against the reference before trusting it: `--ref <commit before the reference change>` must say TODO for that repository and `--ref <the change>` must say DONE. A probe that says DONE for both is matching something that was always there.

Some changes can't be probed with one pattern (a refactor, a behaviour). Then probe for the nearest fixed sign (a new test name, a new file), say in the plan what the probe can't see, and read those repositories by hand.

## Is it shared code?

Before planning edits, look the anchor files up in each repository's own rules. If a repository says the file is synced, vendored or generated from somewhere else (a manifest or lock file naming a source repository is the usual sign), editing it in place is wrong twice: the next sync overwrites it, and a drift check may fail CI before that.

The change belongs in the source repository. After it merges there, that repository's own tool opens the per-repo sync PRs; use it as documented rather than copying files by hand. Two things the tool typically does not do, which are this skill's job:

- **Discovery by name.** A tool that finds members by a name pattern misses members named differently. In the family this skill came from, the sync tool looks for one name prefix, and two other repositories carry the same lock file; one of them was pinned to an older commit than the rest, and the other was synced by hand. Run the probe with `--marker <the lock file>` and an anchor of the lock file itself, `--has` the new commit id: every member not at the new commit shows as TODO, whatever it is called.
- **Reading CI afterwards.** A tool that opens PRs has not seen their CI. Run `ci_state.py` on each.
