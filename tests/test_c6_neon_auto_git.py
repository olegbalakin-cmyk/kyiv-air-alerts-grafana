"""Offline guard tests: no writer, HTTP, Git push or Netlify deploy."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from scripts import c6_neon_auto_git as auto

ROOT = Path(__file__).resolve().parents[1]


class AutoGitOnlyTests(unittest.TestCase):
    def test_schedule_default_off_no_deploy(self):
        workflow = (ROOT / ".github/workflows/update-netlify-site.yml").read_text()
        self.assertIn('cron: "15 */4 * * *"', workflow)
        self.assertIn("vars.C6_AUTO_NEON_GIT_ENABLED == 'true'", workflow)
        self.assertIn("vars.C6_GIT_ONLY_PUBLISHER_PAUSED != 'true'", workflow)
        self.assertIn("C6_AUTO_NEON_GIT_ENABLED != 'true'", workflow)
        self.assertIn("c6-neon-auto-git-publish:", workflow)
        self.assertIn("needs: [update-site, c6-neon-six-json-prepare]", workflow)
        self.assertIn("NETLIFY_DEPLOYMENTS_PER_UPDATE: '0'", workflow)
        self.assertNotIn("netlify deploy", workflow.lower())
        netlify = (ROOT / ".github/workflows/netlify-production.yml").read_text()
        only_push = netlify.split("  push:", 1)[1].split("concurrency:", 1)[0]
        self.assertNotIn("data/**", only_push)
        self.assertNotIn("grafana/dashboard.json", only_push)

    def test_switch_and_zero_deploys_required(self):
        for enabled, count in [("", "0"), ("true", "1")]:
            with self.assertRaisesRegex(auto.Blocked, "AUTO_MODE_DISABLED_OR_NETLIFY_NOT_ZERO"):
                auto.publish("missing", "missing", "missing", "missing",
                             repository=auto.REPOSITORY, workflow_sha="x",
                             run_id=1, run_attempt=1, enabled=enabled,
                             zero_deploys=count)

    def test_allowlisted_data_only(self):
        for path in (
            "kyiv-air-alerts-grafana/data/dashboard_data.json",
            "kyiv-air-alerts-grafana/data/c2_history_capture_checkpoints.json",
            "kyiv-air-alerts-grafana/data/casualties/review_queue.json",
            auto.GRAFANA,
        ):
            self.assertTrue(auto.allowed(path), path)
        for path in (
            "historical-daily-kpi.json", "netlify.toml",
            "kyiv-air-alerts-grafana/pages-preview/app.js",
            ".github/workflows/netlify-production.yml",
            "kyiv-air-alerts-grafana/data/../../netlify.toml",
        ):
            self.assertFalse(auto.allowed(path), path)

    def test_exact_c2_manifest_and_sha(self):
        with TemporaryDirectory() as t:
            d = Path(t)
            key = auto.PREFIX + "dashboard_data.json"
            p = d / "files" / key
            p.parent.mkdir(parents=True)
            p.write_text('{"cities":{}}')
            manifest = {
                "schema": auto.SCHEMA, "input_sha": "a" * 40,
                "workflow_sha": "b" * 40, "run_id": 12,
                "run_attempt": 1, "netlify_deployments_per_update": 0,
                "git_publication_performed": False, "files": {key: "0" * 64},
            }
            (d / "manifest.json").write_text(json.dumps(manifest))
            receipt = {"c2_input_sha": "a" * 40, "c2_workflow_sha": "b" * 40,
                       "c2_run_id": 12, "c2_run_attempt": 1}
            with self.assertRaisesRegex(auto.Blocked, "C2_DELTA_SHA_MISMATCH"):
                auto.verify_capture(d, receipt, workflow_sha="b" * 40,
                                    run_id=12, run_attempt=1)
            manifest["files"][key] = auto.sha(p)
            (d / "manifest.json").write_text(json.dumps(manifest))
            self.assertEqual(auto.verify_capture(
                d, receipt, workflow_sha="b" * 40,
                run_id=12, run_attempt=1), manifest["files"])
            receipt["c2_run_id"] = 13
            with self.assertRaisesRegex(auto.Blocked, "C2_DELTA_IDENTITY_MISMATCH"):
                auto.verify_capture(d, receipt, workflow_sha="b" * 40,
                                    run_id=12, run_attempt=1)

    def test_checkpoint_preservation(self):
        self.assertTrue(auto.retains_keys({"a": 1}, {"a": 2, "b": 3}))
        self.assertFalse(auto.retains_keys({"a": 1}, {"b": 3}))
        self.assertFalse(auto.retains_keys([1, 2], [1]))


if __name__ == "__main__":
    unittest.main()
