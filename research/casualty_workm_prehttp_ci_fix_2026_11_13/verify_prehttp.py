#!/usr/bin/env python3
"""Offline-only Work M proof. Mirrors pre-HTTP Work L dependencies; NEVER source HTTP."""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import subprocess
import sys
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from research.casualty_one_time_capture_2026_11_13 import run_capture as r
from research.casualty_one_time_capture_2026_11_13 import test_workk, verify_workk, verify_workl
from research.casualty_one_time_capture_2026_11_13.test_workk import synthetic_env
from research.casualty_one_time_capture_2026_11_13.test_workl import WorkL
from research.casualty_controlled_capture_preflight_2026_11_13 import test_preflight
from review_casualty_candidates import load_queue

MODULES = (
    "research.casualty_evidence_ingestion_2026_11_13.test_ingest",
    "research.casualty_controlled_capture_preflight_2026_11_13.test_preflight",
    "research.casualty_strict_redirect_2026_11_13.test_redirect",
    "research.casualty_fact_retention_workj_2026_11_13.test_workj",
    "research.casualty_one_time_capture_2026_11_13.test_workk",
    "research.casualty_one_time_capture_2026_11_13.test_workl",
)
PINS = {
    "_wip": "43b580491d54d1df3bd84a0ae59a6987f8ea4d03",
    "_pr102": "bb553f9285eaa5a9b55f8cf92b3dcb0bbbce97ee",
    "_site": "d0a7d22de2828c93236562cccc9d2e68c6a66e3d",
}


def check_fixtures():
    workflow = (r.ROOT / ".github/workflows/research-casualty-workl-three-live-once.yml").read_text()
    for directory, sha in PINS.items():
        actual = subprocess.check_output(
            ["git", "-C", str(r.ROOT / directory), "rev-parse", "HEAD"], text=True
        ).strip()
        assert actual == sha, (directory, actual)
        assert "ref: " + sha + "\n          path: " + directory in workflow, directory
    assert not (r.HERE / "launch.json").exists(), "REAL_LAUNCH_NOT_ALLOWED"
    assert "branches: [research-casualty-workn-prehttp-launch-state-fix-2026-11-13]" in workflow
    assert "research-casualty-workl-three-source-preflight-2026-11-13" not in workflow
    assert "research-casualty-workm-prehttp-ci-fix-2026-11-13" not in workflow
    assert "One approved source-only pilot; no publication" in workflow


def rejected(name, action, reason, rows):
    try:
        action()
    except RuntimeError as exc:
        assert reason in str(exc), (name, str(exc))
    else:
        raise AssertionError("UNSAFE_GATE_ACCEPTED:" + name)
    rows.append(name)


def verify_mock_gates():
    queue = load_queue(r.ROOT / "_wip/kyiv-air-alerts-grafana/data/casualties/multicity_review_queue.json")
    plan, template = r.check_scope(queue)
    fixture = WorkL()
    grant, mock_plan = fixture.launch()
    assert plan == mock_plan
    policy = r.validate_launch(grant, template, queue, environ=synthetic_env())
    r.validate_one_launch_commit(grant, plan, environ=fixture.env(), git_call=fixture.fakegit)
    denied = []
    rejected("missing_owner_grant",
             lambda: r.validate_launch({}, template, queue, environ=synthetic_env()),
             "NEW_OWNER_GRANT_SCOPE_INVALID", denied)
    repeat = dict(synthetic_env(), GITHUB_RUN_ATTEMPT="2")
    rejected("replayed_attempt",
             lambda: r.validate_launch(grant, template, queue, environ=repeat),
             "FRESH_SINGLE_PUSH_OWNER_GRANT_REQUIRED", denied)
    wrong_parent = dict(synthetic_env(), GITHUB_EVENT_BEFORE="c" * 40)
    rejected("wrong_previous_sha",
             lambda: r.validate_launch(grant, template, queue, environ=wrong_parent),
             "FRESH_SINGLE_PUSH_OWNER_GRANT_REQUIRED", denied)
    reused = dict(grant, authorization_id="CASUALTY-T01-T10-OWNER-20261113-ONE-SHOT-01")
    rejected("reused_prior_authorization_id",
             lambda: r.validate_launch(reused, template, queue, environ=synthetic_env()),
             "NEW_OWNER_GRANT_SCOPE_INVALID", denied)
    expired = dict(grant, approved_at_utc="2020-01-01T00:00:00+00:00",
                   expires_at_utc="2020-01-01T01:00:00+00:00")
    old_workl = dict(grant, authorization_id="CASUALTY-T03-T05-OWNER-20261113-2021Z-ONE-SHOT-01")
    rejected("consumed_workl_authorization_id",
             lambda: r.validate_launch(old_workl, template, queue, environ=synthetic_env()),
             "NEW_OWNER_GRANT_SCOPE_INVALID", denied)
    rejected("expired_grant",
             lambda: r.validate_launch(expired, template, queue, environ=synthetic_env()),
             "SINGLE_USE_AUTHORIZATION_EXPIRED_OR_INVALID", denied)
    not_owner = dict(fixture.env(), GITHUB_ACTOR="not-owner")
    old_branch_env = dict(synthetic_env(), GITHUB_REF="refs/heads/research-casualty-workl-three-source-preflight-2026-11-13")
    rejected("old_branch_not_authorized",
             lambda: r.validate_launch(grant, template, queue, environ=old_branch_env),
             "FRESH_SINGLE_PUSH_OWNER_GRANT_REQUIRED", denied)
    rejected("wrong_actor",
             lambda: r.validate_one_launch_commit(grant, plan, environ=not_owner,
                                                   git_call=fixture.fakegit),
             "WORKL_LAUNCH_IDENTITY_OR_ATTEMPT_REJECTED", denied)
    extra = copy.deepcopy(grant)
    extra["exact_urls"].append("https://mig.com.ua/extra")
    rejected("unapproved_fourth_url",
             lambda: r.validate_one_launch_commit(extra, plan, environ=fixture.env(),
                                                   git_call=fixture.fakegit),
             "WORKL_EXACT_OWNER_GRANT_NOT_MATCHED", denied)
    redirect = copy.deepcopy(grant)
    redirect["approved_redirect_urls"]["T03"].append("https://mig.com.ua/other-path")
    rejected("unapproved_redirect",
             lambda: r.validate_one_launch_commit(redirect, plan, environ=fixture.env(),
                                                   git_call=fixture.fakegit),
             "WORKL_EXACT_OWNER_GRANT_NOT_MATCHED", denied)
    over = copy.deepcopy(grant)
    over["limits"]["max_requests_total"] = 7
    rejected("excessive_budget",
             lambda: r.validate_one_launch_commit(over, plan, environ=fixture.env(),
                                                   git_call=fixture.fakegit),
             "WORKL_EXACT_OWNER_GRANT_NOT_MATCHED", denied)
    def dirty_git(*args):
        if args[0] == "diff-tree":
            return r.LAUNCH_REL + "\nother-file.py"
        return fixture.fakegit(*args)
    rejected("non_launch_only_commit",
             lambda: r.validate_one_launch_commit(grant, plan, environ=fixture.env(),
                                                   git_call=dirty_git),
             "WORKL_LAUNCH_ONLY_COMMIT_REQUIRED", denied)
    def used_git(*args):
        if args[0] == "log":
            return "old-launch-commit"
        return fixture.fakegit(*args)
    rejected("earlier_launch_in_history",
             lambda: r.validate_one_launch_commit(grant, plan, environ=fixture.env(),
                                                   git_call=used_git),
             "WORKL_AUTHORIZATION_ALREADY_USED_IN_BRANCH_HISTORY", denied)
    opener = test_preflight.FakeOpener([])
    rec, _ = r.e._capture_once(plan["targets"][0]["url"], policy,
                               {"used": 6}, opener)
    assert rec["reason"] == "REQUEST_BUDGET_EXCEEDED"
    assert opener.urls == [], "EXCESS_GET_ATTEMPTED"
    return denied, len(queue)


def run_tests(out):
    log = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromNames(MODULES)
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    output = log.getvalue()
    (out / "tests.log").write_text(output, encoding="utf-8")
    print(output[-900:])
    summary = {
        "run": result.testsRun, "pass": result.testsRun - len(result.errors) - len(result.failures)
                  - len(result.skipped) - len(result.expectedFailures),
        "fail": len(result.failures), "error": len(result.errors),
        "skip": len(result.skipped), "expected_failures": len(result.expectedFailures),
    }
    if not result.wasSuccessful() or summary["run"] != 68 or summary["skip"]:
        raise AssertionError("FULL_PREHTTP_SAFETY_SUITE_NOT_68_OF_68:" + str(summary))
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    out = parser.parse_args().output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    attempts = []

    def forbid_network(*args, **kwargs):
        attempts.append("BLOCKED_OUTBOUND_SOCKET_OR_HTTP")
        raise AssertionError("SOURCE_HTTP_FORBIDDEN_IN_OFFLINE_PROOF")

    # Tests, mocked owner gates and synthetic fact retention execute with all
    # real socket/request entry points denied, including redirects.
    with ExitStack() as guards:
        for target in ("socket.socket.connect", "socket.create_connection",
                       "urllib.request.urlopen", "urllib.request.OpenerDirector.open",
                       "http.client.HTTPConnection.connect",
                       "requests.sessions.Session.request"):
            guards.enter_context(patch(target, side_effect=forbid_network))
        check_fixtures()
        suite = run_tests(out)
        negative, queue_len = verify_mock_gates()
        with patch.object(sys, "argv", ["verify_workk", "--output", str(out / "synthetic")]):
            verify_workk.main()
        with patch.object(sys, "argv", ["verify_workl", "--output", str(out)]):
            verify_workl.main()

    assert attempts == [], "ANY_ACTUAL_NETWORK_ATTEMPT"
    synthetic = out / "synthetic"
    facts = json.loads((synthetic / "minimal_capture_facts.json").read_text())
    assert [c["claim_deaths"] for c in facts["facts"]] == [2, 3, 3]
    assert all(c["decision"] == "NEEDS_REVIEW" for c in facts["facts"])
    manifest = json.loads((synthetic / "manifest.json").read_text())["files_sha256"]
    assert len(manifest) == 4
    for name, digest in manifest.items():
        assert hashlib.sha256((synthetic / name).read_bytes()).hexdigest() == digest

    proof = {
        "verdict": "WORKL_PREHTTP_CI_FIX_PASS",
        "method": "offline_python_312_git_actions_no_real_launch",
        "pre_http_full_suite": suite,
        "negative_owner_gate_cases_passed": negative,
        "mock_owner_gate_positive": "PASS",
        "mock_queue_candidates": queue_len,
        "pinned_fixture_commits": PINS,
        "source_http_get": 0, "network_attempts": len(attempts),
        "launch_json_exists": False, "prior_authorization_reused": False,
        "targets": ["T03", "T04", "T05"],
        "max_get_including_redirects": 6,
        "synthetic_evidence_cards": 3, "claim_deaths": [2, 3, 3],
        "review_required_cards": 3, "automatic_promote": False,
        "publication_allowed": False, "whole_source_text_saved": False,
        "fact_file_sha256": manifest,
    }
    (out / "workm-prehttp-proof.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("WORKM_PREHTTP_EXACT_LIVE_CHECKOUT_PASS 68/68, 0 REAL SOURCE HTTP GET")


if __name__ == "__main__":
    main()
