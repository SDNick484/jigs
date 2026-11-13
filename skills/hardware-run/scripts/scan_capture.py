#!/usr/bin/env python3
"""Look for identifying details in device captures before they are committed.

A capture taken from a real device (a config dump, a debug log, a recorded message) is the one file
in a hardware run that the author did not write, and it goes into a repository's history for good.
The repo's own tool scrubs it on the way out, but that scrub is a list of the keys someone has seen
so far, and new firmware brings new ones. So this is a second, independent look, by shape instead
of by key list, run on the capture as it would be committed.

It does not rewrite anything. A finding means the repo's scrubber missed something: fix the
scrubber, add a test with a made-up value of the same shape, and take or scrub the capture again.
A capture edited by hand is clean once, and the next dump leaks the same field.

Checks (JSON is walked value by value, with strings that hold JSON opened up; anything else is read
line by line):

  must fix
    email        an address anywhere in a value, also mid-string
    ip           an IPv4 or IPv6 address that is not loopback or a documentation range
    mac          a hardware address (aa:bb:cc:dd:ee:ff or aa-bb-...)
    uuid         a UUID that is not all zeros
    secret-key   a JSON key that names a credential (password, token, secret, ...) with a value
    deny         a term from --deny FILE (one per line): the names no pattern can know

  look at       (reported; they fail only with --strict)
    id-key       a JSON key that names an identity (serial, account, uuid, session, location, ...)
                 with a value. One line per key name, with how many times it occurs
    opaque       a long single token of mixed letters and digits: often a hash or a device id

A value that is empty, null or already masked (<redacted>, ***, xxxx) is skipped. The output is
where and which rule, never the value, unless --show is given: tool output ends up in logs and
transcripts too.

Usage: scan_capture.py PATH [PATH ...] [--deny FILE] [--strict] [--show] [--json]
Exit status: 0 nothing to fix, 1 findings, 2 usage or setup error.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import re
import sys
from collections import Counter
from pathlib import Path

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@((?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,})")
PLACEHOLDER_DOMAIN = re.compile(r"(?:^|\.)(?:example\.(?:com|org|net)|example|invalid)$", re.I)
IPV4 = re.compile(r"(?<![0-9A-Za-z.])(?:\d{1,3}\.){3}\d{1,3}(?![0-9A-Za-z]|\.[0-9])")
IPV6 = re.compile(r"(?<![0-9A-Za-z:.])(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}(?![0-9A-Za-z:])")
MAC = re.compile(r"(?<![0-9A-Fa-f:-])[0-9A-Fa-f]{2}(?:([:-])[0-9A-Fa-f]{2})(?:\1[0-9A-Fa-f]{2}){4}(?![0-9A-Fa-f:-])")
DOC_MAC = re.compile(r"^00[:-]00[:-]5e[:-]00[:-]53[:-]", re.I)  # RFC 7042 documentation range
UUID = re.compile(r"(?<![0-9A-Fa-f-])[0-9A-Fa-f]{8}-(?:[0-9A-Fa-f]{4}-){3}[0-9A-Fa-f]{12}(?![0-9A-Fa-f-])")
OPAQUE = re.compile(r"^(?:[0-9A-Fa-f]{16,}|[A-Za-z0-9_-]{24,}|[A-Za-z0-9+/]{22,}={1,2})$")
MASKED = re.compile(r"^(?:|<[^<>]*>|\*+|x{3,}|redacted|removed|null|none|n/a)$", re.I)
DOC_NETS = [
    ipaddress.ip_network(n)
    for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24", "2001:db8::/32", "3fff::/20")
]
SECRET_KEY = re.compile(
    r"pass(?:word|wd|phrase)?$|secret|token|api_?key|auth(?:orization)?$|cookie|credential|private_?key|^psk$", re.I
)
ID_KEY = re.compile(
    r"e_?mail|user(?:_?name|_?id)?$|account|uuid|guid|serial|mac(?:_?addr(?:ess)?)?$|ssid|session|"
    r"(?:hub|remote|client|household|home|owner)_?id$|lat(?:itude)?$|lon(?:g|gitude)?$|"
    r"zip|postal|address|location|time_?zone|^tz|host(?:_?name)?$|^ip$",
    re.I,
)
# Keys whose values look like addresses but are versions or protocol constants.
VERSION_KEY = re.compile(r"version|firmware|^fw|^sw|build|release", re.I)
MUST_FIX = ("email", "ip", "mac", "uuid", "secret-key", "deny")
LOOK_AT = ("id-key", "opaque")
PER_RULE = 20  # lines printed per file and rule before the rest are counted


def ip_is_fine(text: str) -> bool:
    try:
        ip = ipaddress.ip_address(text)
    except ValueError:
        return True  # not an address after all (a time, a version with four parts over 255)
    if ip.is_loopback or ip.is_unspecified:
        return True
    return any(ip.version == n.version and ip in n for n in DOC_NETS)


def rules_in(text: str, deny: list[str], *, versions: bool = False) -> list[str]:
    """The must-fix rules this piece of text trips."""
    hits: list[str] = []
    if any(not PLACEHOLDER_DOMAIN.search(m.group(1)) for m in EMAIL.finditer(text)):
        hits.append("email")
    macs = [m.group(0) for m in MAC.finditer(text)]
    if any(not DOC_MAC.match(m) for m in macs):
        hits.append("mac")
    if not versions:
        rest = MAC.sub(" ", text)  # six hex pairs with colons also parse as part of an IPv6 address
        candidates = [m.group(0) for m in IPV4.finditer(rest)]
        candidates += [m.group(0) for m in IPV6.finditer(rest) if m.group(0).count(":") >= 2 and re.search(r"[0-9A-Fa-f]", m.group(0))]
        if any(not ip_is_fine(c) for c in candidates if _is_address(c)):
            hits.append("ip")
    if any(set(m.group(0)) - set("0-") for m in UUID.finditer(text)):
        hits.append("uuid")
    low = text.lower()
    hits += [f"deny #{n}" for n, term in enumerate(deny, 1) if term in low]
    return hits


def _is_address(text: str) -> bool:
    try:
        ipaddress.ip_address(text)
    except ValueError:
        return False
    # "12:30:00" never parses; "::" and "1::" do, and are not worth a finding on their own.
    return len(text.replace(":", "")) >= 4


class Scan:
    def __init__(self, deny: list[str]) -> None:
        self.deny = deny
        self.findings: list[tuple[str, str, str]] = []  # (where, rule, value)
        self.keys: dict[tuple[str, str], list[str]] = {}  # (file, key) -> places, for id-key

    def add(self, where: str, rule: str, value: str) -> None:
        self.findings.append((where, rule, value))

    def value(self, file: str, path: str, key: str, value: object) -> None:
        if isinstance(value, dict):
            for k, v in value.items():
                self.value(file, f"{path}.{k}" if path else str(k), str(k), v)
            return
        if isinstance(value, list):
            for i, v in enumerate(value):
                self.value(file, f"{path}[{i}]", key, v)
            return
        if value is None or isinstance(value, bool):
            return
        text = str(value)
        if MASKED.match(text.strip()):
            return
        if isinstance(value, str) and text.lstrip()[:1] in "{[":
            try:
                inner = json.loads(text)
            except ValueError:
                inner = None
            if isinstance(inner, (dict, list)):
                self.value(file, f"{path}<json>", key, inner)
                return
        where = f"{file}:{path}"
        for rule in rules_in(text, self.deny, versions=bool(VERSION_KEY.search(key))):
            self.add(where, rule, text)
        if SECRET_KEY.search(key):
            self.add(where, "secret-key", text)
        elif ID_KEY.search(key):
            self.keys.setdefault((file, key), []).append(path)
        elif isinstance(value, str) and OPAQUE.match(text) and len(re.findall(r"\d", text)) >= 3 and re.search(r"[A-Za-z]", text):
            self.add(where, "opaque", text)

    def file(self, path: Path, label: str) -> None:
        data = path.read_bytes()
        if b"\0" in data[:8192]:
            self.add(label, "binary: not scanned, look at it yourself", "")
            return
        text = data.decode("utf-8", "replace")
        docs: list[object] | None = None
        try:
            docs = [json.loads(text)]
        except ValueError:
            try:  # one JSON document per line (a message log)
                docs = [json.loads(line) for line in text.splitlines() if line.strip()]
            except ValueError:
                docs = None
        if docs is not None and all(isinstance(d, (dict, list)) for d in docs):
            for n, doc in enumerate(docs):
                self.value(label, f"[line {n + 1}]" if len(docs) > 1 else "", "", doc)
            return
        for n, line in enumerate(text.splitlines(), 1):
            for rule in rules_in(line, self.deny):
                self.add(f"{label}:{n}", rule, line.strip())


def read_deny(path: str | None) -> list[str]:
    if not path:
        return []
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError as e:
        raise SystemExit(f"error: --deny: cannot read {path}: {e.strerror}") from e
    return [x.strip().lower() for x in lines if x.strip() and not x.strip().startswith("#")]


def expand(paths: list[str]) -> list[tuple[Path, str]]:
    out: list[tuple[Path, str]] = []
    for given in paths:
        p = Path(given)
        if p.is_dir():
            out += [(f, f.as_posix()) for f in sorted(p.rglob("*")) if f.is_file()]
        elif p.is_file():
            out.append((p, p.as_posix()))
        else:
            raise SystemExit(f"error: {given}: no such file or directory")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("paths", nargs="+", help="capture files, or directories of them")
    ap.add_argument("--deny", metavar="FILE", help="terms that must not appear, one per line (keep this file out of git)")
    ap.add_argument("--strict", action="store_true", help='fail on the "look at" findings too')
    ap.add_argument("--show", action="store_true", help="print the matched values (they will be in your terminal and logs)")
    ap.add_argument("--json", action="store_true", help="print findings as JSON")
    try:
        args = ap.parse_args(argv)
        scan = Scan(read_deny(args.deny))
        files = expand(args.paths)
    except SystemExit as e:
        if isinstance(e.code, str):
            print(e.code, file=sys.stderr)
            return 2
        return int(e.code or 0)
    if not files:
        print("error: no files to scan", file=sys.stderr)
        return 2
    for path, label in files:
        scan.file(path, label)

    must = [f for f in scan.findings if f[1].split()[0] in MUST_FIX or f[1].startswith("binary")]
    look = [f for f in scan.findings if f[1] in LOOK_AT]
    id_keys = [
        (f"{file}: key {key!r} has a value in {len(places)} place(s), first at {places[0]}", "id-key", "")
        for (file, key), places in sorted(scan.keys.items())
    ]
    if args.json:
        print(json.dumps({
            "files": len(files),
            "must_fix": [{"where": w, "rule": r, **({"value": v} if args.show else {})} for w, r, v in must],
            "look_at": [{"where": w, "rule": r, **({"value": v} if args.show else {})} for w, r, v in look + id_keys],
        }, indent=2))
    else:
        for title, group in (("must fix", must), ("look at", look + id_keys)):
            print(f"{title} ({len(group)}):")
            printed: Counter[tuple[str, str]] = Counter()
            for where, rule, value in group:
                bucket = (where.split(":")[0], rule)
                printed[bucket] += 1
                if printed[bucket] <= PER_RULE:
                    print(f"    {rule:<11} {where}" + (f"   {value[:80]}" if args.show and value else ""))
            for (file, rule), n in printed.items():
                if n > PER_RULE:
                    print(f"    {rule:<11} {file}: {n - PER_RULE} more")
        print(f"scanned {len(files)} file(s). Names (people, rooms, devices, networks) are found only with --deny.")
    return 1 if must or (args.strict and (look or id_keys)) else 0


if __name__ == "__main__":
    sys.exit(main())
