"""Pure offline tests for final release binding, no Git push or live credentials."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts import c6_neon_git_candidate as candidate
from scripts import c6_neon_release_binding as release


class FinalBindingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.prepared = self.root / "prepared"
        self.research = self.prepared / "candidate"
        self.output = self.root / "release"
        self.cities = ["kyiv", "sevastopol"] + ["city_" + str(i) for i in range(21)]
        self.authority = {
            "publication_allowed": False,
            "scope": "RESEARCH_CANDIDATE_NOT_CURRENT_DATA_CERTIFICATION",
            "branch_id": "br-bold-mode-b5rub8pq",
            "historical_freshness": {"binding_sha256": "a" * 64},
            "dst_simulation": False, "source_fallback": False,
            "active_status": "UNKNOWN_UNCERTIFIED",
        }
        self.index = {"schema": "verified-historical-daily-start-counts-v1",
                      "meta": {"source_ref": "neon:br-bold-mode-b5rub8pq",
                               "source_dashboard_generated_at": "2026-11-12T19:00:00Z",
                               "verified_count": 23, "expected_cities": 23},
                      "cities": {city: {"status": "verified"} for city in self.cities}}
        self.dash = {
            "meta": {"generated_at": "2026-11-12T19:00:00Z",
                     "publication_authority": self.authority},
            "multicity_meta": {"production_city_keys": self.cities},
            "cities": {c: {} for c in self.cities},
            "historical_daily_kpi": self.index,
        }
        values = {
            "dashboard_data.json": self.dash,
            "site_derived.json": {"meta": {"publication_authority": self.authority}},
            "historical-daily-kpi.json": self.index,
            "alerts_combined.json": [{"start": "2026-01-01", "end": "2026-01-02"}],
            "kyiv_threat_mix.json": {"test": 1},
            "sevastopol_events.json": {"test": 2},
        }
        files = {}
        for name, rel in candidate.FILES.items():
            p = self.research / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(values[name]), encoding="utf-8")
            files[rel] = candidate.sha(p.read_bytes())
        self.report = {
            "state": candidate.STATE, "publication_allowed": False,
            "production_git_push_executed": False, "prepared_files": 6,
            "files": files, "neon_branch": "br-bold-mode-b5rub8pq",
            "c2_run_id": 123, "c2_run_attempt": 1,
            "c2_workflow_sha": "b" * 40, "c2_input_sha": "c" * 40,
            "c2_bundle_sha256": "d" * 64,
            "c2_corpus_sha256": "e" * 64,
        }

    def build(self):
        return release.release_candidate(
            self.prepared, self.report,
            repository="olegbalakin-cmyk/kyiv-air-alerts-grafana",
            release_id="release-20261112-01", output=self.output)

    def test_positive_contract_and_no_research_mutation(self):
        original = dict(self.report["files"])
        result = self.build()
        manifest = release.load(self.output / "RELEASE_MANIFEST.json")
        final = self.output / "candidate"
        dashboard = release.load(final / candidate.FILES["dashboard_data.json"])
        index = release.load(final / candidate.FILES["historical-daily-kpi.json"])
        derived = release.load(final / candidate.FILES["site_derived.json"])
        auth = dashboard["meta"]["publication_authority"]
        self.assertIs(auth["publication_allowed"], True)
        self.assertEqual(auth["scope"], "PRODUCTION_NEON_GIT_RELEASE")
        self.assertEqual(auth["delivery"], "site-prod-git")
        self.assertEqual(auth["release_manifest_sha256"], result["release_manifest_sha256"])
        self.assertEqual(index["meta"]["release_manifest_sha256"], result["release_manifest_sha256"])
        self.assertEqual(index["meta"]["verified_cities"], self.cities)
        self.assertEqual(dashboard["historical_daily_kpi"], index)
        self.assertEqual(derived["meta"]["publication_authority"], auth)
        self.assertEqual(manifest["files"], result["files"])
        self.assertEqual(original, self.report["files"])
        for rel, h in result["files"].items():
            self.assertEqual(candidate.sha((final / rel).read_bytes()), h)
        for rel in (candidate.FILES["kyiv_threat_mix.json"],
                    candidate.FILES["alerts_combined.json"],
                    candidate.FILES["sevastopol_events.json"]):
            self.assertEqual(result["files"][rel], original[rel])
        self.assertFalse(release.load(self.research / candidate.FILES["dashboard_data.json"])
                         ["meta"]["publication_authority"]["publication_allowed"])
        approval = {
            "release_manifest_sha256": result["release_manifest_sha256"],
            "approved_generation": result["generation"],
            "approved_netlify_static_kpi_sha256": result["files"]["historical-daily-kpi.json"],
            "final_files": result["files"]
        }
        self.assertEqual(release.verify_final(approval, result)["files"], result["files"])

    def test_modified_research_sha_blocks(self):
        self.report["files"][candidate.FILES["dashboard_data.json"]] = "0" * 64
        with self.assertRaisesRegex(candidate.Blocked, "RESEARCH_FILE_SHA_MISMATCH"):
            self.build()

    def test_final_sha_requires_separate_approval(self):
        result = self.build()
        with self.assertRaisesRegex(candidate.Blocked, "FINAL_SIX_SHA_NOT_APPROVED"):
            release.verify_final({"final_files": self.report["files"]}, result)

    def test_netlify_static_kpi_mismatch_blocks(self):
        result = self.build()
        approval = {"final_files": result["files"],
                    "release_manifest_sha256": result["release_manifest_sha256"],
                    "approved_generation": result["generation"],
                    "approved_netlify_static_kpi_sha256": "f" * 64}
        with self.assertRaisesRegex(candidate.Blocked, "FINAL_MANIFEST_OR_NETLIFY_KPI_MISMATCH"):
            release.verify_final(approval, result)

    def test_no_unauthorized_research_approval(self):
        self.dash["meta"]["publication_authority"]["publication_allowed"] = True
        p = self.research / candidate.FILES["dashboard_data.json"]
        p.write_text(json.dumps(self.dash))
        self.report["files"][candidate.FILES["dashboard_data.json"]] = candidate.sha(p.read_bytes())
        with self.assertRaisesRegex(candidate.Blocked, "RESEARCH_AUTHORITY_MISMATCH"):
            self.build()


if __name__ == "__main__":
    unittest.main()
