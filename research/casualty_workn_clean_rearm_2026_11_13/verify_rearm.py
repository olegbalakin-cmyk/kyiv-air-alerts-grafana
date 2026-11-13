#!/usr/bin/env python3
"""Work N independent clean-rearm offline proof; never opens publisher URLs."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
from pathlib import Path

from research.casualty_one_time_capture_2026_11_13 import run_capture as runner
from research.casualty_one_time_capture_2026_11_13.test_workk import synthetic_env
from research.casualty_one_time_capture_2026_11_13.test_workl import WorkL
from review_casualty_candidates import load_queue

BRANCH = "research-casualty-workp-worko-runner-2026-11-14"
WORKM = "657fd70564bf5393d3fcd209e47d95fa986f3010"
PREVIOUS_LAUNCH = "e1f9c3af1dacd3fe77e2ba899df14afb6dd84858"


def command(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=runner.ROOT, text=True).strip()


def denied(label, call, reason, rows):
    try:
        call()
    except RuntimeError as exc:
        assert reason in str(exc), (label, str(exc))
    else:
        raise AssertionError("OWNER_GATE_UNSAFE_ACCEPT:" + label)
    rows.append(label)


def check_clean_branch():
    live = (runner.ROOT / ".github/workflows/research-casualty-workl-three-live-once.yml").read_text()
    offline = (runner.ROOT / ".github/workflows/research-casualty-workl-offline.yml").read_text()
    assert runner.EXPECTED_BRANCH == BRANCH
    assert runner.EXPECTED_BASE == WORKM
    required = (
        "on:\n  push:\n    branches: [" + BRANCH + "]\n    paths:\n"
        "      - " + runner.LAUNCH_REL + "\n"
        "permissions:\n"
    )
    assert required in live, "LIVE_TRIGGER_NOT_EXACT_SINGLE_BRANCH_AND_PATH"
    assert "pull_request:" not in live and "workflow_dispatch:" not in live
    assert "schedule:" not in live
    assert ("  push:\n    branches: [" + BRANCH + "]\n    paths-ignore:\n"
            "      - " + runner.LAUNCH_REL) in offline
    assert "  pull_request:\n    branches: [research-casualty-workm-prehttp-ci-fix-2026-11-13]" in offline
    assert not (runner.HERE / "launch.json").exists(), "LAUNCH_FILE_ALREADY_PRESENT"
    assert command("log", "--format=%H", "HEAD", "--", runner.LAUNCH_REL) == "", "OLD_LAUNCH_IN_HISTORY"
    subprocess.run(["git", "merge-base", "--is-ancestor", WORKM, "HEAD"],
                   cwd=runner.ROOT, check=True)
    actual_head = command("rev-parse", "HEAD")
    assert actual_head != PREVIOUS_LAUNCH
    # The legacy Work L launch remains on an entirely different branch.
    assert "research-casualty-workl-three-source-preflight-2026-11-13" not in live
    assert "research-casualty-workm-prehttp-ci-fix-2026-11-13" not in live
    return actual_head


def check_mock_grant():
    queue = load_queue(runner.ROOT / "_wip/kyiv-air-alerts-grafana/data/casualties/multicity_review_queue.json")
    plan, template = runner.check_scope(queue)
    assert template["status"] == "NOT_AUTHORIZED"
    assert template["authorization_id"] is None
    assert template["enable_controlled_capture"] is False
    assert [t["target_id"] for t in plan["targets"]] == ["T03", "T04", "T05"]
    assert all(t["approved_redirect_urls"] == [] for t in template["targets"])
    mock = WorkL()
    grant, _ = mock.launch()
    runner.validate_launch(grant, template, queue, environ=synthetic_env())
    runner.validate_one_launch_commit(grant, plan, environ=mock.env(), git_call=mock.fakegit)
    cases = []
    denied("no_grant", lambda: runner.validate_launch({}, template, queue, environ=synthetic_env()),
           "NEW_OWNER_GRANT_SCOPE_INVALID", cases)
    old = copy.deepcopy(grant)
    old["authorization_id"] = "CASUALTY-T03-T05-OWNER-20261113-2021Z-ONE-SHOT-01"
    denied("consumed_workl_grant", lambda: runner.validate_launch(old, template, queue, environ=synthetic_env()),
           "NEW_OWNER_GRANT_SCOPE_INVALID", cases)
    env = dict(synthetic_env(), GITHUB_REF="refs/heads/research-casualty-workl-three-source-preflight-2026-11-13")
    denied("old_branch", lambda: runner.validate_launch(grant, template, queue, environ=env),
           "FRESH_SINGLE_PUSH_OWNER_GRANT_REQUIRED", cases)
    env = dict(synthetic_env(), GITHUB_RUN_ATTEMPT="2")
    denied("repeat_attempt", lambda: runner.validate_launch(grant, template, queue, environ=env),
           "FRESH_SINGLE_PUSH_OWNER_GRANT_REQUIRED", cases)
    env = dict(mock.env(), GITHUB_SHA="f" * 40)
    denied("wrong_head", lambda: runner.validate_one_launch_commit(grant, plan, environ=env, git_call=mock.fakegit),
           "WORKL_EXACT_PARENT_OR_HEAD_REJECTED", cases)
    extra = copy.deepcopy(grant)
    extra["exact_urls"].append("https://mig.com.ua/fourth-url")
    denied("fourth_url", lambda: runner.validate_one_launch_commit(extra, plan, environ=mock.env(), git_call=mock.fakegit),
           "WORKL_EXACT_OWNER_GRANT_NOT_MATCHED", cases)
    redirect = copy.deepcopy(grant)
    redirect["approved_redirect_urls"]["T03"].append("https://www.ukrinform.ua/unknown-path")
    denied("redirect", lambda: runner.validate_one_launch_commit(redirect, plan, environ=mock.env(), git_call=mock.fakegit),
           "WORKL_EXACT_OWNER_GRANT_NOT_MATCHED", cases)
    def wrong_lineage(*args):
        if args == ("merge-base", "--is-ancestor", WORKM, "a" * 40):
            raise RuntimeError("not descendant of Work M")
        return mock.fakegit(*args)
    denied("wrong_workm_lineage",
           lambda: runner.validate_one_launch_commit(grant, plan, environ=mock.env(), git_call=wrong_lineage),
           "WORKN_WORKM_ANCESTRY_NOT_VERIFIED", cases)
    return cases


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    output = ap.parse_args().output
    proof = json.loads((output / "workm-prehttp-proof.json").read_text())
    suite = proof["pre_http_full_suite"]
    assert suite["run"] == 68 and suite["pass"] == 68
    assert suite["skip"] == 0 and suite["fail"] == 0 and suite["error"] == 0
    assert proof["source_http_get"] == 0 and proof["network_attempts"] == 0
    assert proof["synthetic_evidence_cards"] == 3 and proof["review_required_cards"] == 3
    assert proof["automatic_promote"] is False and proof["publication_allowed"] is False
    assert proof["claim_deaths"] == [2, 3, 3]
    manifest = proof["fact_file_sha256"]
    assert len(manifest) == 4
    for filename, digest in manifest.items():
        assert hashlib.sha256((output / "synthetic" / filename).read_bytes()).hexdigest() == digest
    head = check_clean_branch()
    cases = check_mock_grant()
    report = {
        "verdict": "THREE_SOURCE_CLEAN_REARM_OFFLINE_PASS",
        "head_sha": head, "branch": BRANCH, "immutable_workm_ancestor": WORKM,
        "prior_launch_sha_ancestor": False,
        "live_trigger": "single_launch_json_only_push_on_new_branch",
        "live_grant_status": "NOT_AUTHORIZED", "authorization_id_issued": False,
        "launch_json_present": False, "owner_approval_required": True,
        "mock_positive": "PASS", "rejection_cases": cases,
        "full_safety_tests": suite, "source_http_get": 0,
        "card_count": 3, "card_counts": [2, 3, 3], "card_status": "NEEDS_REVIEW",
        "card_file_sha256": manifest, "auto_death_credits": 0,
        "production_changed": False,
        "t03_t04_t05_only": True, "max_get_including_redirects": 6,
        "unknown_redirect_allowed": False, "retries": 0
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "workn-rearm-proof.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("WORKN_CLEAN_REARM_OFFLINE_PASS 68/68; LIVE AUTHORIZATION NONE; SOURCE_GET=0")


if __name__ == "__main__":
    main()
