#!/usr/bin/env python3
"""Check a worker's finished branch before it is pushed or built on, the same way every time.

Usage: prepush_check.py WORKTREE --base REF --issue N
                        [--forbid GLOB]... [--other-lane GLOB]... [--require GLOB]... [--body PATH]

  WORKTREE      the worker's git worktree, with its branch checked out
  --base        what the branch started from: the default branch, or the branch below it in its lane.
                The diff is taken from the point where the two diverged, so commits that landed on
                the base afterwards are not counted as the worker's.
  --issue       the issue number the branch implements
  --forbid      a file the repo marks as shared or generated (repeatable; shell-style pattern)
  --other-lane  a file that belongs to an issue running in a parallel lane (repeatable)
  --require     a file that has to change together with this kind of work, such as CHANGELOG.md
                or 'tests/*' (repeatable; met when any changed file matches)
  --body        the PR description; default WORKTREE/.queue/PR_BODY.md

Git only: no network and nothing to install. Patterns match the whole path and `*` also matches
`/`, so 'shared/*' covers everything under shared/.

Prints OK or FAIL on the first line, then one line per finding and the list of changed files.
A `read:` line is not a failure: it names something only a reader can judge. Exit 0 on OK, 1 on
FAIL, 2 on a usage or git error.
"""
from __future__ import annotations

import argparse
import fnmatch
import re
import subprocess
import sys
from pathlib import Path

# What the PR description has to cover (references/worker-brief.md). A repo's PR template may
# word its headings differently, so a missing word is something to read, not a failure.
BODY_TOPICS = {"decision": "decisions made", "deviat": "deviations from the issue", "unverified": "what is unverified"}


def git(worktree: str, *args: str) -> str:
    done = subprocess.run(["git", "-C", worktree, *args], capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {done.stderr.strip() or done.stdout.strip()}")
    return done.stdout


def matching(files: list[str], patterns: list[str]) -> list[str]:
    return [f for f in files if any(fnmatch.fnmatchcase(f, p) for p in patterns)]


def check(worktree: str, base: str, issue: int, forbid: list[str], other_lane: list[str],
          require: list[str], body_path: Path) -> tuple[list[str], list[str], list[str]]:
    """Return (failures, things to read, changed files)."""
    fails: list[str] = []
    reads: list[str] = []
    changed = [f for f in git(worktree, "diff", "--name-only", f"{base}...HEAD").splitlines() if f]

    if not changed:
        fails.append(f"no commits on this branch since {base}: the worker has not committed its work")
    if git(worktree, "status", "--porcelain").strip():
        fails.append("uncommitted changes in the worktree: what is pushed would not be what was tested")
    hit = matching(changed, forbid)
    if hit:
        fails.append(f"changed a shared or generated file: {', '.join(hit)}")
    hit = matching(changed, other_lane)
    if hit:
        fails.append(f"changed a file that belongs to another lane: {', '.join(hit)}")
    missing = [p for p in require if not matching(changed, [p])]
    if missing:
        fails.append(f"expected to change, not in the diff: {', '.join(missing)}")

    if not body_path.is_file():
        fails.append(f"no PR description at {body_path} (PR_BODY.md)")
    else:
        text = body_path.read_text(encoding="utf-8", errors="replace")
        first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
        if not re.match(rf"Closes #{issue}\b", first):
            fails.append(f"PR description must open with 'Closes #{issue}'; it opens with: {first[:60]!r}")
        for word, meaning in BODY_TOPICS.items():
            if word not in text.lower():
                reads.append(f"the PR description never says '{word}...': check it covers {meaning}")
    return fails, reads, changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("worktree")
    parser.add_argument("--base", required=True)
    parser.add_argument("--issue", required=True, type=int)
    parser.add_argument("--forbid", action="append", default=[])
    parser.add_argument("--other-lane", action="append", default=[])
    parser.add_argument("--require", action="append", default=[])
    parser.add_argument("--body")
    args = parser.parse_args(argv)
    body = Path(args.body) if args.body else Path(args.worktree) / ".queue" / "PR_BODY.md"
    try:
        fails, reads, changed = check(args.worktree, args.base, args.issue, args.forbid,
                                      args.other_lane, args.require, body)
    except RuntimeError as err:
        print(f"ERROR {err}", file=sys.stderr)
        return 2
    print(f"{'FAIL' if fails else 'OK'} #{args.issue}: {len(changed)} file(s) changed since {args.base}")
    for line in fails:
        print(f"  fail: {line}")
    for line in reads:
        print(f"  read: {line}")
    for name in changed:
        print(f"  changed: {name}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
