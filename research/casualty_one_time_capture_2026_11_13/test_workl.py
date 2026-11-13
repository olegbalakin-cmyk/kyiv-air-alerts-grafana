"""Work L isolated launch gate and fact artifact tests. No source network."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research.casualty_one_time_capture_2026_11_13 import run_capture as r
from research.casualty_one_time_capture_2026_11_13.test_workk import (
    mock_inputs, queue, synthetic_launch, synthetic_env)


class WorkL(unittest.TestCase):
    def launch(self):
        plan = json.loads(r.PLAN_PATH.read_text())
        g = synthetic_launch()
        g.update({
            "status": "OWNER_APPROVED_SINGLE_LAUNCH",
            "workk_head_sha": r.WORKK_HEAD,
            "expected_preflight_head_sha": "a"*40,
            "exact_urls": [t["url"] for t in plan["targets"]],
            "allowed_hosts": plan["allowed_hosts"],
            "limits": r.LIMITS,
            "approved_redirect_urls": {t["target_id"]: [] for t in plan["targets"]},
            "production_write_allowed": False,
            "source_fulltext_persistence_allowed": False,
            "authorization_id": "CASUALTY-T03-T05-NEW-AUTH-MOCK-ONLY"
        })
        return g, plan

    def env(self):
        env = synthetic_env()
        env.update(GITHUB_ACTOR="olegbalakin-cmyk", GITHUB_SHA="b"*40)
        return env

    def fakegit(self, *args):
        if args == ("rev-parse", "HEAD"):
            return "b"*40
        if args == ("rev-parse", "HEAD^"):
            return "a"*40
        if args == ("diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"):
            return r.LAUNCH_REL
        if args == ("log", "--format=%H", "HEAD^", "--", r.LAUNCH_REL):
            return ""
        if args == ("merge-base", "--is-ancestor", r.WORKK_HEAD, "a"*40):
            return ""
        raise AssertionError(("unexpected git", args))

    def test_01_launch_gate_nominal_synthetic_only(self):
        grant, plan = self.launch()
        r.validate_one_launch_commit(grant, plan, environ=self.env(), git_call=self.fakegit)

    def test_02_any_fourth_url_fails_before_get(self):
        grant, plan = self.launch()
        grant["exact_urls"].append("https://mig.com.ua/extra")
        with self.assertRaisesRegex(RuntimeError, "EXACT_OWNER"):
            r.validate_one_launch_commit(grant, plan, environ=self.env(), git_call=self.fakegit)

    def test_03_no_grant_and_no_live_launch_in_tree(self):
        self.assertFalse((r.HERE/"launch.json").exists())
        self.assertEqual(json.loads(r.TEMPLATE_PATH.read_text())["status"], "NOT_AUTHORIZED")
        grant, plan = self.launch()
        for k in ("status","workk_head_sha","expected_preflight_head_sha",
                  "exact_urls","allowed_hosts","limits","approved_redirect_urls"):
            bad = copy.deepcopy(grant)
            bad.pop(k)
            with self.subTest(k=k), self.assertRaisesRegex(RuntimeError, "EXACT_OWNER"):
                r.validate_one_launch_commit(bad, plan, environ=self.env(), git_call=self.fakegit)

    def test_04_replay_and_non_owner_blocked(self):
        grant, plan = self.launch()
        for key, val in (("GITHUB_ACTOR","unapproved-person"),
                         ("GITHUB_RUN_ATTEMPT","2"),
                         ("GITHUB_EVENT_NAME","pull_request"),
                         ("GITHUB_EVENT_BEFORE","c"*40),
                         ("GITHUB_SHA","c"*40)):
            env = self.env()
            env[key] = val
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, "IDENTITY|PARENT"):
                r.validate_one_launch_commit(grant, plan, environ=env, git_call=self.fakegit)

    def test_05_launch_only_commit_and_no_prior_launch(self):
        grant, plan = self.launch()
        def changed(*args):
            if args[0] == "diff-tree": return "launch.json\nother-file.py"
            return self.fakegit(*args)
        with self.assertRaisesRegex(RuntimeError, "LAUNCH_ONLY"):
            r.validate_one_launch_commit(grant, plan, environ=self.env(), git_call=changed)
        def prior(*args):
            if args[0] == "log": return "old-commit-sha"
            return self.fakegit(*args)
        with self.assertRaisesRegex(RuntimeError, "ALREADY_USED"):
            r.validate_one_launch_commit(grant, plan, environ=self.env(), git_call=prior)

    def test_06_synthetic_authorization_id_not_live_grant(self):
        grant, plan = self.launch()
        grant["authorization_id"] = "CASUALTY-T03-T05-TEST-123"
        with self.assertRaisesRegex(RuntimeError, "NOT_A_REAL"):
            r.validate_one_launch_commit(grant, plan, environ=self.env(), git_call=self.fakegit)

    def test_07_privacy_fails_closed_and_marks_review(self):
        card={"excerpts":[{"text":"Загинули 3 людини. Свідок Петро Іваненко повідомив деталі."},
                          {"text":"Загинули 3 людини."}],
              "reasons":[]}
        r.withhold_unsafe_excerpts(card)
        self.assertEqual(len(card["excerpts"]),1)
        self.assertIn("PRIVACY_REVIEW_EXCERPT_WITHHELD",card["reasons"])
        self.assertNotIn("Іваненко",str(card))

    def test_08_three_cards_and_sha_manifest_without_fulltext(self):
        plan,volatile,audit,bodies=mock_inputs()
        with tempfile.TemporaryDirectory() as d:
            r.retain_results(queue(),plan,volatile,audit,Path(d),authorization_id="MOCK")
            root=Path(d)
            facts=json.loads((root/"minimal_capture_facts.json").read_text())
            assert len(facts["facts"]) == 3
            assert [c["claim_deaths"] for c in facts["facts"]]==[2,3,3]
            assert all(c["decision"]=="NEEDS_REVIEW" for c in facts["facts"])
            assert facts["official_incidents_automatically_matched"]==0
            raw="\n".join(x.read_text() for x in root.glob("*.json"))
            assert all(b not in raw for b in bodies)
            manifest=json.loads((root/"manifest.json").read_text())["files_sha256"]
            import hashlib
            assert len(manifest)==4
            for name,sha in manifest.items():
                assert hashlib.sha256((root/name).read_bytes()).hexdigest()==sha

    def test_09_no_unknown_redirect_or_extra_get(self):
        from research.casualty_controlled_capture_preflight_2026_11_13 import test_preflight as g
        grant,plan=self.launch()
        _,template=r.check_scope(queue())
        policy=r.validate_launch(synthetic_launch(),template,queue(),environ=synthetic_env())
        opener=g.FakeOpener([g.Response(302,"https://mig.com.ua/unknown")])
        receipt,_=r.e._capture_once(plan["targets"][0]["url"],policy,{"used":0},opener)
        self.assertEqual(len(opener.urls),1)
        self.assertIn("REDIRECT_NOT_",receipt["reason"])
        budget={"used":6}
        unopened=g.FakeOpener([])
        receipt,_=r.e._capture_once(plan["targets"][0]["url"],policy,budget,unopened)
        self.assertEqual(len(unopened.urls),0)
        self.assertEqual(receipt["reason"],"REQUEST_BUDGET_EXCEEDED")

if __name__=="__main__":
    unittest.main()
