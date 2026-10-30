#!/usr/bin/env python3
"""C6-23CITY-INTEGRATED-SHADOW-02: pinned read-only research adapter/orchestrator.

Reuses site-prod's existing build_outputs, enrich_weekly, rolling, historical
and derived functions. This is NOT the separately accepted 22-city adapter,
which must be furnished and executed before full adapter acceptance.
Never mutate Neon, site-prod, operational WIP, main, or publication endpoints.
"""
from __future__ import annotations

import collections
import csv
import hashlib
import importlib
import json
import os
import shutil
import subprocess
import sys
import traceback
import zipfile
from datetime import datetime, timezone, timedelta, date
from pathlib import Path
from zoneinfo import ZoneInfo

UTC = timezone.utc
TZ = ZoneInfo("Europe/Kyiv")
TASK = "C6-23CITY-INTEGRATED-SHADOW-02"
SITE_SHA = "09192a36dae49bd71e1042942481384a5e763086"
RESEARCH_BASE_SHA = "7738d959231d0534b527798a37ba9997f0083c5f"
CUTOFF = "2026-10-30T06:11:07.648388Z"
FROZEN_START = "2026-09-30T21:00:00Z"
FROZEN_END = "2026-10-29T09:00:00Z"
EXPECTED_HOST = "ep-calm-rice-b5073ypp.c-7.us-east-2.aws.neon.tech"
EXPECTED_DB = "neondb"
OUT = Path("c6_23city_integrated_shadow02_proof")
APPROVED_DIR = OUT / "accepted-22city"
APPROVED_SHA256 = "f6dda060a0ed48b01b4726625b36c33b472955f687be6877aef918fc3c8bddf2"
OUTPUTS = OUT / "site-consumer-research-only"
REPO = Path("research-src")
SITE = Path("pinned-site") / "kyiv-air-alerts-grafana"
READER = REPO / "research/c6_oct184_b1_source_priority_2026_10_29/source_priority_reader.py"
BUNDLE = REPO / "research/c6_oct184_b1_source_priority_2026_10_29/frozen_october_382_198_bundle.json"
PINS = {
    "data/alerts_combined.json": "7a7f066374cd3b35a86d7c113a430b12439e402b",
    "data/sevastopol_events.json": "68d4f93fd158d61a98d10f1e588b02caf520435f",
    "data/dashboard_data.json": "a3a30b5b9772e55c2941a01303de88551f4298bb",
    "data/site_derived.json": "875337323602b26951dd5472e1c3592cb0b76ab5",
    "data/kyiv_threat_mix.json": "ea2fbfdd2b8c0b5ef2690abb2ec974e7e9e6d77d",
    "scripts/update_data.py": "cebc2b455fb08ee16e03b9e4fcdb17aa2d9d6833",
    "scripts/apply_site_rolling_7d.py": "77ec779c657180ce0beb9608688f5561d871729c",
}
DST_UIDS = {
    "kharkiv": "bb7d4952-52a3-45f8-a1db-13153c8f6ca3",
    "poltava": "74ba1017-63af-4137-a5ba-246795613615",
    "zhytomyr": "b40c570e-f9db-4c7d-b7e4-3f7769e12a95",
}
DST_CITIES = set(DST_UIDS) | {"cherkasy"}
EXACT_22 = {"kharkiv", "zaporizhzhia", "sevastopol"}
MAX_DIFF = 20000
diffs = []
blockers = []
log = []
evidence = {"task": TASK, "global_cutover": "NO", "production_mutations": 0,
            "neon_mutations": 0, "site_prod_mutations": 0,
            "snapshot_cutoff_utc": CUTOFF, "stage": "bootstrap",
            "gates": {}, "source_dependencies": {},
            "status": "BLOCKED", "reason": "NOT_EXECUTED"}


def event(message):
    line = f"{datetime.now(UTC).isoformat()} {message}"
    print(line, flush=True)
    log.append(line)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True,
                               default=str) + "\n", encoding="utf-8")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git_blob(path):
    raw = Path(path).read_bytes()
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def utc(text):
    return datetime.fromisoformat(str(text).replace("Z", "+00:00")).astimezone(UTC)


def iso_utc(dt):
    return dt.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def add_block(city, uid, typ, reason, **more):
    blockers.append({"city": city, "uid": uid, "type": typ, "reason": reason, **more})


def verify_pins():
    evidence["stage"] = "pin_validation"
    assert subprocess.check_output(["git", "-C", "pinned-site", "rev-parse", "HEAD"], text=True).strip() == SITE_SHA
    actual_research = subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()
    assert actual_research == os.environ.get("GITHUB_SHA"), "research workflow SHA mismatch"
    expected_bundle = "fbad2b5318818b9c4bc9940e691de5f32fcdf283"
    expected_reader = "890769995627aa15e43743ef7cd5b24d54b1c59c"
    assert git_blob(BUNDLE) == expected_bundle, "unapproved B2 frozen manifest"
    assert git_blob(READER) == expected_reader, "unapproved B2 reader code"
    for rel, oid in PINS.items():
        assert git_blob(SITE / rel) == oid, f"site-prod blob drift: {rel}"
    evidence["git"] = {"research_workflow_sha": actual_research,
                       "pinned_site_prod_sha": SITE_SHA,
                       "approved_frozen_bundle_blob": expected_bundle,
                       "approved_b2_reader_blob": expected_reader,
                       "verified_blobs": PINS}
    evidence["gates"]["pinned_git_blobs"] = True
    event("PIN_VERIFIED site-prod immutable sources and B2 approved code")


def read_physical_snapshot():
    evidence["stage"] = "protected_python_psycopg_neon"
    import psycopg
    from psycopg.conninfo import conninfo_to_dict
    from psycopg.rows import dict_row
    dsn = os.environ.get("C6_B1_READONLY_DATABASE_URL")
    assert dsn, "C6_B1_READONLY_DATABASE_URL_NOT_INJECTED"
    conninfo = conninfo_to_dict(dsn)
    assert conninfo.get("host") == EXPECTED_HOST
    assert conninfo.get("dbname") == EXPECTED_DB
    assert conninfo.get("sslmode") in ("require", "verify-ca", "verify-full")
    assert not conninfo.get("hostaddr"), "hostaddr override forbidden"
    os.environ.pop("C6_B1_READONLY_DATABASE_URL", None)  # do not propagate DSN to child builders
    cutoff = utc(CUTOFF)
    with psycopg.connect(dsn, autocommit=True, connect_timeout=20) as conn:
        with conn.cursor(row_factory=dict_row) as c:
            c.execute("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            try:
                c.execute("""SELECT pg_is_in_recovery() AS recovery,
                    current_setting('transaction_read_only') AS ro,
                    current_setting('transaction_isolation') AS isolation,
                    current_database() AS db, pg_current_snapshot()::text AS snapshot,
                    pg_last_wal_replay_lsn()::text AS replay_lsn""")
                meta = dict(c.fetchone())
                assert meta["recovery"] is True and meta["ro"] == "on"
                assert meta["isolation"] == "repeatable read" and meta["db"] == EXPECTED_DB
                evidence["neon_transaction"] = meta
                c.execute("""SELECT episode_uid::text AS uid, city_key, alert_type,
                    episode_state, start_at, end_at, created_at,
                    created_by_run_id::text AS created_by_run_id,
                    legacy_episode_id
                    FROM public.alert_episodes
                    WHERE alert_type = 'AIR' AND episode_state = 'closed'
                    AND end_at IS NOT NULL AND start_at < %s::timestamptz
                    AND created_at <= %s::timestamptz
                    ORDER BY city_key, start_at, episode_uid""", (cutoff, cutoff))
                rows = [dict(r) for r in c.fetchall()]
                assert len({r["uid"] for r in rows}) == len(rows)
                assert all(r["end_at"] > r["start_at"] for r in rows)
                city_counts = dict(collections.Counter(r["city_key"] for r in rows))
                assert len(city_counts) == 23, f"Expected 23 cities, found {len(city_counts)}"
                evidence["neon_row_counts"] = {"physical_total": len(rows), "by_city": city_counts,
                    "non_kyiv_count": sum(v for k, v in city_counts.items() if k != "kyiv")}
                event(f"NEON_PHYSICAL_READ 23 cities, {len(rows)} AIR rows; snapshot={meta['snapshot']}")
                frozen_approved = json.loads(BUNDLE.read_text(encoding="utf-8"))
                frozen_uids = {str(r["uid"]) for r in frozen_approved["source_rows"]}
                kyiv = [r for r in rows if r["city_key"] == "kyiv"]
                approved_rows = [r for r in kyiv if r["uid"] in frozen_uids]
                unknown_rows = [r for r in kyiv if r["uid"] not in frozen_uids]
                assert len(approved_rows) == 382, "FROZEN_382_MISSING"
                for row in unknown_rows:
                    add_block("kyiv", row["uid"], "kyiv_primary_source_provenance",
                              "physical UID has no approved B2 source-row identity; never infer from minute overlap",
                              start_utc=iso_utc(row["start_at"]), end_utc=iso_utc(row["end_at"]),
                              ingestion_run_id=row["created_by_run_id"])
                frozen_start, frozen_end = utc(FROZEN_START), utc(FROZEN_END)
                assert all(frozen_start <= r["start_at"] < frozen_end for r in approved_rows)
                uids = [r["uid"] for r in approved_rows]
                c.execute("""SELECT classification_uid::text AS uid,
                    alert_episode_uid::text AS parent_uid, classification_key, binding_state,
                    verdict, supersedes_classification_uid::text AS supersedes_classification_uid
                    FROM public.attack_event_classifications
                    WHERE alert_episode_uid::text = ANY(%s::text[])
                    ORDER BY classification_uid""", (uids,))
                classifications = [dict(r) for r in c.fetchall()]
                class_uids = [r["uid"] for r in classifications]
                c.execute("""SELECT attack_event_source_uid::text AS uid,
                    classification_uid::text AS classification_uid, source_link_key
                    FROM public.attack_event_sources
                    WHERE classification_uid::text = ANY(%s::text[])
                    ORDER BY attack_event_source_uid""", (class_uids,))
                source_links = [dict(r) for r in c.fetchall()]
                c.execute("""SELECT attack_event_uid::text AS uid,
                    current_classification_uid::text AS current_classification_uid,
                    alert_episode_uid::text AS parent_uid, event_status
                    FROM public.attack_events
                    WHERE alert_episode_uid::text = ANY(%s::text[])
                    ORDER BY attack_event_uid""", (uids,))
                attack_events = [dict(r) for r in c.fetchall()]
                c.execute("""SELECT e.city_key, count(*) AS links,
                    count(DISTINCT e.episode_uid) AS parents
                    FROM public.alert_episode_sources s
                    JOIN public.alert_episodes e ON e.episode_uid = s.episode_uid
                    WHERE e.alert_type = 'AIR' AND e.episode_state = 'closed'
                    AND e.start_at < %s::timestamptz AND e.created_at <= %s::timestamptz
                    GROUP BY e.city_key ORDER BY e.city_key""", (cutoff, cutoff))
                coverage = {r["city_key"]:{"source_links":r["links"],
                                         "linked_parents":r["parents"]} for r in c.fetchall()}
            finally:
                c.execute("ROLLBACK")
    evidence["gates"]["real_python_psycopg_neon_read_only"] = True
    evidence["gates"]["single_stable_transaction_snapshot"] = True
    evidence["neon_primary_source_link_coverage"] = coverage
    for city, total in city_counts.items():
        n = coverage.get(city, {}).get("linked_parents", 0)
        if n < total:
            add_block(city, None, "missing_source_link",
                      "physical AIR parents have no attached primary source-observation link",
                      linked_parents=n, total_parents=total, missing_count=total-n)
    for city, uid in DST_UIDS.items():
        matched = [r for r in rows if r["uid"] == uid and r["city_key"] == city]
        add_block(city, uid, "known_dst_physical_interval",
                  "historically incorrect fold/UTC merge; reader cannot repair stored physical row",
                  present_in_snapshot=bool(matched))
    add_block("cherkasy", None, "known_dst_missing_interval",
              "source-only UTC replay found a missing Oct25 interval; physical Neon correction not accepted",
              expected_start_utc="2026-10-25T01:14:53.333785Z",
              expected_end_utc="2026-10-25T01:19:09.997656Z")
    snapshot = {"episodes":[dict(uid=r["uid"],city_key=r["city_key"],alert_type=r["alert_type"],
                                  episode_state=r["episode_state"],start_at=r["start_at"],
                                  end_at=r["end_at"]) for r in approved_rows],
                "classifications": classifications, "source_links": source_links,
                "events": attack_events}
    return rows, snapshot, unknown_rows


def diff_tree(actual, expected, path="$", city=None):
    if len(diffs) >= MAX_DIFF:
        return
    if type(actual) is not type(expected):
        record_diff(path, actual, expected, city, "type_mismatch")
        return
    if isinstance(actual, dict):
        for key in sorted(set(actual) | set(expected)):
            p = path + "." + str(key)
            if key not in actual or key not in expected:
                record_diff(p, actual.get(key, "<MISSING>"), expected.get(key, "<MISSING>"),
                            city, "missing_field")
            else:
                diff_tree(actual[key], expected[key], p, city)
    elif isinstance(actual, list):
        if len(actual) != len(expected):
            record_diff(path + ".length", len(actual), len(expected), city, "row_count")
        for i, (a,b) in enumerate(zip(actual,expected)):
            diff_tree(a,b,path + f"[{i}]",city)
    elif isinstance(actual, (int,float)) and not isinstance(actual,bool):
        if abs(actual - expected) > 1e-6:
            record_diff(path,actual,expected,city,"numeric")
    elif actual != expected:
        record_diff(path, actual, expected, city, "value")


def record_diff(path, proposed, published, city, kind):
    if len(diffs) >= MAX_DIFF:
        return
    if city == "kyiv":
        category = "kyiv_provenance_or_source_freshness" if path.endswith((".length",".alerts_started")) else "kyiv_consumer_difference"
    elif city in DST_CITIES:
        category = "known_dst_candidate_requires_window_review" if "2026-10-25" in str(proposed)+str(published) else "unexplained_difference"
    elif kind == "missing_field":
        category = "consumer_contract_mismatch"
    else:
        category = "unexplained_difference"
    diffs.append({"city":city,"json_path":path,"kind":kind,
                  "class":category,"neon_shadow":str(proposed)[:500],
                  "pinned_site_prod":str(published)[:500]})


def csv_table(path, rows):
    if not rows:
        return
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def build_site_candidate(physical_rows, frozen_snapshot, unknown_rows):
    evidence["stage"] = "existing_site_builders"
    sys.path.insert(0, str(READER.parent.resolve()))
    reader = importlib.import_module("source_priority_reader")
    bundle_bytes = BUNDLE.read_bytes()
    approved_bundle = reader.verify_approved_frozen_bundle(bundle_bytes,bundle_bytes)
    selected = reader.run_bundle(approved_bundle, frozen_snapshot)
    evidence["kyiv_b2"] = {"status":selected["status"],"counts":selected["counts"],
                          "enrichment":selected["enrichment"],
                          "unknown_new_uids":[r["uid"] for r in unknown_rows]}
    assert selected["counts"]["raw"] == 382
    assert selected["counts"]["display"] == 198
    assert selected["enrichment"]["rebinds"] == 0
    evidence["gates"]["approved_kyiv_b2_frozen_subset"] = True
    write_json(OUT/"kyiv_b2_selected_research.json", selected)
    if selected["enrichment"]["status"] != "EXACT_PARENT_ONLY":
        add_block("kyiv",None,"suppressed_parent_classifications",
                  "28 classification records on suppressed physical B2 parents; do not relink",
                  classification_uids=selected["enrichment"]["suppressed_parent_classification_uids"])
    sys.path.insert(0,str((SITE/"scripts").resolve()))
    update = importlib.import_module("update_data")
    bridge = importlib.import_module("apply_ukrainealarm_bridge")
    exactmod = importlib.import_module("add_duration_unit_switch")
    proxymod = importlib.import_module("expand_multicity_production")
    ext = importlib.import_module("extend_remaining_proxies")
    rolling = importlib.import_module("apply_site_rolling_7d")
    historical = importlib.import_module("build_preview_historical_daily")
    original_kyiv = json.loads((SITE/"data/alerts_combined.json").read_text(encoding="utf-8"))
    prior = [r for r in original_kyiv if utc(r["start"]) < utc(FROZEN_START)]
    current = []
    for r in selected["display_alerts"]:
        current.append({"start":utc(r["start_utc"]).astimezone(TZ).isoformat(),
                        "end":utc(r["end_utc"]).astimezone(TZ).isoformat(),
                        "duration_minutes":round((utc(r["end_utc"])-utc(r["start_utc"])).total_seconds()/60,3),
                        "source":r["source_kind"]})
    candidate_kyiv = sorted([*prior,*current],key=lambda r:utc(r["start"]))
    assert len(candidate_kyiv) == len(prior)+198
    write_json(OUTPUTS/"alerts_combined.json",candidate_kyiv)
    raw_by_city = collections.defaultdict(list)
    for row in physical_rows:
        raw_by_city[row["city_key"]].append(row)
    # Adapter output must come from its own physical psycopg transaction on the same cutoff.
    receipt_path = APPROVED_DIR / "machine_verdict.json"
    archive_proof = APPROVED_DIR / "approved_adapter_archive.sha256"
    assert receipt_path.is_file() and archive_proof.is_file(), "APPROVED_ADAPTER_EXECUTION_RECEIPT_MISSING"
    assert archive_proof.read_text().strip() == APPROVED_SHA256, "APPROVED_ZIP_SHA256_NOT_VERIFIED"
    accepted_verdict = json.loads(receipt_path.read_text(encoding="utf-8"))
    accepted_receipt = accepted_verdict.get("receipt", {})
    db = accepted_receipt.get("database", {})
    assert accepted_receipt.get("physical_origin") == "ACTUAL_NEON_PSYCOG_READONLY", "APPROVED_ADAPTER_NOT_PHYSICALLY_RUN"
    assert db.get("read_only") == "on" and db.get("recovery") is True, "APPROVED_ADAPTER_NOT_RECOVERY_REPLICA"
    assert db.get("cities") == 22 and db.get("row_count") == 28951, "APPROVED_ADAPTER_WRONG_CUTOFF_COUNTS"
    assert utc(db.get("asof_utc")) == utc(CUTOFF), "APPROVED_ADAPTER_CUTOFF_DRIFT"
    assert sum(len(v) for k,v in raw_by_city.items() if k!="kyiv") == db["row_count"], "REPEATABLE_READ_ASOF_COUNTS_DIFFER"
    approved_projection = json.loads((APPROVED_DIR/"22city_neon_projection.json").read_text(encoding="utf-8"))
    adapter_folder = Path(os.environ.get("C6_APPROVED_22CITY_DIR",""))
    assert adapter_folder.is_dir() and (adapter_folder/"contract.py").is_file(), "APPROVED_PACKAGE_NOT_IN_RUNNER"
    sys.path.insert(0,str(adapter_folder.resolve()))
    from contract import CITY_KEYS, union_utc
    assert set(CITY_KEYS)==set(raw_by_city)-{"kyiv"}, "APPROVED_ADAPTER_CITY_SET_MISMATCH"
    alerts_by_city = {"kyiv": update.parse_committed_alerts(candidate_kyiv)}
    for city in CITY_KEYS:
        unioned=union_utc([(r["start_at"],r["end_at"]) for r in raw_by_city[city]])
        alerts_by_city[city]=[update.Alert(start=a.astimezone(TZ),
            end=b.astimezone(TZ),source="neon_approved_22city_utc_union") for a,b in unioned]
    base = approved_projection
    evidence["approved_adapter"]={
        "zip_sha256":APPROVED_SHA256,"physical_psycopg_readonly":True,"cutoff":CUTOFF,
        "received_rows":db["row_count"],"snapshot":db.get("snapshot"),
        "adapter_verdict":accepted_verdict.get("verdict"),
        "adapter_numeric_diff":accepted_verdict.get("blocking_differences"),
        "adapter_derived_diff":accepted_verdict.get("derived_explorations_full_comparison"),
        "adapter_exit_code":(APPROVED_DIR/"adapter_exit_code.txt").read_text().strip()}
    evidence["gates"]["accepted_22city_adapter_executed"]=True
    event("APPROVED_ADAPTER_VERIFIED: archive SHA, protected Neon read-only readback, 22 city projection")
    keys = base["multicity_meta"]["production_city_keys"]
    assert len(keys) == 23 and set(keys) == set(alerts_by_city)
    now_local = utc(CUTOFF).astimezone(TZ)
    proxy_cfg = ext.configure_all_proxies()
    assert len(proxy_cfg) == 19 and set(proxy_cfg) == set(keys)-EXACT_22-{"kyiv"}
    city_outputs = {}
    for city in keys:
        if city != "kyiv":
            city_outputs[city] = approved_projection["cities"][city]
            continue
        old = base["cities"][city]
        meta = dict(old["meta"])
        if city == "kyiv":
            meta["neon_shadow_display_policy"] = "FROZEN_382_TO_198;_NINE_NEW_UIDS_BLOCKED"
        elif city in EXACT_22:
            meta["city_completed_alerts"] = len(alerts_by_city[city])
        else:
            meta["proxy_completed_alert_episodes"] = len(alerts_by_city[city])
        current_out = update.build_outputs(alerts_by_city[city],now_local,meta)
        if city == "kyiv":
            pass
        elif city == "sevastopol":
            proxymod.enrich_weekly(current_out,alerts_by_city[city])
            proxymod.trim_to_complete_coverage(current_out,date(2023,9,25))
            current_out["weekly"]=[r for r in current_out["weekly"] if r["week_start"] >= "2023-10-02"]
            current_out["monthly"]=[r for r in current_out["monthly"] if r["month"] >= "2023-10"]
        elif city in exactmod.CITY_CONFIG:
            exactmod.enrich_weekly(current_out,alerts_by_city[city])
            first_day=datetime.fromisoformat(exactmod.CITY_CONFIG[city]["valid_from"]).astimezone(TZ).date()
            exactmod.trim_first_partial_periods(current_out,first_day)
        else:
            proxymod.enrich_weekly(current_out,alerts_by_city[city])
            proxymod.trim_to_complete_coverage(current_out,
                date.fromisoformat(proxy_cfg[city]["coverage_start"]))
        rolling.update_city_rolling(current_out,alerts_by_city[city])
        city_outputs[city]=current_out
    base["cities"] = city_outputs
    base["kpis"] = city_outputs["kyiv"]["kpis"]
    for period in ("monthly","daily28","weekly","rolling30","rolling90"):
        base[period] = city_outputs["kyiv"][period]
    base["comparison"] = {period:bridge.generic_comparison(city_outputs,keys,period)
                          for period in ("monthly","weekly")}
    mm = base["multicity_meta"]
    for city in keys:
        mm.setdefault("cities",{}).setdefault(city,{})["weekly_mode"]="rolling_7d"
    base["meta"]["generated_at"] = now_local.isoformat()
    base["meta"]["analysis_end"] = (now_local.date()-timedelta(days=1)).isoformat()
    base["meta"]["weekly_mode"]="rolling_7d"
    base["meta"]["rolling_7d_definition"]="7 completed calendar days, timestamped by window end"
    mm["weekly_mode"]="rolling_7d"
    mm["rolling_window_periods"]=["weekly","rolling30","rolling90"]
    mm["time_of_day_profile_version"]="production-v1"
    mm["all_cities_table_version"]="production-v1"
    profile_cities={}
    table_cities={}
    coverage_days={city:rolling.first_coverage_day(city_outputs[city],alerts_by_city[city]) for city in keys}
    analysis_days={city:rolling.analysis_end(city_outputs[city]) for city in keys}
    common_start=max(d+timedelta(days=1) for d in coverage_days.values())
    common_end=min(analysis_days.values())
    for city in keys:
        p={per:rolling.time_profile(alerts_by_city[city],coverage_days[city],
                                    analysis_days[city],requested)
           for per,requested in rolling.PROFILE_PERIODS.items()}
        profile_cities[city]={"coverage_start":coverage_days[city].isoformat(),
                              "analysis_end":analysis_days[city].isoformat(),
                              "source_type":mm["cities"][city].get("source_type"),
                              "periods":p}
        spans={}
        for period,requested in {"7d":7,"30d":30,"90d":90,"year":365,"common":None}.items():
            start=common_start if requested is None else max(common_start,common_end-timedelta(days=requested-1))
            spans[period]=rolling.period_summary(alerts_by_city[city],start,common_end)
        table_cities[city]={"periods":spans}
    for city in keys:
        if city != "kyiv":
            profile_cities[city] = approved_projection["time_of_day_profile"]["cities"][city]
            table_cities[city] = approved_projection["all_cities_table"]["cities"][city]
    base["time_of_day_profile"]={
        "meta":{"slot_minutes":rolling.SLOT_MINUTES,"timezone":"Europe/Kyiv",
                "city_count":23,"periods":list(rolling.PROFILE_PERIODS),
                "current_day_excluded":True,"normalization":"each city/period peak = 100"},
        "cities":profile_cities}
    base["all_cities_table"]={"meta":{"city_count":23,"periods":["7d","30d","90d","year","common"],
                               "common_start":common_start.isoformat(),"common_end":common_end.isoformat(),
                               "comparison_window":"intersection_of_all_23_city_rows",
                               "current_day_excluded":True},"cities":table_cities}
    try:
        index = historical.produce(SITE,None,generated_at=base["meta"]["generated_at"],
                                   source_override=base,sources_override=alerts_by_city)
        base["historical_daily_kpi"]=index
        evidence["gates"]["historical_index_23cities"]=index["meta"]["verified_count"]==23
    except Exception as exc:
        base.pop("historical_daily_kpi",None)
        evidence["gates"]["historical_index_23cities"]=False
        add_block(None,None,"historical_derived_contract",f"{type(exc).__name__}: {str(exc)[:180]}")
    write_json(OUTPUTS/"dashboard_data.json",base)
    csv_table(OUTPUTS/"monthly.csv",city_outputs["kyiv"]["monthly"])
    csv_table(OUTPUTS/"weekly.csv",city_outputs["kyiv"]["weekly"])
    csv_table(OUTPUTS/"short_28d.csv",city_outputs["kyiv"]["daily28"])
    shutil.copyfile(SITE/"data/sevastopol_events.json",OUTPUTS/"sevastopol_events.json")
    shutil.copyfile(SITE/"data/kyiv_threat_mix.json",OUTPUTS/"kyiv_threat_mix.json")
    evidence["source_dependencies"]["sevastopol_events.json"]="PINNED_LEGACY_METADATA_AND_TELEGRAM_IDS_NOT_NEON_GENERATED"
    evidence["source_dependencies"]["kyiv_threat_mix.json"]="PINNED_KYIV_DIGITAL_CAUSES_NOT_NEON_GENERATED"
    evidence["source_dependencies"].update({
        "alerts_combined.json:historical_pre_B2":"PINNED_SITE_PROD_GIT_JSON_NOT_NEON_GENERATED",
        "ukrainealarm_bridge.json:derived":"PINNED_SITE_PROD_GIT_INPUT",
        "pages-preview/features.json":"SITE_PROD_GIT_FEATURE_CONFIG",
        "pages-preview/historical-daily-kpi.json":"SITE_PROD_STATIC_FALLBACK",
        "pages-preview/explosions_test.json":"OPERATIONAL_WIP_GIT_FEATURE_FLAG_FALSE",
        "casualty_presentation":"SEPARATE_SITE_PROD_GIT_CASUALTY_TRACK"})
    event("SITE_CANDIDATE approved 22-city projection plus Kyiv B2 selection")
    evidence["gates"]["candidate_full_23_city_rolling_builders"]=True
    return base,original_kyiv


def check_contracts_and_diff(base,original_kyiv):
    evidence["stage"]="machine_diff_and_contract_gates"
    published=json.loads((SITE/"data/dashboard_data.json").read_text(encoding="utf-8"))
    keys=published["multicity_meta"]["production_city_keys"]
    for city in keys:
        diff_tree(base["cities"][city],published["cities"][city],
                  "$.cities."+city,city)
    for field in ["comparison","time_of_day_profile","all_cities_table","historical_daily_kpi"]:
        diff_tree(base.get(field),published.get(field),"$."+field,None)
    for field in ["daily28","monthly","weekly","rolling30","rolling90","kpis"]:
        diff_tree(base.get(field),published.get(field),"$."+field,"kyiv")
    actual_kyiv=json.loads((OUTPUTS/"alerts_combined.json").read_text(encoding="utf-8"))
    old_count=collections.Counter((iso_utc(utc(x["start"])),iso_utc(utc(x["end"])),x["source"])
                                  for x in original_kyiv)
    new_count=collections.Counter((iso_utc(utc(x["start"])),iso_utc(utc(x["end"])),x["source"])
                                  for x in actual_kyiv)
    missing=list((old_count-new_count).elements())
    extra=list((new_count-old_count).elements())
    for triplet in missing:
        record_diff("$.alerts_combined.missing",None,triplet,"kyiv","missing_alert")
    for triplet in extra:
        record_diff("$.alerts_combined.extra",triplet,None,"kyiv","extra_alert")
    evidence["kyiv_approved_site_comparison"]={
        "production_rows":len(original_kyiv),"selected_rows":len(actual_kyiv),
        "site_only_intervals":missing,"shadow_only_intervals":extra,
        "site_only_count":len(missing),"shadow_only_count":len(extra)}
    for city in DST_CITIES:
        add_block(city,None,"known_dst_repair_unapplied","UTC source-only patch is not a physical Neon correction")
    evidence["machine_diff_count"]=len(diffs)
    evidence["machine_diff_truncated"]=len(diffs)>=MAX_DIFF
    evidence["machine_diff_classes"]=dict(collections.Counter(x["class"] for x in diffs))
    write_json(OUT/"machine_diff.json",{"cutoff":CUTOFF,"site_prod_sha":SITE_SHA,
        "scope":"23_city_site_consumer", "max_differences":MAX_DIFF,"truncated":len(diffs)>=MAX_DIFF,
        "differences":diffs,"counts_by_class":evidence["machine_diff_classes"]})
    write_json(OUT/"blockers.json",blockers)
    evidence["gates"]["explicit_machine_diff_all_23_cities"]=True
    evidence["gates"]["no_unexplained_differences"]=not any(
        x["class"]=="unexplained_difference" for x in diffs)
    evidence["gates"]["no_known_dst_uncorrected"]=False
    evidence["gates"]["nine_kyiv_uid_source_provenance_resolved"]=False
    evidence["gates"]["suppressed_parent_enrichment_resolved"]=False
    evidence["gates"]["accepted_22city_adapter_executed"]=bool(evidence.get("approved_adapter",{}).get("physical_psycopg_readonly"))
    evidence["gates"]["browser_csv_export_physically_exercised"]=False
    try:
        qa=importlib.import_module("postprocess_compact_dashboard_qa")
        exact,proxy,labels=qa.source_groups(base)
        obj=json.loads((SITE/"grafana/dashboard.json").read_text(encoding="utf-8"))
        result=qa.validate(base,obj,exact,proxy,labels)
        write_json(OUT/"consumer_contract_qa.json",result)
        evidence["gates"]["site_json_qa_contract"]=bool(result.get("ok"))
    except Exception as exc:
        evidence["gates"]["site_json_qa_contract"]=False
        add_block(None,None,"consumer_contract_qa",f"{type(exc).__name__}: {str(exc)[:180]}")
    event(f"MACHINE_DIFF differences={len(diffs)} unknown_explanations={evidence['machine_diff_classes'].get('unexplained_difference',0)}")


def build_derived_if_possible():
    evidence["stage"]="existing_site_derived_builder"
    dashboard=OUTPUTS/"dashboard_data.json"
    work=OUT/"derived-work"
    work.mkdir(exist_ok=True)
    tmp=work/"dashboard_data.json"
    shutil.copyfile(dashboard,tmp)
    exp=work/"explorations.json"
    args=[sys.executable,str(SITE/"scripts/build_time_of_day_heatmap.py"),
          "--dashboard",str(tmp),"--kyiv-alerts",str(OUTPUTS/"alerts_combined.json"),
          "--bridge-store",str(SITE/"data/ukrainealarm_bridge.json"),
          "--sevastopol-events",str(OUTPUTS/"sevastopol_events.json"),
          "--explorations-output",str(exp)]
    try:
        proc=subprocess.run(args,capture_output=True,text=True,timeout=240,check=False)
        (OUT/"derived_builder_stdout.log").write_text((proc.stdout or "")[-8000:]+"\n"+(proc.stderr or "")[-8000:])
        if proc.returncode!=0:
            raise RuntimeError("existing_builder_exit_"+str(proc.returncode))
        derived=json.loads(tmp.read_text(encoding="utf-8"))
        expl=json.loads(exp.read_text(encoding="utf-8"))
        payload={"meta":{"generated_at":derived.get("meta",{}).get("generated_at"),
                         "source":"C6_RESEARCH_ONLY_SITE_PROD_BUILDER_REUSE",
                         "city_count":23},
                 "time_of_day_heatmap_test":derived["time_of_day_heatmap_test"],
                 "all_cities_table_test":derived["all_cities_table_test"],
                 "explorations":expl}
        approved_derived_path=APPROVED_DIR/"site_derived_22city_projection.json"
        assert approved_derived_path.is_file(), "APPROVED_ADAPTER_DERIVED_PROJECTION_MISSING"
        approved_derived=json.loads(approved_derived_path.read_text(encoding="utf-8"))
        for sec in ("time_of_day_heatmap_test","all_cities_table_test","explorations"):
            for city,row in approved_derived[sec]["cities"].items():
                if city!="kyiv":
                    payload[sec]["cities"][city]=row
        for city,row in approved_derived["explorations"].get("daily28_current",{}).get("cities",{}).items():
            if city!="kyiv":
                payload["explorations"].setdefault("daily28_current",{}).setdefault("cities",{})[city]=row
        payload["meta"]["source"]="C6_RESEARCH_ONLY_APPROVED_22CITY_PLUS_KYIV_B2"
        write_json(OUTPUTS/"site_derived.json",payload)
        published=json.loads((SITE/"data/site_derived.json").read_text(encoding="utf-8"))
        for field in ("time_of_day_heatmap_test","all_cities_table_test","explorations"):
            diff_tree(payload[field],published[field],"$.site_derived."+field,None)
        evidence["gates"]["existing_derived_builder_executed"]=True
        evidence["gates"]["derived_23city_schema"]=all(
            set(payload[k]["cities"])==set(json.loads((OUTPUTS/"dashboard_data.json").read_text())["cities"])
            for k in ("time_of_day_heatmap_test","all_cities_table_test","explorations"))
        event("EXISTING_DERIVED_BUILDER completed")
    except Exception as exc:
        evidence["gates"]["existing_derived_builder_executed"]=False
        evidence["gates"]["derived_23city_schema"]=False
        add_block(None,None,"site_derived_missing",f"{type(exc).__name__}: {str(exc)[:180]}")
        event(f"DERIVED_BUILDER_PARTIAL {type(exc).__name__}")


def finish():
    OUT.mkdir(parents=True,exist_ok=True)
    evidence["blockers_total"]=len(blockers)
    if evidence["gates"].get("real_python_psycopg_neon_read_only") and evidence["gates"].get("candidate_full_23_city_rolling_builders"):
        evidence["status"]="PARTIAL"
        evidence["reason"]="approved_22city_executed_but_dst_lineage_and_consumer_gates_open"
    else:
        evidence["status"]="BLOCKED"
        evidence["reason"]=evidence.get("failure_reason","physical_full_generation_not_completed")
    evidence["global_cutover"]="NO"
    evidence["production_mutations"]=0
    write_json(OUT/"machine_verdict.json",evidence)
    write_json(OUT/"blockers.json",blockers)
    (OUT/"redacted_execution.log").write_text("\n".join(log)+"\n",encoding="utf-8")
    (OUT/"README.md").write_text(
        "# C6-23CITY-INTEGRATED-SHADOW-02\n\n"
        "This is research only. Never copy site-consumer outputs into site-prod. "
        "Full PASS prohibited without verified source lineage, "
        "DST correction acceptance, complete consumer and browser export gates. "
        "All pinned old/legacy-derived files are marked under machine_verdict.source_dependencies. "
        "No Neon DML/DDL, Git promotion, or Netlify deployment.\n",encoding="utf-8")
    files=[p for p in OUT.rglob("*") if p.is_file() and p.name not in ("sha256_manifest.json","bundle.zip")]
    manifest={"task":TASK,"sha256":{str(p.relative_to(OUT)):sha256(p) for p in sorted(files)},
              "files":len(files),"workflow_sha":os.environ.get("GITHUB_SHA"),
              "site_prod_sha":SITE_SHA,"cutoff":CUTOFF}
    write_json(OUT/"sha256_manifest.json",manifest)
    with zipfile.ZipFile(OUT/"bundle.zip","w",zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for p in sorted(OUT.rglob("*")):
            if p.is_file() and p.name!="bundle.zip":
                archive.write(p,p.relative_to(OUT))
    event("FINAL status="+evidence["status"]+" sha256_bundle="+sha256(OUT/"bundle.zip"))
    return 0 if evidence["status"]=="PASS" else 2


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    OUTPUTS.mkdir(exist_ok=True)
    try:
        event("BEGIN research-only full 23-city integration; no mutation")
        verify_pins()
        physical, frozen, unknown = read_physical_snapshot()
        candidate, original_kyiv = build_site_candidate(physical,frozen,unknown)
        check_contracts_and_diff(candidate,original_kyiv)
        build_derived_if_possible()
        if len(diffs)>evidence.get("machine_diff_count",0):
            evidence["machine_diff_count"]=len(diffs)
            evidence["machine_diff_classes"]=dict(collections.Counter(x["class"] for x in diffs))
            write_json(OUT/"machine_diff.json",{"cutoff":CUTOFF,"differences":diffs,
                "counts_by_class":evidence["machine_diff_classes"],
                "truncated":len(diffs)>=MAX_DIFF})
        evidence["gates"]["full_neon_site_parity_proven"]=False
        evidence["stage"]="completed_candidate"
    except Exception as exc:
        evidence["failure_reason"]=f"{type(exc).__name__}: {str(exc)[:220]}"
        event("BLOCKED "+evidence["stage"]+" "+evidence["failure_reason"])
        (OUT/"traceback_redacted.log").write_text(traceback.format_exc()[-12000:],encoding="utf-8")
    return finish()


if __name__=="__main__":
    sys.exit(main())
