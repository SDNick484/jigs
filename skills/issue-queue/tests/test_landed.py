"""landed.py against canned GitHub API answers (no network, no gh)."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "landed.py"
spec = importlib.util.spec_from_file_location("landed", SCRIPT)
landed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(landed)

REPO = "owner/repo"


def pr(base: str = "main", state: str = "closed", merged: bool = True, sha: str = "m1") -> dict:
    return {"state": state, "merged": merged, "base": {"ref": base}, "merge_commit_sha": sha if merged else None}


class FakeApi:
    """`prs` maps number to a pull request; `on_default` is the set of merge commits main has."""

    def __init__(self, prs: dict, on_default: set[str]):
        self.prs, self.on_default = prs, on_default

    def __call__(self, path: str):
        if path == f"repos/{REPO}":
            return {"default_branch": "main"}
        if "/pulls/" in path:
            return self.prs[path.rsplit("/", 1)[1]]
        sha = path.rsplit("...", 1)[1]
        return {"status": "behind" if sha in self.on_default else "ahead"}


def run(api: FakeApi, *numbers: str) -> tuple[int, list[str]]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = landed.main([REPO, *numbers], api=api)
    return code, [line.split()[0] for line in out.getvalue().splitlines()]


class Landed(unittest.TestCase):
    def test_merged_into_the_default_branch_is_landed(self):
        self.assertEqual(run(FakeApi({"28": pr()}, {"m1"}), "28"), (0, ["LANDED"]))

    def test_merged_into_another_pull_requests_branch_is_not_landed(self):
        api = FakeApi({"28": pr(sha="m1"), "29": pr(base="claude/first", sha="m2")}, {"m1"})
        self.assertEqual(run(api, "28", "29"), (1, ["LANDED", "NOT_ON_DEFAULT"]))

    def test_merged_into_a_branch_that_later_reached_default_is_landed(self):
        api = FakeApi({"29": pr(base="claude/first", sha="m2")}, {"m2"})
        self.assertEqual(run(api, "29"), (0, ["LANDED"]))

    def test_open_against_another_branch_is_flagged_before_anyone_merges_it(self):
        api = FakeApi({"30": pr(base="claude/first", state="open", merged=False)}, set())
        self.assertEqual(run(api, "30"), (1, ["WRONG_BASE"]))

    def test_open_and_closed_are_not_landed(self):
        api = FakeApi({"31": pr(state="open", merged=False), "32": pr(merged=False)}, set())
        self.assertEqual(run(api, "31", "32"), (1, ["OPEN", "CLOSED"]))

    def test_usage(self):
        for argv in ([], [REPO], ["repo", "1"], [REPO, "abc"]):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(landed.main(argv, api=FakeApi({}, set())), 64)


if __name__ == "__main__":
    unittest.main()
