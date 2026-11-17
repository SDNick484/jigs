"""prepush_check.py: what a worker's branch changed, against what it was allowed and expected to."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prepush_check.py"
spec = importlib.util.spec_from_file_location("prepush_check", SCRIPT)
prepush_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepush_check)

GOOD_BODY = "Closes #12\n\n## Decisions\n- none\n\n## Deviations\nnone\n\n## Unverified\nnothing\n"


def git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false", *args],
        cwd=cwd, check=True, capture_output=True,
    )


class Repo(unittest.TestCase):
    """A repository with one commit on `main`, and a branch `work` checked out on top of it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        git(self.root, "init", "-q", "-b", "main")
        self.write("README.md", "# x\n")
        self.write("shared/remote.py", "A = 1\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "first")
        git(self.root, "checkout", "-q", "-b", "work")
        (self.root / ".git" / "info" / "exclude").write_text(".queue/\n")

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def commit(self, files: dict[str, str]) -> None:
        for rel, text in files.items():
            self.write(rel, text)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "work")

    def run_check(self, *args: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = prepush_check.main([str(self.root), "--base", "main", "--issue", "12", *args])
        return code, out.getvalue()

    def test_a_branch_inside_its_scope_with_a_complete_body_passes(self):
        self.commit({"app.py": "x = 1\n", "CHANGELOG.md": "- x\n"})
        self.write(".queue/PR_BODY.md", GOOD_BODY)
        code, out = self.run_check("--forbid", "shared/*", "--require", "CHANGELOG.md")
        self.assertEqual(code, 0, out)
        self.assertTrue(out.startswith("OK"), out)
        self.assertIn("app.py", out)

    def test_a_forbidden_file_fails_and_is_named(self):
        self.commit({"shared/remote.py": "A = 2\n"})
        self.write(".queue/PR_BODY.md", GOOD_BODY)
        code, out = self.run_check("--forbid", "shared/*")
        self.assertEqual(code, 1)
        self.assertIn("FAIL", out.splitlines()[0])
        self.assertIn("shared/remote.py", out)

    def test_a_file_that_belongs_to_another_lane_fails(self):
        self.commit({"app.py": "x = 1\n", "routes.py": "r = 1\n"})
        self.write(".queue/PR_BODY.md", GOOD_BODY)
        code, out = self.run_check("--other-lane", "routes.py")
        self.assertEqual(code, 1)
        self.assertIn("another lane", out)
        self.assertIn("routes.py", out)

    def test_a_required_file_missing_from_the_diff_fails(self):
        self.commit({"app.py": "x = 1\n"})
        self.write(".queue/PR_BODY.md", GOOD_BODY)
        code, out = self.run_check("--require", "CHANGELOG.md", "--require", "tests/*")
        self.assertEqual(code, 1)
        self.assertIn("CHANGELOG.md", out)
        self.assertIn("tests/*", out)

    def test_a_required_glob_is_met_by_any_matching_file(self):
        self.commit({"app.py": "x = 1\n", "tests/test_app.py": "pass\n"})
        self.write(".queue/PR_BODY.md", GOOD_BODY)
        code, out = self.run_check("--require", "tests/*")
        self.assertEqual(code, 0, out)

    def test_no_commit_on_the_branch_fails(self):
        self.write(".queue/PR_BODY.md", GOOD_BODY)
        code, out = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn("no commits", out)

    def test_uncommitted_work_fails(self):
        self.commit({"app.py": "x = 1\n"})
        self.write("app.py", "x = 2\n")
        self.write(".queue/PR_BODY.md", GOOD_BODY)
        code, out = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn("uncommitted", out)

    def test_the_body_must_exist_and_open_with_closes_for_this_issue(self):
        self.commit({"app.py": "x = 1\n"})
        code, out = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn("PR_BODY.md", out)
        self.write(".queue/PR_BODY.md", GOOD_BODY.replace("#12", "#13"))
        code, out = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn("Closes #12", out)
        self.write(".queue/PR_BODY.md", GOOD_BODY.replace("#12", "#123"))
        self.assertEqual(self.run_check()[0], 1)

    def test_a_body_that_never_mentions_deviations_is_flagged_to_read_not_failed(self):
        self.commit({"app.py": "x = 1\n"})
        self.write(".queue/PR_BODY.md", "Closes #12\n\nAdded x. Decisions: none. Unverified: none.\n")
        code, out = self.run_check()
        self.assertEqual(code, 0, out)
        self.assertIn("read:", out)
        self.assertIn("deviat", out)

    def test_the_base_is_the_fork_point_so_later_commits_on_main_are_not_counted(self):
        self.commit({"app.py": "x = 1\n"})
        git(self.root, "checkout", "-q", "main")
        self.write("other.py", "o = 1\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "later on main")
        git(self.root, "checkout", "-q", "work")
        self.write(".queue/PR_BODY.md", GOOD_BODY)
        code, out = self.run_check("--other-lane", "other.py")
        self.assertEqual(code, 0, out)


if __name__ == "__main__":
    unittest.main()
