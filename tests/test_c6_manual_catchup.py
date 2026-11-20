"""No-network contract for owner-only catch-up through scheduled C6 path."""
import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github/workflows/update-netlify-site.yml"
SCHEDULE = "(github.event_name == 'schedule' && vars.C6_AUTO_NEON_GIT_ENABLED == 'true')"
MANUAL = ("(github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' "
          "&& github.actor == 'olegbalakin-cmyk' && inputs.c6_run_now "
          "&& !inputs.c6_neon_git_pilot && !inputs.c6_final_prepare_only "
          "&& !inputs.c6_neon_git_release && vars.C6_AUTO_NEON_GIT_ENABLED == 'true')")
MANUAL_TRUE = {"event": "workflow_dispatch", "ref": "refs/heads/main",
               "actor": "olegbalakin-cmyk", "run_now": True, "auto": True,
               "pilot": False, "prepare": False, "release": False}


def allowed(ctx):
    return (ctx["event"] == "workflow_dispatch"
            and ctx["ref"] == "refs/heads/main"
            and ctx["actor"] == "olegbalakin-cmyk"
            and ctx["run_now"] and ctx["auto"]
            and not ctx["pilot"] and not ctx["prepare"] and not ctx["release"])


class ManualCatchupContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = WF.read_text(encoding="utf-8")
        cls.doc = yaml.safe_load(cls.raw)
        cls.jobs = cls.doc["jobs"]

    def test_exact_default_off_owner_main_auto_gate(self):
        inputs = self.doc[True]["workflow_dispatch"]["inputs"]
        self.assertIs(inputs["c6_run_now"]["default"], False)
        self.assertEqual(inputs["c6_run_now"]["type"], "boolean")
        self.assertTrue(inputs["c6_run_now"]["required"])
        self.assertEqual(self.doc[True]["schedule"][0]["cron"], "15 */4 * * *")
        self.assertEqual(self.raw.count(SCHEDULE), 8)
        self.assertEqual(self.raw.count(MANUAL), 8)
        for name in ("update-site", "c6-neon-six-json-prepare", "c6-neon-auto-git-publish"):
            self.assertIn(MANUAL, self.jobs[name]["if"])
        self.assertIn("needs.update-site.result == 'success'", self.jobs["c6-neon-six-json-prepare"]["if"])
        self.assertIn("needs.c6-neon-six-json-prepare.result == 'success'", self.jobs["c6-neon-auto-git-publish"]["if"])

    def test_unsafe_manual_contexts_blocked(self):
        self.assertTrue(allowed(MANUAL_TRUE))
        for key, alternate in (
            ("event", "push"), ("ref", "refs/heads/feature"),
            ("actor", "someone-else"), ("run_now", False),
            ("auto", False), ("pilot", True),
            ("prepare", True), ("release", True),
        ):
            with self.subTest(key=key):
                self.assertFalse(allowed({**MANUAL_TRUE, key: alternate}))

    def test_shell_gate_and_unchanged_protections(self):
        steps = self.jobs["update-site"]["steps"]
        checks = [x for x in steps if x.get("name") == "Require C2 same-run Neon bundle for scheduled or manual Git-only cycle"]
        self.assertEqual(len(checks), 1)
        shell = checks[0]["run"]
        self.assertIn('test "$RUN_NOW_INPUT" = "true"', shell)
        self.assertIn('test "$PILOT_INPUT" != "true"', shell)
        self.assertIn('test "$AUTO_ENABLED" = "true"', shell)
        self.assertIn('test "$GITHUB_ACTOR" = "olegbalakin-cmyk"', shell)
        self.assertIn('test "$GITHUB_REF" = "refs/heads/main"', shell)
        self.assertIn('test "$FINAL_PREPARE_INPUT" != "true"', shell)
        self.assertIn('test "$LEGACY_RELEASE_INPUT" != "true"', shell)
        self.assertIn('test "$PILOT_INPUT" = "true"', shell)  # existing manual pilot remains gated
        self.assertIn('test "$LEGACY_PAUSED" = "true"', shell)
        self.assertIn('test "$AUTO_ENABLED" != "true"', shell)
        publisher = self.jobs["c6-neon-auto-git-publish"]
        self.assertEqual(publisher["needs"], ["update-site", "c6-neon-six-json-prepare"])
        publish_shell = "\n".join(x.get("run","") for x in publisher["steps"])
        self.assertNotIn("netlify deploy", publish_shell.lower())
        self.assertEqual(publisher["steps"][-1]["env"]["NETLIFY_DEPLOYMENTS_PER_UPDATE"], "0")
        self.assertEqual(self.doc["concurrency"]["cancel-in-progress"], False)
        self.assertEqual(self.jobs["c6-neon-six-json-prepare"]["environment"], "c6-neon-shadow-readonly")


if __name__ == "__main__":
    unittest.main()
