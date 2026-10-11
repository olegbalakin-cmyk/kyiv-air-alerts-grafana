#!/usr/bin/env python3
"""Eight isolated, real-PG16 canonical queue safety scenarios.

Uses the unchanged production schema/semantics and disposable DB only.
All injected faults are at Python call boundaries or real SQL transactions.
No SQL mocks, classifier override, real external sources, or historical backfill.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
from psycopg.errors import ForeignKeyViolation, UniqueViolation
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests/fixtures/parent_contract"))
import db_phase1_core as core
import attack_event_canonical_persistence as p
import live_canonical_queue as q
import live_parent_ordering as po
import monitor_explosion_candidates as monitor

DSN = os.environ["LOCAL_PROOF_POSTGRES_DSN"]
UTC = timezone.utc
START = datetime(2026, 10, 9, 1, tzinfo=UTC)
NOW = datetime(2026, 10, 15, 12, tzinfo=UTC)
CUTOFF = datetime(2026, 10, 8, 19, 5, tzinfo=UTC)
os.environ["CANONICAL_PARENT_CONTRACT_DIR"] = str(ROOT / "tests/fixtures/parent_contract")
os.environ["CANONICAL_PARENT_DB_BRANCH"] = "offline-disposable-postgres-16"
os.environ["ATTACK_EVENT_ORIGIN_COMMIT_SHA"] = os.environ.get("GITHUB_SHA", "0" * 40)
os.environ["ATTACK_EVENT_ORIGIN_REF"] = "kyiv-live-canonical-queue-pg16-safety-matrix-2026-10-11"

def episode(index=0, city="kyiv"):
    start = START + timedelta(hours=index * 2)
    end = start + timedelta(minutes=30)
    return {
        "city_key": city,
        "episode_id": core.legacy_episode_id(city, start, end),
        "alert_start": start.isoformat(), "alert_end": end.isoformat(),
        "checks": [{"label": "immediate", "due_at": end.isoformat(), "checked_at": None}],
    }

def state_for(episodes):
    state = {"cities": {}}
    for e in episodes:
        state["cities"].setdefault(e["city_key"], {"episodes": []})["episodes"].append(e)
    q.register_state(state, CUTOFF)
    for ent in q.store(state).values():
        for check in ent["coverage_checks"].values():
            check.update({"status": "complete", "completed_at": NOW.isoformat(), "reason": None})
    return state

def positive_row(e, discriminator="a"):
    start = datetime.fromisoformat(e["alert_start"])
    return {
        "url": "https://example.invalid/offline-verified-" + discriminator,
        "title": "У Києві чули вибухи під час тривоги",
        "publisher": "Offline synthetic source",
        "published_at": (start + timedelta(minutes=20)).isoformat(),
        "source": "Google News RSS",
        "snippet": "Київ, вибухи вночі під час повітряної тривоги",
    }

def classified_positive(e, discriminator="a"):
    rows = []
    now_check = {"label": "immediate", "due_at": e["alert_end"], "checked_at": NOW.isoformat()}
    n, strict = monitor.add_candidates(rows, e["city_key"], [positive_row(e, discriminator)],
                                       [(e, now_check)], [e], NOW)
    assert n == 1 and strict == 1 and len(rows) == 1, (n, strict, rows)
    assert rows[0]["status"] == "approved_strict" and rows[0]["matched_episode_id"] == e["episode_id"]
    rec = p.build_episode_classification(e, rows, origin=p._origin_context())
    assert rec["verdict"] == "STRICT_EVENT_POSITIVE" and rec["source_rows"]
    return rows, rec

def initial_parent(e):
    with psycopg.connect(DSN, autocommit=False) as conn:
        return po.ensure_canonical_parent(conn, e)

def persist(rec, expected_tip=None, fault_after=None):
    with psycopg.connect(DSN, autocommit=False) as conn:
        return p.persist_episode_classification(conn, rec, expected_tip=expected_tip, fault_after=fault_after)

def erase():
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("""TRUNCATE public.attack_event_sources, public.attack_events,
           public.attack_event_classifications, public.alert_episode_sources,
           public.alert_episodes, public.ingestion_checkpoints, public.ingestion_runs
           RESTART IDENTITY CASCADE""")

def sql_one(query, args=()):
    with psycopg.connect(DSN, autocommit=True) as conn:
        return conn.execute(query, args).fetchone()

def snapshot():
    """Stable row-level links, with generated UUIDs resolved to semantic row keys."""
    with psycopg.connect(DSN, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT city_key, legacy_episode_id, start_at, end_at
              FROM public.alert_episodes ORDER BY city_key, legacy_episode_id, start_at""")
            parents = [[str(v) for v in r] for r in cur.fetchall()]
            cur.execute("""SELECT c.city_key, c.historical_episode_id, c.classification_key,
                      c.verdict, c.is_event, c.evidence_set_sha256, prev.classification_key,
                      p.city_key, p.legacy_episode_id, p.start_at, p.end_at
              FROM public.attack_event_classifications c
              LEFT JOIN public.attack_event_classifications prev
                ON prev.classification_uid = c.supersedes_classification_uid
              LEFT JOIN public.alert_episodes p ON p.episode_uid = c.alert_episode_uid
              ORDER BY c.city_key, c.historical_episode_id, c.classification_key""")
            classifications = [[str(v) if v is not None else None for v in r] for r in cur.fetchall()]
            cur.execute("""SELECT c.classification_key, s.source_link_key, s.observation_id,
                        s.content_sha256, s.source_url
              FROM public.attack_event_sources s
              JOIN public.attack_event_classifications c ON s.classification_uid=c.classification_uid
              ORDER BY c.classification_key, s.source_link_key""")
            sources = [[str(v) if v is not None else None for v in r] for r in cur.fetchall()]
            cur.execute("""SELECT e.city_key, e.historical_episode_id, e.attack_event_key,
                        e.event_status, c.classification_key, p.legacy_episode_id
              FROM public.attack_events e
              JOIN public.attack_event_classifications c
                ON c.classification_uid = e.current_classification_uid
              LEFT JOIN public.alert_episodes p ON p.episode_uid = e.alert_episode_uid
              ORDER BY e.city_key, e.historical_episode_id""")
            events = [[str(v) if v is not None else None for v in r] for r in cur.fetchall()]
    return {"parents": parents, "classifications": classifications, "sources": sources, "events": events}

def counts():
    state = snapshot()
    return {k: len(v) for k, v in state.items()}

def get_tip(e):
    with psycopg.connect(DSN, autocommit=True) as conn:
        tips = q.read_current_tips(conn, CUTOFF)
    return tips.get(q.identity_key(q.identity(e)))

def select(state, candidates=(), at=NOW, max_episodes=10):
    with psycopg.connect(DSN, autocommit=False) as conn:
        tips = q.read_current_tips(conn, CUTOFF)
        conn.rollback()
    return q.reconcile_and_select(state, tips=tips, candidates=list(candidates),
                                  cutoff=CUTOFF, max_episodes=max_episodes, now=at)

def independent(rec, saved, expected_tip):
    with psycopg.connect(DSN, autocommit=True) as conn:
        return p.independent_post_commit_readback(conn, rec, saved, expected_tip)

def fail_readback(rec, saved, expected_tip, label):
    try:
        independent(rec, saved, expected_tip)
    except p.PersistenceContractError as exc:
        assert "POST_COMMIT_" in str(exc), (label, exc)
        return type(exc).__name__ + ":" + str(exc)
    raise AssertionError("independent read-back accepted tampering: " + label)

def t1():
    e0, e1 = episode(0), episode(1)
    journal = state_for([e0, e1])
    frozen_journal = json.loads(json.dumps(journal))
    initial_parent(e0)
    rec = p.build_episode_classification(e0, [], origin=p._origin_context())
    first = persist(rec)
    assert first["classification_inserted"]
    assert q.store(journal)[q.identity_key(q.identity(e0))]["status"] == "pending"
    restart = json.loads(json.dumps(frozen_journal))
    selection = select(restart)
    assert selection["db_committed_current"] == 1 and len(selection["selected"]) == 1
    assert selection["selected"][0]["episode"]["episode_id"] == e1["episode_id"]
    assert q.store(restart)[q.identity_key(q.identity(e0))]["status"] == "committed"
    initial_parent(e1)
    result = p.persist_canonical_work(state=restart, selection=selection,
                                       candidates=[], dsn=DSN, at=NOW)
    assert result["committed"] == 1 and result["readback_verified"] == 1, result
    assert counts() == {"parents": 2, "classifications": 2, "sources": 0, "events": 0}
    q.retry(restart, q.identity_key(q.identity(e0)), NOW, "transient-after-recovery")
    serialized = json.loads(json.dumps(restart))
    assert q.store(serialized)[q.identity_key(q.identity(e0))]["attempts"] == 1
    assert select(serialized)["db_committed_current"] == 2
    assert not select(serialized)["selected"]
    return {"commit_before_ack": True, "restarted_from_stale_serialized_journal": True,
            "no_duplicate_revision": True, "unrelated_episode_committed": True,
            "retry_state_serialized": True, "max_batch": 10,
            "input_sha256": p.canonical_sha256(frozen_journal)}

def t2():
    e, other = episode(0), episode(1)
    initial_parent(e)
    base = persist(p.build_episode_classification(e, [], origin=p._origin_context()))
    tip = base["classification_uid"]
    _, r1 = classified_positive(e, "race-1")
    _, r2 = classified_positive(e, "race-2")
    assert r1["classification_key"] != r2["classification_key"]
    key = f"{e['city_key']}|{e['episode_id']}|{r1['alert_start_utc_microseconds']}|{r1['alert_end_utc_microseconds']}"
    start = threading.Barrier(3)
    def writer(rec):
        with psycopg.connect(DSN, autocommit=False) as conn:
            conn.execute("SET lock_timeout = '12000ms'")
            conn.rollback()
            start.wait(timeout=15)
            try:
                res = p.persist_episode_classification(conn, rec, expected_tip=tip)
                return ("COMMITTED", rec["classification_key"], res["source_inserts"])
            except p.PersistenceContractError as exc:
                assert "STALE_EXPECTED_CURRENT_CLASSIFICATION_TIP" in str(exc)
                return ("STALE_REJECTED", rec["classification_key"], 0)
    with psycopg.connect(DSN, autocommit=False) as locker:
        with locker.transaction():
            locker.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (key,))
            with ThreadPoolExecutor(max_workers=2) as pool:
                a, b = pool.submit(writer, r1), pool.submit(writer, r2)
                start.wait(timeout=15)
                locked = False
                for _ in range(100):
                    waiting = sql_one("SELECT count(*) FROM pg_locks WHERE locktype='advisory' AND NOT granted")[0]
                    if waiting >= 2:
                        locked = True
                        break
                    time.sleep(.05)
                assert locked, "both PostgreSQL writers did not wait on the advisory lock"
                initial_parent(other)
                other_saved = persist(p.build_episode_classification(other, [], origin=p._origin_context()))
                assert other_saved["classification_inserted"]
        outcomes = [a.result(timeout=20), b.result(timeout=20)]
    assert sorted(x[0] for x in outcomes) == ["COMMITTED", "STALE_REJECTED"], outcomes
    current = get_tip(e)
    assert current and current["classification_key"] in {r1["classification_key"], r2["classification_key"]}
    assert counts() == {"parents": 2, "classifications": 3, "sources": 1, "events": 1}, counts()
    rec = r1 if current["classification_key"] == r1["classification_key"] else r2
    with psycopg.connect(DSN, autocommit=True) as conn:
        cur = conn.execute("SELECT classification_uid FROM public.attack_event_classifications WHERE classification_key=%s",
                           (rec["classification_key"],))
        uid = str(cur.fetchone()[0])
    independent(rec, {"classification_uid": uid, "classification_inserted": True}, tip)
    return {"waiting_writers": 2, "one_committed": True, "one_stale_failed_closed": True,
            "unrelated_completed_while_same_episode_locked": True, "one_current_tip": True,
            "input_sha256": p.canonical_sha256([r1["classification_key"],r2["classification_key"]])}

def t3():
    e = episode(0)
    initial_parent(e)
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("UPDATE public.alert_episodes SET end_at=end_at+interval '1 minute' WHERE legacy_episode_id=%s",
                     (e["episode_id"],))
    try:
        with psycopg.connect(DSN, autocommit=False) as conn:
            po.ensure_canonical_parent(conn, e)
    except po.CanonicalParentIdentityMismatch as exc:
        same_id = str(exc)
    else:
        raise AssertionError("same identity / different interval was bound")
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("UPDATE public.alert_episodes SET end_at=end_at-interval '1 minute' WHERE legacy_episode_id=%s",
                     (e["episode_id"],))
        conn.execute("UPDATE public.alert_episodes SET legacy_episode_id=%s WHERE legacy_episode_id=%s",
                     ("f"*24, e["episode_id"]))
    try:
        with psycopg.connect(DSN, autocommit=False) as conn:
            po.ensure_canonical_parent(conn, e)
    except po.CanonicalParentIdentityMismatch as exc:
        same_interval = str(exc)
    else:
        raise AssertionError("same interval / different identity was bound")
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("UPDATE public.alert_episodes SET legacy_episode_id=%s WHERE legacy_episode_id=%s",
                     (e["episode_id"], "f"*24))
    try:
        with psycopg.connect(DSN, autocommit=False) as conn:
            with conn.transaction():
                conn.execute("""INSERT INTO public.alert_episodes
                  (legacy_episode_id,city_key,alert_type,start_at,end_at,episode_state,
                   canonicalization_version,created_by_run_id,updated_by_run_id)
                  SELECT %s,city_key,alert_type,start_at,end_at,episode_state,
                    canonicalization_version,created_by_run_id,updated_by_run_id
                  FROM public.alert_episodes WHERE legacy_episode_id=%s""",
                  ("e"*24, e["episode_id"]))
    except UniqueViolation:
        pg_unique = True
    else:
        raise AssertionError("PG16 did not enforce unique canonical interval")
    base_rec = p.build_episode_classification(e, [], origin=p._origin_context())
    persist(base_rec)
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("UPDATE public.alert_episodes SET end_at=end_at+interval '1 minute' WHERE legacy_episode_id=%s",
                     (e["episode_id"],))
    journal = state_for([e])
    selection = select(journal)
    ent = q.store(journal)[q.identity_key(q.identity(e))]
    assert selection["quarantined"] == 1 and ent["status"] == "quarantined", selection
    assert not selection["selected"] and counts()["classifications"] == 1
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("UPDATE public.alert_episodes SET end_at=end_at-interval '1 minute' WHERE legacy_episode_id=%s",
                     (e["episode_id"],))
    assert counts()["sources"] == 0 and counts()["events"] == 0
    return {"same_id_different_interval": same_id.split(":")[0],
            "same_interval_different_id": same_interval.split(":")[0],
            "schema_uniqueness_rejected": pg_unique, "db_tip_parent_conflict_quarantined": True,
            "no_conflicting_classification_committed": True, "input_sha256": p.canonical_sha256(e)}

def seed_source(conn, source_key, classification_uid, observation_id, content_hash):
    provenance = {"kind": "disposable-pg16-source-failure-injection"}
    conn.execute("""INSERT INTO public.attack_event_sources
        (source_link_key_version,source_link_key,classification_uid,observation_id,
         content_sha256,content_hash_basis,evidence_payload,origin_provenance,
         origin_provenance_sha256,source_type_state,source_timestamp_state)
         VALUES (%s,%s,%s,%s,%s,'NORMALIZED_EVIDENCE',%s,%s,%s,
                 'UNMATERIALIZED_IN_ACCEPTED_SOURCE','ABSENT_IN_ACCEPTED_SOURCE')""",
         (p.SOURCE_LINK_KEY_VERSION, source_key, classification_uid, observation_id,
          content_hash, Jsonb({}), Jsonb(provenance), p.canonical_sha256(provenance)))

def t4():
    e, other = episode(0), episode(1)
    initial_parent(e)
    initial_parent(other)
    aux = persist(p.build_episode_classification(other, [], origin=p._origin_context()))
    _, rec = classified_positive(e, "source-conflict")
    source = rec["source_rows"][0]
    with psycopg.connect(DSN, autocommit=True) as conn:
        seed_source(conn, source["source_link_key"], aux["classification_uid"],
                    source["observation_id"], "0"*64)
    try:
        persist(rec)
    except p.PersistenceContractError as exc:
        conflict = str(exc)
        assert "source-link semantic conflict" in conflict
    else:
        raise AssertionError("source collision was silently accepted")
    assert counts() == {"parents": 2, "classifications": 1, "sources": 1, "events": 0}
    try:
        with psycopg.connect(DSN, autocommit=False) as conn:
            with conn.transaction():
                seed_source(conn, "d"*64, str(uuid.uuid4()), "invalid-parent", "a"*64)
    except ForeignKeyViolation as exc:
        fk_constraint = exc.diag.constraint_name
    else:
        raise AssertionError("real source FK violation was accepted")
    assert fk_constraint == "attack_event_sources_classification_uid_fkey", fk_constraint
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("DELETE FROM public.attack_event_sources WHERE source_link_key=%s",
                     (source["source_link_key"],))
    valid = persist(rec)
    assert valid["classification_inserted"] and valid["source_inserts"] == 1
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("UPDATE public.attack_event_sources SET content_sha256=%s WHERE source_link_key=%s",
                     ("f"*64, source["source_link_key"]))
    try:
        persist(rec, expected_tip=valid["classification_uid"])
    except p.PersistenceContractError as exc:
        content_conflict = str(exc)
        assert "source-link semantic conflict" in content_conflict
    else:
        raise AssertionError("source-content drift was silently accepted")
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("UPDATE public.attack_event_sources SET content_sha256=%s WHERE source_link_key=%s",
                     (source["content_sha256"], source["source_link_key"]))
    independent(rec, valid, None)
    assert counts() == {"parents": 2, "classifications": 2, "sources": 1, "events": 1}
    return {"identity_conflict": conflict, "content_conflict": content_conflict,
            "actual_fk_constraint": fk_constraint, "atomic_rollback": True,
            "source_hash_restored": True, "input_sha256": p.canonical_sha256(source)}

def t5():
    e = episode(0)
    initial_parent(e)
    state = state_for([e])
    neg_sel = select(state)
    first = p.persist_canonical_work(state=state, selection=neg_sel, candidates=[], dsn=DSN, at=NOW)
    assert first["committed"] == 1 and first["readback_verified"] == 1, first
    negative = get_tip(e)
    assert negative is not None and counts()["events"] == 0
    rows, rec = classified_positive(e, "followup")
    entry = q.store(state)[q.identity_key(q.identity(e))]
    entry["evidence_snapshots"] = {row["candidate_id"]: copy.deepcopy(row) for row in rows}
    pos_sel = select(state, rows)
    assert len(pos_sel["selected"]) == 1 and pos_sel["selected"][0]["expected_current_tip"] == negative["classification_uid"], pos_sel
    moved = p.persist_canonical_work(state=state, selection=pos_sel, candidates=rows,
                                     dsn=DSN, at=NOW)
    assert moved["committed"] == 1 and moved["readback_verified"] == 1 and moved["classification_revisions"] == 1, moved
    assert counts() == {"parents": 1, "classifications": 2, "sources": 1, "events": 1}
    current = get_tip(e)
    assert current and current["classification_key"] == rec["classification_key"]
    with psycopg.connect(DSN, autocommit=True) as conn:
        relation = conn.execute("""SELECT prev.classification_key, cur.revision_reason,
           e.event_status, event_tip.classification_key
           FROM public.attack_event_classifications cur
           JOIN public.attack_event_classifications prev
             ON prev.classification_uid=cur.supersedes_classification_uid
           JOIN public.attack_events e ON e.current_classification_uid=cur.classification_uid
           JOIN public.attack_event_classifications event_tip
             ON event_tip.classification_uid=e.current_classification_uid
           WHERE cur.classification_key=%s""", (rec["classification_key"],)).fetchone()
    assert relation == (negative["classification_key"],"LIVE_FOLLOWUP_RECLASSIFICATION",
                        "ACTIVE",rec["classification_key"]), relation
    assert not select(state, rows)["selected"]
    return {"initial": "NO_CONFIRMED_EVENT", "revised": "STRICT_EVENT_POSITIVE",
            "authoritative_classifier_invoked": True, "source_links": 1,
            "attack_event_active": True, "revision_chain_exact": True,
            "input_sha256": p.canonical_sha256(rows)}

def t6():
    e = episode(0)
    initial_parent(e)
    rows, rec = classified_positive(e, "retention")
    state = state_for([e])
    entry = q.store(state)[q.identity_key(q.identity(e))]
    entry["evidence_snapshots"] = {row["candidate_id"]: copy.deepcopy(row) for row in rows}
    initial_sel = select(state, rows)
    first = p.persist_canonical_work(state=state, selection=initial_sel, candidates=rows, dsn=DSN, at=NOW)
    assert first["committed"] == 1 and first["readback_verified"] == 1
    before = snapshot()
    # Approved observations can disappear from the mutable discovery queue, but
    # the authoritative retention policy must not reinterpret absence as a negative.
    recovered = q.relevant_evidence(entry, [])
    assert len(recovered) == 1 and recovered[0]["status"] == "approved_strict"
    post_drop_sel = select(state, [])
    assert not post_drop_sel["selected"] and post_drop_sel["db_committed_current"] == 1
    assert snapshot() == before
    assert get_tip(e)["classification_key"] == rec["classification_key"]
    return {"requested_transition": "STRICT_EVENT_POSITIVE -> NO_CONFIRMED_EVENT",
            "decision": "REJECTED_BY_DURABLE_POSITIVE_EVIDENCE_RETENTION_POLICY",
            "no_manual_demote_or_classifier_override": True,
            "no_withdrawal_without_valid_review": True, "event_remains_active": True,
            "input_sha256": p.canonical_sha256(rows)}

def t7():
    e = episode(0)
    initial_parent(e)
    rows, rec = classified_positive(e, "event-fault")
    before = counts()
    try:
        persist(rec, expected_tip=None, fault_after="event")
    except RuntimeError as exc:
        failure = str(exc)
        assert "FORCED_PERSISTENCE_FAILURE_AFTER_EVENT" in failure
    else:
        raise AssertionError("event-stage injected fault did not fire")
    assert counts() == before == {"parents": 1, "classifications": 0, "sources": 0, "events": 0}, counts()
    saved = persist(rec, expected_tip=None)
    assert saved["classification_inserted"] and saved["event_inserted"] and saved["source_inserts"] == 1
    independent(rec, saved, None)
    assert counts() == {"parents": 1, "classifications": 1, "sources": 1, "events": 1}
    return {"injected_failure": failure, "atomic_three_table_rollback": True,
            "retry_one_consistent_commit": True, "input_sha256": p.canonical_sha256(rows)}

def t8():
    e, decoy = episode(0), episode(1)
    initial_parent(e)
    initial_parent(decoy)
    rows, rec = classified_positive(e, "readback")
    state = state_for([e])
    entry = q.store(state)[q.identity_key(q.identity(e))]
    entry["evidence_snapshots"] = {row["candidate_id"]: copy.deepcopy(row) for row in rows}
    selection = select(state, rows)
    assert len(selection["selected"]) == 1
    original = p.independent_post_commit_readback
    source_key = rec["source_rows"][0]["source_link_key"]
    source_hash = rec["source_rows"][0]["content_sha256"]
    def tamper_before_verify(verifier, record, persisted, expected_tip):
        with psycopg.connect(DSN, autocommit=True) as mutator:
            mutator.execute("UPDATE public.attack_event_sources SET content_sha256=%s WHERE source_link_key=%s",
                            ("f"*64, source_key))
        return original(verifier, record, persisted, expected_tip)
    p.independent_post_commit_readback = tamper_before_verify
    try:
        result = p.persist_canonical_work(state=state, selection=selection, candidates=rows, dsn=DSN, at=NOW)
    finally:
        p.independent_post_commit_readback = original
    assert result["retryable"] == 1 and result["committed"] == 0 and result["readback_verified"] == 0, result
    assert entry["status"] == "retryable_failure" and entry["last_committed_key"] is None
    recovered = json.loads(json.dumps(state))
    assert q.store(recovered)[q.identity_key(q.identity(e))]["attempts"] == 1
    assert counts() == {"parents": 2, "classifications": 1, "sources": 1, "events": 1}
    with psycopg.connect(DSN, autocommit=True) as conn:
        uid = str(conn.execute("SELECT classification_uid FROM public.attack_event_classifications WHERE classification_key=%s",
                               (rec["classification_key"],)).fetchone()[0])
    saved = {"classification_uid": uid, "classification_inserted": True}
    detected = {"source_link": fail_readback(rec, saved, None, "content")}
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("UPDATE public.attack_event_sources SET content_sha256=%s WHERE source_link_key=%s",
                     (source_hash, source_key))
    independent(rec, saved, None)
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("UPDATE public.attack_event_classifications SET classification_key=%s WHERE classification_uid=%s",
                     ("e"*64, uid))
    detected["current_tip"] = fail_readback(rec, saved, None, "tip")
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("UPDATE public.attack_event_classifications SET classification_key=%s WHERE classification_uid=%s",
                     (rec["classification_key"], uid))
        decoy_uid = str(conn.execute("SELECT episode_uid FROM public.alert_episodes WHERE legacy_episode_id=%s",
                                     (decoy["episode_id"],)).fetchone()[0])
        original_uid = str(conn.execute("SELECT episode_uid FROM public.alert_episodes WHERE legacy_episode_id=%s",
                                        (e["episode_id"],)).fetchone()[0])
        conn.execute("UPDATE public.attack_event_classifications SET alert_episode_uid=%s WHERE classification_uid=%s",
                     (decoy_uid, uid))
    detected["parent"] = fail_readback(rec, saved, None, "parent")
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("UPDATE public.attack_event_classifications SET alert_episode_uid=%s WHERE classification_uid=%s",
                     (original_uid, uid))
        conn.execute("DELETE FROM public.attack_event_sources WHERE source_link_key=%s", (source_key,))
    detected["required_source_missing"] = fail_readback(rec, saved, None, "missing-source")
    # Repeat the actual writer idempotently: it must recreate its missing link.
    recreated = persist(rec, expected_tip=uid)
    assert recreated["classification_inserted"] is False and recreated["source_inserts"] == 1
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("UPDATE public.attack_events SET event_status='WITHDRAWN' WHERE attack_event_key=%s",
                     (rec["attack_event_key"],))
    detected["event_status"] = fail_readback(rec, saved, None, "event-status")
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("UPDATE public.attack_events SET event_status='ACTIVE' WHERE attack_event_key=%s",
                     (rec["attack_event_key"],))
    independent(rec, saved, None)
    assert counts() == {"parents": 2, "classifications": 1, "sources": 1, "events": 1}
    # A later valid independent read-back is allowed to reconcile completion.
    assert select(recovered, rows)["db_committed_current"] == 1
    assert q.store(recovered)[q.identity_key(q.identity(e))]["status"] == "committed"
    return {"corruptions_detected": detected, "journal_not_acknowledged_on_failed_readback": True,
            "retry_survives_restart": True, "valid_repair_reconciled_after_independent_readback": True,
            "input_sha256": p.canonical_sha256(rows)}

def main():
    report = {
        "matrix": "kyiv-live-canonical-queue-pg16-safety-2026-10-11",
        "schema_git_blob": p._git_blob_sha(ROOT / "tests/fixtures/pg16_verified_canonical_schema.sql"),
        "persistence_git_blob": p._git_blob_sha(ROOT / "scripts/attack_event_canonical_persistence.py"),
        "queue_git_blob": p._git_blob_sha(ROOT / "scripts/live_canonical_queue.py"),
        "parent_git_blob": p._git_blob_sha(ROOT / "scripts/live_parent_ordering.py"),
        "authoritative_classifier_blob": monitor.AUTHORITATIVE_CLASSIFIER_BLOB,
        "postgres_major": None,
        "canary_max": int(os.environ["ATTACK_EVENT_PERSISTENCE_CANARY_MAX_EPISODES"]),
        "cases": {}, "failures": [],
    }
    assert report["canary_max"] == 10
    with psycopg.connect(DSN, autocommit=True) as conn:
        v = conn.execute("SHOW server_version_num").fetchone()[0]
        assert 160000 <= int(v) < 170000, v
        report["postgres_major"] = 16
    for name, fn in (("T1", t1),("T2", t2),("T3", t3),("T4", t4),
                     ("T5", t5),("T6", t6),("T7", t7),("T8", t8)):
        erase()
        pre = snapshot()
        try:
            details = fn()
            report["cases"][name] = {"status": "PASS", "pre": pre,
                                      "post": snapshot(), "assertions": details}
        except Exception as exc:
            report["failures"].append(name)
            report["cases"][name] = {"status": "FAIL", "pre": pre, "post": snapshot(),
                                      "error": type(exc).__name__ + ":" + str(exc)}
    canonical = json.dumps(report,sort_keys=True,separators=(",",":"),ensure_ascii=False)
    report["fingerprint"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    print(json.dumps(report,sort_keys=True,indent=2,ensure_ascii=False))
    return 0 if not report["failures"] else 1

if __name__ == "__main__":
    sys.exit(main())
