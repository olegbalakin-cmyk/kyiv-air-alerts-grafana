import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import differentiated_alert_source_capture as capture
import differentiated_alert_shadow_runtime as runtime

NOW = datetime(2026, 10, 2, 6, 0, tzinfo=timezone.utc)


class FakeStore:
    def __init__(self, target):
        self.snapshots = {}
        self.observations = {}
    def persist(self, record):
        s = record["snapshot"]
        before_s = len(self.snapshots)
        before_o = len(self.observations)
        self.snapshots.setdefault(s["snapshot_key"], s)
        for row in record.get("threat_observations", []):
            self.observations.setdefault(row["observation_key"], row)
        return {
            "inserted_snapshots": len(self.snapshots) - before_s,
            "inserted_observations": len(self.observations) - before_o,
        }
    def counts(self):
        return {"snapshots": len(self.snapshots), "observations": len(self.observations)}
    def close(self):
        pass


def upstream_payloads():
    kyiv = {
        "current": {"state": 1, "causes": ["drone"], "last_cause": "drone", "created_at": "2026-10-02 08:30:00"},
        "stats": {"total_alerts": 2600},
    }
    ua = [
        {
            "regionId": "147", "regionType": "District", "regionName": "Бердянський район",
            "activeAlerts": [{
                "regionId": "147", "regionType": "District", "type": "AIR",
                "lastUpdate": "2026-10-02T05:30:00Z",
                "activeAlertLevels": [
                    {"alertLevel": "Yellow", "reason": "Дронова загроза (жовтий рівень)", "createdAt": "2026-10-02T05:20:00Z"}
                ],
            }],
        }
    ]
    aiu = {
        "source": "alerts.in.ua API", "cachedat": "2026-10-02T05:31:00Z",
        "raw": [{
            "id": 300001, "location_title": "Донецький район", "location_type": "raion",
            "location_uid": "53", "started_at": "2026-10-02T05:15:00Z", "finished_at": None,
            "updated_at": "2026-10-02T05:31:00Z", "alert_type": "air_raid",
            "alert_level": "red",
            "threats": [{"threat_type": "unspecified_missiles", "level": "red",
                         "started_at": "2026-10-02T05:25:00Z",
                         "source_message": "Ракетна загроза (червоний рівень)"}],
        }],
    }
    return {capture.KYIV_URL: kyiv, capture.UA_URL: ua, capture.AIU_URL: aiu}


class SourceSeamProof(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.paths = {
            runtime.KYIV_INPUT_ENV: str(base / "kyiv.json"),
            runtime.UA_INPUT_ENV: str(base / "ua.json"),
            runtime.AIU_INPUT_ENV: str(base / "aiu.json"),
        }
        self.requests = []
        payloads = upstream_payloads()
        def fetch(url, *, headers, timeout):
            self.requests.append(url)
            return 200, payloads[url]
        self.fetch = fetch

    def capture_env(self, shadow="0"):
        return {
            capture.CAPTURE_ENV: "1",
            capture.UA_TOKEN_ENV: "secret-not-printed",
            runtime.FEATURE_FLAG: shadow,
            **self.paths,
        }

    def shadow_env(self):
        return {
            runtime.FEATURE_FLAG: "1",
            runtime.DB_ENV: "fake",
            runtime.INPUT_MODE_ENV: runtime.STORED_ONLY_MODE,
            **self.paths,
        }

    def product_hash(self, p):
        return hashlib.sha256(Path(p).read_bytes()).hexdigest()

    def test_control_capture_off_shadow_off_zero_requests(self):
        r = capture.capture_sources(env={capture.CAPTURE_ENV: "0"}, fetch=self.fetch)
        self.assertEqual(r["status"], "DISABLED")
        self.assertEqual(self.requests, [])
        self.assertEqual(sum(r["logical_acquisition_counts"].values()), 0)

    def test_capture_only_and_capture_plus_shadow_request_counts_match(self):
        product = Path(self.tmp.name) / "product.json"
        product.write_text('{"authoritative":true}\n', encoding="utf-8")
        h0 = self.product_hash(product)

        b = capture.capture_sources(env=self.capture_env("0"), fetch=self.fetch, captured_at="2026-10-02T06:00:00Z")
        b_counts = dict(b["logical_acquisition_counts"])
        b_hashes = {k: v["sha256"] for k, v in b["sources"].items()}
        self.assertEqual(b["status"], "SUCCEEDED")
        self.assertEqual(b_counts, {"kyiv_official": 1, "ukrainealarm": 1, "alerts_in_ua": 1})
        self.assertEqual(self.product_hash(product), h0)

        self.requests.clear()
        c = capture.capture_sources(env=self.capture_env("1"), fetch=self.fetch, captured_at="2026-10-02T06:00:00Z")
        c_counts = dict(c["logical_acquisition_counts"])
        self.assertEqual(c_counts, b_counts)
        self.assertEqual({k: v["sha256"] for k, v in c["sources"].items()}, b_hashes)

        sidecar_fetches = []
        def forbidden_fetch(url, timeout):
            sidecar_fetches.append(url)
            raise AssertionError("stored_only sidecar attempted network")
        sr = runtime.run_shadow(
            [], env=self.shadow_env(), fetch_json=forbidden_fetch,
            store_factory=FakeStore, now=NOW,
        )
        self.assertEqual(sr["status"], "SUCCEEDED")
        self.assertEqual(sidecar_fetches, [])
        self.assertEqual(sr["sidecar_network_requests"], 0)
        self.assertEqual(self.product_hash(product), h0)

    def test_stored_only_missing_input_is_explicit_and_never_opens_store(self):
        capture.capture_sources(env=self.capture_env("0"), fetch=self.fetch)
        Path(self.paths[runtime.AIU_INPUT_ENV]).unlink()
        touched = {"store": 0, "fetch": 0}
        def bad_store(target):
            touched["store"] += 1
            raise AssertionError("store must not open")
        def bad_fetch(url, timeout):
            touched["fetch"] += 1
            raise AssertionError("network must not run")
        r = runtime.run_shadow([], env=self.shadow_env(), fetch_json=bad_fetch, store_factory=bad_store, now=NOW)
        self.assertEqual(r["status"], "FAILED")
        self.assertEqual(r["stored_input_error"]["source"], "alerts_in_ua")
        self.assertEqual(r["sidecar_network_requests"], 0)
        self.assertEqual(touched, {"store": 0, "fetch": 0})

    def test_capture_failure_is_fail_open_and_identifies_source(self):
        product = Path(self.tmp.name) / "product.json"
        product.write_text('{"authoritative":true}\n', encoding="utf-8")
        before = self.product_hash(product)
        payloads = upstream_payloads()
        def flaky(url, *, headers, timeout):
            if url == capture.UA_URL:
                raise OSError("forced transport failure")
            return 200, payloads[url]
        r = capture.capture_sources(env=self.capture_env("0"), fetch=flaky)
        self.assertEqual(r["status"], "PARTIAL_FAILURE")
        self.assertEqual(r["sources"]["ukrainealarm"]["status"], "FAILED")
        self.assertEqual(r["sources"]["ukrainealarm"]["error_type"], "OSError")
        self.assertFalse(r["credentials_exposed"])
        self.assertEqual(self.product_hash(product), before)

    def test_exact_source_object_selection_is_mechanical(self):
        payloads = upstream_payloads()
        env = self.capture_env("0")
        r = capture.capture_sources(env=env, fetch=self.fetch)
        self.assertEqual(r["status"], "SUCCEEDED")
        ua = json.loads(Path(self.paths[runtime.UA_INPUT_ENV]).read_text(encoding="utf-8"))
        aiu = json.loads(Path(self.paths[runtime.AIU_INPUT_ENV]).read_text(encoding="utf-8"))
        self.assertEqual(str(ua["regionId"]), "147")
        self.assertEqual(str(aiu["location_uid"]), "53")
        self.assertEqual(aiu["location_title"], "Донецький район")


if __name__ == "__main__":
    unittest.main(verbosity=2)
