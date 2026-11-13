#!/usr/bin/env python3
"""Fail if two skills carry different copies of the same script.

A skill is installed on its own, so it cannot import from a sibling directory: a script two skills
need is copied into each (skills/<skill>/scripts/<path>). Copies drift unless something compares
them, and a drifted copy is a bug fixed in one skill and still live in the other.

Two files are "the same script" when they have the same path under their skill's scripts/
directory. A copy that was renamed is not recognised, so keep the name when copying.

Usage: check_script_copies.py [--root DIR]
Exit status: 0 all copies match (or nothing is shared), 1 copies differ, 2 usage or setup error.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

SKIP_DIRS = {"__pycache__"}


def script_copies(skills: Path) -> dict[str, dict[str, str]]:
    """{path under scripts/: {skill name: sha256}} for every script in every skill."""
    found: dict[str, dict[str, str]] = {}
    for skill in sorted(p for p in skills.iterdir() if p.is_dir()):
        scripts = skill / "scripts"
        if not scripts.is_dir():
            continue
        for path in sorted(scripts.rglob("*")):
            if not path.is_file() or SKIP_DIRS & set(path.relative_to(scripts).parts):
                continue
            rel = path.relative_to(scripts).as_posix()
            found.setdefault(rel, {})[skill.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", default=".", help="repository to check (default: current directory)")
    args = ap.parse_args(argv)
    skills = Path(args.root).resolve() / "skills"
    if not skills.is_dir():
        print(f"error: no skills/ directory under {args.root}", file=sys.stderr)
        return 2

    shared = {rel: by_skill for rel, by_skill in script_copies(skills).items() if len(by_skill) > 1}
    differing = 0
    for rel, by_skill in sorted(shared.items()):
        if len(set(by_skill.values())) == 1:
            continue
        differing += 1
        print(f"scripts/{rel} differs between skills:")
        for skill, digest in sorted(by_skill.items()):
            print(f"  skills/{skill}/scripts/{rel}  sha256 {digest[:12]}")
    print(f"checked {len(shared)} shared script(s): "
          f"{'all copies match' if not differing else str(differing) + ' with differing copies'}")
    return 1 if differing else 0


if __name__ == "__main__":
    sys.exit(main())
