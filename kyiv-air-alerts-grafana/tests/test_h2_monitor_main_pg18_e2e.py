#!/usr/bin/env python3
"""Full actual monitor.main() -> real PG18 offline E2E, deliberately reduced schema.

Never connect to Neon or use production credentials. Every scenario gets synthetic
files and a reset ephemeral SQL fixture. Parent contract SQL is the pinned
site-prod implementation, not a stub. Source network adapters are fail-closed.
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from unittest import mock

import psycopg

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
DSN = os.environ["H2_OFFLINE_POSTGRES_DSN"]
assert ("127.0.0.1" in DSN or "localhost" in DSN) and "synthetic_only" in DSN
assert os.environ.get("CANONICAL_PARENT_DB_BRANCH") == "synthetic-offline"
assert os.environ.get("ATTACK_EVENT_ORIGIN_COMMIT_SHA") == "f" * 40
os.environ["H2_TEST_PHASE"] = "post_fix"

import monitor_explosion_candidates as mon
import attack_event_canonical_persistence as writer
import attack_event_tip_snapshot as snapshot
import live_parent_ordering as parent

# The accepted T1-T24 and extra regressions really run first against this
# exact PG18 service. We reuse only its DDL constructor, not its mock SQL.
legacy = runpy.run_path(str(HERE / "test_h2_canonical_writer_pg18_offline.py"))
assert all(x == "PASS" for x in legacy["test_results"].values()), legacy["test_results"]

UTC = timezone.utc
T0 = datetime(2026, 1, 1, 4, 21, tzinfo=UTC)
CITY = "kharkiv"
CASE_LOG = {}
NETWORK = {"live_calls": 0, "stubbed_news_queries": 0, "stubbed_telegram_pages": 0}
CURRENT_TEST = None

def conn():
    c = psycopg.connect(DSN, autocommit=True)
    c.execute("SET lock_timeout = '5s'")
    c.execute("SET statement_timeout = '15s'")
    return c

def reset_schema():
    with conn() as c:
        c.execute("DROP TABLE IF EXISTS public.ingestion_runs CASCADE")
        legacy["schema"](c)
        c.execute("ALTER TABLE public.alert_episodes ADD COLUMN created_by_run_id uuid")
        c.execute("ALTER TABLE public.alert_episodes ADD COLUMN updated_by_run_id uuid")
        c.execute("CREATE UNIQUE INDEX synthetic_parent_episode_unique ON public.alert_episodes(legacy_episode_id)")
        c.execute("""CREATE TABLE public.ingestion_runs (
            run_id uuid PRIMARY KEY, run_kind text, source_key text, city_key text,
            workflow_repository text, workflow_name text, workflow_ref text,
            workflow_sha text, input_repository text, input_ref text, input_sha text,
            github_run_id bigint, github_run_attempt bigint, db_branch text,
            schema_version text, canonicalization_version text, status text,
            started_at timestamptz, ingest_committed_at timestamptz,
            finished_at timestamptz, parameters jsonb, stats jsonb
        )""")
        c.execute("""ALTER TABLE public.attack_event_classifications
            ADD CONSTRAINT synthetic_classification_parent_fk
            FOREIGN KEY (alert_episode_uid) REFERENCES public.alert_episodes(episode_uid)""")
        c.execute("""ALTER TABLE public.attack_events
            ADD CONSTRAINT synthetic_event_parent_fk
            FOREIGN KEY (alert_episode_uid) REFERENCES public.alert_episodes(episode_uid)""")

def read_db():
    with conn() as c:
        counts = {}
        for t in ("alert_episodes", "ingestion_runs", "attack_event_classifications",
                  "attack_event_sources", "attack_events"):
            counts[t] = c.execute("SELECT count(*) FROM public." + t).fetchone()[0]
        rows = c.execute("""SELECT a.city_key,a.legacy_episode_id,a.episode_uid::text,
                                   a.start_at::text,a.end_at::text
                            FROM public.alert_episodes a ORDER BY a.start_at,a.episode_uid""").fetchall()
        classifications = c.execute("""SELECT historical_episode_id,classification_key,
                                    classification_uid::text,supersedes_classification_uid::text,
                                    alert_episode_uid::text,verdict
                                    FROM public.attack_event_classifications
                                    ORDER BY historical_episode_id,created_at,classification_uid""").fetchall()
        tips = c.execute("""SELECT c.historical_episode_id,c.classification_uid::text
             FROM public.attack_event_classifications c
             WHERE NOT EXISTS (SELECT 1 FROM public.attack_event_classifications n
              WHERE n.supersedes_classification_uid=c.classification_uid)
             ORDER BY c.historical_episode_id,c.classification_uid""").fetchall()
        broken_sources = c.execute("""SELECT count(*) FROM public.attack_event_sources s
            LEFT JOIN public.attack_event_classifications c
            ON s.classification_uid=c.classification_uid
            WHERE c.classification_uid IS NULL""").fetchone()[0]
        broken_events = c.execute("""SELECT count(*) FROM public.attack_events e
            LEFT JOIN public.attack_event_classifications c
            ON e.current_classification_uid=c.classification_uid
            WHERE c.classification_uid IS NULL""").fetchone()[0]
        wrong_parents = c.execute("""SELECT count(*) FROM public.attack_event_classifications c
            LEFT JOIN public.alert_episodes a ON c.alert_episode_uid=a.episode_uid
            WHERE a.episode_uid IS NULL OR a.legacy_episode_id<>c.historical_episode_id
            OR a.city_key<>c.city_key OR a.start_at<>c.alert_start_at
            OR a.end_at<>c.alert_end_at""").fetchone()[0]
    return {"counts": counts, "parents": rows, "classifications": classifications,
            "tips": tips, "broken_sources": broken_sources,
            "broken_events": broken_events, "wrong_parents": wrong_parents}

def assert_integrity(db):
    assert db["broken_sources"] == db["broken_events"] == db["wrong_parents"] == 0, db
    assert len(db["tips"]) == len({x[0] for x in db["tips"]}), db["tips"]
    assert db["counts"]["attack_event_classifications"] == len(db["classifications"])

def json_write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def json_read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def file_receipt(path):
    if not path.exists():
        return {"exists": False, "bytes": 0, "sha256": None}
    raw = path.read_bytes()
    return {"exists": True, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}

def leak(*args, **kwargs):
    NETWORK["live_calls"] += 1
    raise AssertionError("FORBIDDEN_LIVE_NETWORK_ADAPTER")

def fake_telegram(*args, **kwargs):
    NETWORK["stubbed_telegram_pages"] += 1
    return [], "offline-synthetic"

def fake_news(*args, **kwargs):
    NETWORK["stubbed_news_queries"] += 1
    return [], None, {"query_urls": {}, "query_family_result_counts": {},
                       "fulltext_fetches": 0, "fulltext_rescued_candidates": 0,
                       "results_after_family_merge": 0}

def queue_row(ep, label="first", status="approved_strict"):
    return {"candidate_id": "synthetic-" + label,
            "city_key": CITY, "matched_episode_id": ep["episode_id"],
            "classification_evidence": {"classification_episode_id": ep["episode_id"]},
            "source": "synthetic", "status": status,
            "title": "Offline synthetic " + label,
            "url": "https://example.invalid/" + label,
            "first_discovered_at": "2026-01-01T00:00:00Z"}

class Fixture:
    def __init__(self, number=1):
        self.tmp = tempfile.TemporaryDirectory(prefix="h2-real-monitor-main-")
        self.root = Path(self.tmp.name)
        self.state_path = self.root / "data" / "state.json"
        self.queue_path = self.root / "data" / "queue.json"
        self.report_path = self.root / "data" / "last_run.json"
        self.baseline_path = self.root / "data" / "baseline.json"
        self.bridge_path = self.root / "data" / "bridge.json"
        self.kyiv_path = self.root / "data" / "kyiv.json"
        self.sevastopol_path = self.root / "data" / "sevastopol.json"
        self.activation_path = self.root / "config" / "activation.json"
        self.clock = T0
        self.episodes = []
        for i in range(number):
            start = datetime(2026, 1, 1, 0, 0, tzinfo=UTC) + timedelta(hours=i * 2)
            end = start + timedelta(minutes=20)
            self.episodes.append(mon.make_episode(CITY, start, end))
        json_write(self.baseline_path, {"cities": {CITY: {"coverage_end": "2025-12-31"}}})
        json_write(self.kyiv_path, [])
        json_write(self.sevastopol_path, {"pairs": []})
        json_write(self.activation_path, {"schema_version": 1,
            "eligibility_field": "alert_end", "boundary": "inclusive",
            "activation_cutoff_utc": "2026-01-01T00:00:00Z"})
        json_write(self.state_path, {"schema_version": 1, "cities": {CITY: {
            "city": "Харків", "baseline_coverage_end": "2025-12-31",
            "episodes": self.episodes}}})
        json_write(self.queue_path, [queue_row(ep, "first-" + str(i)) for i, ep in enumerate(self.episodes)])
        self.refresh_bridge()

    def refresh_bridge(self):
        json_write(self.bridge_path, {"events": [], "regions": {
            CITY: {"last_checked_at": mon.iso(self.clock)}}})

    def advance(self, when):
        self.clock = when
        self.refresh_bridge()

    def files(self):
        return {name: file_receipt(path) for name, path in
                [("state", self.state_path), ("queue", self.queue_path),
                 ("last_run", self.report_path)]}

    @contextlib.contextmanager
    def isolated(self):
        with contextlib.ExitStack() as e:
            changes = {
                "CITY_CONFIG": {CITY: copy.deepcopy(mon.ALL_CITY_CONFIG[CITY])},
                "STATE_FILE": self.state_path, "QUEUE_FILE": self.queue_path,
                "LAST_RUN_FILE": self.report_path, "BASELINE_FILE": self.baseline_path,
                "BRIDGE_FILE": self.bridge_path,
                "KYIV_ALERTS_FILE": self.kyiv_path,
                "SEVASTOPOL_EVENTS_FILE": self.sevastopol_path,
                "LIVE_PERSISTENCE_ACTIVATION_FILE": self.activation_path,
                "now_utc": lambda: self.clock,
                "telegram_page": fake_telegram,
                "search_city_news": fake_news,
                "poll_alerts": leak,
                "fetch_publisher_fulltext": leak,
            }
            for key, value in changes.items():
                e.enter_context(mock.patch.object(mon, key, value))
            e.enter_context(mock.patch.object(mon.ua, "UkraineAlarmClient", leak))
            e.enter_context(mock.patch("requests.sessions.Session.request", side_effect=leak))
            e.enter_context(mock.patch("urllib.request.urlopen", side_effect=leak))
            e.enter_context(mock.patch.dict(os.environ, {
                "ATTACK_EVENT_DATABASE_URL": DSN,
                "ATTACK_EVENT_PERSISTENCE_CANARY_MAX_EPISODES": "10",
                "PRODUCTION_PERSISTENCE_CANARY_CUTOFF": "",
            }))
            yield self

    def main(self):
        argv = ["monitor_explosion_candidates.py", "--local-only",
                "--bridge-file", str(self.bridge_path),
                "--kyiv-alerts-file", str(self.kyiv_path),
                "--sevastopol-events-file", str(self.sevastopol_path)]
        with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
            mon.main()
        return json_read(self.report_path)

    def close(self):
        self.tmp.cleanup()

def assert_completed(f, db, expected):
    saved = json_read(f.state_path)
    report = json_read(f.report_path)
    checks = [(e["episode_id"], e["checks"][0]["checked_at"])
              for e in saved["cities"][CITY]["episodes"]]
    completed = [eid for eid, checked in checks if checked]
    assert len(completed) == expected, (checks, db)
    assert report["canonical_persistence"]["episodes_persisted"] >= 0
    assert_integrity(db)
    for eid in completed:
        assert sum(1 for c in db["classifications"] if c[0] == eid) >= 1, (eid,db)
    return {"completed": completed, "checks": checks,
            "db_counts": db["counts"], "db_tip_count": len(db["tips"]),
            "canonical_persistence": report["canonical_persistence"],
            "report_ok": report["ok"], "report_mode": report["mode"]}

def record_case(name, fn):
    reset_schema()
    before_network = NETWORK["live_calls"]
    try:
        trace = fn()
        assert NETWORK["live_calls"] == before_network == 0, NETWORK
        CASE_LOG[name] = {"status": "PASS", **trace}
        print(name + ": PASS", flush=True)
    except Exception as exc:
        CASE_LOG[name] = {"status": "FAIL", "error": repr(exc)}
        print(name + ": FAIL " + repr(exc), flush=True)
        raise

def first_restart_revision():
    f = Fixture()
    try:
        with f.isolated():
            initial_files = f.files()
            r1 = f.main()
            db1 = read_db()
            check1 = assert_completed(f, db1, 1)
            assert db1["counts"]["alert_episodes"] == 1 and db1["counts"]["ingestion_runs"] == 1
            assert db1["counts"]["attack_event_classifications"] == 1
            assert db1["counts"]["attack_event_sources"] == 1
            assert db1["counts"]["attack_events"] == 1
            assert check1["canonical_persistence"]["classification_inserts"] == 1
            assert r1["parent_ordering"]["parents_newly_inserted"] == 1
            CASE_LOG["M1"] = {"status": "PASS", "before_files": initial_files,
                              "after_files": f.files(), "readback": check1,
                              "parents": db1["parents"]}
            r2 = f.main()
            db2 = read_db()
            assert db2["counts"] == db1["counts"] and db2["tips"] == db1["tips"]
            assert r2["canonical_persistence"]["classification_inserts"] == 0
            assert r2["canonical_persistence"]["episodes_persisted"] == 0
            CASE_LOG["M2"] = {"status": "PASS", "readback": assert_completed(f, db2, 1),
                              "after_files": f.files()}
            f.advance(T0 + timedelta(days=1))
            queue = json_read(f.queue_path)
            queue.append(queue_row(f.episodes[0], "followup", "approved_sensitivity"))
            json_write(f.queue_path, queue)
            r3 = f.main()
            db3 = read_db()
            assert db3["counts"]["attack_event_classifications"] == 2, db3
            assert len(db3["tips"]) == 1
            assert r3["canonical_persistence"]["classification_revisions"] == 1, r3
            assert db3["classifications"][1][3] == db3["classifications"][0][2]
            check3 = assert_completed(f, db3, 1)
            checks = json_read(f.state_path)["cities"][CITY]["episodes"][0]["checks"]
            assert checks[0]["checked_at"] and checks[1]["checked_at"], checks
            CASE_LOG["M3"] = {"status": "PASS", "readback": check3,
                              "after_files": f.files(), "revision_chain": db3["classifications"]}
    finally:
        f.close()

def stale_race(refresh_badly=False):
    f = Fixture()
    pins = {}
    try:
        original = snapshot.observe_expected_tips
        with f.isolated(), mock.patch.object(snapshot, "observe_expected_tips") as hook:
            def race(due, *, dsn=None, connection=None):
                with conn() as c_snapshot:
                    pins["snapshot_pid"] = c_snapshot.execute("SELECT pg_backend_pid()").fetchone()[0]
                    out = original(due, connection=c_snapshot)
                ep = f.episodes[0]
                identity = snapshot.episode_identity(ep)
                assert out[identity]["expected_current_tip"] is None
                pins["snapshot_tip"] = out[identity]["expected_current_tip"]
                pins["snapshot_parent_uid"] = out[identity]["canonical_parent_uid"]
                with conn() as c_compete:
                    pins["competitor_pid"] = c_compete.execute("SELECT pg_backend_pid()").fetchone()[0]
                    rec = writer.build_episode_classification(ep,[queue_row(ep,"competitor")])
                    committed = writer.persist_episode_classification(
                        c_compete,rec,expected_current_tip=None,
                        expected_parent_uid=pins["snapshot_parent_uid"])
                    assert committed["commit_state"] == "COMMITTED"
                    pins["competing_classification_uid"] = committed["classification_uid"]
                return out
            hook.side_effect = race
            before = f.files()
            error = None
            try:
                f.main()
            except writer.PersistenceContractError as exc:
                error = str(exc)
            assert error and "STALE_EXPECTED_TIP" in error, error
            db = read_db()
            assert len(db["tips"]) == 1 and db["tips"][0][1] == pins["competing_classification_uid"]
            assert db["counts"]["attack_event_classifications"] == 1
            assert f.files() == before
            assert pins["snapshot_pid"] != pins["competitor_pid"]
            assert_integrity(db)
            return {"before_files": before, "after_files": f.files(),
                    "race": pins, "rejection": error[:220], "db_counts": db["counts"]}
    finally:
        f.close()

def unavailable():
    f = Fixture()
    try:
        with f.isolated():
            before = f.files()
            with mock.patch.dict(os.environ, {"ATTACK_EVENT_DATABASE_URL":
                "postgresql://h2_local:synthetic_only@127.0.0.1:1/h2_offline"}):
                try: f.main()
                except (psycopg.Error, parent.ParentOrderingError, writer.PersistenceContractError): pass
                else: raise AssertionError("database unavailable did not fail")
            db = read_db()
            assert db["counts"]["attack_event_classifications"] == 0
            assert f.files() == before
            return {"before_files": before, "after_files": f.files(), "db_counts": db["counts"]}
    finally:
        f.close()

def incomplete():
    f = Fixture()
    try:
        with f.isolated(), mock.patch.object(mon,"search_city_news",side_effect=RuntimeError("synthetic incomplete coverage")):
            before = f.files()
            report = f.main()
            db = read_db()
            assert report["ok"] is False and report["canonical_persistence"]["episodes_skipped_incomplete_coverage"] == 1, report
            saved = json_read(f.state_path)
            assert saved["cities"][CITY]["episodes"][0]["checks"][0]["checked_at"] is None
            assert db["counts"]["attack_event_classifications"] == 0
            assert f.files()["last_run"]["exists"]
            assert_integrity(db)
            return {"before_files": before, "after_files": f.files(),
                    "db_counts": db["counts"],
                    "checkpoint_pending": True,
                    "canonical_persistence": report["canonical_persistence"]}
    finally:
        f.close()

def inject_failure(partial=False):
    f = Fixture(2 if partial else 1)
    original = writer.persist_episode_classification
    before = None
    try:
        with f.isolated():
            before = f.files()
            count = {"calls": 0}
            def fault(conn, rec, **kw):
                count["calls"] += 1
                if not partial or count["calls"] == 2:
                    return original(conn,rec,fault_after="classification",**kw)
                return original(conn,rec,**kw)
            with mock.patch.object(writer, "persist_episode_classification", side_effect=fault):
                try: f.main()
                except RuntimeError as exc:
                    assert "FORCED_PERSISTENCE_FAILURE_AFTER_CLASSIFICATION" in str(exc), exc
                else: raise AssertionError("expected PostgreSQL transaction rollback fault")
            db = read_db()
            assert db["counts"]["alert_episodes"] == (2 if partial else 1)
            assert db["counts"]["attack_event_classifications"] == (1 if partial else 0)
            assert db["counts"]["attack_event_sources"] == (1 if partial else 0)
            assert db["counts"]["attack_events"] == (1 if partial else 0)
            assert f.files() == before
            assert_integrity(db)
            phase = {"before_files": before, "after_files": f.files(),
                     "db_counts": db["counts"], "real_writer_calls": count["calls"],
                     "parents": db["parents"]}
            if not partial: return phase
            CASE_LOG["M8"] = {"status":"PASS", **phase}
            after = f.main()
            db_after = read_db()
            assert db_after["counts"]["alert_episodes"] == 2
            assert db_after["counts"]["attack_event_classifications"] == 2
            assert db_after["counts"]["attack_event_sources"] == 2
            assert db_after["counts"]["attack_events"] == 2
            assert len(db_after["tips"]) == 2
            assert after["canonical_persistence"]["episodes_persisted"] == 2
            assert after["canonical_persistence"]["classification_inserts"] == 1, after
            report = assert_completed(f, db_after, 2)
            CASE_LOG["M9"] = {"status":"PASS", "after_files": f.files(),
                              "readback": report, "db_counts": db_after["counts"]}
            final = f.main()
            db_final = read_db()
            assert db_after["counts"] == db_final["counts"]
            assert db_after["tips"] == db_final["tips"]
            assert final["canonical_persistence"]["episodes_persisted"] == 0
            CASE_LOG["M10"] = {"status":"PASS", "after_files": f.files(),
                               "readback": assert_completed(f, db_final, 2),
                               "db_counts": db_final["counts"]}
            return phase
    finally:
        f.close()

def negative_controls():
    # A deliberately bypassed writer produces a false checkpoint. Our independent
    # persisted-file/database reconciliation must fail on that corrupted run.
    reset_schema()
    f = Fixture()
    try:
        with f.isolated():
            fake = {"enabled": True, "cities_with_due_checks":[CITY],
                "episodes_considered":1,"episodes_persisted":1,
                "episodes_skipped_incomplete_coverage":0,
                "classification_inserts":1,"classification_revisions":0,
                "event_inserts":1,"event_updates":0,"source_inserts":1,
                "verdicts":{"STRICT_EVENT_POSITIVE":1},"records":[]}
            with mock.patch.object(writer,"persist_due_episode_classifications",return_value=fake):
                report = f.main()
            db = read_db()
            assert db["counts"]["attack_event_classifications"] == 0
            assert report["canonical_persistence"]["classification_inserts"] == 1
            try: assert_completed(f,db,1)
            except AssertionError: CASE_LOG["N1_BYPASS_PERSISTENCE_DETECTED"] = {"status":"PASS"}
            else: raise AssertionError("false checkpoint was not detected")
    finally: f.close()

    # A persisted JSON checkpoint corrupted after real success is detected too.
    reset_schema()
    f = Fixture()
    try:
        with f.isolated():
            f.main()
            saved = json_read(f.state_path)
            saved["cities"][CITY]["episodes"][0]["checks"][0]["checked_at"] = None
            json_write(f.state_path,saved)
            db = read_db()
            check = json_read(f.state_path)["cities"][CITY]["episodes"][0]["checks"][0]
            assert check["checked_at"] is None and len(db["tips"]) == 1
            try:
                assert_state_tip_equivalence(f,db)
            except AssertionError: CASE_LOG["N2_BAD_PERSISTED_JSON_DETECTED"] = {"status":"PASS"}
            else: raise AssertionError("broken persisted state was not detected")
    finally: f.close()

    # Inject a forbidden second current tip to show independent DB verifier
    # detects duplication, without modifying application writer code.
    reset_schema()
    f = Fixture()
    try:
        with f.isolated():
            f.main()
            with conn() as c:
                c.execute("""INSERT INTO public.attack_event_classifications (
                    classification_key, historical_episode_id, city_key,
                    alert_start_at, alert_end_at, alert_episode_uid, verdict
                ) SELECT %s,historical_episode_id,city_key,alert_start_at,
                         alert_end_at,alert_episode_uid,verdict
                  FROM public.attack_event_classifications LIMIT 1""", ("f"*64,))
            try: assert_integrity(read_db())
            except AssertionError: CASE_LOG["N3_DUPLICATE_CURRENT_TIP_DETECTED"] = {"status":"PASS"}
            else: raise AssertionError("duplicate current tips not detected")
    finally: f.close()

def assert_state_tip_equivalence(f, db):
    state = json_read(f.state_path)
    ids = {e["episode_id"] for e in state["cities"][CITY]["episodes"]
           if e["checks"][0]["checked_at"]}
    tips = {eid for eid,_ in db["tips"]}
    assert ids == tips, (ids,tips)
    assert_integrity(db)

def main():
    out = Path(os.environ.get("H2_MAIN_OUTPUT", "/tmp/h2_monitor_main_report.json"))
    try:
        reset_schema()
        first_restart_revision()
        record_case("M4", stale_race)
        record_case("M5", unavailable)
        record_case("M6", incomplete)
        record_case("M7", lambda: inject_failure(False))
        reset_schema()
        inject_failure(True)
        negative_controls()
        for x in ("M1","M2","M3","M4","M5","M6","M7","M8","M9","M10"):
            assert CASE_LOG.get(x,{}).get("status") == "PASS", x
        for x in ("N1_BYPASS_PERSISTENCE_DETECTED",
                  "N2_BAD_PERSISTED_JSON_DETECTED",
                  "N3_DUPLICATE_CURRENT_TIP_DETECTED"):
            assert CASE_LOG.get(x,{}).get("status") == "PASS", x
        assert NETWORK["live_calls"] == 0
        verdict = "PASS"
    except Exception as exc:
        verdict = "FAIL"
        CASE_LOG["harness_exception"] = {"error":repr(exc)}
        raise
    finally:
        payload = {"verdict":verdict, "postgres_version": None,
            "source": "ACTUAL_monitor_explosion_candidates.main",
            "schema":"REDUCED_SYNTHETIC_PG18_PARENT_CONTRACT_EXTENDED",
            "cases":CASE_LOG,"network":NETWORK,
            "writer_regressions":legacy["test_results"]}
        with conn() as c:
            payload["postgres_version"] = c.execute("SHOW server_version").fetchone()[0]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload,ensure_ascii=False,indent=2,default=str) + "\n",
                       encoding="utf-8")
        print("MONITOR_MAIN_E2E_VERDICT:",verdict,flush=True)
        print("MONITOR_MAIN_E2E_REPORT:",str(out),flush=True)

if __name__=="__main__":
    main()
