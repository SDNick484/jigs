"""assumption_map.py against small made-up repos (a registry, a checklist, a README table)."""
from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import assumption_map as am  # noqa: E402

REGISTRY = '''
    """Every device behavior relied on."""
    from .registry import Assumption

    _RUN_1 = "2026-01-02, tv-1 on firmware 1.2"
    SEEN = f"Seen {_RUN_1}: "

    ASSUMPTIONS = (
        Assumption("T-PORT", "The device listens on TCP 8000.", "vendor docs", "high",
                   status="hardware-verified", note=_RUN_1 + ": connected on 8000."),
        Assumption(
            "T-PUSH",
            "A change made elsewhere is pushed "
            "to every client.",
            "read in source",
            "medium",
        ),
        Assumption("T-PUSH-OFF", "Power off is pushed too.", "a guess", "low", note="Partial: " + helper()),
        Assumption("T-LIST", "GET /list answers JSON.", "vendor docs", "medium",
                   status="hardware-contradicted", note=SEEN + "it answers 404."),
    )
'''
RECORD = '''
    from dataclasses import dataclass
    from typing import Literal

    Status = Literal["simulator-only", "hardware-verified", "hardware-contradicted"]

    @dataclass(frozen=True)
    class Assumption:
        id: str
        claim: str
        source: str
        confidence: str
        status: Status = "simulator-only"
        note: str = ""
'''
CHECKLIST = '''
    # Hardware validation

    Everything here has been verified against the simulator only.

    ## Before you start

    Have the device in view.

    ## 1. Connect

    ```sh
    ## 9. not a heading, this is inside a code block
    tool doctor
    ```

    Confirms: **T-PORT**.

    ## 2. Pushes

    Confirms T-PUSH (item 1) and T-PUSH-OFF (item 2).

    ### Step 2a: Lists

    Confirms `T-LIST`.

    ## Which step confirms what

    | Assumption | Step |
    | --- | --- |
    | `T-PORT` | 1 |
'''
README = '''
    # Thing

    Not yet tried on hardware: pushes (`T-PUSH`).

    | Assumption | Confidence | Status |
    | --- | --- | --- |
    | `T-PORT` | high | hardware-verified |
    | `T-PUSH` | medium | simulator-only |
    | `T-PUSH-OFF` | low | simulator-only |
    | `T-LIST` | medium | hardware-contradicted |
'''
TEST_FILE = '''
    """Replays recorded captures.

    Nothing is recorded yet.
    """
    # ASSUMPTION T-PUSH
    not_yet = "not yet"  # code, not a document: never reported
'''


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip("\n"), encoding="utf-8")


def git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.com",
         "-c", "commit.gpgsign=false", *args],
        check=True, capture_output=True,
    )


class RepoCase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        write(self.root, "src/thing/assumptions.py", REGISTRY)
        write(self.root, "src/thing/registry.py", RECORD)
        write(self.root, "HARDWARE_VALIDATION.md", CHECKLIST)
        write(self.root, "README.md", README)
        write(self.root, "tests/test_recorded.py", TEST_FILE)
        git(self.root, "init", "-q")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "base")

    def run_map(self, *args: str) -> tuple[int, dict]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = am.main(["--root", str(self.root), "--json", *args])
        return code, json.loads(out.getvalue())

    def fails(self, *args: str) -> str:
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(am.main(["--root", str(self.root), *args]), 2)
        return err.getvalue()

    def edit(self, rel: str, old: str, new: str) -> None:
        path = self.root / rel
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new), encoding="utf-8")


class RegistryTests(RepoCase):
    def test_reads_statuses_without_importing_the_package(self):
        # registry.py's relative import and helper() could not run here; the file is parsed, not executed.
        code, report = self.run_map()
        self.assertEqual(code, 0)
        self.assertEqual(report["registry"], "src/thing/assumptions.py")
        self.assertEqual(report["counts"], {"hardware-contradicted": 1, "hardware-verified": 1, "simulator-only": 2})

    def test_default_status_comes_from_the_record_class(self):
        self.edit("src/thing/registry.py", 'status: Status = "simulator-only"', 'status: Status = "bench-only"')
        self.edit("src/thing/registry.py", '"simulator-only", ', '"bench-only", ')
        self.edit("README.md", "| `T-PUSH` | medium | simulator-only |", "| `T-PUSH` | medium | bench-only |")
        self.edit("README.md", "| `T-PUSH-OFF` | low | simulator-only |", "| `T-PUSH-OFF` | low | bench-only |")
        code, report = self.run_map()
        self.assertEqual((code, report["unchecked_status"]), (0, "bench-only"))
        self.assertEqual(report["counts"]["bench-only"], 2)

    def test_strings_built_from_constants_are_resolved_and_the_rest_is_marked(self):
        parsed = {a.id: a for a in am.parse_registry(
            textwrap.dedent(REGISTRY), "Assumption", "simulator-only")}
        self.assertEqual(parsed["T-PORT"].note, "2026-01-02, tv-1 on firmware 1.2: connected on 8000.")
        self.assertEqual(parsed["T-LIST"].note, "Seen 2026-01-02, tv-1 on firmware 1.2: it answers 404.")
        self.assertEqual(parsed["T-PUSH"].claim, "A change made elsewhere is pushed to every client.")
        self.assertEqual(parsed["T-PUSH-OFF"].note, "Partial: " + am.UNRESOLVED)

    def test_no_registry_is_a_setup_error_that_says_what_to_pass(self):
        (self.root / "src/thing/assumptions.py").unlink()
        self.assertIn("--registry", self.fails())

    def test_a_registry_under_another_name_can_be_passed(self):
        (self.root / "src/thing/assumptions.py").rename(self.root / "src/thing/claims.py")
        code, report = self.run_map("--registry", "src/thing/claims.py")
        self.assertEqual((code, report["registry"]), (0, "src/thing/claims.py"))


class StepTests(RepoCase):
    def test_steps_and_the_assumptions_under_each(self):
        _, report = self.run_map()
        got = {s["number"]: [a["id"] for a in s["assumptions"]] for s in report["steps"]}
        self.assertEqual(got, {"1": ["T-PORT"], "2": ["T-PUSH", "T-PUSH-OFF"], "2a": ["T-LIST"]})

    def test_an_id_that_starts_another_id_is_not_counted_twice(self):
        _, report = self.run_map("--steps", "2")
        self.assertEqual([a["id"] for a in report["steps"][0]["assumptions"]], ["T-PUSH", "T-PUSH-OFF"])

    def test_a_step_ends_at_the_next_heading_of_its_level(self):
        # The table under "Which step confirms what" names T-PORT; that is not part of step 2a.
        _, report = self.run_map("--steps", "2a")
        self.assertEqual([a["id"] for a in report["steps"][0]["assumptions"]], ["T-LIST"])

    def test_steps_filter_takes_ranges_and_suffixes(self):
        _, report = self.run_map("--steps", "1-2,2a")
        self.assertEqual([s["number"] for s in report["steps"]], ["1", "2", "2a"])
        self.assertEqual(am.wanted_steps("10 to 12, 8A"), {"10", "11", "12", "8a"})

    def test_asking_for_a_step_that_is_not_there_is_an_error(self):
        self.assertIn("no step 7", self.fails("--steps", "7"))
        self.assertIn("can't read", self.fails("--steps", "two"))

    def test_unchecked_assumptions_outside_the_chosen_steps_stay_in_view(self):
        _, report = self.run_map("--steps", "1")
        self.assertEqual(
            report["unchecked_elsewhere"],
            [{"id": "T-PUSH", "confidence": "medium", "steps": ["2"]},
             {"id": "T-PUSH-OFF", "confidence": "low", "steps": ["2"]}],
        )

    def test_an_assumption_no_step_confirms_is_listed_but_does_not_fail(self):
        self.edit("HARDWARE_VALIDATION.md", "Confirms `T-LIST`.", "Lists.")
        code, report = self.run_map()
        self.assertEqual((code, report["in_no_step"]), (0, ["T-LIST"]))


class TableTests(RepoCase):
    def test_a_table_that_disagrees_with_the_registry_must_be_fixed(self):
        self.edit("src/thing/assumptions.py", '"medium",\n    ),', '"medium",\n        status="hardware-verified", note="seen",\n    ),')
        code, report = self.run_map()
        self.assertEqual(code, 1)
        self.assertEqual(len(report["must_fix"]), 1)
        self.assertIn("README.md:8: table says T-PUSH is simulator-only; the registry says hardware-verified",
                      report["must_fix"][0])

    def test_a_table_without_a_status_column_is_left_alone(self):
        code, report = self.run_map()  # the checklist's own table has only a step column
        self.assertEqual((code, report["must_fix"]), (0, []))


class SinceBaseTests(RepoCase):
    def verify_push(self) -> None:
        self.edit("src/thing/assumptions.py", '"medium",\n    ),',
                  '"medium",\n        status="hardware-verified", note=_RUN_1 + ": seen.",\n    ),')

    def test_reports_what_changed_and_what_still_has_to_follow(self):
        self.verify_push()
        code, report = self.run_map("--base", "HEAD")
        since = report["since"]
        self.assertEqual(code, 1)  # the README table is behind
        self.assertEqual(since["changed"], [
            {"id": "T-PUSH", "changed": ["status", "note"], "was": "simulator-only", "now": "hardware-verified"}])
        self.assertEqual(since["files_changed"], ["src/thing/assumptions.py"])
        self.assertEqual(since["untouched_lines_citing_a_changed_assumption"], [
            "HARDWARE_VALIDATION.md:20: cites T-PUSH", "README.md:3: cites T-PUSH"])
        wording = since["untouched_lines_saying_not_checked_yet"]
        self.assertTrue(any(w.startswith("HARDWARE_VALIDATION.md:3:") for w in wording), wording)
        self.assertTrue(any(w.startswith("README.md:3:") for w in wording), wording)
        self.assertTrue(any(w.startswith("README.md:8:") for w in wording), wording)       # its own table row
        self.assertFalse(any(w.startswith("README.md:9:") for w in wording), wording)      # T-PUSH-OFF: untouched, true
        self.assertTrue(any(w.startswith("tests/test_recorded.py:3:") for w in wording), wording)
        self.assertFalse(any(w.startswith("tests/test_recorded.py:6:") for w in wording), wording)

    def test_lines_the_run_rewrote_drop_off_the_lists(self):
        self.verify_push()
        self.edit("README.md", "Not yet tried on hardware: pushes (`T-PUSH`).", "Pushes were seen on tv-1 (`T-PUSH`).")
        self.edit("README.md", "| `T-PUSH` | medium | simulator-only |", "| `T-PUSH` | medium | hardware-verified |")
        self.edit("tests/test_recorded.py", "Nothing is recorded yet.", "Recorded so far: tv-1.")
        code, report = self.run_map("--base", "HEAD")
        since = report["since"]
        self.assertEqual(code, 0)
        self.assertEqual(since["untouched_lines_citing_a_changed_assumption"], ["HARDWARE_VALIDATION.md:20: cites T-PUSH"])
        self.assertEqual([w.split(":")[0] for w in since["untouched_lines_saying_not_checked_yet"]],
                         ["HARDWARE_VALIDATION.md"])

    def test_code_that_cites_a_claim_is_listed_only_when_the_claim_moved(self):
        self.verify_push()
        _, report = self.run_map("--base", "HEAD")
        self.assertFalse(any("test_recorded.py:5" in x for x in report["since"]["untouched_lines_citing_a_changed_assumption"]))
        self.edit("src/thing/assumptions.py", "to every client.", "to every client, a second late.")
        _, report = self.run_map("--base", "HEAD")
        self.assertIn("tests/test_recorded.py:5: cites T-PUSH", report["since"]["untouched_lines_citing_a_changed_assumption"])

    def test_a_new_step_is_fine_and_a_renumbered_one_is_not(self):
        self.edit("HARDWARE_VALIDATION.md", "## Which step confirms what", "## 3. Sleep timer\n\nRecord it.\n\n## Which step confirms what")
        code, report = self.run_map("--base", "HEAD")
        self.assertEqual((code, report["must_fix"]), (0, []))
        self.edit("HARDWARE_VALIDATION.md", "## 2. Pushes", "## 3. Pushes")
        self.edit("HARDWARE_VALIDATION.md", "## 3. Sleep timer", "## 2. Sleep timer")
        code, report = self.run_map("--base", "HEAD")
        self.assertEqual(code, 1)
        self.assertEqual(report["must_fix"], ["HARDWARE_VALIDATION.md: step 2 ('Pushes') is now step 3: renumbered"])

    def test_a_removed_step_and_a_deleted_assumption_must_be_fixed(self):
        self.edit("HARDWARE_VALIDATION.md", "### Step 2a: Lists\n\nConfirms `T-LIST`.\n", "")
        self.edit("src/thing/assumptions.py",
                  '    Assumption("T-LIST", "GET /list answers JSON.", "vendor docs", "medium",\n'
                  '               status="hardware-contradicted", note=SEEN + "it answers 404."),\n', "")
        self.edit("README.md", "| `T-LIST` | medium | hardware-contradicted |\n", "")
        code, report = self.run_map("--base", "HEAD")
        self.assertEqual(code, 1)
        self.assertTrue(any("removed from the registry" in m and "T-LIST" in m for m in report["must_fix"]))
        self.assertTrue(any("step 2a ('Lists') is gone" in m for m in report["must_fix"]))

    def test_a_base_that_does_not_exist_is_a_setup_error(self):
        self.assertIn("does not exist at no-such-ref", self.fails("--base", "no-such-ref"))


class TextOutputTests(RepoCase):
    def test_text_report_marks_unchecked_and_says_when_a_step_confirms_nothing(self):
        self.edit("HARDWARE_VALIDATION.md", "## Which step confirms what", "## 3. Sleep timer\n\nRecord it.\n\n## Which step confirms what")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            am.main(["--root", str(self.root)])
        text = out.getvalue()
        self.assertRegex(text, r"T-PUSH\s+simulator-only\s+medium\s+<- unchecked")
        self.assertNotRegex(text, r"T-PORT.*unchecked")
        self.assertIn("confirms no assumption (still record what happened)", text)
        self.assertIn("must fix (0):", text)


if __name__ == "__main__":
    unittest.main()
