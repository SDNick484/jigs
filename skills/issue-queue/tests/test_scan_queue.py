"""scan_queue.py: decoding paginated API output, and the patterns the plan relies on."""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
