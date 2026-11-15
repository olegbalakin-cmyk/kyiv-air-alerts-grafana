"""Exact one-shot C6 owner recovery: static, no HTTP/DB/production test."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ".github/workflows/update-netlify-site.yml"
MARKER = "C6-OWNER-ONESHOT-2026-11-15-NEON-GIT-ONLY"
SCHEDULE = "(github.event_name == 'schedule' && vars.C6_AUTO_NEON_GIT_ENABLED == 'true')"
PUSH = ("(github.event_name == 'push' && github.ref == 'refs/heads/main' && "
        "startsWith(github.event.head_commit.message, '" + MARKER + "') && "
        "vars.C6_AUTO_NEON_GIT_ENABLED == 'true')")
APPROVED = (("${{ github.event_name == 'push' && github.ref == 'refs/heads/main' && "
             "startsWith(github.event.head_commit.message, '" + MARKER + "') && "
             "vars.C6_AUTO_NEON_GIT_ENABLED == 'true' }}").replace("\\$", "$"))
ENV_BASE = ("          FINAL_PREPARE_INPUT: ${{ inputs.c6_final_prepare_only }}\n"
            "          LEGACY_RELEASE_INPUT: ${{ inputs.c6_neon_git_release }}").replace("\\$", "$")
ENV_PATCHED = ENV_BASE + "\n          OWNER_ONESHOT_APPROVED: " + APPROVED
SHELL_BASE = ('            test "$LEGACY_RELEASE_INPUT" != "true"\n'
              '          else\n'
              '            test "$GITHUB_EVENT_NAME" = "schedule"\n'
              '            test "$AUTO_ENABLED" = "true"\n'
              '          fi')
SHELL_PATCHED = ('            test "$LEGACY_RELEASE_INPUT" != "true"\n'
                 '          elif [ "$GITHUB_EVENT_NAME" = "push" ]; then\n'
                 '            test "$GITHUB_REF" = "refs/heads/main"\n'
                 '            test "$AUTO_ENABLED" = "true"\n'
                 '            test "$OWNER_ONESHOT_APPROVED" = "true"\n'
                 '          else\n'
                 '            test "$GITHUB_EVENT_NAME" = "schedule"\n'
                 '            test "$AUTO_ENABLED" = "true"\n'
                 '          fi')


class ExactOwnerOneShot(unittest.TestCase):
    def test_only_eight_conditional_replacements_and_two_guards(self):
        base = (ROOT / "accepted-baseline" / WORKFLOW).read_text()
        actual = (ROOT / WORKFLOW).read_text()
        expanded = "(" + SCHEDULE + " || " + PUSH + ")"
        self.assertEqual(base.count(SCHEDULE), 8)
        self.assertEqual(actual.count(expanded), 8)
        self.assertEqual(actual.count(ENV_PATCHED), 1)
        self.assertEqual(actual.count(SHELL_PATCHED), 1)
        restored = actual.replace(expanded, SCHEDULE)
        restored = restored.replace(ENV_PATCHED, ENV_BASE).replace(SHELL_PATCHED, SHELL_BASE)
        self.assertEqual(restored, base, "No unrelated production changes permitted")

    def test_fail_closed_publisher_guards_and_no_netlify(self):
        w = (ROOT / WORKFLOW).read_text()
        self.assertIn('cron: "15 */4 * * *"', w)
        self.assertIn("concurrency:\n  group: update-netlify-site", w)
        self.assertIn("needs: [update-site, c6-neon-six-json-prepare]", w)
        self.assertIn("needs.update-site.result == 'success'", w)
        self.assertIn("needs.c6-neon-six-json-prepare.result == 'success'", w)
        self.assertIn("NETLIFY_DEPLOYMENTS_PER_UPDATE: '0'", w)
        self.assertNotIn("netlify deploy", w.lower())
        self.assertIn('if: ${{ vars.C6_AUTO_NEON_GIT_ENABLED != \'true\' && !inputs.c6_neon_git_pilot }}'.replace("\\$", "$"), w)
        self.assertIn("ref: 82a7cc775ed2f2a6fd0134440db709690f0c04d1", w)
        self.assertIn("--site-bridge pinned-site/kyiv-air-alerts-grafana/scripts/apply_ukrainealarm_bridge.py", w)


if __name__ == "__main__":
    unittest.main()
