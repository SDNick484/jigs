# Restacking, conflicts, and after "merged"

## First: did it land?

```sh
python3 scripts/landed.py OWNER/REPO <PR> [<PR> ...]     # every PR the owner says they merged
```

Go on only when every line says `LANDED`. `NOT_ON_DEFAULT` means the PR was merged into another PR's branch: GitHub shows "merged" and the default branch has none of it. Say which PR, and offer the repair: find the branch that holds the merged work (`git branch -r --contains <merge commit>`) and open a PR from it into the default branch. When the merges are spread over several branches, one PR per branch, lowest in the stack first. `WRONG_BASE` on a PR that is still open is the same mistake before it happens: retarget it with `gh api -X PATCH repos/OWNER/REPO/pulls/<N> -f base=<default branch>` and tell the owner.

One run merged a stack of PRs into each other this way before anyone noticed. This check makes it one command to see.

## Before any rebase: deepen

The push recipe in some hosted sessions ends with `git fetch --depth=1 origin <branch>`. That makes the branch tip a shallow boundary, so a later rebase finds no common ancestor and reports **every file** as an add/add conflict. If a rebase shows conflicts in files the branch never touched, this is why. Abort and deepen:

```sh
git rebase --abort
git fetch --depth=50 origin main
git fetch --depth=50 origin <branch>
```

Then rebase again. Never resolve a wall of add/add conflicts by hand.

## Restacking (initially, and after each merge)

In merge order, one branch at a time:

```sh
git fetch --depth=50 origin main
git checkout <branch-1> && git rebase origin/main
# resolve, gate, then:
git checkout <branch-2> && git rebase <branch-1>
...
```

After the owner merges the bottom PR with a merge commit, rebase the next branch onto `origin/main`; git drops the commits that are already there. If they squash-merged instead, the next branch's copies of those commits no longer match; use `git rebase --onto origin/main <old-branch-1-tip> <branch-2>` and tell them the next one should be a merge commit.

Push each with `git push --force-with-lease origin <branch>` (only branches this run created), then update the first line of each PR body: which PR it sits on, "review the last commit only", the merge order, and any renumbered slot ("The hardware step is now 12").

## Resolving append conflicts

The usual conflict is two branches appending at the same place: two README tool rows, two CHANGELOG bullets, two names in a test set, two "step 10" sections. Keep both, in merge order, and renumber what the plan renumbered. Then check, because keeping both is not always a text operation (both happened on 2026-11-12):

- **Lists of constructor calls or literals** (`assumptions.py`): joining two appended `Assumption(...)` entries dropped the `),` and `Assumption(` between them. Read the merged region as code; the gate catches the syntax error but not a merged-into-one entry that still parses.
- **Markdown tables**: joining two rows with a blank line between them splits the table into two, and the second half renders as text. Look for a blank line inside every table a conflict touched.
- **Numbered sections**: a "step 10" heading, the "Which step confirms what" table row, and any cross-reference ("see step 10") must all move together.

```sh
git diff --name-only --diff-filter=U            # during the rebase: which files conflicted
git diff origin/main -- <file>                  # after: read every conflicted region
```

Then run the full gate (not only the touched tests), and `ci_state.py` after the push.

## After "merged": the two-line report

```
#26 is in main. #27 and #28 are rebased on it, the gate passes on both, and CI is green on both. Next to merge: #27.
```

Then re-sort the queue (`scan_queue.py`): a merged PR may unblock an issue. If one becomes runnable, say so and include it in the plan; start it if the plan is unambiguous.
