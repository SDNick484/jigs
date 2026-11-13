#!/usr/bin/env python3
"""Say which repositories still need a change, the same way before, during and after a sweep.

Usage:
  sweep_status.py (--root DIR | REPO_DIR ...) --anchor GLOB [--anchor GLOB ...]
                  (--has REGEX | --lacks REGEX) [--marker PATH] [--ref REF] [--json]

  --root DIR     every git checkout directly under DIR is a candidate. Name none by hand: a
                 repository left out of the list is how a sweep misses one.
  REPO_DIR ...   or name the checkouts.
  --anchor GLOB  the files the change applies to, as a path glob from the repository root
                 (`*` also crosses `/`). A repository with no such file is N/A.
  --has REGEX    the change is present in a file when REGEX matches it (multi-line search).
  --lacks REGEX  for a change that removes something: present when REGEX no longer matches.
  --marker PATH  a file that marks family membership (a lock file, a manifest). Adds a column;
                 it filters nothing, so a member the anchor misses and a non-member the anchor
                 hits are both visible.
  --ref REF      read files from this git ref (default HEAD). `WORKTREE` reads the files on
                 disk instead, uncommitted edits included.

Each repository is one of:
  TODO     has anchor files, none has the change
  PARTIAL  some anchor files have it and some don't (the files are listed)
  DONE     every anchor file has it
  N/A      no file matches the anchor
  ERROR    not readable at that ref

It reads only local checkouts and decides nothing about what to edit: it answers "where does
this stand", so the plan, the report and the check after merging all come from one probe.

Exit status: 0 nothing left to do (no TODO, PARTIAL or ERROR), 1 something left, 2 usage.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

WORKTREE = "WORKTREE"


class RepoError(RuntimeError):
    pass


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, errors="replace")
    if proc.returncode != 0:
        raise RepoError((proc.stderr or proc.stdout).strip().splitlines()[-1] if (proc.stderr or proc.stdout).strip() else "git failed")
    return proc.stdout


def list_files(repo: Path, ref: str) -> list[str]:
    if ref == WORKTREE:
        out = git(repo, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
        return sorted({f for f in out.split("\0") if f and (repo / f).is_file()})
    return sorted(f for f in git(repo, "ls-tree", "-r", "-z", "--name-only", ref).split("\0") if f)


def read_file(repo: Path, ref: str, path: str) -> str:
    if ref == WORKTREE:
        return (repo / path).read_text(encoding="utf-8", errors="replace")
    return git(repo, "show", f"{ref}:{path}")


def probe(repo: Path, *, anchors: list[str], pattern: re.Pattern[str], want_match: bool,
          marker: str | None, ref: str) -> dict[str, object]:
    row: dict[str, object] = {"repo": repo.name, "path": str(repo), "ref": ref}
    try:
        files = list_files(repo, ref)
        if ref != WORKTREE:
            row["commit"] = git(repo, "rev-parse", "--short", ref).strip()
        if marker is not None:
            row["marker"] = marker in files
        matched = [f for f in files if any(fnmatch.fnmatchcase(f, a) for a in anchors)]
        have = [f for f in matched if bool(pattern.search(read_file(repo, ref, f))) == want_match]
    except (RepoError, OSError) as exc:
        row.update(state="ERROR", error=str(exc), have=[], missing=[])
        return row
    missing = [f for f in matched if f not in have]
    if not matched:
        state = "N/A"
    elif not missing:
        state = "DONE"
    elif not have:
        state = "TODO"
    else:
        state = "PARTIAL"
    row.update(state=state, have=have, missing=missing)
    return row


def candidates(root: str | None, repos: list[str]) -> list[Path]:
    if root is not None:
        base = Path(root)
        if not base.is_dir():
            raise RepoError(f"{root} is not a directory")
        return sorted((p for p in base.iterdir() if (p / ".git").exists()), key=lambda p: p.name)
    return [Path(r) for r in repos]


def render(rows: list[dict[str, object]], show_marker: bool) -> str:
    order = {"TODO": 0, "PARTIAL": 1, "ERROR": 2, "DONE": 3, "N/A": 4}
    rows = sorted(rows, key=lambda r: (order[str(r["state"])], str(r["repo"])))
    width = max([len(str(r["repo"])) for r in rows] + [4])
    lines = []
    for r in rows:
        state = str(r["state"])
        cells = [str(r["repo"]).ljust(width), state.ljust(7)]
        if show_marker:
            cells.append("marker" if r.get("marker") else "-     ")
        if state == "ERROR":
            detail = str(r["error"])
        elif state == "N/A":
            detail = "no file matches the anchor"
        else:
            parts = []
            if r["missing"]:
                parts.append("missing in: " + ", ".join(r["missing"]))  # type: ignore[arg-type]
            if r["have"]:
                parts.append("present in: " + ", ".join(r["have"]))  # type: ignore[arg-type]
            detail = "; ".join(parts)
        lines.append("  ".join(cells + [detail]).rstrip())
    n = {s: sum(1 for r in rows if r["state"] == s) for s in order}
    lines.append("")
    lines.append(f"{len(rows)} repositories: {n['TODO']} TODO, {n['PARTIAL']} PARTIAL, {n['DONE']} DONE, "
                 f"{n['N/A']} N/A, {n['ERROR']} ERROR")
    if show_marker:
        odd = [str(r["repo"]) for r in rows if r.get("marker") and r["state"] == "N/A"]
        odd2 = [str(r["repo"]) for r in rows if r.get("marker") is False and r["state"] not in ("N/A", "ERROR")]
        if odd:
            lines.append("marker but no anchor file (a member this change does not apply to; say why): " + ", ".join(odd))
        if odd2:
            lines.append("anchor file but no marker (not a member by the marker; in or out is a decision): " + ", ".join(odd2))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], usage=__doc__.split("\n\n")[1])
    ap.add_argument("repos", nargs="*")
    ap.add_argument("--root")
    ap.add_argument("--anchor", action="append", default=[])
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--has")
    group.add_argument("--lacks")
    ap.add_argument("--marker")
    ap.add_argument("--ref", default="HEAD")
    ap.add_argument("--json", action="store_true")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    problem = None
    if not args.anchor:
        problem = "give at least one --anchor"
    elif (args.has is None) == (args.lacks is None):
        problem = "give exactly one of --has and --lacks"
    elif (args.root is None) == (not args.repos):
        problem = "give --root or repository directories, not both and not neither"
    if problem is None:
        try:
            pattern = re.compile(args.has if args.has is not None else args.lacks, re.MULTILINE)
            repos = candidates(args.root, args.repos)
        except (re.error, RepoError) as exc:
            problem = str(exc)
    if problem is not None:
        print(f"error: {problem}", file=sys.stderr)
        return 2
    if not repos:
        print("error: no git checkouts found", file=sys.stderr)
        return 2

    rows = [probe(r, anchors=args.anchor, pattern=pattern, want_match=args.has is not None,
                  marker=args.marker, ref=args.ref) for r in repos]
    if args.json:
        print(json.dumps({"ref": args.ref, "anchors": args.anchor, "repositories": rows}, indent=2))
    else:
        print(render(rows, args.marker is not None))
    return 1 if any(r["state"] in ("TODO", "PARTIAL", "ERROR") for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
