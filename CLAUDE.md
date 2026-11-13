# CLAUDE.md

## What this is

`jigs`: Agent Skills for recurring engineering work, one directory per skill. Each skill captures
a procedure that was first done by hand several times, with the lessons that were easy to forget.

## Layout

- `skills/<name>/`: one skill. `SKILL.md` (frontmatter `name` matching the directory, and a
  `description` that says when to use it), plus optional `references/` for detail the main file
  links to and `scripts/` for steps that must run the same way every time. A skill's tests live in
  `skills/<name>/tests/`.
- `.github/scripts/privacy_scan.py` and `tests/test_privacy_scan.py`: the public-repo scan, copied
  from `mcp-server-steam-backlog` at `c6a969b`. One difference: the `PRIVATE_NETS` line carries a
  `privacy-scan: allow` mark, because this repo's denylist matched the scanner's own list of
  private ranges. Change anything else there (or in `steam-backlog-triage`, where it started) and
  copy it again, keeping that mark; don't edit it here.
  `.github/privacy-scan-allowed-commits` is optional and absent: see the script's docstring.
- `.github/scripts/check_script_copies.py` and `tests/test_check_script_copies.py`: the copy check
  (below).
- `.github/workflows/ci.yml`: the repo tests and each skill's tests (one `unittest discover` per
  `skills/<name>/tests/`, so a new skill's tests run without touching the workflow), the privacy
  scan over files and every commit, and the copy check.

## Rules

- **The repo is public and generic.** No personal names, hostnames, IP addresses, domains, room
  names, device names, time zones, account ids, personal emails or household references anywhere:
  skills, scripts, tests, docs, examples, commit messages, branch names, PR text. Use the
  placeholders `mcp-server-shared` uses: `mcp.example.com`, `example.cloudflareaccess.com`,
  `user@example.com`, device keys like `tv-1`, and the documentation address ranges
  (`192.0.2.0/24`, `2001:db8::/32`) rather than `192.168.x.x`. Why: a skill is read by people who
  don't share the owner's setup, and anything specific to one repo belongs in that repo's own
  `CLAUDE.md`, which the skill reads at run time.
- **The privacy scan enforces part of that, not all of it.** It checks patterns (addresses,
  emails, SteamIDs) and a denylist held in the `PRIVACY_DENYLIST` secret, over tracked files and
  over every commit's author, committer and message. The list can't be read from a session, so a
  local run (`python .github/scripts/privacy_scan.py`) only covers the patterns: a clean local run
  does not mean CI will pass. CI output is public, so the scan prints where and which rule, never
  the value. If it reports `denylist entry #N`, reword the line; don't guess the term in a commit
  message or PR comment. A flagged commit message means rewriting that commit before merge, since
  history is scanned.
- **A script used by two skills is copied into each**, at the same path under `scripts/` and with
  the same name. Why: a skill is installed on its own, so it can't import from a sibling
  directory. `check_script_copies.py` fails CI when copies with the same path under `scripts/`
  differ by a single byte, so a fix made in one copy is made in all of them in the same PR. It
  can't recognise a renamed copy: keep the name.
- **This repo is the source of truth for these skills.** A skill is changed here, by PR, never by
  editing an installed or saved copy. After a change to a skill merges, propose the same update to
  the owner as a skill update for review; the work isn't finished until that proposal is made.
  Why: the saved copy is what actually runs, and it only stays equal to `main` if every merge is
  followed through.
- **Never without the owner:** merge, tag, publish, or change repository settings and secrets.

## Commands

```sh
python -m unittest discover -s tests -v          # the repo's own checks (standard library only)
for d in skills/*/tests; do python -m unittest discover -s "$d" -v; done   # each skill's tests
python .github/scripts/privacy_scan.py           # patterns only, unless PRIVACY_DENYLIST is set
python .github/scripts/check_script_copies.py    # copies of a shared script match
```
