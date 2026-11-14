"""scan_queue.py: decoding paginated API output, and the patterns the plan relies on."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "scan_queue.py"
spec = importlib.util.spec_from_file_location("scan_queue", SCRIPT)
scan_queue = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan_queue)


class ParsePages(unittest.TestCase):
    def test_single_object(self):
        self.assertEqual(scan_queue.parse_pages('{"number": 3}\n'), {"number": 3})

    def test_single_page(self):
        self.assertEqual(scan_queue.parse_pages('[{"n": 1}, {"n": 2}]'), [{"n": 1}, {"n": 2}])

    def test_pages_back_to_back_and_newline_separated(self):
        self.assertEqual(scan_queue.parse_pages('[{"n": 1}][{"n": 2}]\n[{"n": 3}]'), [{"n": 1}, {"n": 2}, {"n": 3}])

    def test_empty_pages(self):
        self.assertEqual(scan_queue.parse_pages("[][]"), [])

    def test_a_body_containing_the_page_separator_is_left_alone(self):
        # The old join replaced "][" everywhere, which turned this body into "- [x,docs](...)".
        body = "- [x][docs](https://example.com) and a[0][1]\n]\n[ on two lines"
        pages = json.dumps([{"body": body}]) + json.dumps([{"body": "second"}])
        self.assertEqual(scan_queue.parse_pages(pages), [{"body": body}, {"body": "second"}])

    def test_mixed_documents_are_refused(self):
        with self.assertRaises(ValueError):
            scan_queue.parse_pages('[1]{"a": 2}')


class Patterns(unittest.TestCase):
    def test_owner_gate_needs_more_than_the_word_owner(self):
        self.assertIsNone(scan_queue.OWNER_GATE.search("the owner's devices run older firmware"))
        self.assertIsNotNone(scan_queue.OWNER_GATE.search("It needs the owner present for the physical steps"))
        self.assertIsNotNone(scan_queue.OWNER_GATE.search("Before starting, check with the owner"))

    def test_issue_refs_skip_paths_and_words(self):
        self.assertEqual(scan_queue.ISSUE_REF.findall("after #31, see other/repo#16 and abc#7"), ["31"])

    def test_header_lines(self):
        body = "**Suggested model:** Sonnet. small\n**Runs after:** #31 (why)\n**Needs the owner:** no\n"
        self.assertEqual(scan_queue.HEADER["runs_after"].search(body).group(1).strip(), "#31 (why)")
        self.assertEqual(scan_queue.HEADER["needs_owner"].search(body).group(1).strip(), "no")


class FakeGh:
    """Answers scan_queue.gh(path). `tree` is the set of paths on the default branch, or None
    for a repository with no commits."""

    def __init__(self, issues, tree=frozenset()):
        self.issues, self.tree = issues, tree

    def absent(self, code: int):
        return subprocess.CalledProcessError(1, "gh", stderr=f"gh: Not Found (HTTP {code})")

    def __call__(self, path: str):
        if path == "repos/owner/repo":
            return {"default_branch": "main"}
        if path == "repos/owner/repo/branches/main":
            if self.tree is None:
                raise self.absent(404)
            return {"name": "main"}
        if "/contents/" in path:
            if path.split("/contents/")[1].split("?")[0] not in self.tree:
                raise self.absent(404)
            return {"type": "file"}
        if "/issues?" in path:
            return self.issues
        if "/pulls?" in path:
            return []
        raise self.absent(404)


def prompt(number: int, body: str) -> dict:
    return {"number": number, "title": f"Prompt: task {number}", "body": body, "state": "open", "labels": []}


def scan(fake: FakeGh, *flags: str) -> str:
    out = io.StringIO()
    with mock.patch.object(scan_queue, "gh", fake), mock.patch.object(sys, "argv", ["scan_queue.py", "owner/repo", *flags]):
        with contextlib.redirect_stdout(out):
            scan_queue.main()
    return out.getvalue()


PLAN = "docs/plans/core.md"
BODY = f"Implement Task 2 of `{PLAN}`. Creates `guards.py` and `tests/test_guards.py`; adds a README row."


class DefaultBranch(unittest.TestCase):
    def test_empty_repository_is_reported_and_every_cited_doc_is_missing(self):
        out = scan(FakeGh([prompt(2, BODY)], tree=None))
        self.assertIn("default branch: none", out)
        self.assertIn(f"cited but not on main: {PLAN}", out)

    def test_a_cited_plan_that_is_not_on_the_branch_is_flagged(self):
        out = scan(FakeGh([prompt(2, BODY)], tree={"README.md"}))
        self.assertIn("default branch: main", out)
        self.assertIn(f"cited but not on main: {PLAN}", out)

    def test_a_seeded_repository_is_quiet(self):
        out = scan(FakeGh([prompt(2, BODY)], tree={PLAN}))
        self.assertNotIn("cited but not on", out)

    def test_files_the_issue_will_create_are_not_treated_as_cited_documents(self):
        data = json.loads(scan(FakeGh([prompt(2, BODY)], tree={PLAN}), "--json"))
        self.assertEqual(data["default_branch"], {"name": "main", "exists": True})
        self.assertEqual(data["prompts"][0]["docs_not_on_default_branch"], [])
        self.assertIn("guards.py", data["prompts"][0]["files"])

    def test_a_failure_that_is_not_an_answer_is_raised(self):
        def broken(path: str):
            if path == "repos/owner/repo":
                return {"default_branch": "main"}
            raise subprocess.CalledProcessError(1, "gh", stderr="gh: connection refused")
        with self.assertRaises(subprocess.CalledProcessError):
            scan(broken)

    def test_builds_on_header_is_read(self):
        body = "**Runs after:** none\n**Builds on:** #1 (uses its schema)\n**Needs the owner:** no"
        self.assertEqual(scan_queue.HEADER["builds_on"].search(body).group(1).strip(), "#1 (uses its schema)")


if __name__ == "__main__":
    unittest.main()
