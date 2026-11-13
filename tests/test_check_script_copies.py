"""The copy check (.github/scripts/check_script_copies.py): identical copies pass, differing ones fail."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / ".github" / "scripts" / "check_script_copies.py"


class CopyCheck(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "skills").mkdir()

    def add(self, rel: str, text: str) -> None:
        p = self.root / "skills" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def check(self, root: Path | None = None):
        return subprocess.run([sys.executable, str(SCRIPT), "--root", str(root or self.root)],
                              capture_output=True, text=True)

    def test_no_skills_yet_passes(self):
        p = self.check()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("checked 0 shared", p.stdout)

    def test_identical_copies_pass(self):
        self.add("one/scripts/ci_state.py", "print(1)\n")
        self.add("two/scripts/ci_state.py", "print(1)\n")
        p = self.check()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("checked 1 shared", p.stdout)

    def test_differing_copies_fail_and_name_both(self):
        self.add("one/scripts/ci_state.py", "print(1)\n")
        self.add("two/scripts/ci_state.py", "print(2)\n")
        self.add("three/scripts/ci_state.py", "print(1)\n")
        p = self.check()
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        for skill in ("one", "two", "three"):
            self.assertIn(f"skills/{skill}/scripts/ci_state.py", p.stdout)

    def test_a_whitespace_only_difference_still_fails(self):
        """Byte for byte: a 'harmless' edit is how copies start to drift."""
        self.add("one/scripts/a.sh", "echo hi\n")
        self.add("two/scripts/a.sh", "echo hi \n")
        self.assertEqual(self.check().returncode, 1)

    def test_a_script_in_one_skill_only_is_not_compared(self):
        self.add("one/scripts/only_here.py", "print(1)\n")
        self.add("two/scripts/other.py", "print(2)\n")
        p = self.check()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("checked 0 shared", p.stdout)

    def test_same_name_in_different_subdirectories_is_not_the_same_script(self):
        self.add("one/scripts/lib/util.py", "a = 1\n")
        self.add("two/scripts/util.py", "a = 2\n")
        self.assertEqual(self.check().returncode, 0)

    def test_files_outside_scripts_are_ignored(self):
        self.add("one/SKILL.md", "one\n")
        self.add("two/SKILL.md", "two\n")
        self.add("one/references/notes.md", "one\n")
        self.add("two/references/notes.md", "two\n")
        self.assertEqual(self.check().returncode, 0)

    def test_bytecode_caches_are_ignored(self):
        self.add("one/scripts/__pycache__/a.pyc", "x")
        self.add("two/scripts/__pycache__/a.pyc", "y")
        self.assertEqual(self.check().returncode, 0)

    def test_a_missing_skills_directory_is_a_setup_error(self):
        with tempfile.TemporaryDirectory() as empty:
            self.assertEqual(self.check(Path(empty)).returncode, 2)

    def test_this_repository_passes(self):
        p = self.check(Path(__file__).resolve().parent.parent)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)


if __name__ == "__main__":
    unittest.main()
