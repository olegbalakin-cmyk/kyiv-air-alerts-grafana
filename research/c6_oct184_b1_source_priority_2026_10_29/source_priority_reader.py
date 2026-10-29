#!/usr/bin/env python3
"""Research-only Kyiv AIR presentation projection; NEVER a source-native identity merge.

Inputs must be pinned immutable Git JSON and a separately verified source-lineage
manifest. Source-kind is an external Git/ingestion provenance assertion; there is
no assumed `alert_episodes.source` column. This module executes SELECTs only.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

UTC = timezone.utc
KYIV = ZoneInfo("Europe/Kyiv")
GIT_REPO = "olegbalakin-cmyk/kyiv-air-alerts-grafana"
GIT_INPUT_PATH = "kyiv-air-alerts-grafana/data/alerts_combined.json"
PINNED_COMMIT = "e08cc7da8cf29fc8603f199c85f0964610a850a7"
PINNED_BLOB = "e39dfc6fdbdb90863b5bfb595e12cadf8c20b068"
FROZEN_184_SOURCE_MANIFEST = "0bb0371fecad4f0cd84b3d82f0e539a8860da02e"


class ReaderGateError(RuntimeError):
    def __init__(self, code: str, details: object = None):
        self.code = code
        self.details = details
        super().__init__(code + (": " + str(details) if details is not None else ""))


def require(condition, code, details=None):
    if not condition:
        raise ReaderGateError(code, details)


def iso_utc(value):
    if isinstance(value, datetime):
        dt = value
    else:
        require(isinstance(value, str) and value.strip(), "INVALID_TIMESTAMP")
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as ex:
            raise ReaderGateError("INVALID_TIMESTAMP", value) from ex
    require(dt.tzinfo is not None and dt.utcoffset() is not None,
            "NAIVE_TIME_FORBIDDEN", str(value))
    return dt.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def interval(start, end):
    s, e = iso_utc(start), iso_utc(end)
    require(e > s, "INVALID_CLOSED_INTERVAL", [s, e])
    return s, e


def duration_seconds(start, end):
    a, b = interval(start, end)
    return int((datetime.fromisoformat(b.replace("Z", "+00:00")) -
                datetime.fromisoformat(a.replace("Z", "+00:00"))).total_seconds())


def git_blob_sha(blob: bytes):
    return hashlib.sha1(b"blob " + str(len(blob)).encode() + b"\0" + blob).hexdigest()


def sha256_canonical(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def parse_pinned_combined(blob: bytes, expected_blob: str, *, fallback=False):
    """Reject unpinned network/fallback bytes. The caller owns acquisition provenance."""
    require(git_blob_sha(blob) == expected_blob, "UNPINNED_MUNICIPAL_FALLBACK" if fallback
            else "SOURCE_GIT_BLOB_MISMATCH")
    try:
        rows = json.loads(blob)
    except (ValueError, UnicodeDecodeError) as ex:
        raise ReaderGateError("BAD_COMMITTED_JSON") from ex
    require(isinstance(rows, list) and bool(rows), "EMPTY_COMMITTED_JSON")
    return rows


def classify_live_sequence(events):
    """Strict on/off transitions. Never invent a completed interval from a broken feed."""
    active = None
    finished = []
    faults = []
    previous = None
    for entry in events:
        try:
            t = iso_utc(entry["at"])
            kind = entry["kind"]
        except (KeyError, TypeError, ReaderGateError):
            faults.append("BAD_EVENT")
            continue
        if previous is not None and t < previous:
            faults.append("OUT_OF_ORDER")
        previous = t
        if kind == "start":
            if active is not None:
                faults.append("DUPLICATE_START")
            else:
                active = t
        elif kind == "end":
            if active is None or t <= active:
                faults.append("ORPHAN_OR_INVALID_END")
            else:
                finished.append((active, t))
                active = None
        else:
            faults.append("UNKNOWN_EVENT_KIND")
    if active is not None:
        faults.append("UNPAIRED_ACTIVE_START")
    return {"completed_intervals": finished,
            "status": "UNRESOLVED_LIVE_SEQUENCE" if faults else "VALID_COMPLETE",
            "faults": sorted(set(faults))}


def verify_source_versions(previous, current, authorized_corrections=()):
    """Guard against incomplete, disappearing or retro-corrected official JSON.

    Explicitly authorized correction: (old_uid, new_uid) tuple. Source versions
    must each already have Git blob provenance. No raw row is deleted.
    """
    prev = {r["uid"]: r for r in previous}
    nxt = {r["uid"]: r for r in current}
    corrections = dict(authorized_corrections)
    require(len(corrections) == len(list(authorized_corrections)), "DUPLICATE_CORRECTION")
    missing = set(prev) - set(nxt)
    unapproved = sorted(uid for uid in missing if uid not in corrections)
    require(not unapproved, "UNVERIFIED_MUNICIPAL_CONTRACTION", unapproved[:5])
    for old_uid in missing:
        target = corrections[old_uid]
        require(target in nxt and prev[old_uid]["source_kind"] == "official_json" and
                nxt[target]["source_kind"] == "official_json", "BAD_SOURCE_CORRECTION", old_uid)
        require(prev[old_uid].get("origin_git_blob") != nxt[target].get("origin_git_blob"),
                "MISSING_NEW_OFFICIAL_SOURCE_VERSION", old_uid)
    return {"added": len(set(nxt) - set(prev)), "corrections": len(missing), "status": "PASS"}


def project_display(raw_episodes, source_rows, combined, display_overrides,
                    classifications=(), source_links=(), events=(),
                    *, expected_source_blob=None, expected_relationships=None,
                    new_source_completeness=None):
    """Pure strict projection. No physical aliases, relinks, writes or source guesses.

    `source_rows` are externally Git-proven labels for physical episode UIDs;
    arbitrary time-nearest/minute-floor matching is expressly forbidden.
    `display_overrides` are bounded OWNER-approved *view* supersessions only;
    their `physical_identity` must be NOT_PROVEN.
    """
    raw = {}
    for r in raw_episodes:
        uid = str(r["uid"])
        require(uid not in raw, "DUPLICATED_RAW_UID", uid)
        s, e = interval(r["start_at"], r["end_at"])
        require(r.get("city_key", "kyiv") == "kyiv" and
                r.get("alert_type", "AIR") == "AIR" and
                r.get("episode_state", "closed") == "closed", "BAD_RAW_EPISODE_SCOPE", uid)
        raw[uid] = {"uid": uid, "start": s, "end": e,
                    "duration_seconds": duration_seconds(s, e)}
    labels = {}
    for src in source_rows:
        uid = str(src["uid"])
        require(uid not in labels, "DUPLICATED_PROVENANCE_UID", uid)
        require(src.get("source_kind") in ("official_json", "kyiv_digital_live"),
                "UNVERIFIED_SOURCE_KIND", uid)
        require(src.get("origin_git_blob") and src.get("origin_git_commit"),
                "MISSING_GIT_INGESTION_PROVENANCE", uid)
        s, e = interval(src["start"], src["end"])
        require(uid in raw and (raw[uid]["start"], raw[uid]["end"]) == (s, e),
                "GIT_NEON_INTERVAL_MISMATCH", uid)
        labels[uid] = dict(src, uid=uid, start=s, end=e)
    unknown = sorted(set(raw) - set(labels))
    require(not(set(labels) - set(raw)), "DANGLING_LINEAGE_UID")
    expected_rows = []
    for row in combined:
        require(row.get("source") in ("official_json", "kyiv_digital_live"),
                "BAD_GIT_SOURCE_LABEL")
        s, e = interval(row["start"], row["end"])
        if "duration_minutes" in row:
            require(abs(duration_seconds(s, e) / 60 - float(row["duration_minutes"])) < 0.00051,
                    "GIT_SOURCE_DURATION_MISMATCH", [s, e])
        expected_rows.append((s, e, row["source"]))
    require(len(set(expected_rows)) == len(expected_rows), "DUPLICATED_COMMITTED_INTERVAL")
    exact_to_uids = defaultdict(list)
    for uid, src in labels.items():
        exact_to_uids[(src["start"], src["end"], src["source_kind"])].append(uid)
    selected = {}
    unresolved = []
    expected_set = set(expected_rows)
    for s, e, kind in expected_rows:
        matches = exact_to_uids[(s, e, kind)]
        if len(matches) != 1:
            unresolved.append({"status": "SOURCE_ROW_WITHOUT_UNIQUE_PARENT", "start": s,
                               "end": e, "source_kind": kind, "candidate_uids": sorted(matches)})
            continue
        uid = matches[0]
        require(uid not in selected, "DUPLICATED_SELECTED_UID")
        selected[uid] = kind
    overrides = {}
    seen_official = set()
    for rule in display_overrides:
        live_uid, official_uid = rule["live_uid"], rule["official_uid"]
        require(live_uid not in overrides and official_uid not in seen_official,
                "NON_UNIQUE_VIEW_REPLACEMENT")
        require(rule.get("authority") and rule.get("physical_identity") == "NOT_PROVEN" and
                rule.get("decision_scope") == "DISPLAY_ONLY", "UNAUTHORIZED_ALIAS_CLAIM")
        require(live_uid in labels and official_uid in labels and
                labels[live_uid]["source_kind"] == "kyiv_digital_live" and
                labels[official_uid]["source_kind"] == "official_json", "BAD_VIEW_REPLACEMENT")
        live, official = labels[live_uid], labels[official_uid]
        # A known view-only resolution is scoped to independently checked minute-floor
        # comparisons; the rule itself is the authority, not the timestamp coincidence.
        def minute_floor(s):
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return iso_utc(dt.replace(second=0, microsecond=0))
        require((live["start"], live["end"]) ==
                (minute_floor(official["start"]), minute_floor(official["end"])),
                "UNVERIFIED_VIEW_REPLACEMENT_INTERVAL")
        overrides[live_uid] = official_uid
        seen_official.add(official_uid)
    display = []
    suppressed = []
    for uid, src in sorted(labels.items()):
        kind = src["source_kind"]
        if kind == "official_json":
            if uid not in selected:
                # Retained old official parents must be explicitly historical versions.
                if not src.get("retired_view_version"):
                    unresolved.append({"uid": uid, "status": "OFFICIAL_PARENT_NOT_IN_PINNED_SOURCE"})
                continue
            display.append(_as_display(raw[uid], src, "MUNICIPAL_PRECISE"))
        elif uid in overrides:
            official_uid = overrides[uid]
            if official_uid in selected:
                suppressed.append({"uid": uid, "displayed_instead_uid": official_uid,
                                   "status": "DISPLAY_SUPPRESSED_IDENTITY_NOT_PROVEN"})
            else:
                unresolved.append({"uid": uid, "status": "OVERRIDE_WITHOUT_PINNED_OFFICIAL"})
        elif uid in selected:
            # Do not discard within 'covered' period just because start <= max(official.start).
            # Checked against all pinned officials, not current iteration order.
            touching = [labels[puid] for puid, pkind in selected.items()
                         if pkind == "official_json" and
                         src["start"] < labels[puid]["end"] and
                         src["end"] > labels[puid]["start"]]
            if touching:
                unresolved.append({"uid": uid, "status": "UNKNOWN_CANDIDATE_FAIL_CLOSED",
                                   "official_candidate_uids": sorted({x["uid"] for x in touching})})
            else:
                display.append(_as_display(raw[uid], src, "VERIFIED_LIVE_COMPLETED"))
        else:
            # A retained live parent absent from pinned combined must be explained.
            unresolved.append({"uid": uid, "status": "LIVE_NOT_IN_PINNED_SOURCE_OR_OVERRIDE"})
    for uid in unknown:
        unresolved.append({"uid": uid, "status": "UNKNOWN_INGESTION_PROVENANCE"})
    if new_source_completeness and new_source_completeness.get("status") != "VALID_COMPLETE":
        unresolved.append({"status": "LIVE_SEQUENCE_INCOMPLETE",
                           "faults": new_source_completeness.get("faults", [])})
    display.sort(key=lambda r: (r["start_utc"], r["end_utc"], r["uid"]))
    require(len({r["uid"] for r in display}) == len(display), "DUPLICATED_DISPLAY_PARENT")
    exact = [(r["start_utc"], r["end_utc"], r["source_kind"]) for r in display]
    require(len(set(exact)) == len(exact), "DUPLICATED_DISPLAY_INTERVAL")
    class_rows = [dict(r) for r in classifications]
    link_rows = [dict(r) for r in source_links]
    event_rows = [dict(r) for r in events]
    require(len({str(r["uid"]) for r in class_rows}) == len(class_rows), "DUPLICATE_CLASSIFICATION")
    require(len({str(r["uid"]) for r in link_rows}) == len(link_rows), "DUPLICATE_SOURCE_LINK")
    cids = {str(r["uid"]) for r in class_rows}
    require(all(str(r["classification_uid"]) in cids for r in link_rows),
            "DANGLING_SOURCE_RELATIONSHIP")
    require(all(not r.get("parent_uid") or str(r["parent_uid"]) in raw for r in class_rows),
            "DANGLING_CLASSIFICATION_PARENT")
    require(all(not e.get("current_classification_uid") or
                str(e["current_classification_uid"]) in cids for e in event_rows),
            "DANGLING_EVENT_CLASSIFICATION")
    relationships = {"classifications": sorted(class_rows, key=lambda r: str(r["uid"])),
                     "source_links": sorted(link_rows, key=lambda r: str(r["uid"])),
                     "events": sorted(event_rows, key=lambda r: str(r["uid"]))}
    if expected_relationships:
        require(len(class_rows) == expected_relationships["classifications"],
                "CLASSIFICATIONS_COUNT_CHANGED")
        require(len(link_rows) == expected_relationships["source_links"],
                "SOURCE_LINKS_COUNT_CHANGED")
        if "sha256" in expected_relationships:
            require(sha256_canonical(relationships) == expected_relationships["sha256"],
                    "CLASSIFICATION_RELATIONSHIPS_CHANGED")
        for frozen_key, current_key in (("classifications_rows", "classifications"),
                                        ("source_link_rows", "source_links"),
                                        ("event_rows", "events")):
            if frozen_key in expected_relationships:
                require(sha256_canonical(relationships[current_key]) ==
                        sha256_canonical(expected_relationships[frozen_key]),
                        "CLASSIFICATION_RELATIONSHIPS_CHANGED", frozen_key)
    suppressed_set = {r["uid"] for r in suppressed}
    impacted = sorted(str(c["uid"]) for c in class_rows if c.get("parent_uid") in suppressed_set)
    official_ends = [datetime.fromisoformat(src["end"].replace("Z", "+00:00"))
                     for uid, src in labels.items() if uid in selected and
                     src["source_kind"] == "official_json"]
    return {"display_alerts": display,
            "raw_episode_identities": [{**raw[uid], "source_kind": labels[uid]["source_kind"]
                                        if uid in labels else "UNVERIFIED"} for uid in sorted(raw)],
            "classification_relationships": relationships,
            "unresolved_associations": sorted(unresolved, key=lambda r: (r.get("uid", ""), r["status"])),
            "view_only_suppressed": sorted(suppressed, key=lambda r: r["uid"]),
            "enrichment": {"status": "UNRESOLVED_ALIAS_CLASSIFICATIONS" if impacted else "EXACT_PARENT_ONLY",
                           "suppressed_parent_classification_uids": impacted,
                           "rebinds": 0},
            "watermark": {"verified_official_last_end_utc": iso_utc(max(official_ends))
                          if official_ends else None,
                          "selection_algorithm": "PINNED_SOURCE_ROWS_AND_EXPLICIT_VIEW_RULES_NOT_MAX_START"},
            "status": "PARTIAL_UNRESOLVED" if unresolved else "PASS_ALERTS_ONLY",
            "counts": {"raw": len(raw), "display": len(display),
                       "official_display": sum(d["source_kind"] == "official_json" for d in display),
                       "live_display": sum(d["source_kind"] == "kyiv_digital_live" for d in display),
                       "suppressed_view_only": len(suppressed),
                       "classifications": len(class_rows), "source_links": len(link_rows),
                       "unresolved": len(unresolved), "retained_classifications_on_suppressed": len(impacted)}}


def _as_display(raw, source, status):
    return {"uid": raw["uid"], "start_utc": raw["start"], "end_utc": raw["end"],
            "duration_seconds": raw["duration_seconds"], "source_kind": source["source_kind"],
            "display_reason": status, "source_provenance": {
                "git_commit": source["origin_git_commit"], "git_blob": source["origin_git_blob"]}}


# The SQL text is SELECT-only. The full transaction is owned by psycopg, not an
# MCP sequence of independent read-committed queries. This guard also works on a
# PostgreSQL 16 disposable fixture supplied by an external test runner.
EPISODES_SQL = """SELECT episode_uid::text AS uid, city_key, alert_type,
    episode_state, start_at, end_at FROM public.alert_episodes
    WHERE city_key = 'kyiv' AND alert_type = 'AIR' AND episode_state = 'closed'
    AND start_at >= %s::timestamptz AND start_at < %s::timestamptz
    ORDER BY start_at, episode_uid"""
CLASSIFICATIONS_SQL = """SELECT classification_uid::text AS uid,
    alert_episode_uid::text AS parent_uid, classification_key, binding_state,
    verdict, supersedes_classification_uid::text AS supersedes_classification_uid
    FROM public.attack_event_classifications
    WHERE alert_episode_uid::text = ANY(%s::text[])
    ORDER BY classification_uid"""
SOURCE_LINKS_SQL = """SELECT attack_event_source_uid::text AS uid,
    classification_uid::text AS classification_uid, source_link_key
    FROM public.attack_event_sources WHERE classification_uid::text = ANY(%s::text[])
    ORDER BY attack_event_source_uid"""
EVENTS_SQL = """SELECT attack_event_uid::text AS uid,
    current_classification_uid::text AS current_classification_uid,
    alert_episode_uid::text AS parent_uid, event_status
    FROM public.attack_events WHERE alert_episode_uid::text = ANY(%s::text[])
    ORDER BY attack_event_uid"""


def physical_readonly_snapshot(conn, start_utc, end_utc):
    """One REPEATABLE READ READ ONLY Neon transaction. Never publish from here."""
    from psycopg.rows import dict_row  # imported only in protected physical runner
    with conn.transaction():
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            cur.execute("""SELECT current_setting('transaction_isolation') AS isolation,
                       current_setting('transaction_read_only') AS ro,
                       pg_is_in_recovery() AS recovery, current_database() AS db,
                       txid_current_snapshot()::text AS snapshot,
                       pg_last_wal_replay_lsn()::text AS replay_lsn""")
            meta = cur.fetchone()
            require(meta["isolation"] == "repeatable read" and meta["ro"] == "on",
                    "TRANSACTION_MUST_BE_REPEATABLE_READ_READ_ONLY")
            require(meta["recovery"] is True and meta["db"] == "neondb",
                    "NEON_READ_REPLICA_IDENTITY_REQUIRED")
            cur.execute(EPISODES_SQL, (start_utc, end_utc))
            episodes = cur.fetchall()
            uids = [r["uid"] for r in episodes]
            cur.execute(CLASSIFICATIONS_SQL, (uids,))
            classes = cur.fetchall()
            cids = [r["uid"] for r in classes]
            cur.execute(SOURCE_LINKS_SQL, (cids,))
            links = cur.fetchall()
            cur.execute(EVENTS_SQL, (uids,))
            events = cur.fetchall()
    return {"meta": meta, "episodes": episodes, "classifications": classes,
            "source_links": links, "events": events,
            "mutations": 0, "publication_callbacks": 0}


def load_bundle(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    require(data.get("schema_version") == "c6-oct184-b1-bundle-v1", "BAD_BUNDLE_VERSION")
    return data


def run_bundle(bundle, snapshot):
    return project_display(snapshot["episodes"], bundle["source_rows"], bundle["combined"],
                           bundle["display_overrides"], snapshot.get("classifications", []),
                           snapshot.get("source_links", []), snapshot.get("events", []),
                           expected_relationships=bundle.get("expected_relationships"))


def verify_september_a5_untouched(raw_rows, combined_official, crosswalk):
    """Independent A5 regression readback. B1 never creates/updates these mappings."""
    require(len(crosswalk) == 9, "A5_NOT_NINE")
    alias_ids = {r["alias_uid"] for r in crosswalk}
    canonical_ids = {r["canonical_uid"] for r in crosswalk}
    require(len(alias_ids) == len(canonical_ids) == 9 and not(alias_ids & canonical_ids),
            "A5_NONUNIQUE_CERTIFIED_IDS")
    raw = {r["uid"]: r for r in raw_rows}
    require(len(raw) == len(raw_rows) == 199, "A5_RAW_COUNT_CHANGED")
    for pair in crosswalk:
        a, c = raw.get(pair["alias_uid"]), raw.get(pair["canonical_uid"])
        require(a is not None and c is not None, "A5_MISSING_PHYSICAL_PARENT")
        require(interval(a["start_at"], a["end_at"]) ==
                (iso_utc(pair["alias_start_utc"]), iso_utc(pair["alias_end_utc"])),
                "A5_ALIAS_INTERVAL_CHANGED")
        require(interval(c["start_at"], c["end_at"]) ==
                (iso_utc(pair["canonical_start"]), iso_utc(pair["canonical_end"])),
                "A5_CANONICAL_INTERVAL_CHANGED")
    selected = [r for uid, r in raw.items() if uid not in alias_ids]
    expected = Counter(interval(r["start"], r["end"]) for r in combined_official)
    actual = Counter(interval(r["start_at"], r["end_at"]) for r in selected)
    require(len(selected) == len(combined_official) == 190 and actual == expected,
            "SEPTEMBER_190_EXACT_PARITY_FAILED")
    return {"raw":199, "display":190, "aliases":9, "exact_parity":"190/190", "changed":0}


def main():
    import argparse
    import os
    p = argparse.ArgumentParser(description="READ ONLY C6-OCT184-B1 research reader")
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--git-json", type=Path, required=True,
                   help="exact bytes of pinned Git alerts_combined.json")
    p.add_argument("--expected-git-blob", default=PINNED_BLOB)
    p.add_argument("--start-utc", default="2026-09-30T21:00:00Z")
    p.add_argument("--end-utc", default="2026-10-31T22:00:00Z")
    p.add_argument("--fixture-snapshot", type=Path,
                   help="offline fixture; without this flag a protected real Neon URL is mandatory")
    p.add_argument("--result", type=Path, required=True)
    args = p.parse_args()
    bundle = load_bundle(args.bundle)
    pinned_json = parse_pinned_combined(args.git_json.read_bytes(), args.expected_git_blob,
                                      fallback=True)
    month = [r for r in pinned_json if r["start"][:7] == "2026-10"]
    require(Counter((iso_utc(r["start"]), iso_utc(r["end"]), r["source"]) for r in month)
            == Counter((iso_utc(r["start"]), iso_utc(r["end"]), r["source"])
                       for r in bundle["combined"]), "PINNED_COMBINED_SCOPE_DRIFT")
    if args.fixture_snapshot:
        snapshot = json.loads(args.fixture_snapshot.read_text(encoding="utf-8"))
        execution_mode = "OFFLINE_FIXTURE_NOT_NEON"
    else:
        url = os.environ.get("C6_B1_READONLY_DATABASE_URL")
        require(bool(url), "ACCESS_BLOCKED_NO_PROTECTED_NEON_URL")
        try:
            import psycopg
        except ImportError as ex:
            raise ReaderGateError("ACCESS_BLOCKED_PSYCOPG_UNAVAILABLE") from ex
        # A READ ONLY replica with a verified recovery flag is mandatory.
        with psycopg.connect(url, autocommit=False, connect_timeout=15) as conn:
            snapshot = physical_readonly_snapshot(conn, args.start_utc, args.end_utc)
        execution_mode = "LIVE_PYTHON_NEON_REPEATABLE_READ_RO"
    result = run_bundle(bundle, snapshot)
    report = {"execution_mode": execution_mode, "status": result["status"],
              "counts": result["counts"], "watermark": result["watermark"],
              "unresolved_associations": result["unresolved_associations"],
              "view_only_suppressed": len(result["view_only_suppressed"]),
              "enrichment": result["enrichment"],
              "display_intervals_sha256": sha256_canonical(result["display_alerts"]),
              "relationship_sha256": sha256_canonical(result["classification_relationships"]),
              "database_writes": 0, "reader_switch": False, "publication_callbacks": 0}
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)+"\n")
    print(json.dumps({k:report[k] for k in ("execution_mode", "status", "counts", "watermark")},
                     ensure_ascii=False))
    # Unresolved alerts-only output is research-inspectable, never certified for publication.
    require(result["status"] == "PASS_ALERTS_ONLY", "UNRESOLVED_DISPLAY_NOT_PUBLISHABLE")


if __name__ == "__main__":
    main()
