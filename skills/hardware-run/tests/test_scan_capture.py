"""scan_capture.py against made-up captures.

Values that look like real addresses are put together at run time, so that this file holds none:
the repository's own privacy scan reads it too.
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import scan_capture as sc  # noqa: E402

LAN_IP = ".".join(["10", "20", "30", "40"])
PUBLIC_IP = ".".join(["8", "8", "4", "4"])
DOC_IP = "192.0.2.7"
REAL_MAC = ":".join(["A4", "5E", "60", "01", "02", "03"])
DOC_MAC = "00:00:5E:00:53:0A"
MAIL = "owner" + "@" + "mail.test"
UUID = "-".join(["72d0aab4", "2ed8", "4644", "84d2", "0031bdae356e"])
FOUR_PART_VERSION = ".".join("1234")  # a build number after a three-part version parses as an address
GLOBAL_V6 = ":".join(["2606", "4700", "", "1111"])


def scan(doc: object | str, *args: str, name: str = "capture.json") -> tuple[int, dict]:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / name
        path.write_text(doc if isinstance(doc, str) else json.dumps(doc), encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = sc.main([str(path), "--json", *args])
        report = json.loads(out.getvalue()) if out.getvalue() else {}
    return code, report


def rules(report: dict, group: str = "must_fix") -> list[tuple[str, str]]:
    return [(f["where"].split(":", 1)[1], f["rule"]) for f in report[group]]


class MustFixTests(unittest.TestCase):
    def test_a_clean_capture_passes(self):
        code, report = scan({"name": "tv-1", "port": 8000, "at": "2026-01-02T12:30:00+00:00",
                             "url": "https://mcp.example.com/x", "contact": "user@example.com",
                             "host": DOC_IP, "v6": "2001:db8::1", "hw": DOC_MAC,
                             "none": "00000000-0000-0000-0000-000000000000"})
        self.assertEqual((code, report["must_fix"]), (0, []))

    def test_an_email_in_the_middle_of_a_value_is_found(self):
        # The case a key list misses: the address sits inside a longer value under a harmless key.
        code, report = scan({"global": {"stamp": f"{{abc}};{MAIL};2026"}})
        self.assertEqual((code, rules(report)), (1, [("global.stamp", "email")]))

    def test_addresses_of_each_kind(self):
        code, report = scan({"a": LAN_IP, "b": f"http://{PUBLIC_IP}:8080/x", "c": REAL_MAC,
                             "d": REAL_MAC.replace(":", "-").lower(), "e": GLOBAL_V6, "f": f"key/{UUID.upper()}.png"})
        self.assertEqual(code, 1)
        self.assertEqual(rules(report), [("a", "ip"), ("b", "ip"), ("c", "mac"), ("d", "mac"), ("e", "ip"), ("f", "uuid")])

    def test_a_mac_is_not_also_reported_as_an_ipv6_address(self):
        _, report = scan({"c": REAL_MAC})
        self.assertEqual(rules(report), [("c", "mac")])

    def test_versions_and_times_are_not_addresses(self):
        code, report = scan({"firmware_version": "4.15.600.2", "sw": FOUR_PART_VERSION, "time": "12:30:00",
                             "range": "0::", "ratio": "16:9", "version": "300.1.1.1"})
        self.assertEqual((code, report["must_fix"]), (0, []))

    def test_a_string_that_holds_json_is_opened(self):
        code, report = scan({"device": [{"action": json.dumps({"command": "VolumeUp", "target": LAN_IP})}]})
        self.assertEqual((code, rules(report)), (1, [("device[0].action<json>.target", "ip")]))

    def test_a_credential_key_with_a_value_must_be_fixed_and_a_masked_one_is_skipped(self):
        code, report = scan({"auth": {"password": "hunter2", "api_key": "<redacted>", "token": "", "secret": None,
                                      "refreshToken": "***"}})
        self.assertEqual((code, rules(report)), (1, [("auth.password", "secret-key")]))

    def test_deny_terms_are_found_without_regard_to_case_and_reported_by_position(self):
        with tempfile.TemporaryDirectory() as tmp:
            deny = Path(tmp) / "deny.txt"
            deny.write_text("# names\nfront room\n\nplumbus\n", encoding="utf-8")
            code, report = scan({"label": "Front Room TV", "model": "Plumbus 9"}, "--deny", str(deny))
        self.assertEqual((code, rules(report)), (1, [("label", "deny #1"), ("model", "deny #2")]))

    def test_values_are_printed_only_with_show(self):
        _, quiet = scan({"a": LAN_IP})
        _, shown = scan({"a": LAN_IP}, "--show")
        self.assertNotIn("value", quiet["must_fix"][0])
        self.assertEqual(shown["must_fix"][0]["value"], LAN_IP)
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(out):
            path = Path(tmp) / "c.json"
            path.write_text(json.dumps({"a": LAN_IP}), encoding="utf-8")
            sc.main([str(path)])
        self.assertNotIn(LAN_IP, out.getvalue())
        self.assertIn("ip", out.getvalue())


class LookAtTests(unittest.TestCase):
    def test_identity_keys_are_reported_once_per_key_and_do_not_fail(self):
        code, report = scan({"hub": {"serial": "SN123", "hubId": "771", "tz": "UTC+1"},
                             "devices": [{"serial": "SN124", "id": "5", "deviceId": "9"}]})
        self.assertEqual(code, 0)
        self.assertEqual(report["must_fix"], [])
        found = sorted(f["where"].split(": ", 1)[1] for f in report["look_at"])
        self.assertEqual(found, [
            "key 'hubId' has a value in 1 place(s), first at hub.hubId",
            "key 'serial' has a value in 2 place(s), first at hub.serial",
            "key 'tz' has a value in 1 place(s), first at hub.tz",
        ])

    def test_strict_fails_on_them(self):
        code, _ = scan({"hub": {"serial": "SN123"}}, "--strict")
        self.assertEqual(code, 1)

    def test_an_opaque_token_is_reported_and_an_ordinary_long_name_is_not(self):
        token = "9f8e7d6c5b4a" + "39281706f5e4"
        _, report = scan({"hash": token, "command": "Audio2EQ/Multi/MusicModeOn", "label": "InputHdmiArcSelectTheLongOne"})
        self.assertEqual(rules(report, "look_at"), [("hash", "opaque")])

    def test_a_masked_identity_key_is_not_reported(self):
        _, report = scan({"account": "<redacted>", "email": "", "uuid": "<masked>"})
        self.assertEqual(report["look_at"], [])


class FileTests(unittest.TestCase):
    def test_a_log_is_read_line_by_line(self):
        code, report = scan(f"connect ok\nws://{LAN_IP}:8088/ open\nbye {MAIL}\n", name="debug.log")
        self.assertEqual(code, 1)
        self.assertEqual(rules(report), [("2", "ip"), ("3", "email")])

    def test_one_json_document_per_line(self):
        code, report = scan(json.dumps({"topic": "up"}) + "\n" + json.dumps({"topic": REAL_MAC + "/up"}) + "\n",
                            name="messages.jsonl")
        self.assertEqual((code, rules(report)), (1, [("[line 2].topic", "mac")]))

    def test_a_directory_is_walked_and_a_binary_file_is_named_not_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.json").write_text(json.dumps({"ok": True}), encoding="utf-8")
            (Path(tmp) / "sub").mkdir()
            (Path(tmp) / "sub" / "b.bin").write_bytes(b"\0\1\2")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = sc.main([tmp, "--json"])
        report = json.loads(out.getvalue())
        self.assertEqual((code, report["files"]), (1, 2))
        self.assertIn("binary", report["must_fix"][0]["rule"])

    def test_a_missing_path_or_deny_file_is_a_usage_error(self):
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(sc.main(["/no/such/capture.json"]), 2)
            self.assertIn("no such file", err.getvalue())
        code, _ = scan({"a": 1}, "--deny", "/no/such/deny.txt")
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
