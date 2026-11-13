#!/usr/bin/env python3
"""Map a repo's assumption registry onto its hardware checklist, and say what a recorded run left stale.

A repo that keeps device behavior it has not seen on hardware as named assumptions states each one
in several places: the registry (a Python file of `Assumption(...)` records), the checklist that
confirms them step by step, a status table in the README, and prose around all three. A hardware
run changes the registry, and every other place has to follow in the same change. This script reads
them without importing the package (the registry is parsed, not executed), so it needs nothing
installed and works on any commit.

Two uses:

  before a run   assumption_map.py --steps 10-13
                 which assumptions those steps confirm, and what each one's status is now

  after editing  assumption_map.py --base origin/main
                 what changed in the registry since BASE, every line that still cites a changed
                 assumption but was not touched, every untouched line whose wording says "not
                 checked yet", tables that disagree with the registry, and checklist steps that
                 were renumbered or removed

Usage: assumption_map.py [--root DIR] [--registry FILE] [--checklist FILE] [--steps LIST]
                         [--base REF] [--record NAME] [--default-status S] [--json]

Exit status: 0 nothing wrong, 1 something must be fixed (a table disagrees with the registry, a
step was renumbered or removed, an assumption was deleted), 2 usage or setup error.
The "re-read" lists never fail the run: only a reader can tell whether a sentence is stale.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

UNRESOLVED = "…"  # stands in for any part of a string the parser could not evaluate
STEP_HEADING = re.compile(r"^(#{2,4})\s+(?:Step\s+)?(\d+[a-z]?)[.:)]\s+(.+?)\s*$", re.I)
ANY_HEADING = re.compile(r"^(#{1,6})\s+\S")
FENCE = re.compile(r"^\s*(```|~~~)")
# Wording that claims something has not been checked. A line with one of these that the run did not
# touch is worth a second look; most will still be true.
NOT_YET = re.compile(
    r"simulator[- ]only|not yet|untried|unchecked|nothing is recorded|"
    r"(?:has|have|is|are|was|were)(?: not|n't) (?:been )?(?:run|checked|verified|tested|confirmed|tried|recorded)|"
    r"still to do|to be (?:checked|confirmed|verified)",
    re.I,
)
TEXT_SUFFIXES = {".md", ".rst", ".txt", ".py"}
SKIP_PARTS = {".git", ".venv", "venv", "node_modules", "__pycache__", "build", "dist", ".tox"}


class SetupError(Exception):
    """The repo does not have what this script reads; the message says what is missing."""


@dataclass
class Assumption:
    id: str
    status: str
    confidence: str
    claim: str
    note: str
    line: int


@dataclass
class Step:
    number: str
    title: str
    line: int
    end: int  # last line of the step's section, inclusive
    ids: list[str] = field(default_factory=list)


# --- the registry ---------------------------------------------------------------------------------


def _text(node: ast.AST | None, consts: dict[str, str]) -> str:
    """A string expression's value, as far as it can be known without running it."""
    if node is None:
        return ""
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else str(node.value)
    if isinstance(node, ast.Name):
        return consts.get(node.id, UNRESOLVED)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _text(node.left, consts) + _text(node.right, consts)
    if isinstance(node, ast.JoinedStr):
        return "".join(
            _text(v.value, consts) if isinstance(v, ast.FormattedValue) else _text(v, consts) for v in node.values
        )
    return UNRESOLVED


def _module_strings(tree: ast.Module) -> dict[str, str]:
    """Module-level NAME = "..." constants, which notes are often built from (one per hardware run)."""
    consts: dict[str, str] = {}
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            target, value = stmt.targets[0].id, stmt.value
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.value is not None:
            target, value = stmt.target.id, stmt.value
        else:
            continue
        text = _text(value, consts)
        if UNRESOLVED not in text and isinstance(value, (ast.Constant, ast.BinOp, ast.JoinedStr, ast.Name)):
            consts[target] = text
    return consts


FIELDS = ("id", "claim", "source", "confidence", "status", "note")


def parse_registry(source: str, record: str, default_status: str) -> list[Assumption]:
    """Every `record(...)` call in the source, in order. Positional arguments follow FIELDS."""
    tree = ast.parse(source)
    consts = _module_strings(tree)
    found: list[Assumption] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
        if name != record:
            continue
        values = dict(zip(FIELDS, node.args))
        values.update({kw.arg: kw.value for kw in node.keywords if kw.arg})
        ident = values.get("id")
        if not (isinstance(ident, ast.Constant) and isinstance(ident.value, str)):
            continue  # a helper that builds records from variables; nothing to map
        found.append(
            Assumption(
                id=ident.value,
                status=_text(values.get("status"), consts) or default_status,
                confidence=_text(values.get("confidence"), consts),
                claim=_text(values.get("claim"), consts),
                note=_text(values.get("note"), consts),
                line=node.lineno,
            )
        )
    found.sort(key=lambda a: a.line)
    return found


def default_status_from(source: str, record: str) -> str | None:
    """The record class's own default for `status`, if this file defines the class."""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ClassDef) and node.name == record:
            for stmt in node.body:
                if (
                    isinstance(stmt, ast.AnnAssign)
                    and isinstance(stmt.target, ast.Name)
                    and stmt.target.id == "status"
                    and isinstance(stmt.value, ast.Constant)
                    and isinstance(stmt.value.value, str)
                ):
                    return stmt.value.value
    return None


def status_words(sources: list[str]) -> set[str]:
    """Every `Literal["a-b", ...]` value in the sources: the status vocabulary, when it is declared."""
    words: set[str] = set()
    for source in sources:
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Subscript) and getattr(node.value, "id", getattr(node.value, "attr", "")) == "Literal":
                inner = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
                words |= {e.value for e in inner if isinstance(e, ast.Constant) and isinstance(e.value, str)}
    return {w for w in words if "-" in w}


# --- the checklist --------------------------------------------------------------------------------


def id_pattern(ids: list[str]) -> re.Pattern[str] | None:
    if not ids:
        return None
    alternatives = "|".join(re.escape(i) for i in sorted(ids, key=len, reverse=True))
    return re.compile(rf"(?<![A-Za-z0-9-])(?:{alternatives})(?![A-Za-z0-9]|-[A-Za-z0-9])")


def parse_steps(text: str, ids: list[str]) -> list[Step]:
    """Numbered headings ("## 3. Title", "### Step 8a: Title") and the ids cited under each."""
    lines = text.splitlines()
    steps: list[Step] = []
    levels: dict[int, int] = {}  # index in steps -> heading level, for the steps still open
    in_fence = False
    for n, line in enumerate(lines, 1):
        if FENCE.match(line):
            in_fence = not in_fence
        if in_fence:
            continue
        heading = ANY_HEADING.match(line)
        if not heading:
            continue
        m = STEP_HEADING.match(line)
        # A step ends at the next step, or at any heading that is not below it.
        for index in [i for i, level in levels.items() if m or len(heading.group(1)) <= level]:
            steps[index].end = n - 1
            del levels[index]
        if m:
            steps.append(Step(m.group(2).lower(), m.group(3), n, 0))
            levels[len(steps) - 1] = len(m.group(1))
    for index in levels:
        steps[index].end = len(lines)
    pattern = id_pattern(ids)
    for step in steps:
        seen: list[str] = []
        for line in lines[step.line - 1 : step.end]:
            for hit in pattern.findall(line) if pattern else []:
                if hit not in seen:
                    seen.append(hit)
        step.ids = seen
    return steps


def wanted_steps(spec: str) -> set[str] | None:
    """"10-13,8a" -> {"10","11","12","13","8a"}. None means every step."""
    if not spec:
        return None
    wanted: set[str] = set()
    for part in (p.strip().lower() for p in spec.split(",") if p.strip()):
        m = re.fullmatch(r"(\d+)\s*(?:-|to|\.\.)\s*(\d+)", part)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            if hi < lo:
                raise SetupError(f"--steps: {part!r} runs backwards")
            wanted |= {str(i) for i in range(lo, hi + 1)}
        elif re.fullmatch(r"\d+[a-z]?", part):
            wanted.add(part)
        else:
            raise SetupError(f"--steps: can't read {part!r} (use 3, 8a, 10-13)")
    return wanted


def renumbering(base: list[Step], head: list[Step]) -> list[str]:
    """Problems if a step that existed at base no longer has its number. New steps are fine."""
    problems: list[str] = []
    head_numbers = [s.number for s in head]
    head_titles = {s.title: s.number for s in head}
    for step in base:
        if step.number not in head_numbers:
            moved = head_titles.get(step.title)
            problems.append(
                f"step {step.number} ({step.title!r}) "
                + (f"is now step {moved}: renumbered" if moved else "is gone: removed or renumbered")
            )
        elif head_titles.get(step.title, step.number) != step.number:
            problems.append(f"step {step.number} ({step.title!r}) is now step {head_titles[step.title]}: renumbered")
    kept = [n for n in head_numbers if n in {s.number for s in base}]
    if kept != [s.number for s in base if s.number in head_numbers] and not problems:
        problems.append("the steps that existed before are in a different order")
    return problems


# --- docs -----------------------------------------------------------------------------------------


def table_mismatches(rel: str, text: str, by_id: dict[str, Assumption], vocabulary: set[str]) -> list[str]:
    """Table rows that give an assumption a status other than the registry's."""
    problems: list[str] = []
    for n, line in enumerate(text.splitlines(), 1):
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip().strip("*`_ ") for c in line.strip().strip("|").split("|")]
        if not cells or cells[0] not in by_id:
            continue
        stated = [c for c in cells[1:] if c in vocabulary]
        want = by_id[cells[0]].status
        if stated and want not in stated:
            problems.append(f"{rel}:{n}: table says {cells[0]} is {stated[0]}; the registry says {want}")
    return problems


# --- git ------------------------------------------------------------------------------------------


def git(root: Path, *args: str) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args], check=True, capture_output=True, text=True, errors="replace"
        ).stdout
    except FileNotFoundError as e:
        raise SetupError("git is not installed") from e
    except subprocess.CalledProcessError as e:
        raise SetupError(f"git {' '.join(args[:2])} failed: {e.stderr.strip().splitlines()[-1:] or e}") from e


def at_base(root: Path, base: str, rel: str) -> str | None:
    try:
        return git(root, "show", f"{base}:{rel}")
    except SetupError:
        return None  # the file did not exist at base


def touched_lines(root: Path, base: str, rel: str) -> set[int] | None:
    """Line numbers (in the working copy) added or changed since base. None: the whole file is new."""
    if at_base(root, base, rel) is None:
        return None
    lines: set[int] = set()
    for hunk in re.finditer(r"^@@ -\S+ \+(\d+)(?:,(\d+))? @@", git(root, "diff", "-U0", base, "--", rel), re.M):
        start, count = int(hunk.group(1)), int(hunk.group(2) or 1)
        lines |= set(range(start, start + count))
    return lines


def module_docstring_lines(source: str) -> set[int]:
    """The lines of a Python file's opening docstring: the one place in code that reads like a document."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    first = tree.body[0] if tree.body else None
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
        return set(range(first.lineno, (first.end_lineno or first.lineno) + 1))
    return set()


def text_files(root: Path) -> list[str]:
    try:
        listed = git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard").split("\0")
    except SetupError:
        listed = [p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()]
    keep = []
    for rel in listed:
        parts = Path(rel).parts
        if rel and Path(rel).suffix.lower() in TEXT_SUFFIXES and not SKIP_PARTS & set(parts) and (root / rel).is_file():
            keep.append(rel)
    return sorted(keep)


def find_one(root: Path, given: str | None, names: tuple[str, ...], what: str) -> str:
    if given:
        if not (root / given).is_file():
            raise SetupError(f"{what}: {given} is not a file under {root}")
        return Path(given).as_posix()
    hits = [
        rel
        for rel in text_files(root)
        if Path(rel).name.lower() in names and not {"tests", "test"} & set(Path(rel).parts)
    ]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise SetupError(
            f"{what}: no file named {' or '.join(names)} under {root}. The repo's CLAUDE.md should say "
            f"where it is; pass it with --{what}."
        )
    raise SetupError(f"{what}: more than one candidate ({', '.join(hits)}); pass one with --{what}")


# --- the report -----------------------------------------------------------------------------------


def build(args: argparse.Namespace) -> dict:
    root = Path(args.root).resolve()
    if not root.is_dir():
        raise SetupError(f"{args.root} is not a directory")
    registry_rel = find_one(root, args.registry, ("assumptions.py",), "registry")
    checklist_rel = find_one(root, args.checklist, ("hardware_validation.md",), "checklist")
    registry_src = (root / registry_rel).read_text(encoding="utf-8")

    neighbours = [registry_src] + [
        p.read_text(encoding="utf-8", errors="replace") for p in sorted((root / registry_rel).parent.glob("*.py"))
        if p.name != Path(registry_rel).name and f"class {args.record}" in p.read_text(encoding="utf-8", errors="replace")
    ]
    default = args.default_status or next(
        (d for d in (default_status_from(s, args.record) for s in neighbours) if d), "simulator-only"
    )
    try:
        assumptions = parse_registry(registry_src, args.record, default)
    except SyntaxError as e:
        raise SetupError(f"{registry_rel} does not parse: {e.msg} (line {e.lineno})") from e
    if not assumptions:
        raise SetupError(f"{registry_rel} has no {args.record}(...) records; pass --record if they have another name")
    by_id = {a.id: a for a in assumptions}
    ids = list(by_id)

    checklist_text = (root / checklist_rel).read_text(encoding="utf-8")
    steps = parse_steps(checklist_text, ids)
    if not steps:
        raise SetupError(f'{checklist_rel} has no numbered step headings ("## 3. Title")')
    wanted = wanted_steps(args.steps or "")
    if wanted is not None:
        missing = sorted(wanted - {s.number for s in steps})
        if missing:
            raise SetupError(f"{checklist_rel} has no step {', '.join(missing)}")

    must_fix: list[str] = []
    in_a_step = {i for s in steps for i in s.ids}
    in_view = {i for s in steps for i in s.ids if wanted is None or s.number in wanted}

    vocabulary = status_words(neighbours) | {a.status for a in assumptions} | {default}
    files = text_files(root)
    for rel in files:
        if rel.endswith(".md"):
            must_fix += table_mismatches(rel, (root / rel).read_text(encoding="utf-8", errors="replace"), by_id, vocabulary)

    report: dict = {
        "registry": registry_rel,
        "checklist": checklist_rel,
        "unchecked_status": default,
        "counts": {s: sum(a.status == s for a in assumptions) for s in sorted({a.status for a in assumptions})},
        "steps": [
            {"number": s.number, "title": s.title, "line": s.line,
             "assumptions": [{"id": i, "status": by_id[i].status, "confidence": by_id[i].confidence} for i in s.ids]}
            for s in steps if wanted is None or s.number in wanted
        ],
        # Unchecked assumptions the chosen steps do not name. Something seen today can still settle one of
        # them (a capture taken in one step is the replay an earlier step was waiting for), so keep them in view.
        "unchecked_elsewhere": [
            {"id": a.id, "confidence": a.confidence,
             "steps": [s.number for s in steps if a.id in s.ids]}
            for a in assumptions if a.status == default and a.id not in in_view
        ],
        "in_no_step": [a.id for a in assumptions if a.id not in in_a_step],
    }

    if args.base:
        base_registry = at_base(root, args.base, registry_rel)
        if base_registry is None:
            raise SetupError(f"{registry_rel} does not exist at {args.base}")
        before = {a.id: a for a in parse_registry(base_registry, args.record, default)}
        changed = []
        for a in assumptions:
            old = before.get(a.id)
            what = (
                ["new"] if old is None
                else [f for f in ("status", "claim", "note", "confidence") if getattr(old, f) != getattr(a, f)]
            )
            if what:
                changed.append({"id": a.id, "changed": what, "was": old.status if old else None, "now": a.status})
        removed = sorted(set(before) - set(by_id))
        if removed:
            must_fix.append(f"removed from the registry since {args.base}: {', '.join(removed)} (a checked assumption "
                            "is kept with its result, not deleted)")
        status_changed = [c["id"] for c in changed if "status" in c["changed"] or "new" in c["changed"]]
        # Code cites an assumption where it relies on it. That only needs a second look when the claim
        # itself moved (reworded, or found not to hold); a claim confirmed as written changes no code.
        code_matters = {
            c["id"] for c in changed
            if "claim" in c["changed"] or ("status" in c["changed"] and "contradict" in c["now"])
        }
        cite = id_pattern([c["id"] for c in changed])
        still_cites: list[str] = []
        wording: list[str] = []
        for rel in files:
            touched = touched_lines(root, args.base, rel)
            if touched is None:
                continue  # a new file was written for this run
            is_doc = not rel.endswith(".py")
            body = (root / rel).read_text(encoding="utf-8", errors="replace")
            docstring = set() if is_doc else module_docstring_lines(body)
            for n, line in enumerate(body.splitlines(), 1):
                if n in touched:
                    continue
                hits = sorted(set(cite.findall(line))) if cite else []
                row = line.strip().strip("|").split("|")[0].strip().strip("`* ")
                if rel != registry_rel and row not in by_id:
                    shown = hits if is_doc else [h for h in hits if h in code_matters]
                    if shown:
                        still_cites.append(f"{rel}:{n}: cites {', '.join(shown)}")
                if NOT_YET.search(line) and (is_doc or n in docstring or hits):
                    if row in by_id and row not in status_changed:
                        continue  # a table row for an assumption this run did not touch
                    wording.append(f"{rel}:{n}: {line.strip()[:110]}")
        base_checklist = at_base(root, args.base, checklist_rel)
        if base_checklist is not None:
            must_fix += [f"{checklist_rel}: {p}" for p in renumbering(parse_steps(base_checklist, ids), steps)]
        report["since"] = {
            "base": args.base,
            "changed": changed,
            "files_changed": sorted(f for f in git(root, "diff", "--name-only", args.base).splitlines() if f)
            + sorted(f"{f} (new)" for f in git(root, "ls-files", "--others", "--exclude-standard").splitlines() if f),
            "untouched_lines_citing_a_changed_assumption": still_cites,
            "untouched_lines_saying_not_checked_yet": wording,
        }
    report["must_fix"] = must_fix
    return report


def render(report: dict) -> str:
    out = [f"registry:  {report['registry']}", f"checklist: {report['checklist']}",
           "statuses:  " + ", ".join(f"{n} {s}" for s, n in report["counts"].items())
           + f"   (unchecked = {report['unchecked_status']})", ""]
    for step in report["steps"]:
        out.append(f"step {step['number']}  {step['title']}   (line {step['line']})")
        if not step["assumptions"]:
            out.append("    confirms no assumption (still record what happened)")
        for a in step["assumptions"]:
            mark = "  <- unchecked" if a["status"] == report["unchecked_status"] else ""
            out.append(f"    {a['id']:<24} {a['status']:<22} {a['confidence']}{mark}")
    if report["unchecked_elsewhere"]:
        out += ["", "also unchecked, outside these steps (did anything seen today bear on one?):"]
        out += [f"    {a['id']:<24} step {', '.join(a['steps']) or 'none'}" for a in report["unchecked_elsewhere"]]
    if report["in_no_step"]:
        out += ["", "cited under no step (no step confirms them): " + ", ".join(report["in_no_step"])]
    since = report.get("since")
    if since:
        out += ["", f"since {since['base']}:"]
        if not since["changed"]:
            out.append("    the registry has not changed")
        for c in since["changed"]:
            moved = f"{c['was']} -> {c['now']}" if "status" in c["changed"] else f"{c['now']} ({', '.join(c['changed'])} changed)"
            out.append(f"    {c['id']:<24} {moved}")
        out += ["", "files changed:"] + [f"    {f}" for f in since["files_changed"]]
        for key, title in (
            ("untouched_lines_citing_a_changed_assumption",
             "re-read: lines this run did not touch that cite a changed assumption"),
            ("untouched_lines_saying_not_checked_yet",
             're-read: lines this run did not touch that say "not checked yet"'),
        ):
            out += ["", f"{title} ({len(since[key])}):"] + [f"    {x}" for x in since[key]]
    out += ["", f"must fix ({len(report['must_fix'])}):"] + [f"    {x}" for x in report["must_fix"]]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", default=".", help="the repo (default: current directory)")
    ap.add_argument("--registry", help="path of the registry under the repo (default: the one assumptions.py)")
    ap.add_argument("--checklist", help="path of the checklist (default: the one HARDWARE_VALIDATION.md)")
    ap.add_argument("--steps", help="only these steps, e.g. 10-13 or 3,8a")
    ap.add_argument("--base", help="a git ref to compare with, e.g. origin/main: what the run changed and left stale")
    ap.add_argument("--record", default="Assumption", help="the record's class name (default: Assumption)")
    ap.add_argument("--default-status", help="status of a record that names none (default: the class's own default)")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    args = ap.parse_args(argv)
    try:
        report = build(args)
    except SetupError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2) if args.json else render(report))
    return 1 if report["must_fix"] else 0


if __name__ == "__main__":
    sys.exit(main())
