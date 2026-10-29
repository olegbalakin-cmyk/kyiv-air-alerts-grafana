#!/usr/bin/env python3
"""C6-CURRENT-SHADOW-01: one-shot research capture + existing B2 projection.
No source-native identity adjudication, Neon writes, publishing, or retries.
"""
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, HTTPRedirectHandler, build_opener
from zoneinfo import ZoneInfo

import psycopg
from psycopg.conninfo import conninfo_to_dict

UTC = timezone.utc
KYIV = ZoneInfo("Europe/Kyiv")
REPO = Path("b2")
SITE = Path("siteprod")
OUT = Path("c6_current_shadow_01_proof")
RAW = OUT / "raw_source_bytes"
START = "2026-09-30T21:00:00Z"
FROZEN_END = "2026-10-29T09:00:00Z"
READER_PATH = REPO / "research/c6_oct184_b1_source_priority_2026_10_29/source_priority_reader.py"
BUNDLE_PATH = REPO / "research/c6_oct184_b1_source_priority_2026_10_29/frozen_october_382_198_bundle.json"
PROD_PATH = SITE / "kyiv-air-alerts-grafana/data/alerts_combined.json"
QA_PATH = SITE / "kyiv-air-alerts-grafana/data/dashboard_qa.json"
WORKFLOW_PATH = REPO / ".github/workflows/c6-current-shadow-01.yml"
PROD_SHA = "7dca163219b7c6b9208a9445ed9ee9fbffdbd998"
PINS = {
    "reader": "890769995627aa15e43743ef7cd5b24d54b1c59c",
    "bundle": "fbad2b5318818b9c4bc9940e691de5f32fcdf283",
    "prod_json": "af19cfa5bc56e115b73d089776493c037da57bb1",
}
SOURCES = {
    "municipal": ("https://data.kyivcity.gov.ua/dataset/statystyka-povitrianykh-tryvoh-u-misti-kyievi-dep-municipal/resource/5e4fb8a8-f0c8-4a12-885f-192d1f0dba75/data/download", "application/json"),
    "kyiv_digital_history": ("https://kyiv.digital/open-api/air-alert/history", "application/json"),
    "kyiv_digital_state": ("https://kyiv.digital/open-api/air-alert/state", "application/json"),
    "kyiv_digital_html": ("https://kyiv.digital/storage/air-alert/stats.html", "text/html"),
}

def now():
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")

def write(name, value):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, default=str) + "\n", encoding="utf-8")

def blob_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def checked_bytes(label, path):
    data = path.read_bytes()
    if blob_sha(data) != PINS[label]:
        raise RuntimeError("EXACT_GIT_BLOB_MISMATCH_" + label)
    return data

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def capture(label, url, accept):
    """Exactly one origin GET per known endpoint. Preserve received HTTP body bytes."""
    req = Request(url, headers={
        "Accept": accept, "Accept-Encoding": "identity",
        "User-Agent": "kyiv-air-alerts-grafana/C6-current-shadow-one-shot"
    }, method="GET")
    record = {"url": url, "requested_at_utc": now(), "method": "GET",
              "http_status": None, "body_sha256": None, "raw_path": None,
              "response_headers": {}, "parse_status": "NOT_PARSED"}
    response = None
    opener = build_opener(NoRedirect())
    try:
        response = opener.open(req, timeout=22)
    except HTTPError as err:
        response = err
    except (URLError, TimeoutError, OSError) as err:
        record["capture_error_type"] = type(err).__name__
        record["captured_at_utc"] = now()
        return record, None
    try:
        with response:
            record["http_status"] = int(response.status if hasattr(response, "status") else response.code)
            record["response_headers"] = {
                key.lower(): response.headers.get(key) for key in
                ("Date", "Content-Type", "Content-Encoding", "Content-Length",
                 "ETag", "Last-Modified", "Cache-Control")
                if response.headers.get(key) is not None
            }
            body = response.read(12 * 1024 * 1024 + 1)
            record["captured_at_utc"] = now()
            if len(body) > 12 * 1024 * 1024:
                record["capture_error_type"] = "BODY_EXCEEDS_BOUNDED_LIMIT"
                return record, None
            RAW.mkdir(parents=True, exist_ok=True)
            path = RAW / (label + ".http_body")
            path.write_bytes(body)
            record["raw_path"] = str(path.relative_to(OUT))
            record["raw_bytes"] = len(body)
            record["body_sha256"] = hashlib.sha256(body).hexdigest()
            encoding = (response.headers.get("Content-Encoding") or "").lower().strip()
            if encoding == "gzip":
                import gzip
                return record, gzip.decompress(body)
            if encoding == "deflate":
                import zlib
                return record, zlib.decompress(body)
            return record, body
    except Exception as err:
        record["capture_error_type"] = type(err).__name__
        return record, None

def api_time(value):
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        zero, one = dt.replace(tzinfo=KYIV, fold=0), dt.replace(tzinfo=KYIV, fold=1)
        if zero.utcoffset() != one.utcoffset():
            raise ValueError("DST_FOLD_WITHOUT_OFFSET")
        dt = zero
    return dt.astimezone(UTC)

def summarize_api_history(document):
    if not isinstance(document, dict) or not isinstance(document.get("items"), list):
        raise ValueError("API_HISTORY_SCHEMA_MISMATCH")
    items = document["items"]
    records = []
    invalid = 0
    native_ids = []
    for item in items:
        try:
            if not isinstance(item, dict) or item.get("state") not in (0, 1):
                raise ValueError("BAD_STATE")
            event_time = api_time(item["created_at"])
            records.append((event_time, int(item["state"]), item.get("causes", [])))
            native_ids.extend(k for k in ("id", "uid", "event_id") if k in item)
        except (ValueError, TypeError, KeyError):
            invalid += 1
    records.sort(key=lambda r: (r[0], r[1]))
    recent = [r for r in records if r[0] >= datetime(2026, 10, 27, tzinfo=UTC)]
    active = None
    pairs = []
    anomalies = []
    for t, state, causes in recent:
        if state == 1:
            if active is not None:
                anomalies.append("REPEATED_ACTIVE")
            else:
                active = t
        elif active is None:
            anomalies.append("ORPHAN_CLEAR")
        elif t <= active:
            anomalies.append("INVALID_END")
        else:
            pairs.append((active.isoformat(), t.isoformat()))
            active = None
    if active is not None:
        anomalies.append("RECENT_TAIL_ACTIVE_OR_INCOMPLETE")
    return {"item_count": len(items), "parsed_count": len(records),
            "invalid_count": invalid, "native_id_fields_observed": sorted(set(native_ids)),
            "latest_event_utc": max((r[0] for r in records), default=None),
            "recent_since_utc": "2026-10-27T00:00:00Z",
            "recent_completed_candidates": len(pairs), "recent_anomalies": sorted(set(anomalies)),
            "recent_intervals": pairs[-35:], "result": "PARTIAL_DIAGNOSTIC_NO_PHYSICAL_UID"}

def read_git_rev(path):
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"],
                                   text=True, stderr=subprocess.DEVNULL).strip()

def compare_shadow(reader, projected, pinned_rows, extras, cutoff):
    """Time-aligned consumer comparison; never manufacture source labels."""
    start = reader.iso_utc(START)
    bound = reader.iso_utc(cutoff)
    observed = Counter(
        (x["start_utc"], x["end_utc"], x["source_kind"])
        for x in projected if start <= x["start_utc"] and x["end_utc"] <= bound
    )
    expected = Counter(
        (reader.iso_utc(x["start"]), reader.iso_utc(x["end"]), x["source"])
        for x in pinned_rows if start <= reader.iso_utc(x["start"])
        and reader.iso_utc(x["end"]) <= bound
    )
    extra_intervals = {(x["start_utc"], x["end_utc"]): x["uid"] for x in extras}
    missing, unexpected = [], []
    for start_utc, end_utc, source in sorted((expected - observed).elements()):
        uid = extra_intervals.get((start_utc, end_utc))
        missing.append({"start_utc": start_utc, "end_utc": end_utc,
                        "source_kind": source, "matched_unverified_physical_uid": uid,
                        "reason": "INSUFFICIENT_PHYSICAL_SOURCE_PROVENANCE" if uid
                        else "UNEXPLAINED_SOURCE_OR_INTERVAL_DIFFERENCE"})
    for start_utc, end_utc, source in sorted((observed - expected).elements()):
        unexpected.append({"start_utc": start_utc, "end_utc": end_utc,
                           "source_kind": source, "reason": "UNEXPLAINED_SHADOW_EXTRA"})
    known = {(s, e): kind for s, e, kind in expected}
    source_mismatches = [{"start_utc": s, "end_utc": e, "source_kind": k,
                          "expected_source_kind": known[(s, e)]}
                         for s, e, k in (observed - expected).elements()
                         if (s, e) in known and k != known[(s, e)]]
    return {"scope": "OCTOBER_TO_SHARED_PRODUCTION_GENERATED_CUTOFF",
            "shared_cutoff_utc": bound, "expected_count": sum(expected.values()),
            "shadow_count": sum(observed.values()), "missing_in_shadow": missing,
            "unexpected_in_shadow": unexpected, "source_kind_mismatches": source_mismatches,
            "unexplained_count": sum(z["reason"].startswith("UNEXPLAINED") for z in missing + unexpected)
            + len(source_mismatches), "time_alignment_note": "Production generation timestamp bounds comparison; not simultaneous source snapshots"}

def consumer_audit(suppressed_rows, classes, root):
    mapping = {x["uid"]: x["displayed_instead_uid"] for x in suppressed_rows}
    affected = [x for x in classes if str(x.get("parent_uid")) in mapping]
    files = [
        root / "kyiv-air-alerts-grafana/data/alerts_combined.json",
        root / "kyiv-air-alerts-grafana/data/site_derived.json",
        root / "kyiv-air-alerts-grafana/data/kyiv_threat_mix.json",
        root / "kyiv-air-alerts-grafana/grafana/dashboard.json",
    ]
    scan = []
    for file in files:
        if not file.is_file():
            scan.append({"file": str(file.relative_to(root)), "status": "MISSING"})
            continue
        b = file.read_bytes()
        scan.append({"file": str(file.relative_to(root)), "git_blob_sha": blob_sha(b),
                     "direct_classification_uid_key": b'"classification_uid"' in b,
                     "direct_parent_uid_key": b'"parent_uid"' in b,
                     "neon_table_reference": b"attack_event_classifications" in b})
    return {"suppressed_view_alternatives": len(mapping),
            "classifications_on_suppressed": len(affected),
            "physical_parents_holding_classifications": len({str(x["parent_uid"]) for x in affected}),
            "affected": [{
                "classification_uid": str(x["uid"]), "physical_parent_uid": str(x["parent_uid"]),
                "displayed_instead_physical_uid": mapping[str(x["parent_uid"])],
                "binding_state": x.get("binding_state"), "verdict": x.get("verdict"),
                "classification_key": x.get("classification_key")
            } for x in affected],
            "site_consumer_files_inspected": scan,
            "view_level_binding": "NOT_PROVEN_NO_UID_REBIND",
            "note": "Content-key scan of pinned site files is not a complete audit of every client and does not establish consumer equivalence"}

def main():
    OUT.mkdir(exist_ok=True)
    state = {"task": "C6-CURRENT-SHADOW-01", "research_only": True,
             "workflow_git_sha": os.environ.get("GITHUB_SHA"),
             "run_id": os.environ.get("GITHUB_RUN_ID"),
             "source_capture": "SOURCE_CAPTURE_BLOCKED",
             "current_shadow": "CURRENT_SHADOW_NOT_EXECUTED",
             "enrichment": "ENRICHMENT_VIEW_CONTRACT_BLOCKED",
             "full_guarded_cli": "B2_FULL_CLI_INPUT_BLOCKED",
             "production_reader_switch": False, "database_writes": 0,
             "git_or_site_production_writes": 0, "physical_identity_mappings_created": 0,
             "physical_classification_rebindings": 0}
    captures = {}
    parsed = {}
    physical = {}
    diff = {"status": "NOT_EXECUTED"}
    enrich = {"status": "NOT_EXECUTED"}
    stage = "git_preflight"
    try:
        if read_git_rev(REPO) != os.environ.get("GITHUB_SHA") or read_git_rev(SITE) != PROD_SHA:
            raise RuntimeError("CHECKOUT_PIN_DRIFT")
        reader_bytes = checked_bytes("reader", READER_PATH)
        bundle_bytes = checked_bytes("bundle", BUNDLE_PATH)
        prod_bytes = checked_bytes("prod_json", PROD_PATH)
        import sys
        sys.path.insert(0, str(READER_PATH.parent.resolve()))
        import source_priority_reader as reader
        if Path(reader.__file__).resolve() != READER_PATH.resolve():
            raise RuntimeError("NOT_EXISTING_B2_READER")
        bundle = reader.verify_approved_frozen_bundle(bundle_bytes, bundle_bytes)
        prod_rows = json.loads(prod_bytes)
        qa = json.loads(QA_PATH.read_text(encoding="utf-8"))
        production_generated = reader.iso_utc(qa["generated_at"])
        state["immutable_inputs"] = {
            "reader_blob": blob_sha(reader_bytes), "bundle_blob": blob_sha(bundle_bytes),
            "site_prod_commit": PROD_SHA, "site_prod_json_blob": blob_sha(prod_bytes),
            "site_prod_generation_utc": production_generated,
            "workflow_sha256": hashlib.sha256(WORKFLOW_PATH.read_bytes()).hexdigest()}
        stage = "source_capture_one_GET_each"
        sys.path.insert(0, str((SITE / "kyiv-air-alerts-grafana/scripts").resolve()))
        from update_data import parse_official, parse_live_history
        for label, (url, accept) in SOURCES.items():
            receipt, decoded = capture(label, url, accept)
            captures[label] = receipt
            if receipt.get("http_status") != 200 or not decoded:
                continue
            try:
                if label == "municipal":
                    rows = parse_official(json.loads(decoded))
                    parsed[label] = {"completed": len(rows),
                        "latest_end_utc": max((reader.iso_utc(x.end) for x in rows), default=None),
                        "october_completed": sum(reader.iso_utc(x.start) >= reader.iso_utc(START) for x in rows),
                        "status": "PARSED" if rows else "EMPTY"}
                elif label == "kyiv_digital_history":
                    parsed[label] = summarize_api_history(json.loads(decoded))
                    parsed[label]["status"] = "PARSED"
                elif label == "kyiv_digital_state":
                    document = json.loads(decoded)
                    if not isinstance(document, dict) or not isinstance(document.get("current"), dict):
                        raise ValueError("API_STATE_SCHEMA_MISMATCH")
                    current = document["current"]
                    parsed[label] = {"status": "PARSED", "current_state": current.get("state"),
                        "current_created_at": current.get("created_at"),
                        "native_id_fields_observed": sorted(k for k in ("id","uid","event_id") if k in current)}
                elif label == "kyiv_digital_html":
                    alerts, events = parse_live_history(decoded.decode("utf-8"))
                    parsed[label] = {"status": "PARSED" if events else "EMPTY",
                        "transition_count": len(events), "completed_count": len(alerts),
                        "latest_transition_utc": max((reader.iso_utc(x[0]) for x in events), default=None),
                        "tail_intervals": [
                            {"start_utc": reader.iso_utc(a.start), "end_utc": reader.iso_utc(a.end)}
                            for a in alerts[-25:]
                        ]}
                receipt["parse_status"] = parsed[label]["status"]
            except Exception as err:
                receipt["parse_status"] = "PARSE_FAILED"
                receipt["parse_error_type"] = type(err).__name__
        valid = sum(x.get("parse_status") == "PARSED" for x in captures.values())
        state["source_capture"] = ("SOURCE_CAPTURE_VERIFIED" if valid == 4 else
                                   "SOURCE_CAPTURE_PARTIAL" if valid else "SOURCE_CAPTURE_BLOCKED")
        state["source_capture_window_utc"] = {
            "first_request": min((x["requested_at_utc"] for x in captures.values()), default=None),
            "last_observed": max((x.get("captured_at_utc", x["requested_at_utc"]) for x in captures.values()), default=None)}
        stage = "real_neon_transaction_and_b2_projection"
        dsn = os.environ.get("C6_B1_READONLY_DATABASE_URL", "")
        key = os.environ.get("NEON_API_KEY", "")
        if not dsn or not key:
            raise RuntimeError("AUTHORIZED_RUNNER_SECRETS_UNAVAILABLE")
        conn_fields = conninfo_to_dict(dsn)
        if (conn_fields.get("host") != "ep-calm-rice-b5073ypp.c-7.us-east-2.aws.neon.tech"
            or conn_fields.get("dbname") != "neondb"
            or conn_fields.get("sslmode") not in ("require", "verify-ca", "verify-full")
            or conn_fields.get("hostaddr")):
            raise RuntimeError("DSN_IDENTITY_OR_TLS_GUARD")
        endpoint = reader.fetch_live_neon_endpoint(key)
        if reader.verify_neon_control_plane(endpoint, dsn) != "LIVE_AUTHENTICATED_NEON_CONTROL_PLANE_READ_ONLY_MATCHED":
            raise RuntimeError("NEON_CONTROL_PLANE_IDENTITY_GUARD")
        end = now()
        snap_before = now()
        with psycopg.connect(dsn, autocommit=False, connect_timeout=20) as conn:
            snapshot = reader.physical_readonly_snapshot(conn, START, end)
        snap_after = now()
        physical = {"transaction": dict(snapshot["meta"]),
            "started_utc": snap_before, "completed_utc": snap_after,
            "start_filter_utc": START, "end_filter_utc": end,
            "approved_neon_identity": dict(reader.APPROVED_NEON_IDENTITY),
            "counts": {k: len(snapshot[k]) for k in ("episodes", "classifications", "source_links", "events")}}
        labels = {str(x["uid"]) for x in bundle["source_rows"]}
        new_episodes = [
            {"uid": str(x["uid"]), "start_utc": reader.iso_utc(x["start_at"]),
             "end_utc": reader.iso_utc(x["end_at"]),
             "source_kind": "UNVERIFIED", "display_eligible": False}
            for x in snapshot["episodes"] if str(x["uid"]) not in labels
        ]
        new_episodes.sort(key=lambda x: (x["start_utc"], x["uid"]))
        physical["unverified_new_physical_parents"] = new_episodes
        stage = "existing_project_display_with_fail_closed_new_parents"
        projection = reader.project_display(
            snapshot["episodes"], bundle["source_rows"], bundle["combined"],
            bundle["display_overrides"], snapshot["classifications"], snapshot["source_links"],
            snapshot["events"], expected_relationships=bundle.get("expected_relationships"))
        physical["b2_projection_status"] = projection["status"]
        physical["b2_counts"] = projection["counts"]
        physical["b2_unresolved"] = projection["unresolved_associations"]
        physical["b2_watermark"] = projection["watermark"]
        physical["physical_rebindings"] = projection["enrichment"]["rebinds"]
        write("current_shadow_display.json", projection["display_alerts"])
        write("unverified_new_parents.json", new_episodes)
        cutoff = min(production_generated, reader.iso_utc(snap_after))
        diff = compare_shadow(reader, projection["display_alerts"], prod_rows, new_episodes, cutoff)
        physical["production_reference_october_count"] = sum(
            reader.iso_utc(r["start"]) >= reader.iso_utc(START) for r in prod_rows)
        physical["current_total_projected"] = len(projection["display_alerts"])
        stage = "separate_28_classifications_view_consumer_audit"
        enrich = consumer_audit(projection["view_only_suppressed"],
                                snapshot["classifications"], SITE)
        enrich["status"] = ("ENRICHMENT_VIEW_CONTRACT_PARTIAL" if enrich["classifications_on_suppressed"]
                            else "ENRICHMENT_VIEW_CONTRACT_BLOCKED")
        state["enrichment"] = enrich["status"]
        if (diff["unexplained_count"] or
            any(x["status"] not in ("UNKNOWN_INGESTION_PROVENANCE",) for x in projection["unresolved_associations"])):
            state["current_shadow"] = "CURRENT_SHADOW_MISMATCH"
        elif projection["status"] != "PASS_ALERTS_ONLY" or state["source_capture"] != "SOURCE_CAPTURE_VERIFIED":
            state["current_shadow"] = "CURRENT_SHADOW_INPUT_BLOCKED"
        elif diff["missing_in_shadow"] or diff["unexpected_in_shadow"]:
            state["current_shadow"] = "CURRENT_SHADOW_MISMATCH"
        else:
            state["current_shadow"] = "CURRENT_SHADOW_EXACT_PARITY_PASS"
    except Exception as err:
        state["failure"] = {"stage": stage, "exception_type": type(err).__name__,
            "error_code": getattr(err, "code", None) or
            (str(err) if isinstance(err, RuntimeError) and str(err) in (
                "CHECKOUT_PIN_DRIFT", "NOT_EXISTING_B2_READER", "DSN_IDENTITY_OR_TLS_GUARD",
                "NEON_CONTROL_PLANE_IDENTITY_GUARD", "AUTHORIZED_RUNNER_SECRETS_UNAVAILABLE")
             else "RESEARCH_GUARD_OR_EXECUTION_EXCEPTION")}
        if state["current_shadow"] == "CURRENT_SHADOW_NOT_EXECUTED" and physical:
            state["current_shadow"] = "CURRENT_SHADOW_INPUT_BLOCKED"
    finally:
        write("source_capture_manifest.json", captures)
        write("parsed_source_receipts.json", parsed)
        write("neon_transaction_receipt.json", physical)
        write("time_aligned_diff.json", diff)
        write("enrichment_audit.json", enrich)
        write("machine_verdict.json", state)
        files = sorted(p for p in OUT.rglob("*") if p.is_file() and p.name != "sha256_manifest.json")
        write("sha256_manifest.json", {"task": state["task"],
            "workflow_git_sha": os.environ.get("GITHUB_SHA"),
            "files": {str(p.relative_to(OUT)): {
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size
            } for p in files}})
        print(json.dumps({"task": state["task"], "source_capture": state["source_capture"],
            "current_shadow": state["current_shadow"], "enrichment": state["enrichment"],
            "physical_count": physical.get("counts", {}).get("episodes"),
            "new_unverified_count": len(physical.get("unverified_new_physical_parents", [])),
            "aligned_missing": len(diff.get("missing_in_shadow", [])),
            "failure": state.get("failure")}, sort_keys=True))

if __name__ == "__main__":
    main()
