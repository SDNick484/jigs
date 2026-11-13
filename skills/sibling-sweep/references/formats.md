# Formats

## The plan (posted before starting)

```markdown
**Sweep: <the change in one line>** (reference: <repo>@<sha or PR>; branch `<name>` in every repository)

- **Fixed:** <the line(s) that are identical everywhere>
- **Derived per repository:** <the question each one answers>
- **Probe:** anchor `<glob>`, present when `<regex>`; says TODO before the reference change and DONE after.

| Repository | State | Files | Expected to differ here |
|---|---|---|---|
| repo-a | TODO | `deploy/a.initd` | pilot |
| repo-b | TODO | `deploy/b.initd`, `deploy/b-worker.initd` | two services, stopped differently |
| repo-c | DONE | | already has it (since <sha>) |
| repo-d | N/A | | no service file |
| repo-e | TODO | `deploy/e.initd` | **held: default branch is red (<check>)** |

**Decided for all:** <e.g. a changelog entry under Unreleased wherever a changelog exists>.
**Pilot:** repo-a. The rest start when its CI is green.
**Starting now.** <or: "One question first: repo-f has the file but isn't in the family by <marker>. In or out?">
```

## Commits

Subject: the same string in every repository. Body: why (short), then one line per element with this repository's answer, then the tracking reference if there is one.

```text
<subject, identical across the sweep>

<Two or three sentences on why, true for this repository.>

- <element 1>: <applied | already there, unchanged | does not apply: why>
- <element 2>: ...

Refs <tracking issue, if one exists>
```

Author identity, attribution lines and anything forbidden in a message come from the repository's rules. In a public repository the message is as public as the code, and a scanner that reads history will fail the PR on a name or address in a commit message or an author field.

## Pull requests

Title: the subject. Body: the repository's template if it has one, otherwise:

```markdown
Part of a sweep across <n> repositories (branch `<name>` in each).

**Here:** <what was applied, in this repository's terms>
**Different from the others:** <the derived answer and how it was worked out; elements already there or not applicable>
**Gate:** <the exact summary line>
**After merging:** <what does not happen by merging, e.g. the service must be restarted for the setting to apply>
```

## The report (sent once)

```markdown
**Sweep: <the change>**: <n> PRs open, CI green on all. <or: "... on 7 of 8; repo-e is stuck, below.">

| Repository | PR | What differed here | CI |
|---|---|---|---|
| repo-a | #12 | nothing: the reference case | GREEN |
| repo-b | #7 | two service files; the worker stops devices one at a time, so 15 s can be exceeded with three or more (said in the comment) | GREEN |

**Not changed:** repo-c (already had it), repo-d (no service file).
**Held or stuck:** repo-e: default branch red before the sweep (`<check>`); nothing opened.
**Merging does not:** <restart the services; each picks the setting up at its next start>.
**Also found (outside this request):** <e.g. repo-g matches the probe for an older sweep and never got it>.

The PRs are independent: merge in any order. Reply "merged" and I'll re-run the probe on every default branch.
```

"What differed here" is the column that earns the table. If every row says "nothing", either the change had no derived part or nobody looked.

## After "merged"

```markdown
All <n> are in. Probe on each default branch: <n> DONE, <m> N/A, 0 TODO.
<or: "repo-b is still PARTIAL: `deploy/b-worker.initd` has no PR.">
```
