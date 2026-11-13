"""Offline guard tests: no writer, HTTP, Git push or Netlify deploy."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest
import io
import subprocess
from contextlib import redirect_stdout
from unittest.mock import patch

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
        self.assertIn('c6_neon_git_pilot:', workflow)
        self.assertIn('ONE separately owner-approved manual', workflow)
        self.assertIn("github.ref == 'refs/heads/main'", workflow)
        self.assertIn("github.actor == 'olegbalakin-cmyk'", workflow)
        self.assertIn("vars.C6_GIT_ONLY_PUBLISHER_PAUSED == 'true'", workflow)
        self.assertIn("needs: [update-site, c6-neon-six-json-prepare]", workflow)
        self.assertIn("NETLIFY_DEPLOYMENTS_PER_UPDATE: '0'", workflow)
        self.assertIn("C6_AUTO_NEON_GIT_ENABLED: ${{", workflow)
        self.assertNotIn("netlify deploy", workflow.lower())
        netlify = (ROOT / ".github/workflows/netlify-production.yml").read_text()
        only_push = netlify.split("  push:", 1)[1].split("concurrency:", 1)[0]
        self.assertNotIn("data/**", only_push)
        self.assertNotIn("grafana/dashboard.json", only_push)

    def test_manual_pilot_is_default_off_and_solely_isolated(self):
        # YAML is parsed in CI with PyYAML; this stdlib test enforces the
        # exact gating contract even when standalone unit tests run.
        import re
        w = (ROOT / ".github/workflows/update-netlify-site.yml").read_text()
        pilot = re.search(
            r"^      c6_neon_git_pilot:\n(?P<body>(?:        .+\n)+)", w,
            re.MULTILINE,
        )
        self.assertIsNotNone(pilot)
        self.assertIn("type: boolean", pilot["body"])
        self.assertIn("required: true", pilot["body"])
        self.assertIn("default: false", pilot["body"])
        for job in ("update-site", "c6-neon-six-json-prepare",
                    "c6-neon-auto-git-publish"):
            section = w.split(f"  {job}:\n", 1)[1]
            match = re.search(r"^    if: (?P<gate>.+)$", section, re.MULTILINE)
            self.assertIsNotNone(match, job)
            gate = match["gate"]
            self.assertIn("inputs.c6_neon_git_pilot", gate, job)
            self.assertIn("C6_GIT_ONLY_PUBLISHER_PAUSED == 'true'", gate, job)
            self.assertIn("refs/heads/main", gate, job)
            self.assertIn("olegbalakin-cmyk", gate, job)
        self.assertIn("test \"$GITHUB_ACTOR\" = \"olegbalakin-cmyk\"", w)
        self.assertIn("test \"$LEGACY_PAUSED\" = \"true\"", w)
        self.assertIn("test \"$AUTO_ENABLED\" != \"true\"", w)
        self.assertIn("if: ${{ vars.C6_AUTO_NEON_GIT_ENABLED != 'true' && !inputs.c6_neon_git_pilot }}", w)
        self.assertIn("&& !inputs.c6_neon_git_pilot", w)
        self.assertIn("NETLIFY_DEPLOYMENTS_PER_UPDATE: '0'", w)
        self.assertNotIn("netlify deploy", w.lower())

    def test_manual_pilot_capture_not_schedule_only(self):
        w = (ROOT / ".github/workflows/update-netlify-site.yml").read_text()
        section = w.split("      - name: Require C2 same-run Neon bundle", 1)[1].split(
            "      - name: Checkout exact same-run integration scripts", 1)[0]
        self.assertIn("if [ \"$GITHUB_EVENT_NAME\" = \"workflow_dispatch\" ]; then", section)
        self.assertIn('test "$PILOT_INPUT" = "true"', section)
        self.assertIn('test "$GITHUB_EVENT_NAME" = "schedule"', section)
        self.assertIn("NEON_SUCCEEDED", section)
        self.assertIn("c2-shadow-inputs.zip.sha256", section)
        # No old schedule-only guard must run before C2 delta capture.
        self.assertNotIn('test "${{ github.event_name }}" = "schedule"', section)

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
        self.assertFalse(auto.retains_keys([{"id": 1}], [{"id": 2}]))


    def test_capture_reason_is_visible_without_raw_exception(self):
        for exception, expected in (
            (auto.Blocked("C2_WRITER_RECEIPT_NOT_PASS"), "C2_WRITER_RECEIPT_NOT_PASS"),
            (auto.Blocked("C2_GENERATION_NOT_UPDATED"), "C2_GENERATION_NOT_UPDATED"),
            (auto.Blocked("unsafe /tmp/secret=token"), "VALIDATION_BLOCKED"),
            (auto.Blocked("NEON_DATABASE_URL_SECRET123"), "VALIDATION_BLOCKED"),
            (auto.Blocked("UNKNOWN_CAPTURE_GUARD"), "VALIDATION_BLOCKED"),
            (OSError("/tmp/private/connection"), "IO_FAILED"),
            (KeyError("secret_key"), "INVALID_INPUT"),
            (subprocess.CalledProcessError(1, ["git", "secret"]), "SUBPROCESS_FAILED"),
        ):
            self.assertEqual(auto.safe_block_reason(exception), expected)

    def test_cli_unknown_uppercase_block_reason_is_redacted(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            with patch("sys.argv", [
                "c6_neon_auto_git.py", "capture",
                "--checkout", str(root), "--output", str(root / "out"),
                "--status", str(root / "status.json"),
                "--input-sha", "a" * 40, "--workflow-sha", "b" * 40,
                "--run-id", "43510482714", "--run-attempt", "1",
            ]), patch.object(auto, "capture", side_effect=auto.Blocked(
                    "NEON_DATABASE_URL_SECRET123")):
                out = io.StringIO()
                with redirect_stdout(out):
                    self.assertEqual(auto.main(), 2)
                self.assertIn("C6_BLOCK_REASON=VALIDATION_BLOCKED", out.getvalue())
                self.assertIn("ZERO_GIT_PUBLICATION_BY_THIS_RUN", out.getvalue())
                self.assertNotIn("NEON_DATABASE_URL_SECRET123", out.getvalue())

    def test_cli_capture_failure_reports_only_allowlisted_reason(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            with patch("sys.argv", [
                "c6_neon_auto_git.py", "capture",
                "--checkout", str(root), "--output", str(root / "out"),
                "--status", str(root / "status.json"),
                "--input-sha", "a" * 40, "--workflow-sha", "b" * 40,
                "--run-id", "43510482714", "--run-attempt", "1",
            ]), patch.object(auto, "capture", side_effect=auto.Blocked(
                    "C2_GENERATION_NOT_UPDATED")):
                out = io.StringIO()
                with redirect_stdout(out):
                    self.assertEqual(auto.main(), 2)
                self.assertIn("C6_BLOCK_REASON=C2_GENERATION_NOT_UPDATED", out.getvalue())
                self.assertIn("ZERO_GIT_PUBLICATION_BY_THIS_RUN", out.getvalue())

    def test_cli_does_not_leak_sensitive_error_details(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            with patch("sys.argv", [
                "c6_neon_auto_git.py", "capture",
                "--checkout", str(root), "--output", str(root / "out"),
                "--status", str(root / "status.json"),
                "--input-sha", "a" * 40, "--workflow-sha", "b" * 40,
                "--run-id", "43510482714", "--run-attempt", "1",
            ]), patch.object(auto, "capture", side_effect=OSError(
                    "private NEON_DATABASE_URL=secret")):
                out = io.StringIO()
                with redirect_stdout(out):
                    self.assertEqual(auto.main(), 2)
                self.assertIn("C6_BLOCK_REASON=IO_FAILED", out.getvalue())
                self.assertNotIn("NEON_DATABASE_URL", out.getvalue())
                self.assertNotIn("secret", out.getvalue())

    def test_offline_capture_replay_with_valid_status_and_dirty_delta(self):
        with TemporaryDirectory() as temp:
            base = Path(temp)
            checkout = base / "repo"
            checkout.mkdir()
            def run(*args):
                return subprocess.check_output(
                    ["git", "-C", str(checkout), *args], text=True).strip()
            run("init", "-q")
            run("checkout", "-q", "-b", "site-prod")
            run("config", "user.name", "C6 offline")
            run("config", "user.email", "c6@example.invalid")
            dashboard = checkout / auto.PREFIX / "dashboard_data.json"
            checkpoint = checkout / auto.PREFIX / "c2_history_capture_checkpoints.json"
            dashboard.parent.mkdir(parents=True)
            dashboard.write_text('{"old":true}\\n')
            checkpoint.write_text('{"kyiv":{}}\\n')
            run("add", ".")
            run("commit", "-qm", "fixture baseline")
            head = run("rev-parse", "HEAD")
            dashboard.write_text('{"new":true}\\n')
            checkpoint.write_text('{"kyiv":{"run":43510482714}}\\n')
            status = base / "status.json"
            status.write_text(json.dumps({
                "canonical_persistence_status": "NEON_SUCCEEDED",
                "canonical_receipt_validated": True,
                "workflow_sha": "b" * 40,
                "input_sha": head,
            }))
            output = base / "delta"
            manifest = auto.capture(
                checkout, output, input_sha=head,
                workflow_sha="b" * 40, run_id=43510482714,
                run_attempt=1, status_path=status)
            self.assertEqual(set(manifest["files"]), {
                auto.PREFIX + "dashboard_data.json",
                auto.PREFIX + "c2_history_capture_checkpoints.json",
            })
            self.assertEqual(run("rev-parse", "HEAD"), head)
            self.assertFalse((checkout / ".git" / "refs" / "remotes").exists())
            self.assertTrue((output / "manifest.json").is_file())


if __name__ == "__main__":
    unittest.main()
