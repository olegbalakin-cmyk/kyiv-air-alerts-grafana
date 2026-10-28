#!/usr/bin/env python3
"""C3-RC4 isolated PG16: four new real persistence/queue faults, two via monitor.main.

Only a disposable LOCAL_PROOF_POSTGRES_DSN is permitted; network sources are replaced
with fixed local in-memory fixtures. The six RC3 scenarios run via the original harness.
Every scenario gets independent SQL before/failure/retry snapshots; no synthetic DB counts.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import traceback
from datetime import datetime, timedelta, timezone

import psycopg

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(os.environ["C3_RC4_REPORT_DIR"])
OUT.mkdir(parents=True, exist_ok=True)
DSN = os.environ["LOCAL_PROOF_POSTGRES_DSN"]
if not ("localhost" in DSN or "127.0.0.1" in DSN):
    raise SystemExit("REFUSE_NONLOCAL_PG16_DSN")
os.environ["ATTACK_EVENT_DATABASE_URL"] = DSN
os.environ["CANONICAL_PARENT_CONTRACT_DIR"] = str(ROOT / "kyiv-air-alerts-grafana/tests/fixtures/parent_contract")
os.environ["CANONICAL_PARENT_DB_BRANCH"] = "offline-disposable-postgres-16"
os.environ.setdefault("ATTACK_EVENT_ORIGIN_REF", "research-c3-rc4")
os.environ.setdefault("ATTACK_EVENT_ORIGIN_COMMIT_SHA", os.getenv("GITHUB_SHA", "0" * 40))
SCRIPTS = ROOT / "kyiv-air-alerts-grafana/scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / "kyiv-air-alerts-grafana/tests/fixtures/parent_contract"))
import db_phase1_core as core
import live_canonical_queue as journal
import live_parent_ordering as ordering
import monitor_explosion_candidates as monitor
import attack_event_canonical_persistence as persistence

NOW = datetime(2026, 10, 29, 1, 0, tzinfo=timezone.utc)
CUTOFF = datetime(2026, 10, 7, 19, 5, tzinfo=timezone.utc)
NEW = ["independent_readback_failure", "source_identity_conflict", "source_failure_retry", "event_stage_rollback"]
RESULT = {"gate": "C3-RC4", "engine": "disposable PostgreSQL 16", "scenarios": {},
          "rc3_accepted_six_reexecuted": False, "errors": [], "all_10_fault_pass": False,
          "integration_scope": {"independent_readback_failure": "monitor.main",
                                "source_failure_retry": "monitor.main",
                                "source_identity_conflict": "real queue and PG persistence",
                                "event_stage_rollback": "real positive persistence and queue"}}
QUERIES = {
 "parent": "SELECT episode_uid::text, start_at::text, end_at::text FROM public.alert_episodes WHERE city_key=%s AND legacy_episode_id=%s ORDER BY start_at",
 "classification": "SELECT classification_uid::text, classification_key, verdict, is_event, alert_episode_uid::text, supersedes_classification_uid::text FROM public.attack_event_classifications WHERE city_key=%s AND historical_episode_id=%s ORDER BY classification_key",
 "source": "SELECT s.source_link_key, s.observation_id, s.content_sha256, s.classification_uid::text FROM public.attack_event_sources s JOIN public.attack_event_classifications c ON c.classification_uid=s.classification_uid WHERE c.city_key=%s AND c.historical_episode_id=%s ORDER BY s.source_link_key",
 "event": "SELECT attack_event_uid::text, attack_event_key, event_status, current_classification_uid::text, alert_episode_uid::text FROM public.attack_events WHERE city_key=%s AND historical_episode_id=%s ORDER BY attack_event_key",
 "tip": "SELECT c.classification_uid::text, c.classification_key, c.verdict FROM public.attack_event_classifications c WHERE c.city_key=%s AND c.historical_episode_id=%s AND NOT EXISTS (SELECT 1 FROM public.attack_event_classifications n WHERE n.supersedes_classification_uid=c.classification_uid) ORDER BY c.classification_key"
}
def ep(index):
    start = datetime(2026, 10, 17, tzinfo=timezone.utc) + timedelta(minutes=40 * index)
    end = start + timedelta(minutes=30)
    return {"city_key": "kyiv", "episode_id": core.legacy_episode_id("kyiv", start, end),
            "alert_start": start.isoformat(), "alert_end": end.isoformat(),
            "alert_source": "kyiv_combined_exact_city",
            "checks": [{"label": "immediate", "due_at": end.isoformat(),
                        "checked_at": None, "new_candidates": None}]}
def candidate(e, name):
    return {"city_key": "kyiv", "candidate_id": "rc4-" + name,
            "matched_episode_id": e["episode_id"], "matched_episode_ids": [e["episode_id"]],
            "status": "approved_strict", "source": "Offline frozen research fixture",
            "title": "Київ: вибух від атаки під час повітряної тривоги",
            "url": "https://example.invalid/frozen/" + name, "publisher": "offline-rc4",
            "published_at": e["alert_start"], "snippet": "Вибух від ворожої атаки у Києві"}
def parent(e):
    with psycopg.connect(DSN, autocommit=False) as conn:
        ordering.ensure_canonical_parent(conn, e)
def record(e, rows):
    return persistence.build_episode_classification(e, rows, origin=persistence._origin_context())
def save(rec, expected=None, fault_after=None):
    with psycopg.connect(DSN, autocommit=False) as conn:
        return persistence.persist_episode_classification(conn, rec, expected_tip=expected, fault_after=fault_after)
def readback(rec, saved, previous=None):
    with psycopg.connect(DSN, autocommit=True) as conn:
        return persistence.independent_post_commit_readback(conn, rec, saved, previous)
def state_for(e):
    state = {"schema_version": 1, "cities": {"kyiv": {"episodes": [copy.deepcopy(e)]}}}
    journal.register_city(state, "kyiv", [e], CUTOFF)
    work_id = next(iter(journal.store(state)))
    check = next(iter(journal.store(state)[work_id]["coverage_checks"].values()))
    check.update({"status": "complete", "completed_at": NOW.isoformat(), "reason": None})
    return state, work_id
def capture(case, point, e, state):
    with psycopg.connect(DSN, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SHOW server_version")
            version = cur.fetchone()[0]
            assert version.startswith("16."), "not PostgreSQL 16"
            db = {}
            for key, sql in QUERIES.items():
                cur.execute(sql, ("kyiv", e["episode_id"]))
                db[key] = [list(r) for r in cur.fetchall()]
            cur.execute("SELECT count(*) FROM (SELECT classification_key FROM public.attack_event_classifications GROUP BY classification_key HAVING count(*)>1) t")
            db["duplicate_classification_keys"] = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM (SELECT attack_event_key FROM public.attack_events GROUP BY attack_event_key HAVING count(*)>1) t")
            db["duplicate_event_keys"] = cur.fetchone()[0]
    entries = journal.store(state)
    kept = [{"work_id": k, "status": v.get("status"), "attempts": v.get("attempts"),
             "last_committed_key": v.get("last_committed_key"),
             "coverage_checks": v.get("coverage_checks"),
             "next_retry_at": v.get("next_retry_at")}
            for k, v in entries.items() if v.get("episode_id") == e["episode_id"]]
    checks = [dict(x) for x in (state.get("cities", {}).get("kyiv", {}).get("episodes") or [{}])[0].get("checks", [])]
    row = {"scenario": case, "point": point, "server_version": version,
           "episode_id": e["episode_id"], "sql": QUERIES, "db": db,
           "journal": kept, "discovery_checks": checks,
           "last_successful_poll_at": state.get("cities", {}).get("kyiv", {}).get("last_successful_poll_at"),
           "latest_api_alert_end": state.get("cities", {}).get("kyiv", {}).get("latest_api_alert_end")}
    (OUT / (case + "_" + point + ".json")).write_text(json.dumps(row, indent=2, sort_keys=True, default=str) + "\n")
    return row
def delta_count(s, kind):
    return len(s["db"][kind])
def db_equal(a, b):
    return a["db"] == b["db"]
def check_case(name, function):
    try:
        row = function()
        RESULT["scenarios"][name] = row
    except Exception as ex:
        RESULT["scenarios"][name] = {"status": "FAIL", "exception": type(ex).__name__ + ":" + str(ex),
                                      "traceback": traceback.format_exc()[-4000:]}
    print("C3_RC4_CASE=" + json.dumps({"case":name, "status":RESULT["scenarios"][name]["status"]}, sort_keys=True), flush=True)

def main_session(name, e, *, fault_kind):
    saved = {n: getattr(monitor, n) for n in ("now_utc", "poll_cached_bridge", "refresh_telegram_cache",
             "telegram_candidates_for_city", "search_city_news", "STATE_FILE", "QUEUE_FILE", "LAST_RUN_FILE")}
    original_argv = list(sys.argv)
    original_readback = persistence.independent_post_commit_readback
    with tempfile.TemporaryDirectory(prefix="c3-rc4-" + name + "-") as folder:
        root = Path(folder)
        monitor.STATE_FILE = root / "state.json"
        monitor.QUEUE_FILE = root / "queue.json"
        monitor.LAST_RUN_FILE = root / "report.json"
        monitor.STATE_FILE.write_text(json.dumps({"schema_version": 1, "cities": {"kyiv": {"episodes": [e]}}}))
        monitor.QUEUE_FILE.write_text("[]")
        monitor.now_utc = lambda: NOW
        counter = {"readback": 0, "source": 0}
        def frozen_poll(*args):
            counter["source"] += 1
            return ({city: [] for city in monitor.CITY_CONFIG},
                    {"kyiv": "INJECTED_CACHED_SOURCE_FAILURE"} if fault_kind == "source" and counter["source"] == 1 else {})
        monitor.poll_cached_bridge = frozen_poll
        monitor.refresh_telegram_cache = lambda *args: {}
        monitor.telegram_candidates_for_city = lambda *args: []
        evidence = {"url": "https://example.invalid/rc4-integration-" + name,
                    "title": "У Києві чули вибухи під час тривоги",
                    "publisher": "Offline research fixture",
                    "published_at": e["alert_start"],
                    "source": "Google News RSS", "snippet": "Київ, вибухи під час повітряної тривоги"}
        monitor.search_city_news = lambda city, *args: (
            [evidence] if city == "kyiv" else [], None,
            {"fulltext_fetches": 0, "fulltext_rescued_candidates": 0})
        def fail_first_readback(*args, **kwargs):
            counter["readback"] += 1
            if counter["readback"] == 1:
                raise RuntimeError("INJECTED_INDEPENDENT_POST_COMMIT_READBACK_FAILURE")
            return original_readback(*args, **kwargs)
        if fault_kind == "readback":
            persistence.independent_post_commit_readback = fail_first_readback
        sys.argv = ["monitor_explosion_candidates.py", "--local-only"]
        try:
            state = json.loads(monitor.STATE_FILE.read_text())
            before = capture(name, "before", e, state)
            monitor.main()
            failed_report = json.loads(monitor.LAST_RUN_FILE.read_text())
            failed_state = json.loads(monitor.STATE_FILE.read_text())
            failure = capture(name, "failure", e, failed_state)
            if fault_kind == "readback":
                persistence.independent_post_commit_readback = original_readback
            monitor.main()
            recovered_report = json.loads(monitor.LAST_RUN_FILE.read_text())
            recovered_state = json.loads(monitor.STATE_FILE.read_text())
            retry = capture(name, "retry", e, recovered_state)
            monitor.main()
            repeat_report = json.loads(monitor.LAST_RUN_FILE.read_text())
            repeat_state = json.loads(monitor.STATE_FILE.read_text())
            repeated = capture(name, "repeat", e, repeat_state)
            return before, failure, retry, repeated, failed_report, recovered_report, repeat_report, counter
        finally:
            for n, value in saved.items():
                setattr(monitor, n, value)
            persistence.independent_post_commit_readback = original_readback
            sys.argv = original_argv

def case_readback():
    e = ep(401)
    before, failure, retry, repeat, first, recovered, again, counter = main_session(
        "independent_readback_failure", e, fault_kind="readback")
    f = failure["journal"][0] if failure["journal"] else {}
    r = retry["journal"][0] if retry["journal"] else {}
    good = (counter["readback"] == 1
            and delta_count(before, "classification") == 0
            and delta_count(failure, "classification") == 1
            and len(failure["db"]["tip"]) == 1
            and f.get("status") == "retryable_failure"
            and first["canonical_persistence"]["committed"] == 0
            and first["canonical_persistence"]["retryable"] == 1
            and r.get("status") == "committed"
            and db_equal(failure, retry) and db_equal(retry, repeat)
            and recovered["canonical_persistence"]["committed"] == 0
            and again["canonical_persistence"]["committed"] == 0
            and retry["db"]["duplicate_classification_keys"] == 0
            and retry["db"]["duplicate_event_keys"] == 0)
    return {"status": "PASS" if good else "FAIL", "fault_point": "after SQL COMMIT, before independent readback/ACK",
            "monitor_main_calls": 3, "failure_status": f.get("status"), "retry_status": r.get("status"),
            "fault_invocations": counter["readback"], "snapshots": ["before", "failure", "retry", "repeat"],
            "invariants": {"committed_not_lost": delta_count(failure, "classification") == 1,
                           "no_false_ack": f.get("status") != "committed",
                           "retry_reconciles_tip": r.get("status") == "committed",
                           "no_replay_duplicate": db_equal(retry, repeat)}}

def case_source():
    e = ep(402)
    before, failure, retry, repeat, first, recovered, again, counter = main_session(
        "source_failure_retry", e, fault_kind="source")
    f = failure["journal"][0] if failure["journal"] else {}
    r = retry["journal"][0] if retry["journal"] else {}
    failed_checks = failure["discovery_checks"]
    good = (counter["source"] == 3 and "kyiv" in first["errors"]
            and not first.get("canonical_persistence", {}).get("committed")
            and delta_count(failure, "classification") == 0
            and failure["last_successful_poll_at"] == before["last_successful_poll_at"]
            and failure["latest_api_alert_end"] == before["latest_api_alert_end"]
            and all(x.get("checked_at") is None for x in failed_checks)
            and f.get("status") in {"pending", "blocked_evidence", "retryable_failure"}
            and delta_count(retry, "classification") == 1
            and r.get("status") == "committed"
            and db_equal(retry, repeat)
            and recovered["canonical_persistence"]["committed"] == 1
            and again["canonical_persistence"]["committed"] == 0)
    return {"status": "PASS" if good else "FAIL", "fault_point": "frozen poll_cached_bridge returns city source error",
            "monitor_main_calls": 3, "initial_error": first.get("errors"), "failure_status": f.get("status"),
            "retry_status": r.get("status"), "snapshots": ["before", "failure", "retry", "repeat"],
            "invariants": {"checked_at_unadvanced": all(x.get("checked_at") is None for x in failed_checks),
                           "source_cursor_unadvanced": failure["last_successful_poll_at"] == before["last_successful_poll_at"],
                           "no_early_classification": delta_count(failure, "classification") == 0,
                           "recovered_once": delta_count(retry, "classification") == 1,
                           "repeat_idempotent": db_equal(retry, repeat)}}

def case_identity():
    name = "source_identity_conflict"
    e = ep(403)
    parent(e)
    approved = [candidate(e, "identity")]
    rec = record(e, approved)
    assert rec["is_event"] and rec["source_rows"]
    state, work_id = state_for(e)
    persisted = save(rec, None)
    before = capture(name, "before", e, state)
    conflict = copy.deepcopy(rec)
    conflict["source_rows"][0]["observation_id"] = "INJECTED_CROSS_SOURCE_IDENTITY"
    ex_source = None
    try:
        save(conflict, persisted["classification_uid"])
    except Exception as exc:
        ex_source = type(exc).__name__ + ":" + str(exc)
    wrong_episode = copy.deepcopy(e)
    wrong_episode["alert_end"] = (datetime.fromisoformat(e["alert_end"]) + timedelta(minutes=1)).isoformat()
    wrong_rec = record(wrong_episode, approved)
    ex_episode = None
    try:
        save(wrong_rec, None)
    except Exception as exc:
        ex_episode = type(exc).__name__ + ":" + str(exc)
    failure = capture(name, "failure", e, state)
    verified = readback(rec, persisted, None)
    assert verified["verified"]
    again_saved = save(rec, persisted["classification_uid"])
    journal.committed_readback(state, work_id, rec["classification_key"], verified["classification_key"])
    retry = capture(name, "retry", e, state)
    last_saved = save(rec, persisted["classification_uid"])
    repeat = capture(name, "repeat", e, state)
    good = (ex_source is not None and "source-link semantic conflict" in ex_source
            and ex_episode is not None and "exactly one canonical" in ex_episode
            and db_equal(before, failure) and db_equal(retry, repeat)
            and not again_saved["classification_inserted"] and not last_saved["classification_inserted"]
            and failure["journal"][0]["status"] != "committed"
            and retry["journal"][0]["status"] == "committed"
            and len(retry["db"]["source"]) == 1 and len(retry["db"]["event"]) == 1
            and len(retry["db"]["tip"]) == 1)
    return {"status": "PASS" if good else "FAIL", "fault_point": "source_link_key same, altered observation_id; same episode_id with invalid interval",
            "monitor_main_calls": 0, "scope": "direct real DB/queue (not monitor.main)",
            "source_rejection": ex_source, "episode_rejection": ex_episode,
            "snapshots": ["before", "failure", "retry", "repeat"],
            "invariants": {"conflict_did_not_modify_db": db_equal(before, failure),
                           "journal_held_pending": failure["journal"][0]["status"] != "committed",
                           "retry_committed": retry["journal"][0]["status"] == "committed",
                           "no_duplicate_tips": len(retry["db"]["tip"]) == 1}}

def case_positive():
    name = "event_stage_rollback"
    e = ep(404)
    parent(e)
    approved = [candidate(e, "positive")]
    rec = record(e, approved)
    assert rec["is_event"] and rec["verdict"] == "STRICT_EVENT_POSITIVE" and len(rec["source_rows"]) == 1
    state, work_id = state_for(e)
    before = capture(name, "before", e, state)
    injected = None
    try:
        save(rec, None, fault_after="event")
    except Exception as exc:
        injected = type(exc).__name__ + ":" + str(exc)
    failure = capture(name, "failure", e, state)
    saved = save(rec, None)
    verified = readback(rec, saved, None)
    journal.committed_readback(state, work_id, rec["classification_key"], verified["classification_key"])
    retry = capture(name, "retry", e, state)
    second = save(rec, saved["classification_uid"])
    repeat = capture(name, "repeat", e, state)
    good = (injected is not None and "FORCED_PERSISTENCE_FAILURE_AFTER_EVENT" in injected
            and db_equal(before, failure)
            and failure["journal"][0]["status"] != "committed"
            and saved["classification_inserted"] and saved["event_inserted"]
            and len(retry["db"]["classification"]) == 1
            and retry["db"]["classification"][0][3] is True
            and len(retry["db"]["source"]) == 1
            and len(retry["db"]["event"]) == 1
            and retry["db"]["event"][0][2] == "ACTIVE"
            and retry["db"]["event"][0][3] == retry["db"]["classification"][0][0]
            and retry["journal"][0]["status"] == "committed"
            and not second["classification_inserted"] and not second["event_inserted"]
            and db_equal(retry, repeat))
    return {"status": "PASS" if good else "FAIL", "fault_point": "real positive STRICT_EVENT_POSITIVE transaction after _ensure_event and before _ensure_sources",
            "candidate_fixture": "offline synthetic approved_strict source, classified by real build_episode_classification",
            "monitor_main_calls": 0, "scope": "direct real positive DB persistence (not monitor.main)",
            "injected_exception": injected, "snapshots": ["before", "failure", "retry", "repeat"],
            "invariants": {"rollback_atomic": db_equal(before, failure),
                           "pending_journal": failure["journal"][0]["status"] != "committed",
                           "positive_event_created_exactly_once": saved["event_inserted"] and len(retry["db"]["event"]) == 1,
                           "source_consistency": len(retry["db"]["source"]) == 1,
                           "retry_idempotent": db_equal(retry, repeat)}}

def main():
    rc3 = subprocess.run([sys.executable, str(ROOT / "research/c3_rc3_2026_10_28/prove_pg16_faults_rc3.py")],
                        cwd=ROOT, capture_output=True, text=True, timeout=240)
    (OUT / "rc3_six_regression.log").write_text(rc3.stdout + "\nSTDERR\n" + rc3.stderr)
    oldpath = OUT / "c3_rc3_fault_results.json"
    if not oldpath.exists():
        RESULT["errors"].append("RC3_SIX_RESULTS_NOT_EMITTED")
        old = {}
    else:
        old = json.loads(oldpath.read_text())
    accepted_six = ["two_concurrent_workers", "post_commit_pre_ack", "classification_conflict",
                    "stale_current_tip", "pruned_state_legacy_checked_at", "repeated_normal_execution"]
    RESULT["rc3_accepted_six_reexecuted"] = (
        old.get("baseline_monitor_main", {}).get("status") == "PASS"
        and all(old.get("scenarios", {}).get(x, {}).get("status") == "PASS" for x in accepted_six))
    RESULT["original_six"] = {x: old.get("scenarios", {}).get(x, {}).get("status", "NOT_PROVEN") for x in accepted_six}
    check_case("independent_readback_failure", case_readback)
    check_case("source_identity_conflict", case_identity)
    check_case("source_failure_retry", case_source)
    check_case("event_stage_rollback", case_positive)
    RESULT["all_10_fault_pass"] = RESULT["rc3_accepted_six_reexecuted"] and all(
        RESULT["scenarios"][x]["status"] == "PASS" for x in NEW)
    RESULT["result"] = "PASS" if RESULT["all_10_fault_pass"] else "PARTIAL"
    (OUT / "c3_rc4_fault_results.json").write_text(json.dumps(RESULT, indent=2, sort_keys=True, default=str) + "\n")
    print("C3_RC4_FAULT_RESULT=" + json.dumps(
        {"result": RESULT["result"], "new": {k: v["status"] for k, v in RESULT["scenarios"].items()},
         "old_six_pass": RESULT["rc3_accepted_six_reexecuted"]}, sort_keys=True))
    return 0 if RESULT["all_10_fault_pass"] else 2
if __name__ == "__main__":
    raise SystemExit(main())
