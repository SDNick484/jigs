# The waves this came from, and the rule each one left

The skill was written after nine changes had each been carried by hand across a family of similar repositories (nine MCP servers that share a set of modules, and two more repositories that carry the same shared files under different names). Each was found afterwards by an identical branch name or commit subject in several repositories.

| Wave | Repositories | What it left behind |
|---|---|---|
| First scaffold of the hardware-free test kit | 7 | The family's common shape, and so what "the same file" means in each |
| Remote transport behind an access proxy | 4, in two pairs nine days apart | A change that arrives in instalments needs a probe to say who is left |
| Service packaging for one OS | 4, in two pairs a week apart | Same |
| Installer really upgrades on re-run | 5 | **A remembered list misses one** (below) |
| A security and naming remediation | 8, under two branch names | **Pilot first**; **name the branch for the change** (below) |
| Shutdown limit and CI hardening | 9 | **Fixed and derived**; per-element answers in the commit body (below) |
| Shared-module syncs | 9 each, several times | **Shared files are not swept** (below) |
| Packaging metadata and release workflow | 6 | **Name the branch for the change** (below) |
| Pre-launch fixes | 8 | Same |

## A remembered list misses one

The installer fix went to five repositories. A sixth had the same installer, written three days before the wave, and was not on the list. Weeks later it still installs the old way, and a seventh repository created afterwards copied the unfixed form. Nobody decided to skip them; nobody asked. `sweep_status.py` over every checkout, with the fix's own line as the pattern, finds both in one command. Hence step 3: every candidate gets a row, and "not changed" always has a reason next to it.

The same probe for the shutdown wave shows nine repositories DONE and one, created the day before the wave under a different name, still TODO.

## Pilot first

In the remediation wave every one of the six repositories on its main branch name needed a follow-up commit to get CI green, for overlapping reasons: a smoke test that still called a tool by its old name, the formatter, and the shared-file drift check. Each was discovered separately, six times. Running one repository to green first turns that into one discovery and five briefs that already contain it.

## Fixed and derived; answer every element

The shutdown wave is the cleanest case and is written up in `reading-the-change.md` and `example-shutdown.md`: one identical setting line, five different truthful explanations across nine repositories, one repository with two files.

Its CI-hardening commits show the other half. The commit body in each repository lists every element and says "already" or "unchanged" where that repository had it. Only two of the nine had a release workflow, so only two diffs touch one; the other seven are not missing anything, and their messages make that checkable.

## Name the branch for the change

The remediation went to six repositories under one branch name and to two more, the same day, under another; listing it afterwards takes two searches and knowing to make the second. Two later waves went out under an auto-generated session branch name. That name was the same in eight repositories, but in two of the eight the branch carried a different change (a release) and the name could not say so. A branch named for the change (`fix-install-upgrade`, not a session id) is what lets step 3 recognise "a PR for this is already open here" and lets anyone list the wave later with one `git log --grep`.

## Shared files are not swept

Every wave that needed a change in a shared module made it in the shared repository and synced. The sync tool refuses a dirty tree, opens a PR only for a repository whose checks pass, and skips one whose sync PR is already open. Its discovery is by name prefix, which is the one gap: see "Is it shared code?" in `reading-the-change.md`.

## Public rules reach the commit

A repository with a privacy scan over history failed a PR on the sign-off line of an automated commit, not on any file. Commit author, committer, message, branch name and PR text are all public surface. Step 0 reads each repository's rule for them, and sync or sweep commits are authored with the identity the repository states, not whatever the local git config holds.
