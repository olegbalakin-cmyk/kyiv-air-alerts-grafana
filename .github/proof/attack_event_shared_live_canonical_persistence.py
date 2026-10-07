#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "kyiv-air-alerts-grafana" / "scripts"
sys.path.insert(0, str(SCRIPTS))

EXPECTED_CITIES = 23
EXPECTED_REGRESSION = 26363
PROOF_DATABASE_BRANCH = "br-bold-mode-b5rub8pq"


class ProofFailure(RuntimeError):
    pass


def sh(args, *, check=True):
    p = subprocess.run(
        [str(x) for x in args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and p.returncode:
        raise ProofFailure(
            "command failed: " + " ".join(map(str, args)) + "\n" + p.stderr[-5000:]
        )
    return p


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ProofFailure(f"cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def current_blob(path: str) -> str:
    return sh(["git", "rev-parse", f"HEAD:{path}"]).stdout.strip()


def historical_regression(run_id: str) -> dict:
    alignment = load_module(
        ROOT / ".github" / "proof" / "attack_event_shared_live_classifier_alignment.py",
        "accepted_alignment_proof",
    )
    monitor_blob = current_blob(
        "kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py"
    )
    alignment.REPAIRED_BLOB = monitor_blob
    tmp = Path(tempfile.mkdtemp(prefix="shared-live-persistence-regression-"))
    try:
        parity, recovery = alignment.run_historical_regression(
            tmp, sh(["git", "rev-parse", "HEAD"]).stdout.strip(), run_id
        )
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    pt = parity["totals"]
    rs = recovery["summary"]
    replayed = int(pt["episodes_replayed"]) + int(rs["cases_recovered"])
    exact = int(pt["exact_verdict_matches"]) + int(
        rs["exact_verdict_matches_among_recovered"]
    )
    mismatches = int(pt["total_mismatches"]) + int(rs["mismatches"])
    unsafe = (
        int(pt["unsafe_promotions_from_NO_CONFIRMED_EVENT"])
        + int(pt["unsafe_promotions_from_NEEDS_REVIEW"])
        + int(rs["unsafe_promotions"])
    )
    legacy = int(rs["cases_still_untestable"])
    if (replayed, exact, mismatches, unsafe, legacy) != (
        EXPECTED_REGRESSION,
        EXPECTED_REGRESSION,
        0,
        0,
        42,
    ):
        raise ProofFailure(
            f"historical regression failed: replayed={replayed} exact={exact} "
            f"mismatches={mismatches} unsafe={unsafe} legacy={legacy}"
        )
    return {
        "replayed": replayed,
        "exact_matches": exact,
        "semantic_mismatches": mismatches,
        "unsafe_promotions": unsafe,
        "legacy_non_replayable": legacy,
    }


def verify_shared_wiring(monitor) -> dict:
    source = (
        ROOT / "kyiv-air-alerts-grafana" / "scripts" / "monitor_explosion_candidates.py"
    ).read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "explosion-monitor-wip.yml").read_text(
        encoding="utf-8"
    )
    requirements = (
        ROOT / "kyiv-air-alerts-grafana" / "requirements.txt"
    ).read_text(encoding="utf-8")
    cities = sorted(monitor.CITY_CONFIG)
    secret_marker = "ATTACK_EVENT_DATABASE_URL: $" + "{{ secrets.PHASE1_PROD_SHADOW_DATABASE_URL }}"
    checks = {
        "city_count": len(cities),
        "one_shared_persistence_call": source.count(
            "persist_due_episode_classifications("
        )
        == 1,
        "persistence_after_composition": source.find(
            "persist_due_episode_classifications("
        )
        > source.find("composition_refresh = apply_episode_composition("),
        "same_due_object": "queue=queue,\n        due=due," in source,
        "coverage_gate_present": "coverage_by_city=persistence_coverage_by_city"
        in source,
        "database_secret_wired": secret_marker in workflow,
        "database_client_present": "psycopg[binary]" in requirements,
    }
    if len(cities) != EXPECTED_CITIES or not all(
        value for key, value in checks.items() if key != "city_count"
    ):
        raise ProofFailure(f"shared persistence wiring failed: {checks}")
    return {
        "cities": cities,
        "cities_covered": len(cities),
        "cities_bypassing_persistence": [],
        "checks": checks,
    }


def table_counts(cur, episode_id: str, city_key: str) -> dict:
    cur.execute(
        """
        SELECT count(*)
        FROM public.attack_event_classifications
        WHERE city_key=%s AND historical_episode_id=%s
        """,
        (city_key, episode_id),
    )
    classifications = int(cur.fetchone()[0])
    cur.execute(
        """
        SELECT count(*)
        FROM public.attack_events
        WHERE city_key=%s AND historical_episode_id=%s
        """,
        (city_key, episode_id),
    )
    events = int(cur.fetchone()[0])
    cur.execute(
        """
        SELECT count(*)
        FROM public.attack_event_sources s
        JOIN public.attack_event_classifications c
          ON c.classification_uid=s.classification_uid
        WHERE c.city_key=%s AND c.historical_episode_id=%s
        """,
        (city_key, episode_id),
    )
    sources = int(cur.fetchone()[0])
    return {
        "classifications": classifications,
        "events": events,
        "sources": sources,
    }


def latest_unclassified_poltava(cur) -> dict:
    cur.execute(
        """
        SELECT legacy_episode_id, city_key, start_at, end_at
        FROM public.alert_episodes a
        WHERE a.city_key='poltava'
          AND a.alert_type='AIR'
          AND a.episode_state='closed'
          AND a.canonicalization_version='alert-canonicalization-v1'
          AND a.end_at IS NOT NULL
          AND a.start_at >= now() - interval '14 days'
          AND NOT EXISTS (
              SELECT 1
              FROM public.attack_event_classifications c
              WHERE c.city_key=a.city_key
                AND c.historical_episode_id=a.legacy_episode_id
                AND c.alert_start_at=a.start_at
                AND c.alert_end_at=a.end_at
          )
        ORDER BY a.start_at DESC
        LIMIT 1
        """
    )
    row = cur.fetchone()
    if row is None:
        raise ProofFailure(
            "no recent unclassified Poltava canonical parent available for rollback proof"
        )
    return {
        "episode_id": str(row[0]),
        "city_key": str(row[1]),
        "city": "Полтава",
        "alert_start": row[2].isoformat().replace("+00:00", "Z"),
        "alert_end": row[3].isoformat().replace("+00:00", "Z"),
        "checks": [{"label": "proof", "due_at": row[3].isoformat(), "checked_at": None}],
    }


def classify_fixture(monitor, episode: dict, *, fulltext: bool, suffix: str) -> dict:
    start = monitor.parse_dt(episode["alert_start"])
    end = monitor.parse_dt(episode["alert_end"])
    published = start + (end - start) / 2
    row = {
        "city_key": "poltava",
        "city": "Полтава",
        "title": "У Полтаві під час повітряної тривоги пролунали вибухи",
        "snippet": "",
        "publisher": "Proof",
        "publisher_url": "https://proof.invalid",
        "published_at": monitor.iso(published),
        "url": f"https://proof.invalid/{suffix}",
        "source": "Google News RSS",
        "discovery_basis": "publisher_fulltext" if fulltext else "rss_title_snippet",
        "matched_text_excerpt": (
            "У Полтаві під час повітряної тривоги пролунали вибухи"
            if fulltext
            else None
        ),
        "first_discovered_at": monitor.iso(published),
        "trigger_episode_ids": [episode["episode_id"]],
        "trigger_check_labels": ["proof"],
    }
    row["candidate_id"] = monitor.candidate_id("poltava", row["url"], row["title"])
    matching = monitor.match_candidate_to_episodes(row, [episode])
    decision = monitor.classify_candidate(row, "poltava", [episode], matching)
    monitor.apply_classification_decision(row, decision, matching)
    return {"row": row, "decision": decision}


def isolated_write_proof(dsn: str, monitor, persistence) -> dict:
    conn = psycopg.connect(dsn, autocommit=False)
    selected = None
    baseline = None
    proof = {}
    try:
        cur = conn.cursor()
        selected = latest_unclassified_poltava(cur)
        baseline = table_counts(cur, selected["episode_id"], selected["city_key"])
        if baseline != {"classifications": 0, "events": 0, "sources": 0}:
            raise ProofFailure(f"selected rollback episode is not absent: {baseline}")

        rec0 = persistence.build_episode_classification(selected, [])
        if rec0["verdict"] != "NO_CONFIRMED_EVENT":
            raise ProofFailure(f"empty-evidence verdict drift: {rec0['verdict']}")

        first = persistence.persist_episode_classification(conn, rec0)
        counts_after_first = table_counts(
            cur, selected["episode_id"], selected["city_key"]
        )
        if not first["classification_inserted"] or counts_after_first["classifications"] != 1:
            raise ProofFailure("absent classification insert was not proven")
        if counts_after_first["events"] != 0:
            raise ProofFailure("non-positive insert created unsupported attack_event")

        rerun0 = persistence.persist_episode_classification(conn, rec0)
        counts_after_rerun0 = table_counts(
            cur, selected["episode_id"], selected["city_key"]
        )
        if rerun0["classification_inserted"] or counts_after_rerun0 != counts_after_first:
            raise ProofFailure("exact non-positive rerun was not idempotent")

        needs_fixture = classify_fixture(
            monitor, selected, fulltext=True, suffix="needs-review"
        )
        if needs_fixture["decision"]["proposed_outcome"] != "needs_review":
            raise ProofFailure(
                "authoritative classifier did not produce expected NEEDS_REVIEW fixture: "
                + str(needs_fixture["decision"]["proposed_outcome"])
            )
        queue1 = [needs_fixture["row"]]
        rec1 = persistence.build_episode_classification(selected, queue1)
        if rec1["verdict"] != "NEEDS_REVIEW":
            raise ProofFailure(f"NEEDS_REVIEW persistence mapping drift: {rec1['verdict']}")

        before_fault = table_counts(cur, selected["episode_id"], selected["city_key"])
        forced_failure_seen = False
        try:
            persistence.persist_episode_classification(
                conn, rec1, fault_after="classification"
            )
        except RuntimeError as exc:
            if str(exc) != "FORCED_PERSISTENCE_FAILURE_AFTER_CLASSIFICATION":
                raise
            forced_failure_seen = True
        after_fault = table_counts(cur, selected["episode_id"], selected["city_key"])
        if not forced_failure_seen or after_fault != before_fault:
            raise ProofFailure(
                f"forced partial failure was not atomic: {before_fault} -> {after_fault}"
            )

        needs = persistence.persist_episode_classification(conn, rec1)
        counts_after_needs = table_counts(
            cur, selected["episode_id"], selected["city_key"]
        )
        if (
            not needs["classification_inserted"]
            or not needs["revision_inserted"]
            or counts_after_needs["classifications"] != 2
            or counts_after_needs["events"] != 0
            or counts_after_needs["sources"] < 1
        ):
            raise ProofFailure(
                f"NO_CONFIRMED->NEEDS_REVIEW retry/update failed: {counts_after_needs}"
            )
        needs_rerun = persistence.persist_episode_classification(conn, rec1)
        counts_after_needs_rerun = table_counts(
            cur, selected["episode_id"], selected["city_key"]
        )
        if (
            needs_rerun["classification_inserted"]
            or needs_rerun["source_inserts"]
            or counts_after_needs_rerun != counts_after_needs
        ):
            raise ProofFailure("NEEDS_REVIEW exact rerun was not idempotent")

        strict_fixture = classify_fixture(
            monitor, selected, fulltext=False, suffix="strict"
        )
        if strict_fixture["decision"]["proposed_outcome"] != "approved_strict":
            raise ProofFailure(
                "authoritative classifier did not produce expected STRICT fixture: "
                + str(strict_fixture["decision"]["proposed_outcome"])
            )
        queue2 = [needs_fixture["row"], strict_fixture["row"]]
        rec2 = persistence.build_episode_classification(selected, queue2)
        if rec2["verdict"] != "STRICT_EVENT_POSITIVE":
            raise ProofFailure(f"STRICT persistence mapping drift: {rec2['verdict']}")
        strict = persistence.persist_episode_classification(conn, rec2)
        counts_after_strict = table_counts(
            cur, selected["episode_id"], selected["city_key"]
        )
        if (
            not strict["classification_inserted"]
            or not strict["revision_inserted"]
            or not strict["event_inserted"]
            or counts_after_strict["classifications"] != 3
            or counts_after_strict["events"] != 1
            or counts_after_strict["sources"] < 3
        ):
            raise ProofFailure(
                f"NEEDS_REVIEW->STRICT positive persistence failed: {counts_after_strict}"
            )

        cur.execute(
            """
            SELECT e.attack_event_key_version, e.attack_event_key, e.event_grain,
                   e.event_status, c.verdict, c.classifier_blob_sha,
                   c.classifier_methodology_version, c.normalization_version,
                   e.alert_episode_uid=c.alert_episode_uid
            FROM public.attack_events e
            JOIN public.attack_event_classifications c
              ON c.classification_uid=e.current_classification_uid
            WHERE e.city_key=%s AND e.historical_episode_id=%s
            """,
            (selected["city_key"], selected["episode_id"]),
        )
        event_row = cur.fetchone()
        if event_row is None:
            raise ProofFailure("positive event row not found")
        event_contract = {
            "key_version": str(event_row[0]),
            "key": str(event_row[1]),
            "grain": str(event_row[2]),
            "status": str(event_row[3]),
            "verdict": str(event_row[4]),
            "classifier_blob_sha": str(event_row[5]),
            "methodology": str(event_row[6]),
            "normalization": str(event_row[7]),
            "same_parent": bool(event_row[8]),
        }
        expected_event_contract = {
            "key_version": persistence.ATTACK_EVENT_KEY_VERSION,
            "key": rec2["attack_event_key"],
            "grain": persistence.EVENT_GRAIN,
            "status": "ACTIVE",
            "verdict": "STRICT_EVENT_POSITIVE",
            "classifier_blob_sha": persistence.AUTHORITATIVE_CLASSIFIER_BLOB,
            "methodology": persistence.CLASSIFIER_METHODOLOGY_VERSION,
            "normalization": persistence.NORMALIZATION_VERSION,
            "same_parent": True,
        }
        if event_contract != expected_event_contract:
            raise ProofFailure(f"positive event contract mismatch: {event_contract}")

        strict_rerun = persistence.persist_episode_classification(conn, rec2)
        counts_after_strict_rerun = table_counts(
            cur, selected["episode_id"], selected["city_key"]
        )
        if (
            strict_rerun["classification_inserted"]
            or strict_rerun["event_inserted"]
            or strict_rerun["event_updated"]
            or strict_rerun["source_inserts"]
            or counts_after_strict_rerun != counts_after_strict
        ):
            raise ProofFailure("STRICT exact rerun was not idempotent")

        cur.execute(
            """
            SELECT count(*) - count(DISTINCT classification_key)
            FROM public.attack_event_classifications
            WHERE city_key=%s AND historical_episode_id=%s
            """,
            (selected["city_key"], selected["episode_id"]),
        )
        duplicate_classifications = int(cur.fetchone()[0])
        cur.execute(
            """
            SELECT count(*) - count(DISTINCT attack_event_key)
            FROM public.attack_events
            WHERE city_key=%s AND historical_episode_id=%s
            """,
            (selected["city_key"], selected["episode_id"]),
        )
        duplicate_events = int(cur.fetchone()[0])
        if duplicate_classifications != 0 or duplicate_events != 0:
            raise ProofFailure("duplicate deterministic rows created in rollback proof")

        proof = {
            "selected_recent_canonical_episode": {
                "city_key": selected["city_key"],
                "episode_id": selected["episode_id"],
                "alert_start": selected["alert_start"],
                "alert_end": selected["alert_end"],
            },
            "classification_insert_absent": True,
            "idempotent_rerun": True,
            "legitimate_transitions": [
                "NO_CONFIRMED_EVENT -> NEEDS_REVIEW",
                "NEEDS_REVIEW -> STRICT_EVENT_POSITIVE",
            ],
            "transition_outputs_produced_by_authoritative_classifier": True,
            "forced_partial_failure_rolled_back": True,
            "retry_after_partial_failure": True,
            "positive_attack_event_linkage": True,
            "positive_evidence_linkage": counts_after_strict["sources"] >= 3,
            "non_positive_event_rows_created": 0,
            "non_positive_classification_persistence": True,
            "duplicate_classification_rows_created": duplicate_classifications,
            "duplicate_attack_event_rows_created": duplicate_events,
            "counts_at_strict_tip": counts_after_strict,
            "event_contract": event_contract,
        }
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()

    verify = psycopg.connect(dsn, autocommit=True)
    try:
        cur2 = verify.cursor()
        after_rollback = table_counts(
            cur2, selected["episode_id"], selected["city_key"]
        )
    finally:
        verify.close()
    if after_rollback != baseline:
        raise ProofFailure(
            f"rollback isolation failed: baseline={baseline} after={after_rollback}"
        )
    proof["baseline_rows"] = baseline
    proof["rows_after_outer_rollback"] = after_rollback
    proof["durable_proof_mutations"] = 0
    return proof


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()

    dsn = os.environ.get("PHASE1_PROD_SHADOW_DATABASE_URL", "").strip()
    if not dsn:
        raise ProofFailure("PHASE1_PROD_SHADOW_DATABASE_URL is unavailable")
    expected_branch = os.environ.get("PHASE1_PROD_SHADOW_BRANCH_ID", "").strip()
    if expected_branch and expected_branch != PROOF_DATABASE_BRANCH:
        raise ProofFailure(f"unexpected proof database branch: {expected_branch}")

    monitor = load_module(
        SCRIPTS / "monitor_explosion_candidates.py", "live_monitor_persistence_proof"
    )
    persistence = load_module(
        SCRIPTS / "attack_event_canonical_persistence.py",
        "canonical_persistence_adapter_proof",
    )

    monitor.self_test()
    wiring = verify_shared_wiring(monitor)
    regression = historical_regression(args.run_id)
    isolated = isolated_write_proof(dsn, monitor, persistence)

    artifact = {
        "schema_version": 1,
        "proof": "SHARED 23-CITY LIVE CANONICAL PERSISTENCE",
        "verdict": "SHARED 23-CITY LIVE CANONICAL PERSISTENCE = PARTIAL",
        "partial_reason": "PRODUCTION WRITE NOT EXECUTED",
        "actions_run_id": int(args.run_id),
        "canonical_contract": {
            "reused": True,
            "schema_changes_required": False,
            "classification_key_version": persistence.CLASSIFICATION_KEY_VERSION,
            "classification_identity": (
                "attack-event-classification-key-v2 deterministic immutable semantic "
                "revision; logical episode parent is exact city+legacy_episode_id+"
                "start_at+end_at canonical alert_episodes binding"
            ),
            "event_key_version": persistence.ATTACK_EVENT_KEY_VERSION,
            "source_link_key_version": persistence.SOURCE_LINK_KEY_VERSION,
            "revision_semantics": (
                "append-only attack_event_classifications with "
                "supersedes_classification_uid; stable attack_event current pointer/status"
            ),
        },
        "implementation": {
            "monitor_blob": current_blob(
                "kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py"
            ),
            "persistence_adapter_blob": current_blob(
                "kyiv-air-alerts-grafana/scripts/attack_event_canonical_persistence.py"
            ),
            "authoritative_classifier_blob": persistence.AUTHORITATIVE_CLASSIFIER_BLOB,
            "database_secret_reference": "PHASE1_PROD_SHADOW_DATABASE_URL",
            "persistence_position": "after authoritative classification and episode composition",
            "coverage_failure_behavior": "skip persistence for due city checks when discovery coverage is incomplete",
        },
        "shared_wiring": wiring,
        "historical_regression": regression,
        "isolated_write_proof": isolated,
        "production_integration": {
            "executed": False,
            "classifications_persisted": 0,
            "reason": (
                "No existing deployment contract explicitly authorizes this repair proof "
                "to mutate naturally arriving production live classifications. The repair "
                "is wired, but this proof remained rollback-only."
            ),
        },
        "remaining_blocker": "PRODUCTION WRITE NOT EXECUTED",
        "mutation_confirmation": {
            "repository_repair_branch_modified": True,
            "canonical_schema_modified": False,
            "classifier_semantics_modified": False,
            "discovery_modified": False,
            "alert_ingestion_modified": False,
            "historical_backfill_started": False,
            "historical_frozen_verdicts_modified": False,
            "isolated_database_writes_rolled_back": True,
            "production_live_rows_written": 0,
        },
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "PERSISTENCE_PROOF_SUMMARY="
        + json.dumps(
            {
                "verdict": artifact["verdict"],
                "cities": f"{wiring['cities_covered']}/23",
                "historical": f"{regression['exact_matches']}/{regression['replayed']}",
                "duplicates": {
                    "classification": isolated[
                        "duplicate_classification_rows_created"
                    ],
                    "event": isolated["duplicate_attack_event_rows_created"],
                },
                "production_live_rows": 0,
            },
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    try:
        main()
    except ProofFailure as exc:
        print("PERSISTENCE_PROOF_FAILED=" + str(exc), file=sys.stderr)
        raise SystemExit(2)
