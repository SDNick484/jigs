#!/usr/bin/env python3
"""Collect the facts the queue plan is built from, the same way every run.

Usage: scan_queue.py OWNER/REPO [--json]

Reads (REST only; GraphQL is blocked in some sessions):
  - open issues whose title starts with "Prompt:"
  - open pull requests, to find issues already being worked ("Closes #N")
  - the state of every issue or PR a prompt mentions

Prints, per prompt issue: the suggested model, the header lines if present
(Runs after / Needs the owner / Reserves), every #N it mentions with that item's
state, prose sentences that look like an owner gate or a publish step, and the
files and numbered steps it says it will touch. Then the overlaps between issues.

It decides nothing. The hints are deliberately loose: a planner reads every
body in full and makes the call; this only makes sure nothing is missed and the
same facts are gathered each time.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys

HEADER = {
    "model": re.compile(r"\*\*Suggested model:\*\*\s*(.+)", re.I),
    "runs_after": re.compile(r"\*\*Runs after:\*\*\s*(.+)", re.I),
    "needs_owner": re.compile(r"\*\*Needs the owner:\*\*\s*(.+)", re.I),
    "reserves": re.compile(r"\*\*Reserves:\*\*\s*(.+)", re.I),
}

# Phrases that mean "a person has to act or decide". Plain "owner" is not enough:
# issue #30 in mcp-server-harmony says "the owner's hubs" and "the owner also runs
# webOS" without needing the owner at all.
OWNER_GATE = re.compile(
    r"(needs the owner|owner at home|owner (is )?(physically )?present|ask the owner|"
    r"check with the owner|bring back to the owner|decisions to bring back|"
    r"wait for what (he|she|they) reports?|only the owner|the owner's (go-ahead|ok|call))",
    re.I,
)
PUBLISH = re.compile(
    r"(pypi|npm publish|push(ing)? the tag|annotated tag|release\.yml|publishes|"
    r"announce|deploy to production)",
    re.I,
)
ISSUE_REF = re.compile(r"(?<![\w/])#(\d+)\b")
FILE_REF = re.compile(r"`?([\w./-]+\.(?:py|md|toml|ya?ml|jsonl|json|sh|txt)\b)`?")
STEP_REF = re.compile(r"\bsteps?\s+\*{0,2}(\d+)(?:\s*(?:to|-|–)\s*(\d+))?", re.I)
IDENT = re.compile(r"`([A-Za-z_][\w.-]{2,})`")
# Branch names every issue mentions; they link nothing.
COMMON = {"main", "master", "develop", "HEAD"}
DOC_WORDS = re.compile(r"\b(README|CHANGELOG|CLAUDE\.md|HARDWARE_VALIDATION|CONTRIBUTING)\b")


def gh(path: str) -> object:
    out = subprocess.run(
        ["gh", "api", "--paginate", path], check=True, capture_output=True, text=True
    ).stdout
    # --paginate concatenates JSON arrays as "][": join them.
    out = out.replace("]\n[", ",").replace("][", ",")
    return json.loads(out)


def sentences_matching(body: str, pattern: re.Pattern[str]) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", body)
    return [p.strip()[:200] for p in parts if pattern.search(p)]


def main() -> int:
    if len(sys.argv) < 2 or "/" not in sys.argv[1]:
        print(__doc__, file=sys.stderr)
        return 2
    repo = sys.argv[1]
    as_json = "--json" in sys.argv

    issues = [
        i
        for i in gh(f"repos/{repo}/issues?state=open&per_page=100")
        if "pull_request" not in i and i["title"].lower().startswith("prompt:")
    ]
    open_prs = gh(f"repos/{repo}/pulls?state=open&per_page=100")
    in_progress: dict[int, list[int]] = {}
    for pr in open_prs:
        for n in re.findall(r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)", pr["body"] or "", re.I):
            in_progress.setdefault(int(n), []).append(pr["number"])

    state_cache: dict[int, str] = {}

    def state_of(n: int) -> str:
        if n not in state_cache:
            try:
                item = gh(f"repos/{repo}/issues/{n}")
            except subprocess.CalledProcessError:
                state_cache[n] = "unknown"
                return state_cache[n]
            kind = "PR" if "pull_request" in item else "issue"
            st = item["state"]
            if kind == "PR" and item["pull_request"].get("merged_at"):
                st = "merged"
            state_cache[n] = f"{kind} {st}"
        return state_cache[n]

    rows = []
    for i in sorted(issues, key=lambda x: x["number"]):
        body = i["body"] or ""
        header = {}
        for key, rx in HEADER.items():
            m = rx.search(body)
            header[key] = m.group(1).strip() if m else None
        refs = sorted({int(n) for n in ISSUE_REF.findall(body)} - {i["number"]})
        steps = set()
        for a, b in STEP_REF.findall(body):
            lo, hi = int(a), int(b or a)
            steps.update(range(lo, hi + 1) if hi - lo < 20 else [lo, hi])
        rows.append(
            {
                "number": i["number"],
                "title": i["title"],
                "labels": [lb["name"] for lb in i["labels"]],
                "header": header,
                "has_contract_header": header["runs_after"] is not None
                and header["needs_owner"] is not None,
                "open_pr": in_progress.get(i["number"], []),
                "mentions": {f"#{n}": state_of(n) for n in refs},
                "owner_gate_hints": sentences_matching(body, OWNER_GATE),
                "publish_hints": sentences_matching(body, PUBLISH),
                "files": sorted(set(FILE_REF.findall(body)) | set(DOC_WORDS.findall(body))),
                "steps_mentioned": sorted(steps),
                "identifiers": sorted(
                    {t for t in IDENT.findall(body) if not FILE_REF.fullmatch(t) and t not in COMMON}
                ),
            }
        )

    # Pairwise overlaps in files and numbered steps: where parallel branches would collide.
    overlaps = []
    for a in range(len(rows)):
        for b in range(a + 1, len(rows)):
            fa, fb = set(rows[a]["files"]), set(rows[b]["files"])
            common = sorted(fa & fb)
            ids = sorted(set(rows[a]["identifiers"]) & set(rows[b]["identifiers"]))
            if common or ids:
                overlaps.append(
                    {"issues": [rows[a]["number"], rows[b]["number"]], "files": common, "identifiers": ids}
                )

    if as_json:
        print(json.dumps({"repo": repo, "prompts": rows, "overlaps": overlaps}, indent=2))
        return 0

    print(f"{repo}: {len(rows)} open prompt issue(s), {len(open_prs)} open PR(s)\n")
    for r in rows:
        print(f"#{r['number']} {r['title']}")
        print(f"  labels: {', '.join(r['labels']) or '-'}")
        for k, v in r["header"].items():
            print(f"  {k}: {v or '(not stated)'}")
        if not r["has_contract_header"]:
            print("  !! no Runs after / Needs the owner header: plan from the prose, read it in full")
        if r["open_pr"]:
            print(f"  !! already has open PR(s): {r['open_pr']}")
        print(f"  mentions: {r['mentions'] or '-'}")
        for s in r["owner_gate_hints"]:
            print(f"  owner? {s}")
        for s in r["publish_hints"]:
            print(f"  publish? {s}")
        print(f"  files: {', '.join(r['files']) or '-'}")
        print(f"  steps mentioned: {r['steps_mentioned'] or '-'}\n")
    # Shared identifiers are how a dependency hides: #30 "rests on H-FIXIT" and #31
    # "if fixit is missing ... the fix-a-device issue needs rethinking" never cite
    # each other by number, but both name `H-FIXIT`.
    print("Overlaps between issues (files: merge conflicts; identifiers: possible dependency):")
    for o in overlaps:
        print(f"  #{o['issues'][0]} & #{o['issues'][1]}")
        print(f"    files: {', '.join(o['files']) or '-'}")
        print(f"    identifiers: {', '.join(o['identifiers']) or '-'}")
    if not overlaps:
        print("  none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
