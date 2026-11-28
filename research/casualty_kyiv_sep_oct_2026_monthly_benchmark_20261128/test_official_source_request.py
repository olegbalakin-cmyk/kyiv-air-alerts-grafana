"""Request-only regression checks. No network, secrets or writes."""
import csv
import hashlib
import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).parent
NAME = "official_source_request_v2.json"


class OfficialSourceRequest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = (ROOT / NAME).read_bytes()
        cls.doc = json.loads(cls.raw)
        cls.targets = cls.doc["targets"]
        cls.by_url = {t["source_url"]: t for t in cls.targets}
        with (ROOT / "indexed_source_leads.csv").open(encoding="utf-8", newline="") as f:
            cls.leads = list(csv.DictReader(f))

    def test_digest(self):
        expected = (ROOT / "official_source_request_v2.sha256").read_text().split()[0]
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(), expected)

    def test_union(self):
        self.assertEqual(len(self.targets), 19)
        self.assertEqual(len(self.by_url), 19)
        self.assertEqual(len({t["id"] for t in self.targets}), 19)
        self.assertEqual(sum(len(t["source_refs"]) == 2 for t in self.targets), 2)
        expected = {"SEP23", "SEP24", "SEP25_OFFICE", "SEP25_CHILD", "SEP25_CITYWIDE",
                    "SEP27", "SEP28", "SEP30", "OCT07_PREDAWN", "OCT07_EVENING",
                    "OCT08_DAY", "OCT20"}
        self.assertEqual({ref[5:] for t in self.targets for ref in t["source_refs"]
                          if ref.startswith("#258:")}, expected)

    def test_all_indexed_leads(self):
        self.assertEqual(len(self.leads), 9)
        for lead in self.leads:
            self.assertIn("#263:" + lead["id"], self.by_url[lead["url"]]["source_refs"])

    def test_monthly_scope(self):
        self.assertEqual({t["id"] for t in self.targets
                          if t["purpose"] == "MONTHLY_METHODOLOGY_REVIEW"}, {"UN-SEP", "UN-OCT"})
        self.assertEqual(self.doc["review"]["scope_parity"], "UNVERIFIED")
        self.assertEqual(self.doc["review"]["month_completeness"], "UNVERIFIED")
        self.assertTrue(self.doc["review"]["monthly_benchmarks_are_nonadditive"])

    def test_allowlist_and_budget(self):
        hosts = set()
        for t in self.targets:
            p = urlsplit(t["source_url"])
            self.assertEqual(p.scheme, "https")
            self.assertFalse(p.username or p.password or p.port or p.query or p.fragment)
            hosts.add(p.hostname)
        self.assertEqual(hosts, set(self.doc["allowed_hosts"]))
        self.assertEqual(len(hosts), 5)
        g = self.doc["guard"]
        self.assertEqual(g["max_gets_after_separate_owner_go"], len(self.targets))
        self.assertEqual((g["max_per_exact_url"], g["timeout_seconds"], g["max_response_bytes"], g["concurrency"]),
                         (1, 15, 2 * 1024 * 1024, 1))
        self.assertEqual((g["method"], g["redirects"], g["retries"]), ("GET", "OFF", "OFF"))
        self.assertTrue(g["https_only"] and g["public_ip_only"])

    def test_no_execution_or_credit(self):
        d = self.doc
        self.assertEqual(d["authorization"], "NOT_GRANTED")
        self.assertFalse(d["allow_execute"] or d["publication_allowed"])
        self.assertEqual(d["PROMOTE"], "OFF")
        for key, value in d["guard"].items():
            if key.endswith("_writes") or key in {"publisher_gets_now", "rss_gets", "netlify_deploys", "automatic_credits"}:
                self.assertEqual(value, 0)
        self.assertTrue(all(not t["credit_allowed"] and t["body_state"] == "UNARCHIVED" for t in self.targets))

    def test_archive_required(self):
        a = self.doc["archive"]
        self.assertFalse(a["executor_ready"])
        self.assertTrue(all(a[k] for k in ("required_before_capture", "full_raw_and_decoded_bytes",
                                         "encrypted_private_only", "no_plaintext_in_repo_or_logs",
                                         "key_required_before_go_claim")))


if __name__ == "__main__":
    unittest.main()
