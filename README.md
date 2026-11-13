# jigs

Agent Skills for recurring engineering work. A jig holds the work so the same cut comes out the
same way every time; each skill here does that for one procedure that was first done by hand,
more than once, and taught something easy to forget.

## Layout

```
skills/
  <name>/
    SKILL.md        when to use it, the procedure, what it never does on its own
    references/     detail the main file points to (optional)
    scripts/        steps that must run identically every time (optional)
    tests/          tests for those scripts (optional)
```

One directory per skill. Each is self-contained: copy `skills/<name>/` into your skills directory
(for Claude Code, `~/.claude/skills/` or a project's `.claude/skills/`) and it works without the
rest of this repo.

## Skills

| Skill | Use it to |
|---|---|
| [`hardware-run`](skills/hardware-run/SKILL.md) | Record a sitting with a real device and a repository's hardware validation checklist: decide what each observation means for the registry of unverified assumptions, and return one pull request that updates every place the result is stated (registry, checklist, status tables and prose, changelog, scanned captures). |
| [`issue-queue`](skills/issue-queue/SKILL.md) | Work a repository's open `Prompt:` issues: decide what can run now and in what order, run each to an open pull request with CI green, report once, and restack after merges. Also writes a prompt issue in the queue's format. |

## Conventions

- **Generic.** Skills carry no hostnames, addresses, names or account details, and use
  placeholders such as `mcp.example.com` and `user@example.com`. Anything specific to one
  repository belongs in that repository's own `CLAUDE.md`, which a skill reads when it runs.
- **Limits stated.** Every skill says what it never does without you (merge, tag, publish, send,
  delete, spend) and what it reports when it stops.
- **Self-contained.** A script two skills need is copied into each. CI fails if the copies differ.

## Checks

CI runs three jobs, all standard library Python:

- the repo's tests, `python -m unittest discover -s tests -v`, then each skill's own from
  `skills/<name>/tests/`
- a privacy scan over every tracked file and every commit's author, committer and message:
  `python .github/scripts/privacy_scan.py`. It reports the location and the rule, never the
  matched text. A denylist of terms no pattern can know is read from the `PRIVACY_DENYLIST`
  secret; without it (forks, local runs) only the pattern checks run.
- a copy check: `python .github/scripts/check_script_copies.py`

## License

MIT. See [LICENSE](LICENSE).
