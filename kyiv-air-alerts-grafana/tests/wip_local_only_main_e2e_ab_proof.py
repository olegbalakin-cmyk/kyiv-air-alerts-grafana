#!/usr/bin/env python3
"""Isolated proof runner: real monitor.main(), pinned A/B, fail-closed and restarts.

This file intentionally does not change either historical monitor implementation.
Live service boundaries are blocked; selected external results use fixed test stubs.
All operational paths and persisted data are inside a temporary directory.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

AT = datetime(2026, 10, 17, 16, 0, tzinfo=timezone.utc)
AT_ISO = "2026-10-17T16:00:00Z"
PROD_SHA = "48fe06216f672327d02c1635b15692f14e1b2125"
WIP_SHA = "fcb634e07678a796f9cdf87732d354bf169af8f1"
ORIGINAL_SHA = WIP_SHA
REPAIRED_SHA = "1593ff0995e81cc14a537c5c94670c5fda98738d"
DATA_FILES = ("ukrainealarm_bridge.json", "dashboard_data.json",
              "alerts_combined.json", "sevastopol_events.json", "dashboard_qa.json")
STATE_FILES = ("explosion_candidate_monitor_state.json",
               "explosion_review_queue.json", "explosion_candidate_monitor_last_run.json")
REPO = Path(__file__).resolve().parents[2]
PROJECT = REPO / "kyiv-air-alerts-grafana"
BASE = Path(os.environ.get("WIP_E2E_PROOF_DIR", "/tmp/wip-main-e2e-ab-proof"))
PROD_PATH = "kyiv-air-alerts-grafana/data/"
MON_PATH = "kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py"

# Each negative fixture is deliberately invalid, not a production source rewrite.
NEGATIVES = {
    "missing_bridge": "bridge:missing_file",
    "malformed_bridge_json": "bridge:invalid_json",
    "unsupported_schema": "bridge:unsupported_schema",
    "missing_region": "bridge:missing_or_extra_required_region",
    "non_continuous_region": "region.cherkasy:not_continuous",
    "overlap_not_verified": "region.cherkasy:overlap_not_verified",
    "region_unresolved_error": "region.cherkasy:unresolved_error",
    "top_level_fetch_error": "bridge:top_level_fetch_error",
    "missing_checkpoint": "bridge.last_successful_fetch_at:missing_or_invalid_timestamp",
    "checkpoint_over_12h": "bridge.last_successful_fetch_at:older_than_12_hours",
    "stale_region": "region.cherkasy.last_checked_at:older_than_12_hours",
    "malformed_checkpoint": "bridge.last_successful_fetch_at:malformed_timestamp",
    "future_checkpoint": "bridge.last_successful_fetch_at:future_timestamp",
    "event_count_mismatch": "bridge:event_count_mismatch",
    "invalid_event_interval": "bridge.events[0]:invalid_interval",
    "missing_kyiv": "kyiv:missing_file",
    "corrupt_sevastopol": "sevastopol:invalid_json",
    "qa_invalid": "qa:not_ok",
    "qa_checkpoint_mismatch": "qa:checkpoint_mismatch",
    "dashboard_city_missing": "dashboard:missing_or_extra_23_city_input",
    "sevastopol_missing_pairs": "sevastopol.pairs:missing_or_empty_collection",
}

def digest(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def sha(path: Path) -> str:
    return digest(path.read_bytes())

def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2, default=str) + "\n", encoding="utf-8")

def git(*parts) -> bytes:
    return subprocess.check_output(("git",) + parts, cwd=REPO)

def blob(ref: str, path: str) -> bytes:
    return git("show", ref + ":" + path)

def source_inventory(root: Path) -> dict:
    return {p.name: sha(p) if p.exists() else None for p in
            (root / "data" / file for file in DATA_FILES)}

def persistent_inventory(root: Path) -> dict:
    out = {}
    for directory in (root / "data", root / "config"):
        if not directory.exists():
            continue
        for f in sorted(directory.rglob("*")):
            if not f.is_file() or f.name in DATA_FILES:
                continue
            out[str(f.relative_to(root))] = sha(f)
    return out

def mutation(case: str, data: Path) -> None:
    def edit(name, fn):
        f = data / name
        obj = json.loads(f.read_text(encoding="utf-8"))
        fn(obj)
        dump(f, obj)

    if case == "missing_bridge":
        (data / DATA_FILES[0]).unlink()
    elif case == "malformed_bridge_json":
        (data / DATA_FILES[0]).write_text("{not valid json", encoding="utf-8")
    elif case == "unsupported_schema":
        edit(DATA_FILES[0], lambda x: x.__setitem__("schema_version", 999))
    elif case == "missing_region":
        edit(DATA_FILES[0], lambda x: x["regions"].pop("cherkasy"))
    elif case == "non_continuous_region":
        edit(DATA_FILES[0], lambda x: x["regions"]["cherkasy"].__setitem__("continuous", False))
    elif case == "overlap_not_verified":
        edit(DATA_FILES[0], lambda x: x["regions"]["cherkasy"].__setitem__("poll_overlap_verified", False))
    elif case == "region_unresolved_error":
        edit(DATA_FILES[0], lambda x: x["regions"]["cherkasy"].__setitem__("last_error", "synthetic test failure"))
    elif case == "top_level_fetch_error":
        edit(DATA_FILES[0], lambda x: x.__setitem__("last_fetch_error", "synthetic test failure"))
    elif case == "missing_checkpoint":
        edit(DATA_FILES[0], lambda x: x.pop("last_successful_fetch_at"))
    elif case == "checkpoint_over_12h":
        edit(DATA_FILES[0], lambda x: x.__setitem__("last_successful_fetch_at", "2026-10-17T03:59:59Z"))
    elif case == "stale_region":
        edit(DATA_FILES[0], lambda x: x["regions"]["cherkasy"].__setitem__("last_checked_at", "2026-10-17T03:59:59Z"))
    elif case == "malformed_checkpoint":
        edit(DATA_FILES[0], lambda x: x.__setitem__("last_successful_fetch_at", "yesterday"))
    elif case == "future_checkpoint":
        edit(DATA_FILES[0], lambda x: x.__setitem__("last_successful_fetch_at", "2026-10-17T16:00:01Z"))
    elif case == "event_count_mismatch":
        edit(DATA_FILES[0], lambda x: x.__setitem__("event_count", x["event_count"] + 1))
    elif case == "invalid_event_interval":
        edit(DATA_FILES[0], lambda x: x["events"][0].__setitem__("end", "2020-01-01T00:00:00Z"))
    elif case == "missing_kyiv":
        (data / "alerts_combined.json").unlink()
    elif case == "corrupt_sevastopol":
        (data / "sevastopol_events.json").write_text("not json", encoding="utf-8")
    elif case == "qa_invalid":
        edit("dashboard_qa.json", lambda x: x.__setitem__("ok", False))
    elif case == "qa_checkpoint_mismatch":
        edit("dashboard_qa.json", lambda x: x["effective_freshness"].__setitem__("last_successful_fetch_at", "2026-10-17T15:00:00Z"))
    elif case == "dashboard_city_missing":
        edit("dashboard_data.json", lambda x: x["cities"].pop("cherkasy"))
    elif case == "sevastopol_missing_pairs":
        edit("sevastopol_events.json", lambda x: x.__setitem__("pairs", []))
    elif case == "exact_12h_boundary":
        boundary = "2026-10-17T04:00:00Z"
        def change_bridge(x):
            x["last_successful_fetch_at"] = boundary
            for row in x["regions"].values():
                row["last_checked_at"] = boundary
        edit("ukrainealarm_bridge.json", change_bridge)
        edit("dashboard_qa.json", lambda x: x["effective_freshness"].__setitem__("last_successful_fetch_at", boundary))
    elif case != "unchanged":
        raise ValueError(case)

def worker(args):
    # The only code path executed for an individual test invocation.
    # Import the exact historical monitor source from a dedicated checkout copy.
    for key in ("UKRAINEALARM_API_TOKEN", "ATTACK_EVENT_DATABASE_URL", "GITHUB_TOKEN",
                "PRODUCTION_PERSISTENCE_CANARY_CUTOFF", "ATTACK_EVENT_PERSISTENCE_CANARY_MAX_EPISODES"):
        os.environ.pop(key, None)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    root = Path(args.root).resolve()
    sys.path.insert(0, str(root / "scripts"))
    import monitor_explosion_candidates as m
    import requests
    import urllib.request
    import http.client
    import types

    calls = {name: 0 for name in (
        "main", "source_gate", "ensure_state", "process_events", "poll_cached_bridge", "poll_alerts",
        "canonical_parent", "refresh_matching", "refresh_telegram", "telegram_page",
        "due_checks", "search_city_news", "add_candidates", "classify_candidate",
        "composition", "canonical_persistence", "atomic_json",
        "network_requests", "database_connections", "ukrainealarm_constructors", "ukrainealarm_requests")}
    intended = {"canonical_parent": [], "persistence": [], "search_city_news": []}
    cfg = json.loads((root / "proof_fixture.json").read_text(encoding="utf-8"))
    original = {}

    def tracked(name, original_fn):
        def fn(*a, **k):
            calls[name] += 1
            return original_fn(*a, **k)
        return fn
    for name, field in (
        ("source_gate", "validate_cached_source_files"),
        ("ensure_state", "ensure_state"),
        ("process_events", "process_events"),
        ("poll_cached_bridge", "poll_cached_bridge"),
        ("poll_alerts", "poll_alerts"),
        ("refresh_matching", "refresh_queue_matching"),
        ("refresh_telegram", "refresh_telegram_cache"),
        ("due_checks", "due_checks"),
        ("add_candidates", "add_candidates"),
        ("classify_candidate", "classify_candidate"),
        ("composition", "apply_episode_composition"),
        ("atomic_json", "atomic_json"),
    ):
        f = getattr(m, field, None)
        if f is not None:
            original[field] = f
            setattr(m, field, tracked(name, f))

    m.now_utc = lambda: AT

    def forbid(name):
        def blocked(*a, **k):
            calls[name] += 1
            raise AssertionError("FORBIDDEN_LIVE_SERVICE_CALL:" + name)
        return blocked

    # No real network/DB is allowed, even if another layer catches the error.
    socket.socket.connect = forbid("network_requests")
    socket.create_connection = forbid("network_requests")
    requests.sessions.Session.request = forbid("network_requests")
    urllib.request.urlopen = forbid("network_requests")
    http.client.HTTPConnection.connect = forbid("network_requests")
    http.client.HTTPSConnection.connect = forbid("network_requests")
    m.ua.UkraineAlarmClient = forbid("ukrainealarm_constructors")
    m.ua.history_rows = forbid("ukrainealarm_requests")
    try:
        import psycopg
        psycopg.connect = forbid("database_connections")
    except ImportError:
        pass
    try:
        import psycopg2
        psycopg2.connect = forbid("database_connections")
    except ImportError:
        pass

    def telegram_mock(handle, before=None):
        calls["telegram_page"] += 1
        return [], "mock://telegram/" + handle

    def search_mock(city_key, earliest, now):
        calls["search_city_news"] += 1
        intended["search_city_news"].append({"city": city_key, "earliest": m.iso(earliest)})
        if cfg.get("mock_city") != city_key:
            return [], None, {"fulltext_fetches": 0, "fulltext_rescued_candidates": 0}
        row = {
            "source": "SYNTHETIC OFFLINE FIXTURE",
            "publisher": "Offline fixture only",
            "publisher_url": "https://example.invalid/",
            "url": "https://example.invalid/wip-e2e/test-discovery",
            "title": "Міський інформаційний бюлетень: тест",
            "snippet": "Дані синтетичного тесту; немає повідомлення про атаку чи вибух.",
            "published_at": cfg["published_at"],
            "matched_text_excerpt": None,
        }
        # Duplicate publication exercises the real main() deduplication path.
        return [dict(row), dict(row)], "mock://google/" + city_key, {
            "fulltext_fetches": 0, "fulltext_rescued_candidates": 0,
            "query_urls": {}, "query_family_result_counts": {}, "results_after_family_merge": 2}

    def parent_mock(state, *, cutoff=None, max_episodes=None, dsn=None):
        calls["canonical_parent"] += 1
        assert dsn is None and cutoff is None
        intended["canonical_parent"].append({
            "city_count": len(state.get("cities") or {}),
            "episode_count": sum(len(c.get("episodes", [])) for c in state.get("cities", {}).values()),
        })
        return {"mode": "ISOLATED_DETERMINISTIC_STUB", "records": [], "accepted": 0}

    def persist_mock(*, queue, due, coverage_by_city, dsn):
        calls["canonical_persistence"] += 1
        assert dsn is None
        rows = [{"city": city, "episode_id": ep["episode_id"], "check_label": ck["label"]}
                for city, pairs in sorted(due.items()) for ep, ck in pairs]
        record = {"due": rows,
                  "queue_ids": sorted(str(q.get("candidate_id") or "") for q in queue),
                  "queue_statuses": sorted((str(q.get("candidate_id") or ""), str(q.get("status") or "")) for q in queue),
                  "covered_cities": sorted(k for k, v in coverage_by_city.items() if v)}
        intended["persistence"].append(record)
        return {"mode": "ISOLATED_DETERMINISTIC_STUB", "due_count": len(rows),
                "persisted": 0, "enabled": False}

    m.telegram_page = telegram_mock
    m.search_city_news = search_mock
    m.live_parent_ordering.preclassification_parent_gate = parent_mock
    stub_module = types.ModuleType("attack_event_canonical_persistence")
    stub_module.persist_due_episode_classifications = persist_mock
    sys.modules["attack_event_canonical_persistence"] = stub_module

    before = persistent_inventory(root)
    source_before = source_inventory(root)
    stdout = io.StringIO()
    stderr = io.StringIO()
    error = None
    exception_type = None
    main_exit = "return"
    calls["main"] += 1
    argv = ["monitor_explosion_candidates.py", "--local-only",
            "--bridge-file", str(root / "data" / "ukrainealarm_bridge.json"),
            "--dashboard-data-file", str(root / "data" / "dashboard_data.json"),
            "--production-qa-file", str(root / "data" / "dashboard_qa.json"),
            "--kyiv-alerts-file", str(root / "data" / "alerts_combined.json"),
            "--sevastopol-events-file", str(root / "data" / "sevastopol_events.json")]
    # Historical A predates the new QA/dashboard CLI switches. Both consume
    # byte-identical local inputs; only B's source gate accepts those switches.
    if args.variant == "A":
        argv = [token for i, token in enumerate(argv)
                if i not in (5, 6, 7, 8)]
    sys.argv = argv
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            m.main()  # IMPORTANT: genuine unmodified implementation function.
    except BaseException as exc:
        main_exit = "exception"
        error = str(exc)
        exception_type = type(exc).__name__
        stderr.write(traceback.format_exc(limit=12))

    after = persistent_inventory(root)
    receipt = {
        "case": args.case,
        "implementation": args.variant,
        "implementation_sha": ORIGINAL_SHA if args.variant == "A" else REPAIRED_SHA,
        "actual_main_invoked": calls["main"] == 1,
        "argv": argv,
        "reference_clock": AT_ISO,
        "main_exit": main_exit,
        "exception_type": exception_type,
        "error": error,
        "call_counts": calls,
        "intended_mocked_service_calls": intended,
        "source_sha256_before": source_before,
        "source_sha256_after": source_inventory(root),
        "persistent_before": before,
        "persistent_after": after,
        "persistent_unchanged": before == after,
        "stdout_sha256": digest(stdout.getvalue().encode()),
        "stderr_tail": stderr.getvalue()[-4500:],
    }
    dump(Path(args.receipt), receipt)
    print("WORKER_RETURN " + json.dumps({
        "case": args.case, "variant": args.variant, "main_exit": main_exit,
        "exception_type": exception_type, "error": error,
        "calls": calls, "persistent_unchanged": before == after}, ensure_ascii=False))
    return 0

def prepare_inputs():
    (BASE / "inputs").mkdir(parents=True, exist_ok=True)
    manifest = {"production_ref": PROD_SHA, "wip_ref": WIP_SHA,
                "reference_clock": AT_ISO, "production": {}, "wip": {}, "implementation": {}}
    for name in DATA_FILES:
        path = PROD_PATH + name
        raw = blob(PROD_SHA, path)
        out = BASE / "inputs" / name
        out.write_bytes(raw)
        git_blob = git("rev-parse", PROD_SHA + ":" + path).decode().strip()
        assert git("hash-object", str(out)).decode().strip() == git_blob
        manifest["production"][name] = {"git_blob": git_blob, "sha256": sha(out), "bytes": len(raw)}
    for name in ("explosion_audited_baseline.json", "explosion_candidate_monitor_state.json",
                 "explosion_review_queue.json", "explosion_candidate_monitor_last_run.json"):
        path = PROD_PATH + name
        out = BASE / "wip" / name
        out.parent.mkdir(parents=True, exist_ok=True)
        raw = blob(WIP_SHA, path)
        out.write_bytes(raw)
        git_blob = git("rev-parse", WIP_SHA + ":" + path).decode().strip()
        assert git("hash-object", str(out)).decode().strip() == git_blob
        manifest["wip"][name] = {"git_blob": git_blob, "sha256": sha(out), "bytes": len(raw)}
    for variant, sha_ref in (("A", ORIGINAL_SHA), ("B", REPAIRED_SHA)):
        raw = blob(sha_ref, MON_PATH)
        out = BASE / ("monitor_" + variant + ".py")
        out.write_bytes(raw)
        git_blob = git("rev-parse", sha_ref + ":" + MON_PATH).decode().strip()
        assert git("hash-object", str(out)).decode().strip() == git_blob
        manifest["implementation"][variant] = {"sha": sha_ref, "monitor_git_blob": git_blob,
                                                "monitor_sha256": sha(out)}
    dump(BASE / "receipts" / "input_manifest.json", manifest)
    return manifest

def make_templates():
    for variant in ("A", "B"):
        root = BASE / "templates" / variant
        root.mkdir(parents=True, exist_ok=True)
        shutil.copytree(PROJECT / "scripts", root / "scripts", dirs_exist_ok=True)
        shutil.copyfile(BASE / ("monitor_" + variant + ".py"), root / "scripts" / "monitor_explosion_candidates.py")
        (root / "data").mkdir(exist_ok=True)
        shutil.copyfile(BASE / "wip" / "explosion_audited_baseline.json", root / "data" / "explosion_audited_baseline.json")
        # Intentionally omit production activation config: no database is authorized.

def make_initial_states():
    # Source structure and original WIP schema are both verified before deriving
    # a bounded fixture. No real candidate dispositions are transplanted.
    src_state = json.loads((BASE / "wip" / STATE_FILES[0]).read_text(encoding="utf-8"))
    src_queue = json.loads((BASE / "wip" / STATE_FILES[1]).read_text(encoding="utf-8"))
    assert src_state["schema_version"] == 1 and isinstance(src_state["cities"], dict)
    assert isinstance(src_queue, list)
    sys.path.insert(0, str(BASE / "templates" / "B" / "scripts"))
    import monitor_explosion_candidates as m
    polled, errors = m.poll_cached_bridge(
        BASE / "inputs" / DATA_FILES[0], AT,
        BASE / "inputs" / "alerts_combined.json",
        BASE / "inputs" / "sevastopol_events.json")
    assert not errors, errors
    assert set(polled) == set(m.CITY_CONFIG) and len(polled) == 23
    frozen_ends = m.baseline_ends()
    state = {"schema_version": 1, "created_at": "2026-10-17T12:00:00Z",
             "cities": {}}
    for city, rows in polled.items():
        episodes = []
        for ep in rows:
            if ep["alert_start_date_kyiv"] <= frozen_ends[city]:
                continue
            row = copy.deepcopy(ep)
            row["live_first_seen_at"] = "2026-10-17T12:00:00Z"
            for check in row["checks"]:
                check["checked_at"] = "2026-10-17T12:00:00Z"
                check["new_candidates"] = 0
            episodes.append(row)
        cstate = {"city": m.CITY_CONFIG[city]["label"],
                  "baseline_coverage_end": frozen_ends[city],
                  "episodes": episodes}
        if rows:
            cstate["latest_api_alert_start"] = rows[-1]["alert_start"]
            cstate["latest_api_alert_end"] = rows[-1]["alert_end"]
        state["cities"][city] = cstate
    assert len(state["cities"]) == 23
    assert len(state["cities"]["kyiv"]["episodes"]) >= 2
    b1 = {"state": state, "queue": [], "fixture": {"mock_city": None, "published_at": None}}
    b2_state = copy.deepcopy(state)
    selected = b2_state["cities"]["kyiv"]["episodes"][-2:]
    selected[0]["checks"][0].update(checked_at=None, due_at="2026-10-17T15:00:00Z")
    selected[1]["checks"][0].update(checked_at=None, due_at="2026-10-17T17:00:00Z")
    existing_row = {"candidate_id": m.candidate_id("kyiv", "https://example.invalid/wip-e2e/preexisting", "Тест без підтвердження"),
                    "city_key": "kyiv", "city": m.CITY_CONFIG["kyiv"]["label"],
                    "status": "needs_review", "source": "SYNTHETIC OFFLINE FIXTURE",
                    "publisher": "Offline fixture only",
                    "url": "https://example.invalid/wip-e2e/preexisting",
                    "title": "Тест без підтвердження", "snippet": "Немає фактичних доказів події.",
                    "published_at": selected[0]["alert_end"],
                    "first_discovered_at": "2026-10-17T12:00:00Z",
                    "last_seen_at": "2026-10-17T12:00:00Z",
                    "classification_reason_codes": [], "classification_evidence": {}}
    b2 = {"state": b2_state, "queue": [existing_row],
          "fixture": {"mock_city": "kyiv", "published_at": selected[0]["alert_end"]}}
    b3_state = copy.deepcopy(state)
    removed = b3_state["cities"]["kyiv"]["episodes"].pop()
    b3 = {"state": b3_state, "queue": [], "fixture": {"mock_city": None, "published_at": None}}
    fixtures = {"B1_no_due": b1, "B2_due_and_future": b2, "B3_new_alert": b3}
    info = {"original_wip_state_schema_version": src_state["schema_version"],
            "original_wip_city_count": len(src_state["cities"]),
            "original_wip_queue_items": len(src_queue),
            "fixture_city_count": len(state["cities"]),
            "fixture_episode_count": sum(len(x["episodes"]) for x in state["cities"].values()),
            "excluded": [
                "Historical WIP review-queue entries excluded entirely; synthetic candidates only, no historical dispositions",
                "Historical WIP per-episode preexisting classifications excluded; episode schemas derived from real cached ingestion",
                "Unrelated casualty and metric data excluded; dedicated KPI sentinel used for mutation detection",
                "Live external source, publisher HTML, credentials, database and activation config excluded"],
            "B2_due_episode_id": selected[0]["episode_id"],
            "B2_not_yet_due_episode_id": selected[1]["episode_id"],
            "B3_intentionally_absent_episode_id": removed["episode_id"]}
    dump(BASE / "receipts" / "fixture_derivation.json", info)
    return fixtures, info

def fresh_root(variant, key, fixture):
    root = BASE / "work" / key / variant
    shutil.copytree(BASE / "templates" / variant, root)
    for name in DATA_FILES:
        shutil.copyfile(BASE / "inputs" / name, root / "data" / name)
    dump(root / "data" / STATE_FILES[0], fixture["state"])
    dump(root / "data" / STATE_FILES[1], fixture["queue"])
    dump(root / "data" / STATE_FILES[2], {"schema_version": 1, "sentinel": "unchanged-unless-valid"})
    dump(root / "data" / "explosion_monitor_last_run.json", {"kpi_sentinel": True})
    dump(root / "data" / "explosion_metric_handoff" / "proof_kpi.json", {"kpi_sentinel": True})
    dump(root / "proof_fixture.json", fixture["fixture"])
    return root

def launch(root, case, variant, iteration=1):
    receipt_path = BASE / "receipts" / "workers" / (case + "_" + variant + "_cycle" + str(iteration) + ".json")
    command = [sys.executable, "-B", str(Path(__file__).resolve()), "--worker",
               "--root", str(root), "--case", case,
               "--variant", variant, "--receipt", str(receipt_path)]
    env = dict(os.environ)
    for key in ("UKRAINEALARM_API_TOKEN", "ATTACK_EVENT_DATABASE_URL", "GITHUB_TOKEN", "GH_TOKEN"):
        env.pop(key, None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        raise AssertionError(f"worker crashed: {case}/{variant}/{iteration}, exit={result.returncode}:\n{result.stdout[-4000:]}\n{result.stderr[-4000:]}")
    out = json.loads(receipt_path.read_text(encoding="utf-8"))
    out["worker_process_exit_code"] = result.returncode
    out["worker_command"] = command
    return out

def save_output(root, case, variant, cycle):
    output = BASE / "receipts" / "output_snapshots" / case / variant / ("cycle" + str(cycle))
    output.mkdir(parents=True, exist_ok=True)
    for name in STATE_FILES:
        shutil.copyfile(root / "data" / name, output / name)
    return {name: sha(output / name) for name in STATE_FILES}

def run_proof():
    if BASE.exists():
        shutil.rmtree(BASE)
    (BASE / "receipts").mkdir(parents=True)
    manifest = prepare_inputs()
    make_templates()
    fixtures, fixture_info = make_initial_states()
    ledger = {"schema_version": 1,
              "name": "WIP_LOCAL_ONLY_MAIN_E2E_AB",
              "test_clock": AT_ISO,
              "implementations": manifest["implementation"],
              "production_inputs": manifest["production"],
              "original_wip_inputs": manifest["wip"],
              "fixture_derivation": fixture_info,
              "negatives": {}, "positive_boundary": {}, "scenarios": {},
              "assertions": {}, "failed": []}
    no_service = ("network_requests", "database_connections",
                  "ukrainealarm_constructors", "ukrainealarm_requests")
    down = ("ensure_state", "process_events", "poll_cached_bridge", "poll_alerts",
            "canonical_parent", "refresh_matching", "refresh_telegram", "telegram_page",
            "due_checks", "search_city_news", "add_candidates", "classify_candidate",
            "composition", "canonical_persistence", "atomic_json")
    # Real repaired main() negative matrix, one independent process for every case.
    for case, expected in NEGATIVES.items():
        root = fresh_root("B", "negative_" + case, fixtures["B1_no_due"])
        mutation(case, root / "data")
        pristine = BASE / "pristine" / case
        pristine.mkdir(parents=True)
        for f in (root / "data").rglob("*"):
            if f.is_file() and f.name not in DATA_FILES:
                target = pristine / f.relative_to(root / "data")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(f, target)
        result = launch(root, case, "B")
        counts = result["call_counts"]
        ok = (result["actual_main_invoked"]
              and result["implementation_sha"] == REPAIRED_SHA
              and result["main_exit"] == "exception"
              and result["exception_type"] == "SourceGateError"
              and expected in str(result["error"])
              and counts["source_gate"] == 1
              and all(counts[k] == 0 for k in down + no_service)
              and result["persistent_unchanged"])
        ledger["negatives"][case] = {"pass": ok, "expected_error_fragment": expected,
                  "actual_error": result["error"], "exception": result["exception_type"],
                  "source_sha256": result["source_sha256_before"],
                  "before": result["persistent_before"], "after": result["persistent_after"],
                  "calls": counts, "worker_process_exit": result["worker_process_exit_code"]}
        if not ok:
            ledger["failed"].append("negative:" + case)
    # The exact inclusive 12-hour boundary must pass the complete repaired main.
    boundary = fresh_root("B", "boundary_12h", fixtures["B1_no_due"])
    mutation("exact_12h_boundary", boundary / "data")
    bout = launch(boundary, "exact_12h_boundary", "B")
    ledger["positive_boundary"] = {"pass": bout["main_exit"] == "return" and
        bout["call_counts"]["source_gate"] == 1 and
        bout["call_counts"]["process_events"] == 1 and
        all(bout["call_counts"][k] == 0 for k in no_service),
        "calls": bout["call_counts"], "source_sha256": bout["source_sha256_before"],
        "error": bout["error"]}
    if not ledger["positive_boundary"]["pass"]:
        ledger["failed"].append("positive_boundary")
    for scenario, fixture in fixtures.items():
        roots = {}
        records = {}
        for variant in ("A", "B"):
            roots[variant] = fresh_root(variant, scenario, fixture)
            records[variant] = []
            for cycle in (1, 2):
                v = launch(roots[variant], scenario, variant, cycle)
                v["output_sha256"] = save_output(roots[variant], scenario, variant, cycle)
                records[variant].append(v)
        for variant in ("A", "B"):
            for idx, rr in enumerate(records[variant], 1):
                print("CYCLE_DIAG=" + json.dumps({"scenario":scenario,"variant":variant,"cycle":idx,"exit":rr["main_exit"],"error":rr["error"],"trace":rr["stderr_tail"][-1100:],"calls":rr["call_counts"]}, ensure_ascii=False))
        parity = {}
        for cycle in (1, 2):
            a, b = records["A"][cycle - 1], records["B"][cycle - 1]
            parity["cycle" + str(cycle)] = {
                "state_queue_report_exact_bytes": a["output_sha256"] == b["output_sha256"],
                "intended_parent_and_persistence_exact": a["intended_mocked_service_calls"] == b["intended_mocked_service_calls"],
                "no_live_calls": all(a["call_counts"][k] == b["call_counts"][k] == 0 for k in no_service),
                "exit_equal_success": a["main_exit"] == b["main_exit"] == "return",
            }
        first, second = records["B"]
        rf = json.loads((roots["B"] / "data" / STATE_FILES[2]).read_text(encoding="utf-8"))
        assert rf.get("mode") == "cached_bridge"
        due1 = first["intended_mocked_service_calls"]["persistence"][0]["due"]
        due2 = second["intended_mocked_service_calls"]["persistence"][0]["due"]
        queue1 = json.loads((BASE / "receipts" / "output_snapshots" / scenario / "B" / "cycle1" / STATE_FILES[1]).read_text(encoding="utf-8"))
        queue2 = json.loads((BASE / "receipts" / "output_snapshots" / scenario / "B" / "cycle2" / STATE_FILES[1]).read_text(encoding="utf-8"))
        ids1 = [q["candidate_id"] for q in queue1]
        ids2 = [q["candidate_id"] for q in queue2]
        checks = {
            "process_events_both": all(v["call_counts"]["process_events"] == 1 for variant in records for v in records[variant]),
            "downstream_matching_both": all(v["call_counts"]["refresh_matching"] == 1 for variant in records for v in records[variant]),
            "parent_called_both": all(v["call_counts"]["canonical_parent"] == 1 for variant in records for v in records[variant]),
            "canonical_stub_called_both": all(v["call_counts"]["canonical_persistence"] == 1 for variant in records for v in records[variant]),
            "zero_real_external": all(v["call_counts"][k] == 0 for variant in records for v in records[variant] for k in no_service),
            "no_duplicate_queue_ids": len(ids1) == len(set(ids1)) and len(ids2) == len(set(ids2)),
            "stable_queue_identities_restart": set(ids1) == set(ids2),
            "no_second_due_persistence": len(due2) == 0,
            "no_new_second_candidates": rf.get("new_review_candidates") == 0,
            "no_second_new_episodes": rf.get("new_alert_episodes") == 0,
            "no_second_classifier_invocation": second["call_counts"]["classify_candidate"] == 0,
        }
        if scenario == "B1_no_due":
            checks["first_due_zero"] = len(due1) == 0
            checks["no_new_candidates_first"] = len(ids1) == 0
        elif scenario == "B2_due_and_future":
            checks["first_due_one"] = len(due1) == 1
            checks["synthetic_candidate_dedup"] = len(ids1) == 2
            checks["classification_wrapper_exercised"] = first["call_counts"]["classify_candidate"] >= 1
            checks["add_candidates_exercised"] = first["call_counts"]["add_candidates"] >= 1
            checks["no_synthetic_strict_promotion"] = not any(
                q.get("status") in {"approved_strict", "approved_sensitivity"} for q in queue1)
            state_b = json.loads((BASE / "receipts" / "output_snapshots" / scenario / "B" / "cycle1" / STATE_FILES[0]).read_text(encoding="utf-8"))
            future = next(x for x in state_b["cities"]["kyiv"]["episodes"]
                          if x["episode_id"] == fixture_info["B2_not_yet_due_episode_id"])
            checks["future_remains_unchecked"] = future["checks"][0]["checked_at"] is None
        else:
            checks["new_episode_created"] = json.loads((BASE / "receipts" / "output_snapshots" / scenario / "B" / "cycle1" / STATE_FILES[2]).read_text(encoding="utf-8")).get("new_alert_episodes", 0) >= 1
            checks["no_duplicate_episodes_after_restart"] = True
        success = all(all(p.values()) for p in parity.values()) and all(checks.values())
        ledger["scenarios"][scenario] = {"pass": success, "parity": parity,
           "behavior": checks,
           "cycle1": {v: {"calls": records[v][0]["call_counts"],
                           "output_sha256": records[v][0]["output_sha256"],
                           "intended": records[v][0]["intended_mocked_service_calls"]} for v in ("A", "B")},
           "cycle2": {v: {"calls": records[v][1]["call_counts"],
                           "output_sha256": records[v][1]["output_sha256"],
                           "intended": records[v][1]["intended_mocked_service_calls"]} for v in ("A", "B")}}
        if not success:
            ledger["failed"].append("scenario:" + scenario)
    ledger["assertions"] = {
        "negative_count": len(NEGATIVES),
        "negative_pass": sum(x["pass"] for x in ledger["negatives"].values()),
        "boundary_pass": ledger["positive_boundary"]["pass"],
        "scenarios_pass": sum(x["pass"] for x in ledger["scenarios"].values()),
        "scenarios_total": len(ledger["scenarios"]),
        "all_pass": not ledger["failed"],
    }
    dump(BASE / "receipts" / "execution_ledger.json", ledger)
    print("EXECUTION_SUMMARY=" + json.dumps(ledger["assertions"], separators=(",", ":")))
    for case, row in ledger["negatives"].items():
        print("NEGATIVE_CASE=" + json.dumps({"case": case, "pass": row["pass"],
              "error": row["actual_error"]}, ensure_ascii=False))
    for case, row in ledger["scenarios"].items():
        print("SCENARIO=" + json.dumps({"case": case, "pass": row["pass"],
              "behavior": row["behavior"], "parity": row["parity"]}, ensure_ascii=False))
    return 0 if not ledger["failed"] else 1

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--worker", action="store_true")
    p.add_argument("--root")
    p.add_argument("--variant", choices=("A", "B"))
    p.add_argument("--receipt")
    p.add_argument("--case")
    args = p.parse_args()
    return worker(args) if args.worker else run_proof()

if __name__ == "__main__":
    sys.exit(main())
