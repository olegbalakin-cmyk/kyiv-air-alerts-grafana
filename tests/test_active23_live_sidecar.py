"""No-network C2 active-23 source-at-capture gate regression.

The C2 bundle is a pinned public Actions artifact. Tests are fully offline and
cannot write Neon, Git, Netlify, or any live status endpoint.
"""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import io
import json
from tempfile import TemporaryDirectory
import os
import unittest
import zipfile

from scripts import active23_live_sidecar as active
from scripts import c6_neon_auto_git as publish
from scripts import c6_neon_release_binding as release

BUNDLE = os.environ.get("ACTIVE23_BUNDLE", "")
REQUIRED = set(active.EXPECTED_KEYS)


def evidence():
    if not BUNDLE:
        raise unittest.SkipTest("immutable C2 test bundle not provided")
    raw = Path(BUNDLE).read_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        manifest = json.loads(z.read("manifest.json"))
        payload = json.loads(z.read("payload.json"))
    clocks = [active.at(x["last_checked_at"])
              for x in payload["historical_source_receipts"].values()]
    return raw, manifest, max(clocks) + timedelta(minutes=1)


class VerifiedSourceCaptureTests(unittest.TestCase):
    def test_real_same_run_23_city_and_no_open(self):
        raw, manifest, now = evidence()
        self.assertEqual(manifest["github_run_id"], 44680696823)
        self.assertEqual(manifest["github_run_attempt"], 1)
        output = active.build(raw, sha256(raw).hexdigest(),
                              44680696823, 1, as_of=now)
        self.assertEqual(output["schema"], "c6-active-23-source-capture-v1")
        self.assertEqual(output["capture_scope"],
                         "observed_at_last_collection_not_live")
        self.assertEqual(output["source_generated_at"],
                         "2026-11-20T07:24:02.945726+02:00")
        self.assertTrue(output["publication_allowed"])
        self.assertFalse(output["test_only"])
        self.assertEqual(output["count_cities"], 23)
        self.assertEqual(output["count_source_open"], 22)
        self.assertEqual(output["count_source_no_open"], 1)
        self.assertEqual(set(output["cities"]), REQUIRED)
        self.assertEqual(output["cities"]["sevastopol"]["state"],
                         "no_open_at_source_capture")
        self.assertIsNone(output["cities"]["sevastopol"]["start_at"])
        self.assertEqual(output["cities"]["sevastopol"]
                         ["provisional_seconds_today"], 0)
        self.assertEqual(output["cities"]["kyiv"]["state"],
                         "open_at_source_capture")
        self.assertEqual(active.at(output["cities"]["kyiv"]["start_at"])
                         .astimezone(active.KYIV).date().isoformat(),
                         "2026-11-20")
        self.assertEqual(output["c2_corpus_sha256"], manifest["corpus_sha256"])
        self.assertEqual(output["archive_sha256"], sha256(raw).hexdigest())
        for city, row in output["cities"].items():
            self.assertEqual(row["city_key"], city)
            self.assertEqual(row["date"], "2026-11-20")
            self.assertEqual(row["periods"]["day"]["through"], "2026-11-20")
            for period in row["periods"].values():
                self.assertAlmostEqual(
                    period["closed_seconds"] + period["provisional_seconds"],
                    period["combined_seconds"], places=2)

    def test_exact_publication_binding_and_fail_closed(self):
        raw, manifest, now = evidence()
        snapshot = active.build(raw, sha256(raw).hexdigest(),
                                44680696823, 1, as_of=now)
        report = {"c2_run_id": 44680696823,
                  "c2_run_attempt": 1,
                  "c2_corpus_sha256": manifest["corpus_sha256"],
                  "c2_bundle_sha256": sha256(raw).hexdigest()}
        published = {"meta": {"generated_at": snapshot["source_generated_at"]},
                     "multicity_meta": {"production_city_keys": sorted(REQUIRED)}}
        derived = {"meta": {
            "generated_at": snapshot["source_generated_at"],
            "publication_authority": {"release_manifest_sha256": "f" * 64}}}
        # Same-run C2 derived timestamp predates Neon physical readback.
        # Correct release binding MUST NOT demand equal dashboard time.
        published["meta"]["generated_at"] = "2026-11-20T07:51:25.265359+02:00"
        source_hashes = {
            "dashboard_data.json": manifest["files"]["site_data/dashboard_data.json"],
            "site_derived.json": manifest["files"]["site_data/site_derived.json"],
        }
        result = publish.verify_active23_sidecar(
            snapshot, report, published, derived, source_hashes, "f" * 64, now=now)
        self.assertEqual(result["release_manifest_sha256"], "f" * 64)
        self.assertEqual(result["delivery"], "site-prod-git")
        self.assertFalse(result["authoritative_live_status"])
        bad = {**snapshot, "source_generated_at": "2026-11-19"}
        with self.assertRaisesRegex(publish.Blocked, "ACTIVE23_SAME_RUN_BINDING"):
            publish.verify_active23_sidecar(
                bad, report, published, derived, source_hashes, "f" * 64, now=now)
        bad = {**snapshot, "same_run_derived_sha256": "0" * 64}
        with self.assertRaisesRegex(publish.Blocked, "ACTIVE23_SAME_RUN_BINDING"):
            publish.verify_active23_sidecar(
                bad, report, published, derived, source_hashes, "f" * 64, now=now)
        with self.assertRaisesRegex(publish.Blocked, "ACTIVE23_SOURCE_STALE"):
            publish.verify_active23_sidecar(
                snapshot, report, published, derived, source_hashes, "f" * 64,
                now=now + timedelta(hours=9))
        self.assertTrue(publish.allowed(publish.ACTIVE23_PATH))
        self.assertNotIn(publish.ACTIVE23_PATH, publish.DELIVERED)

    def test_real_six_json_release_generation_binding(self):
        """Physical C6 preparation artifacts: two different generated_at stamps.

        No database, network, Git push or Netlify calls during the test.
        """
        prepared_dir = os.environ.get("ACTIVE23_C6_PREPARED_DIR")
        if not prepared_dir:
            raise unittest.SkipTest("real C6 six-file preparation not supplied")
        raw, manifest, now = evidence()
        snapshot = active.build(raw, sha256(raw).hexdigest(),
                                44680696823, 1, as_of=now)
        prepared = Path(prepared_dir)
        report = json.loads((prepared / "REPORT.json").read_text())
        self.assertEqual(report["c2_run_id"], 44680696823)
        self.assertEqual(report["c2_bundle_sha256"], sha256(raw).hexdigest())
        with TemporaryDirectory() as temp:
            out = Path(temp) / "released"
            release.release_candidate(
                prepared, report, repository=publish.REPOSITORY,
                release_id="active23-offline-20261120", output=out)
            emitted = json.loads((out / "RELEASE_MANIFEST.json").read_text())
            path = out / "candidate"
            candidate = publish.candidate.FILES
            dashboard = json.loads((path / candidate["dashboard_data.json"]).read_text())
            derived = json.loads((path / candidate["site_derived.json"]).read_text())
            self.assertNotEqual(dashboard["meta"]["generated_at"],
                                derived["meta"]["generated_at"])
            self.assertEqual(snapshot["source_generated_at"],
                             derived["meta"]["generated_at"])
            binding = emitted["release_manifest_sha256"]
            verified = publish.verify_active23_sidecar(
                snapshot, report, dashboard, derived,
                {"dashboard_data.json":
                    manifest["files"]["site_data/dashboard_data.json"],
                 "site_derived.json":
                    manifest["files"]["site_data/site_derived.json"]},
                binding, now=now)
            self.assertEqual(verified["release_manifest_sha256"], binding)
            self.assertEqual(verified["count_cities"], 23)
            self.assertFalse(verified["authoritative_live_status"])

    def test_stale_snapshot_is_never_publishable(self):
        raw, _, now = evidence()
        with self.assertRaisesRegex(ValueError, "STALE_OR_FUTURE_SOURCE_CAPTURE"):
            active.build(raw, sha256(raw).hexdigest(), 44680696823, 1,
                         as_of=now + timedelta(hours=9))

    def test_following_calendar_day_never_repeats_old_open(self):
        raw, _, now = evidence()
        # Even before the 8h boundary, crossing local midnight is blocked.
        after = datetime(2026, 11, 21, 0, 1, tzinfo=active.KYIV)
        with self.assertRaisesRegex(
                ValueError, "STALE_OR_FUTURE_SOURCE_CAPTURE|INCONSISTENT_CURRENT_KYIV_DAY"):
            active.build(raw, sha256(raw).hexdigest(), 44680696823, 1,
                         as_of=after)

    def test_wrong_digest_fails_before_source_processing(self):
        raw, _, now = evidence()
        with self.assertRaisesRegex(ValueError, "IMMUTABLE_C2_ARCHIVE_SHA_MISMATCH"):
            active.build(raw, "0" * 64, 44680696823, 1, as_of=now)

    def test_wrong_run_attempt_blocks(self):
        raw, _, now = evidence()
        with self.assertRaisesRegex(ValueError, "C2_ARCHIVE_ID_OR_23_CITIES"):
            active.build(raw, sha256(raw).hexdigest(), 44680696823, 2,
                         as_of=now)


if __name__ == "__main__":
    unittest.main()
