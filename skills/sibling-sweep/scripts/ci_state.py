#!/usr/bin/env python3
"""Read a commit's CI the same way every time, instead of trusting a report.

Usage: ci_state.py OWNER/REPO (PR | ref:BRANCH_OR_SHA) [--rerun-queued]

Use ref:main before planning: a red main makes every branch's checks fail for a reason
that is not the branch's.

Counts both kinds of result GitHub keeps for a commit: check runs (GitHub Actions and
apps) and commit statuses (external CI that reports the older way). Prints one verdict
line, then one line per check:
  GREEN    every check on the head commit finished success/skipped/neutral, every commit
           status is success, and no workflow run for that commit is queued or running
  PENDING  something is still queued or running, or nothing has reported yet on a repo
           that has CI (an agent that says "done" now is wrong)
  REQUEUE  the only problem is a job cancelled before any step started: a runner-queue
           problem, not a result. --rerun-queued re-runs exactly those jobs.
  FAILED   at least one check failed or was cancelled after it started, or a commit
           status is failure/error
  NO_CI    nothing reported and the repository has no workflows and no commit statuses:
           there is no CI to wait for. Not a pass; say so and rely on the local gate.
  NO_BRANCH  ref:NAME does not exist: the repository is empty, or has no such branch or
           commit. Nothing can be based on it until it does.

Exit code: 0 GREEN, 1 FAILED, 2 PENDING, 3 REQUEUE, 4 NO_CI, 5 NO_BRANCH, 64 usage.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable
from typing import Any

OK = {"success", "skipped", "neutral"}
EXIT = {"GREEN": 0, "FAILED": 1, "PENDING": 2, "REQUEUE": 3, "NO_CI": 4, "NO_BRANCH": 5}

Gh = Callable[..., Any]


def gh(*args: str) -> Any:
    out = subprocess.run(["gh", "api", *args], check=True, capture_output=True, text=True).stdout
    return json.loads(out) if out.strip() else {}


def ref_is_absent(err: subprocess.CalledProcessError) -> bool:
    """True when GitHub answered that the ref is not there: 409 for an empty repository, 404 or
    422 for a branch or commit it does not have. Any other failure (network, credentials) is
    not an answer about the ref and is raised."""
    return any(f"HTTP {code}" in (err.stderr or "") for code in (404, 409, 422))


def started_no_step(api: Gh, repo: str, job_id: int) -> bool:
    """True when an Actions job was cancelled before any of its steps ran."""
    try:
        job = api(f"repos/{repo}/actions/jobs/{job_id}")
    except subprocess.CalledProcessError:
        return False  # not an Actions job (an external check): treat as a real result
    steps = job.get("steps") or []
    # A job the runner never picked up has no steps at all, or only skipped/unstarted ones.
    return all(st.get("conclusion") == "skipped" or not st.get("started_at") for st in steps)


def repo_has_workflows(api: Gh, repo: str) -> bool:
    """False only when GitHub says the repository has no workflows. Unknown counts as True,
    so a failed lookup can produce PENDING (wait and look again) but never NO_CI."""
    try:
        return int(api(f"repos/{repo}/actions/workflows?per_page=1").get("total_count", 1)) > 0
    except (subprocess.CalledProcessError, TypeError, ValueError):
        return True


def evaluate(api: Gh, repo: str, sha: str) -> tuple[str, list[str], list[dict[str, Any]], dict[str, int]]:
    """(verdict, one line per check, the check runs to re-run on REQUEUE, counts)."""
    runs = api(f"repos/{repo}/commits/{sha}/check-runs?per_page=100").get("check_runs", [])
    wf = api(f"repos/{repo}/actions/runs?head_sha={sha}&per_page=50").get("workflow_runs", [])
    # The combined status holds the latest status per context; its top-level "state" is
    # "pending" when there are none at all, so read the list, not the summary.
    statuses = api(f"repos/{repo}/commits/{sha}/status?per_page=100").get("statuses", [])

    pending: list[Any] = []
    failed: list[Any] = []
    requeue: list[dict[str, Any]] = []
    lines: list[str] = []
    for r in sorted(runs, key=lambda x: x["name"]):
        st, concl = r["status"], r["conclusion"]
        tag = concl or st
        if st != "completed":
            pending.append(r)
        elif concl == "cancelled" and started_no_step(api, repo, r["id"]):
            requeue.append(r)
            tag = "cancelled before any step (runner queue)"
        elif concl not in OK:
            failed.append(r)
        lines.append(f"  {r['name']}: {tag}  {r.get('html_url') or ''}".rstrip())
    for s in sorted(statuses, key=lambda x: x["context"]):
        state = s["state"]
        if state == "pending":
            pending.append(s)
        elif state != "success":
            failed.append(s)
        lines.append(f"  {s['context']} (status): {state}  {s.get('target_url') or ''}".rstrip())
    open_wf = [w for w in wf if w["status"] != "completed"]

    if failed:
        verdict = "FAILED"
    elif pending or open_wf:
        verdict = "PENDING"
    elif not runs and not statuses:
        # Nothing has reported. Either CI has not started yet, or there is none.
        verdict = "PENDING" if wf or repo_has_workflows(api, repo) else "NO_CI"
    elif requeue:
        verdict = "REQUEUE"
    else:
        verdict = "GREEN"
    counts = {
        "checks": len(runs) + len(statuses),
        "failed": len(failed),
        "pending": len(pending) + len(open_wf),
        "requeue": len(requeue),
    }
    return verdict, lines, requeue, counts


def main(argv: list[str] | None = None, api: Gh = gh) -> int:
    argv = sys.argv[1:] if argv is None else argv
    args = [a for a in argv if not a.startswith("--")]
    if len(args) < 2 or "/" not in args[0]:
        print(__doc__, file=sys.stderr)
        return 64
    repo, target = args[0], args[1]
    if target.startswith("ref:"):
        try:
            sha = api(f"repos/{repo}/commits/{target[4:]}")["sha"]
        except subprocess.CalledProcessError as err:
            if not ref_is_absent(err):
                raise
            print(f"NO_BRANCH  {target}: the repository is empty or has no such branch or commit")
            return EXIT["NO_BRANCH"]
        label = target
    else:
        sha = api(f"repos/{repo}/pulls/{target}")["head"]["sha"]
        label = f"PR #{target}"

    verdict, lines, requeue, n = evaluate(api, repo, sha)
    print(f"{verdict}  {label} head {sha[:7]}  checks={n['checks']} failed={n['failed']} "
          f"pending={n['pending']} requeue={n['requeue']}")
    if lines:
        print("\n".join(lines))
    if verdict == "NO_CI":
        print("  no workflows and no commit statuses: nothing will report on this commit")

    if verdict == "REQUEUE" and "--rerun-queued" in argv:
        for r in requeue:
            try:
                api("-X", "POST", f"repos/{repo}/actions/jobs/{r['id']}/rerun")
                print(f"  re-ran {r['name']}")
            except subprocess.CalledProcessError:
                print(f"  could not re-run {r['name']}")
    return EXIT[verdict]


if __name__ == "__main__":
    sys.exit(main())
