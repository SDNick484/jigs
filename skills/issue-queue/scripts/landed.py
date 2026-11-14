#!/usr/bin/env python3
"""Say where each pull request ended up, instead of trusting "merged".

Usage: landed.py OWNER/REPO PR [PR ...]

A pull request can be merged without its commits reaching the default branch: when its base
was another pull request's branch, the merge goes into that branch and stops there. GitHub
shows it as merged either way. This reads each one and prints a verdict per line:

  LANDED          merged, and its merge commit is on the default branch
  NOT_ON_DEFAULT  merged into another branch; the default branch does not have it
  WRONG_BASE      still open, and opened against a branch that is not the default branch:
                  merging it as it stands will not reach the default branch
  OPEN            still open, against the default branch
  CLOSED          closed without merging

Exit code: 0 when every pull request named is LANDED, 1 otherwise, 64 usage.
"""
from __future__ import annotations

import json
import subprocess
import sys
from typing import Any, Callable

Gh = Callable[..., Any]


def gh(*args: str) -> Any:
    out = subprocess.run(["gh", "api", *args], check=True, capture_output=True, text=True).stdout
    return json.loads(out) if out.strip() else {}


def verdict(api: Gh, repo: str, default: str, number: str) -> tuple[str, str]:
    pr = api(f"repos/{repo}/pulls/{number}")
    base = pr["base"]["ref"]
    if pr.get("merged"):
        # "behind" or "identical": the default branch contains the merge commit. This also
        # holds when the pull request was merged into a branch that later reached the
        # default branch, which is landed too.
        cmp_ = api(f"repos/{repo}/compare/{default}...{pr['merge_commit_sha']}")
        if cmp_.get("status") in ("behind", "identical"):
            return "LANDED", f"on {default}"
        return "NOT_ON_DEFAULT", f"merged into {base}; {default} does not have it"
    if pr["state"] == "open":
        if base != default:
            return "WRONG_BASE", f"opened against {base}, not {default}"
        return "OPEN", f"against {default}"
    return "CLOSED", "closed without merging"


def main(argv: list[str], api: Gh = gh) -> int:
    if len(argv) < 2 or "/" not in argv[0] or not all(a.isdigit() for a in argv[1:]):
        print(__doc__)
        return 64
    repo, numbers = argv[0], argv[1:]
    default = api(f"repos/{repo}")["default_branch"]
    all_landed = True
    for n in numbers:
        word, detail = verdict(api, repo, default, n)
        all_landed = all_landed and word == "LANDED"
        print(f"{word:<15} #{n}  {detail}")
    return 0 if all_landed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
