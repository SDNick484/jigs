"""sweep_status.py against small git repositories built in a temporary directory."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sweep_status.py"
spec = importlib.util.spec_from_file_location("sweep_status", SCRIPT)
sweep_status = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sweep_status)

ENV = ["-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false"]


def make_repo(root: Path, name: str, files: dict[str, str]) -> Path:
    repo = root / name
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    commit(repo, files, "first")
    return repo


def commit(repo: Path, files: dict[str, str], message: str) -> None:
    for rel, text in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), *ENV, "commit", "-q", "-m", message], check=True)


def run(*argv: str) -> tuple[int, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = sweep_status.main(list(argv))
    return code, out.getvalue() + err.getvalue()


def states(*argv: str) -> dict[str, dict]:
    code, out = run(*argv, "--json")
    return {r["repo"]: r for r in json.loads(out)["repositories"]}


class SweepStatus(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        make_repo(self.root, "svc-a", {"deploy/a.initd": "name=a\n", "shared.lock": "x\n"})
        make_repo(self.root, "svc-b", {"deploy/b.initd": "name=b\nretry=\"SIGTERM/15\"\n", "shared.lock": "x\n"})
        make_repo(self.root, "svc-c", {"deploy/c.initd": "retry=1\n", "deploy/c-worker.initd": "# retry= in a comment\n",
                                       "shared.lock": "x\n"})
        make_repo(self.root, "lib", {"README.md": "no service\n", "shared.lock": "x\n"})
        make_repo(self.root, "odd-name", {"deploy/odd.initd": "name=odd\n"})
        (self.root / "not-a-repo").mkdir()
        self.args = ("--root", str(self.root), "--anchor", "deploy/*.initd", "--has", "^retry=")

    def test_each_state(self):
        got = {name: r["state"] for name, r in states(*self.args).items()}
        self.assertEqual(got, {"svc-a": "TODO", "svc-b": "DONE", "svc-c": "PARTIAL", "lib": "N/A", "odd-name": "TODO"})

    def test_partial_lists_which_files(self):
        row = states(*self.args)["svc-c"]
        self.assertEqual(row["have"], ["deploy/c.initd"])
        self.assertEqual(row["missing"], ["deploy/c-worker.initd"])  # the pattern is anchored: a comment doesn't count

    def test_exit_status_says_whether_anything_is_left(self):
        self.assertEqual(run(*self.args)[0], 1)
        for repo, rel in (("svc-a", "deploy/a.initd"), ("svc-c", "deploy/c-worker.initd"), ("odd-name", "deploy/odd.initd")):
            commit(self.root / repo, {rel: "retry=1\n"}, "apply")
        code, out = run(*self.args)
        self.assertEqual(code, 0)
        self.assertIn("0 TODO, 0 PARTIAL, 4 DONE, 1 N/A", out)

    def test_marker_shows_membership_without_filtering(self):
        rows = states(*self.args, "--marker", "shared.lock")
        self.assertTrue(rows["lib"]["marker"])
        self.assertFalse(rows["odd-name"]["marker"])
        self.assertEqual(rows["odd-name"]["state"], "TODO")  # still listed
        _, out = run(*self.args, "--marker", "shared.lock")
        self.assertIn("marker but no anchor file", out)
        self.assertIn("anchor file but no marker", out)
        self.assertRegex(out, r"anchor file but no marker.*odd-name")

    def test_ref_reads_history_not_the_working_tree(self):
        repo = self.root / "svc-a"
        before = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        commit(repo, {"deploy/a.initd": "name=a\nretry=1\n"}, "apply")
        self.assertEqual(states(str(repo), *self.args[2:])["svc-a"]["state"], "DONE")
        self.assertEqual(states(str(repo), *self.args[2:], "--ref", before)["svc-a"]["state"], "TODO")

    def test_worktree_sees_uncommitted_edits_and_head_does_not(self):
        repo = self.root / "svc-a"
        (repo / "deploy/a.initd").write_text("retry=1\n")
        self.assertEqual(states(str(repo), *self.args[2:])["svc-a"]["state"], "TODO")
        self.assertEqual(states(str(repo), *self.args[2:], "--ref", "WORKTREE")["svc-a"]["state"], "DONE")

    def test_lacks_is_for_removals(self):
        rows = states("--root", str(self.root), "--anchor", "deploy/*.initd", "--lacks", "^name=")
        self.assertEqual(rows["svc-a"]["state"], "TODO")   # still has the line to remove
        self.assertEqual(rows["svc-c"]["state"], "DONE")   # neither file has it

    def test_unreadable_ref_is_an_error_row_and_counts_as_left(self):
        code, out = run(*self.args, "--ref", "no-such-ref")
        self.assertEqual(code, 1)
        self.assertIn("ERROR", out)

    def test_usage_errors(self):
        self.assertEqual(run("--root", str(self.root), "--has", "x")[0], 2)                       # no anchor
        self.assertEqual(run("--root", str(self.root), "--anchor", "*")[0], 2)                    # neither has nor lacks
        self.assertEqual(run("--anchor", "*", "--has", "x")[0], 2)                                # no repositories
        self.assertEqual(run("--root", str(self.root), str(self.root), "--anchor", "*", "--has", "x")[0], 2)
        self.assertEqual(run("--root", str(self.root), "--anchor", "*", "--has", "(")[0], 2)      # bad regex
        self.assertEqual(run("--root", str(self.root / "not-a-repo"), "--anchor", "*", "--has", "x")[0], 2)


if __name__ == "__main__":
    unittest.main()
