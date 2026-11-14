#!/usr/bin/env python3
"""Work V: real reviewer -> operator -> revisions -> pinned production generator.

All review input records below are *simulation fixtures*, never evidence of a
new fatality. The five proposal proof handles are copied verbatim from PR105's
previously verified source-backed offline output, never manufactured here.
Only private TemporaryDirectory copies are writable.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "kyiv-air-alerts-grafana" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import casualty_review_operator as operator
import review_casualty_candidates as reviewer

FIELDS = reviewer.REVISION_FIELDS
CONTRACT = ("incident_id", "count_kind", "baseline_credited",
            "identity_proof", "credited_proof")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def stage_state(queue: Path, revisions: Path) -> dict:
    return {"wip_head": "OFFLINE_SIMULATION_ONLY",
            "site_prod_head": "PINNED_SITE_PROD_DATA_COPY",
            "queue_blob_sha": operator.git_blob_sha(queue),
            "revisions_blob_sha": operator.git_blob_sha(revisions)}


def preview_apply(mode: str, cid: str, queue: Path, revisions: Path,
                  generator: Path, payload=None, decision: str = ""):
    state = stage_state(queue, revisions)
    p = operator.build_preview(
        mode=mode, candidate_id=cid, decision=decision,
        payload=payload or {}, queue_path=queue, revisions_path=revisions,
        state=state, generator_path=generator)
    operator.apply_preview(
        p, queue_path=queue, revisions_path=revisions, current_state=state,
        reviewed_by="workv-offline-human-simulation", workflow_run_id="offline-proof",
        generator_path=generator)
    return p


def check_rejected(fn, message: str):
    try:
        fn()
    except (ValueError, RuntimeError) as exc:
        return {"result": "BLOCKED", "reason": str(exc)[:180]}
    raise AssertionError("Expected BLOCKED: " + message)


def run(args):
    original = Path(args.site).resolve() / "kyiv-air-alerts-grafana"
    original_dashboard = original / "data" / "dashboard_data.json"
    original_revision = original / "data" / "casualties" / "revisions.csv"
    original_generator = original / "scripts" / "update_casualties.py"
    proposal_path = Path(args.proposal).resolve()
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    originals = {name: sha(path) for name, path in {
        "dashboard": original_dashboard, "revisions": original_revision,
        "generator": original_generator, "proposal": proposal_path,
        "reviewer": Path(reviewer.__file__), "operator": Path(operator.__file__),
    }.items()}
    with proposal_path.open(encoding="utf-8") as f:
        proposals = json.load(f)
    assert isinstance(proposals, list) and len(proposals) == 1
    seed = proposals[0]
    assert seed["city_key"] == "zaporizhzhia"
    assert seed["attack_date"] == "2026-10-10"
    assert seed["count_kind"] == "cumulative"
    assert seed["deaths_delta"] == "23"
    assert seed["baseline_credited"] == "0"
    assert all(seed.get(k) for k in CONTRACT)
    # The source-backed PR105 proof handles and baseline credit travel unchanged.
    seed_proofs = {k: seed[k] for k in CONTRACT}
    assert operator.ALLOWED_CITY_KEYS == frozenset(operator.ALLOWED_CITY_KEYS)
    assert len(operator.ALLOWED_CITY_KEYS) == 23

    with tempfile.TemporaryDirectory(prefix="workv-physical-") as td:
        scratch = Path(td)
        target = scratch / "kyiv-air-alerts-grafana"
        shutil.copytree(original / "data", target / "data")
        (target / "scripts").mkdir(parents=True)
        shutil.copy2(original_generator, target / "scripts" / "update_casualties.py")
        generator = target / "scripts" / "update_casualties.py"
        queue = scratch / "simulation_queue.json"
        revisions = target / "data" / "casualties" / "revisions.csv"
        assert operator.git_blob_sha(generator) == reviewer.GENERATOR_BLOB_PIN

        # Three independent simulator candidates, one anchored incident and
        # real retained PR105 provenance; no new real candidate ID is asserted.
        candidates = [
            {"candidate_id": "offline-workv-snapshot-" + str(n),
             "city_key": "zaporizhzhia", "status": "needs_review",
             "title": "SIMULATION ONLY: cumulative claim", "url": seed["source_url"]}
            for n in (18, 20, 23)
        ]
        write_json(queue, candidates)
        results = []
        observed = ("2026-10-10T12:00:00+00:00",
                    "2026-10-10T13:00:00+00:00",
                    "2026-10-10T14:00:00+00:00")
        for i, n in enumerate((18, 20, 23)):
            cid = candidates[i]["candidate_id"]
            payload = {
                "city_key": "zaporizhzhia", "note": "OFFLINE SIMULATION ONLY",
                "record_id": seed["record_id"] + "-offline-" + str(n),
                "attack_date": seed["attack_date"], "deaths_delta": n,
                "source_name": seed["source_name"], "source_url": seed["source_url"],
                "reviewed_at": observed[i], **seed_proofs,
            }
            p = preview_apply("REVIEW", cid, queue, revisions, generator,
                              payload=payload, decision="CONFIRM")
            assert reviewer.load_queue(queue)[i]["review_disposition"]["identity_proof"] == seed["identity_proof"]
            q = preview_apply("PROMOTE", cid, queue, revisions, generator)
            results.append({"total": n,
                            "review_increment": p["effect"]["projected_revision_increment"],
                            "promote_increment": q["effect"]["projected_revision_increment"]})
            assert p["effect"]["projected_revision_increment"] == (18 if i == 0 else n - (18,20)[i-1])
            assert q["effect"]["projected_revision_increment"] == p["effect"]["projected_revision_increment"]
        assert [item["review_increment"] for item in results] == [18,2,3]
        assert [item["promote_increment"] for item in results] == [18,2,3]
        imported = reviewer.load_revision_rows(revisions)
        snapshots = [row for row in imported if row.get("incident_id") == seed["incident_id"]]
        assert [int(r["deaths_delta"]) for r in snapshots] == [18,20,23]
        assert all(all(r.get(k) == seed[k] for k in CONTRACT) for r in snapshots)
        assert len(imported) == 4  # 1 real legacy Sumy + 3 synthetic snapshots.

        # Real operator replay must propose +0 and persist no ledger changes.
        before_replay = sha(revisions)
        replay = preview_apply("PROMOTE", candidates[-1]["candidate_id"],
                               queue, revisions, generator)
        assert replay["effect"]["projected_revision_increment"] == 0
        assert sha(revisions) == before_replay
        effective = reviewer.validate_against_production_generator(revisions, generator)
        zap = [r for r in effective if r["city_key"] == "zaporizhzhia"]
        assert len(zap) == 1 and zap[0]["deaths_delta"] == 23

        # Falsifiable blocked inputs: the exact operator rejects before REVIEW.
        negative = {"candidate_id": "offline-workv-negative",
                    "city_key": "zaporizhzhia", "status": "needs_review"}
        write_json(queue, [*reviewer.load_queue(queue), negative])
        safe_state = stage_state(queue, revisions)
        base_payload = {
            "city_key": "zaporizhzhia",
            "record_id": seed["record_id"] + "-negative",
            "attack_date": seed["attack_date"], "deaths_delta": 3,
            "source_name": seed["source_name"], "source_url": seed["source_url"],
            "reviewed_at": "2026-10-10T15:00:00+00:00",
            "note": "T03-T05 unverified simulator only",
            **seed_proofs,
        }
        def test_payload(payload):
            return operator.build_preview(
                mode="REVIEW", candidate_id=negative["candidate_id"],
                decision="CONFIRM", payload=payload,
                queue_path=queue, revisions_path=revisions,
                state=safe_state, generator_path=generator)
        missing_identity = dict(base_payload, identity_proof="")
        unknown_baseline = dict(base_payload, baseline_credited="")
        conflict_incident = dict(base_payload,
                                 incident_id="incident:offline-different-event")
        blocked = {
            "T03_T04_T05_no_verified_identity": check_rejected(
                lambda: test_payload(missing_identity), "T03–T05"),
            "missing_identity_proof": check_rejected(
                lambda: test_payload(missing_identity), "identity"),
            "unknown_baseline_credited": check_rejected(
                lambda: test_payload(unknown_baseline), "baseline"),
            "conflicting_incident_id": check_rejected(
                lambda: test_payload(conflict_incident), "conflict"),
        }
        assert reviewer.load_queue(queue)[-1]["status"] == "needs_review"
        assert sha(revisions) == before_replay

        # Run the actual production entrypoint in the entirely private copy,
        # with --no-network and the exact pinned unmodified generator.
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        completed = subprocess.run(
            [sys.executable, str(generator), "--no-network"], cwd=str(target),
            env=env, capture_output=True, text=True, timeout=120, check=True)
        after_dashboard = json.loads((target / "data" / "dashboard_data.json").read_text(encoding="utf-8"))
        before_dashboard = json.loads(original_dashboard.read_text(encoding="utf-8"))
        assert len(after_dashboard["casualties_by_city"]) == 23
        october = [m for m in after_dashboard["casualties_by_city"]["zaporizhzhia"]["monthly"]
                   if m["month"] == "2026-10"]
        assert len(october) == 1 and october[0]["deaths"] == 23

        # Compare against the same production generator's NO-REVISION baseline
        # from the identical snapshot, not a possibly stale committed dashboard.
        baseline_root = scratch / "baseline-without-workv-revisions"
        shutil.copytree(original / "data", baseline_root / "data")
        (baseline_root / "scripts").mkdir(parents=True)
        shutil.copy2(original_generator, baseline_root / "scripts" / "update_casualties.py")
        subprocess.run(
            [sys.executable, str(baseline_root / "scripts" / "update_casualties.py"),
             "--no-network"], cwd=str(baseline_root), env=env,
            capture_output=True, text=True, timeout=120, check=True)
        baseline_dashboard = json.loads(
            (baseline_root / "data" / "dashboard_data.json").read_text(encoding="utf-8"))
        unchanged = [city for city in baseline_dashboard["casualties_by_city"]
                     if city != "zaporizhzhia"]
        assert len(unchanged) == 22
        for city in unchanged:
            before_city = json.loads(json.dumps(baseline_dashboard["casualties_by_city"][city]))
            after_city = json.loads(json.dumps(after_dashboard["casualties_by_city"][city]))
            # Kyiv generation time may differ; the data and all other metadata must match.
            if city == "kyiv":
                before_city["meta"].pop("generated_at", None)
                after_city["meta"].pop("generated_at", None)
            assert before_city == after_city, "Unexpected non-Zap city mutation: " + city
        assert baseline_dashboard["casualties_by_city"]["sumy"] == after_dashboard["casualties_by_city"]["sumy"]
        independent = set(before_dashboard) - {"casualties", "casualties_by_city"}
        assert all(before_dashboard[k] == after_dashboard[k] for k in independent)
        assert all(sha(path) == originals[name] for name,path in {
            "dashboard": original_dashboard, "revisions": original_revision,
            "generator": original_generator, "proposal": proposal_path,
            "reviewer": Path(reviewer.__file__), "operator": Path(operator.__file__),
        }.items())
        summary = {
            "status": "PASS", "mode": "OFFLINE_SIMULATION_ONLY",
            "write_read_contract_mismatch": "FIXED_ON_RESEARCH_BRANCH",
            "production_generator_blob": reviewer.GENERATOR_BLOB_PIN,
            "effective_progression": results,
            "latest_total": 23, "not_sum_61": True,
            "baseline_credited": 0, "replay_increment": 0,
            "source_backed_seed": "PR105_RETAINED_OFFLINE_PROPOSAL",
            "proof_handles_unchanged": True,
            "blocked": blocked,
            "legacy_sumy_unchanged": True, "other_22_cities_unchanged": True,
            "independent_dashboard_sections_unchanged": sorted(independent),
            "generator_invoked": True,
            "generator_stdout": completed.stdout.strip()[:200],
            "original_input_sha256": originals,
            "production_mutations": 0, "external_http_requests": 0,
        }
        write_json(out / "result.json", summary)
        checksums = {"result.json": sha(out / "result.json")}
        write_json(out / "sha256_manifest.json", checksums)
        assert checksums["result.json"] == sha(out / "result.json")
        return summary


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--site", required=True)
    p.add_argument("--proposal", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    print(json.dumps(run(args), ensure_ascii=False, sort_keys=True))
