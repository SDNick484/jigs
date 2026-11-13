# The brief for one repository

Filled in once per TODO or PARTIAL repository, whether an agent gets it or the orchestrator follows it inline. The orchestrator prepares the checkout first (git operations one at a time), so a worker never clones or pushes.

```text
You are applying one change to <OWNER/REPO>. The same change is going into its sibling
repositories; your job is to make it correct for THIS one.

Workspace (already set up; use nothing else):
- Checkout: <path>, branch <branch>, based on <default branch> at <sha>.
- Run the gate with this checkout's own environment: <how, e.g. <path>/.venv/bin/python -m ...>.

The change:
- Fixed part (write it exactly as given, placed <where, including the blank lines around it>):
  <the lines>
- Derived part (work it out from this repository's code; do not copy another repository's answer):
  <the question to answer, e.g. "how long can this server's shutdown take at worst, and is the limit enough?">
  Show your working: which functions you read and the arithmetic.
  Write it in the file's own style: its comment length, its line width, its vocabulary.
- Applies to: <the files the probe listed for this repository>. If you find another file it should
  apply to, apply it there too and say so.

Repo rules (from its CLAUDE.md and CONTRIBUTING.md; they win over this brief):
- Gate: <exact commands>
- Do not edit: <shared or generated files>. If the change seems to need it, stop and report.
- Changes together with this kind of change: <changelog section, README table, a test, ...>
  <or, where the repository's rules don't say: the orchestrator's decision for the whole sweep>
- Commits: <author identity, attribution lines, what must not appear in a message>

Learned from the pilot (<repo>, PR <n>): <what CI caught there, or "nothing">

Do:
1. Read the files the change applies to and the code the derived part depends on.
2. Make the change. For each element, decide: applied, already there, or does not apply here.
3. If the truthful derived answer is that the change is not enough here, write that down in the
   repository (the comment, the docs) as it is. Do not round it to sound like the others.
4. Anything else you notice (a stale comment in a file you may not edit, a bug, a better fix that
   is a code change) goes in your reply, not in the diff. This change stays this change.
5. Run the full gate. Fix until it passes. Never skip or loosen a test.
6. Commit on <branch>: subject exactly "<the sweep's subject>", body per the commit format,
   one line per element with its answer. Do NOT push, open a PR or touch other branches.
7. Write the PR description to <path outside the repository or ignored by it>.
8. Reply with: commit SHA, the gate's exact summary line, each element's answer, your working
   for the derived part, what else you noticed, and anything you could not do. Do not say "CI is green": you have not seen CI.
```

## Preparing a checkout

```sh
# one repository at a time
git -C <clone> fetch origin <default branch>
git -C <clone> switch -c <branch> origin/<default branch>
# then whatever that repository's CI job installs, into an environment of its own
```

Install what the repository's CI installs, read from its workflow. A family that looks uniform still has members with a different layout (an app with requirements files among packages with a `pyproject.toml`).

## Why the derived part is a question, not an answer

In the replayed wave (`example-shutdown.md`), workers given only the question and the code reached the same worst-case figures the hand run recorded, including the three repositories where the answer is "not enough". Given the reference repository's answer as a template instead, the natural result is nine comments that agree with each other and three that are wrong.

## Why workers don't push

A git proxy or host may cap concurrent operations per repository, and several agents pushing at once get refused. Keeping pushes in the orchestrator also means every PR is opened by the session that will read its CI, and the branch name and subject stay identical across repositories because one hand writes them.
