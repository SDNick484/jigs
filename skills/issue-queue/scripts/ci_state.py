#!/usr/bin/env python3
"""Read a pull request's CI the same way every time, instead of trusting a report.

Usage: ci_state.py OWNER/REPO (PR | ref:BRANCH_OR_SHA) [--rerun-queued]

Use ref:main before planning: a red main makes every worker's gate fail for a reason
that is not theirs.

Prints one verdict line, then one line per check:
  GREEN    every check run on the PR's head commit finished success/skipped/neutral,
           and no workflow run for that commit is still queued or in progress
  PENDING  something is still queued or running (an agent that says "done" now is wrong)
  REQUEUE  only problem is a job cancelled before any step started: a runner-queue
           problem, not a result. --rerun-queued re-runs exactly those jobs.
  FAILED   at least one check failed or was cancelled after it started

Exit code: 0 GREEN, 1 FAILED, 2 PENDING, 3 REQUEUE.
"""

from __future__ import annotations

import json
import subprocess
import sys

OK = {"success", "skipped", "neutral"}


def gh(*args: str) -> object:
    out = subprocess.run(["gh", "api", *args], check=True, capture_output=True, text=True).stdout
    return json.loads(out) if out.strip() else {}


def started_no_step(repo: str, job_id: int) -> bool:
    """True when an Actions job was cancelled before any of its steps ran."""
    try:
        job = gh(f"repos/{repo}/actions/jobs/{job_id}")
    except subprocess.CalledProcessError:
        return False  # not an Actions job (an external check): treat as a real result
    steps = job.get("steps") or []
    # A job the runner never picked up has no steps at all, or only skipped/unstarted ones.
    return all(
        st.get("conclusion") == "skipped" or not st.get("started_at") for st in steps
    )


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        return 64
    repo, pr = sys.argv[1], sys.argv[2]
    if pr.startswith("ref:"):
        sha = gh(f"repos/{repo}/commits/{pr[4:]}")["sha"]
    else:
        sha = gh(f"repos/{repo}/pulls/{pr}")["head"]["sha"]
    runs = gh(f"repos/{repo}/commits/{sha}/check-runs?per_page=100")["check_runs"]
    wf = gh(f"repos/{repo}/actions/runs?head_sha={sha}&per_page=50").get("workflow_runs", [])

    pending, failed, requeue, lines = [], [], [], []
    for r in sorted(runs, key=lambda x: x["name"]):
        st, concl = r["status"], r["conclusion"]
        tag = concl or st
        if st != "completed":
            pending.append(r)
        elif concl == "cancelled" and started_no_step(repo, r["id"]):
            requeue.append(r)
            tag = "cancelled before any step (runner queue)"
        elif concl not in OK:
            failed.append(r)
        lines.append(f"  {r['name']}: {tag}  {r['html_url']}")
    open_wf = [w for w in wf if w["status"] != "completed"]

    if failed:
        verdict, code = "FAILED", 1
    elif pending or open_wf or not runs:
        verdict, code = "PENDING", 2
    elif requeue:
        verdict, code = "REQUEUE", 3
    else:
        verdict, code = "GREEN", 0
    print(f"{verdict}  {pr if pr.startswith('ref:') else 'PR #' + pr} head {sha[:7]}  checks={len(runs)} "
          f"failed={len(failed)} pending={len(pending) + len(open_wf)} requeue={len(requeue)}")
    print("\n".join(lines))

    if requeue and "--rerun-queued" in sys.argv and not failed:
        for r in requeue:
            subprocess.run(["gh", "api", "-X", "POST", f"repos/{repo}/actions/jobs/{r['id']}/rerun"],
                           check=False)
            print(f"  re-ran {r['name']}")
    return code


if __name__ == "__main__":
    sys.exit(main())
