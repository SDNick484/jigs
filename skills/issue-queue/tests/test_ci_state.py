"""ci_state.py against canned GitHub API answers (no network, no gh)."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import subprocess
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ci_state.py"
spec = importlib.util.spec_from_file_location("ci_state", SCRIPT)
ci_state = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci_state)

REPO = "owner/repo"
SHA = "a" * 40


def run(name: str, status: str = "completed", conclusion: str | None = "success", id_: int = 1) -> dict:
    return {"id": id_, "name": name, "status": status, "conclusion": conclusion, "html_url": f"https://ci.example.com/{id_}"}


class FakeApi:
    """Answers the paths ci_state.py asks for; records POSTs."""

    def __init__(self, *, runs=(), statuses=(), wf=(), workflows=1, jobs=None, workflows_error=False):
        self.runs, self.statuses, self.wf = list(runs), list(statuses), list(wf)
        self.workflows, self.jobs, self.workflows_error = workflows, jobs or {}, workflows_error
        self.posts: list[str] = []

    def __call__(self, *args: str):
        if args[0] == "-X":
            self.posts.append(args[2])
            return {}
        path = args[0]
        if path.endswith("/pulls/7"):
            return {"head": {"sha": SHA}}
        if "/commits/main" in path and "check-runs" not in path and "/status" not in path:
            return {"sha": SHA}
        if "/check-runs" in path:
            return {"check_runs": self.runs}
        if "/status" in path:
            return {"state": "pending", "statuses": self.statuses}
        if "/actions/runs" in path:
            return {"workflow_runs": self.wf}
        if "/actions/workflows" in path:
            if self.workflows_error:
                raise subprocess.CalledProcessError(1, "gh")
            return {"total_count": self.workflows}
        if "/actions/jobs/" in path:
            job = self.jobs.get(int(path.rsplit("/", 1)[1]))
            if job is None:
                raise subprocess.CalledProcessError(1, "gh")
            return job
        raise AssertionError(f"unexpected path {path}")


def verdict(api: FakeApi, *argv: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = ci_state.main([REPO, "7", *argv], api=api)
    return code, out.getvalue()


class CiState(unittest.TestCase):
    def test_all_success_is_green(self):
        code, out = verdict(FakeApi(runs=[run("test"), run("lint", conclusion="skipped", id_=2)]))
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("GREEN  PR #7 head aaaaaaa  checks=2"))

    def test_running_check_is_pending(self):
        code, out = verdict(FakeApi(runs=[run("test", status="in_progress", conclusion=None)]))
        self.assertEqual((code, out.split()[0]), (2, "PENDING"))

    def test_open_workflow_run_is_pending_even_when_checks_passed(self):
        code, _ = verdict(FakeApi(runs=[run("test")], wf=[{"status": "queued"}]))
        self.assertEqual(code, 2)

    def test_failed_check_is_failed(self):
        code, out = verdict(FakeApi(runs=[run("test", conclusion="failure"), run("lint", id_=2)]))
        self.assertEqual((code, out.split()[0]), (1, "FAILED"))

    def test_failing_commit_status_is_failed_although_every_check_run_passed(self):
        # External CI that reports a commit status, not a check run. Reading only check runs said GREEN.
        api = FakeApi(runs=[run("test")], statuses=[{"context": "ci/external", "state": "failure", "target_url": None}])
        code, out = verdict(api)
        self.assertEqual((code, out.split()[0]), (1, "FAILED"))
        self.assertIn("ci/external (status): failure", out)

    def test_pending_commit_status_is_pending(self):
        api = FakeApi(runs=[run("test")], statuses=[{"context": "ci/external", "state": "pending"}])
        self.assertEqual(verdict(api)[0], 2)

    def test_statuses_only_all_success_is_green(self):
        api = FakeApi(statuses=[{"context": "ci/external", "state": "success"}], workflows=0)
        code, out = verdict(api)
        self.assertEqual((code, out.split()[0]), (0, "GREEN"))

    def test_nothing_reported_on_a_repo_without_workflows_is_no_ci(self):
        code, out = verdict(FakeApi(workflows=0))
        self.assertEqual((code, out.split()[0]), (4, "NO_CI"))

    def test_nothing_reported_yet_on_a_repo_with_workflows_is_pending(self):
        self.assertEqual(verdict(FakeApi(workflows=3))[0], 2)

    def test_unreadable_workflow_list_is_pending_not_no_ci(self):
        self.assertEqual(verdict(FakeApi(workflows=0, workflows_error=True))[0], 2)

    def test_cancelled_before_any_step_is_requeue_and_is_rerun_on_request(self):
        api = FakeApi(runs=[run("test"), run("smoke", conclusion="cancelled", id_=9)], jobs={9: {"steps": []}})
        code, out = verdict(api)
        self.assertEqual((code, out.split()[0]), (3, "REQUEUE"))
        self.assertEqual(api.posts, [])
        code, out = verdict(api, "--rerun-queued")
        self.assertEqual(code, 3)
        self.assertEqual(api.posts, [f"repos/{REPO}/actions/jobs/9/rerun"])

    def test_cancelled_after_a_step_started_is_failed(self):
        jobs = {9: {"steps": [{"conclusion": "success", "started_at": "2026-01-01T00:00:00Z"}]}}
        api = FakeApi(runs=[run("smoke", conclusion="cancelled", id_=9)], jobs=jobs)
        self.assertEqual(verdict(api)[0], 1)

    def test_cancelled_external_check_is_failed(self):
        api = FakeApi(runs=[run("external", conclusion="cancelled", id_=9)])  # no Actions job behind it
        self.assertEqual(verdict(api)[0], 1)

    def test_a_failure_beside_a_requeue_is_failed_and_nothing_is_rerun(self):
        api = FakeApi(runs=[run("test", conclusion="failure"), run("smoke", conclusion="cancelled", id_=9)],
                      jobs={9: {"steps": []}})
        self.assertEqual(verdict(api, "--rerun-queued")[0], 1)
        self.assertEqual(api.posts, [])

    def test_ref_form(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = ci_state.main([REPO, "ref:main"], api=FakeApi(runs=[run("test")]))
        self.assertEqual(code, 0)
        self.assertIn("ref:main head aaaaaaa", out.getvalue())

    def test_usage(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(ci_state.main([REPO]), 64)
            self.assertEqual(ci_state.main(["not-a-repo", "7"]), 64)



class NoBranch(unittest.TestCase):
    """ref:NAME on a repository with no commits, or with no such branch."""

    def api_failing_with(self, stderr: str):
        def api(*args: str):
            raise subprocess.CalledProcessError(1, "gh", stderr=stderr)
        return api

    def run_ref(self, api) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = ci_state.main([REPO, "ref:main"], api=api)
        return code, out.getvalue()

    def test_empty_repository_is_no_branch_not_a_traceback(self):
        code, out = self.run_ref(self.api_failing_with("gh: Git Repository is empty. (HTTP 409)"))
        self.assertEqual((code, out.split()[0]), (5, "NO_BRANCH"))

    def test_unknown_branch_is_no_branch(self):
        code, _ = self.run_ref(self.api_failing_with("gh: No commit found for SHA: main (HTTP 422)"))
        self.assertEqual(code, 5)

    def test_a_failure_that_is_not_an_answer_is_raised(self):
        with self.assertRaises(subprocess.CalledProcessError):
            self.run_ref(self.api_failing_with("gh: connection refused"))
        with self.assertRaises(subprocess.CalledProcessError):
            self.run_ref(self.api_failing_with("gh: Bad credentials (HTTP 401)"))

    def test_a_missing_pull_request_is_still_an_error(self):
        out = io.StringIO()
        with self.assertRaises(subprocess.CalledProcessError), contextlib.redirect_stdout(out):
            ci_state.main([REPO, "7"], api=self.api_failing_with("gh: Not Found (HTTP 404)"))


if __name__ == "__main__":
    unittest.main()
