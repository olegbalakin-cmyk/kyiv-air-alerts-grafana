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
from urllib.parse import urlsplit
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
APPROVED_B1_BUNDLE_BLOB = "fbad2b5318818b9c4bc9940e691de5f32fcdf283"
APPROVED_NEON_IDENTITY = {
    "project": "green-cake-44216048", "branch": "br-bold-mode-b5rub8pq",
    "compute": "ep-calm-rice-b5073ypp", "database": "neondb",
}
# A source-priority decision is not an identity adjudication.
APPROVED_VIEW_SCOPE = "OWNER_SOURCE_VIEW_PRIORITY_WITH_FRESH_FALLBACK"


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


def _canonical_source_fields(row):
    """Anything but capture provenance is material until explicitly adjudicated."""
    ignore = {"origin_git_blob", "origin_git_commit", "ingested_at", "verified_at"}
    return {k: v for k, v in row.items() if k not in ignore}


def _source_fingerprint(row):
    return sha256_canonical(_canonical_source_fields(row))


def verify_source_versions(previous, current, authorized_corrections=()):
    """Fail closed on same-UID start/end/duration changes, removals and UID revisions.

    Retained UIDs changing canonical fields need a fingerprint-bound approval
    containing old_uid, new_uid, old_sha256, new_sha256, and decision_scope.
    Legacy two-element tuples remain valid ONLY for old->new UID replacements
    (historical B1 compatibility); CLI never accepts unsigned tuples.
    Every material change requires an advanced origin Git blob AND commit.
    """
    prev_rows = list(previous)
    next_rows = list(current)
    prev = {str(r["uid"]): r for r in prev_rows}
    nxt = {str(r["uid"]): r for r in next_rows}
    require(len(prev) == len(prev_rows) and len(nxt) == len(next_rows),
            "DUPLICATE_MUNICIPAL_UID")
    require(all(r.get("source_kind") == "official_json" for r in prev_rows + next_rows),
            "NON_MUNICIPAL_VERSION_ROW")
    approvals = {}
    for item in authorized_corrections:
        if isinstance(item, dict):
            require(item.get("decision_scope") == "HISTORICAL_CORRECTION_ONLY" and
                    item.get("authority") == "OWNER_APPROVED_SOURCE_CORRECTION" and
                    bool(item.get("old_sha256")) and bool(item.get("new_sha256")),
                    "UNAPPROVED_SOURCE_CORRECTION")
            old_uid, new_uid = str(item["old_uid"]), str(item["new_uid"])
        else:
            require(isinstance(item, (list, tuple)) and len(item) == 2,
                    "BAD_LEGACY_CORRECTION")
            old_uid, new_uid = map(str, item)
            require(old_uid != new_uid, "SAME_UID_REQUIRES_FINGERPRINT_APPROVAL")
        require(old_uid not in approvals, "DUPLICATE_CORRECTION")
        approvals[old_uid] = (new_uid, item)
    removed = set(prev) - set(nxt)
    same_uid_drift = {uid for uid in set(prev) & set(nxt)
                      if _source_fingerprint(prev[uid]) != _source_fingerprint(nxt[uid])}
    require(not (removed - approvals.keys()), "UNVERIFIED_MUNICIPAL_CONTRACTION",
            sorted(removed - approvals.keys())[:5])
    require(not (same_uid_drift - approvals.keys()), "UNAPPROVED_SAME_UID_CORRECTION",
            sorted(same_uid_drift - approvals.keys())[:5])
    changed = removed | same_uid_drift
    require(not (approvals.keys() - changed), "UNUSED_SOURCE_CORRECTION_APPROVAL",
            sorted(approvals.keys() - changed)[:5])
    targets = set()
    for uid in sorted(changed):
        target, item = approvals[uid]
        require(target in nxt and target not in targets, "BAD_SOURCE_CORRECTION", uid)
        require(target == uid if uid in same_uid_drift else target != uid,
                "BAD_CORRECTION_UID_TARGET", uid)
        require(prev[uid].get("origin_git_blob") and nxt[target].get("origin_git_blob") and
                prev[uid]["origin_git_blob"] != nxt[target]["origin_git_blob"],
                "MISSING_NEW_OFFICIAL_SOURCE_VERSION", uid)
        if isinstance(item, dict):
            require(item["old_sha256"] == _source_fingerprint(prev[uid]) and
                    item["new_sha256"] == _source_fingerprint(nxt[target]),
                    "CORRECTION_FINGERPRINT_MISMATCH", uid)
            require(item.get("old_source_blob") == prev[uid]["origin_git_blob"] and
                    item.get("new_source_blob") == nxt[target]["origin_git_blob"],
                    "CORRECTION_SOURCE_BLOB_MISMATCH", uid)
            require(prev[uid].get("origin_git_commit") != nxt[target].get("origin_git_commit"),
                    "MISSING_NEW_OFFICIAL_SOURCE_COMMIT", uid)
        targets.add(target)
    return {"added": len(set(nxt) - set(prev)), "corrections": len(changed),
            "retained_uid_changes": len(same_uid_drift), "status": "PASS"}


def verify_approved_frozen_bundle(bundle_bytes, approved_bytes, expected_blob=APPROVED_B1_BUNDLE_BLOB):
    """Trust external accepted Git blob pin, never source authority inside candidate JSON."""
    require(expected_blob == APPROVED_B1_BUNDLE_BLOB, "UNAPPROVED_BUNDLE_PIN_OVERRIDE")
    require(git_blob_sha(approved_bytes) == APPROVED_B1_BUNDLE_BLOB,
            "UNAPPROVED_FROZEN_MANIFEST_BLOB")
    require(bundle_bytes == approved_bytes, "FROZEN_SELECTION_MANIFEST_DRIFT")
    bundle = json.loads(bundle_bytes)
    authority = bundle.get("source_authority", {})
    require(authority.get("repository") == GIT_REPO and
            authority.get("site_prod_sha") == PINNED_COMMIT and
            authority.get("alerts_combined_git_blob") == PINNED_BLOB and
            authority.get("lineage_git_commit") == FROZEN_184_SOURCE_MANIFEST and
            authority.get("policy") == APPROVED_VIEW_SCOPE and
            authority.get("physical_identity") == "NOT_PROVEN_184_PAIRS",
            "UNAPPROVED_SOURCE_AUTHORITY")
    require(len(bundle.get("display_overrides", [])) == 184 and
            all(r.get("authority") == "OWNER_C6_OCT184_B_184_FROZEN_VIEW" for r in
                bundle["display_overrides"]), "FROZEN_VIEW_SCOPE_MISMATCH")
    return bundle


def verify_git_provenance(bundle, source_receipt, git_json_bytes):
    """Require independent byte pins and provenance receipt; no self-asserted Git lineage."""
    auth = bundle.get("source_authority", {})
    require(source_receipt.get("git_commit") == PINNED_COMMIT and
            source_receipt.get("git_blob") == PINNED_BLOB and
            source_receipt.get("lineage_git_commit") == FROZEN_184_SOURCE_MANIFEST and
            source_receipt.get("lineage_git_blob") == auth.get("lineage_git_blob") and
            source_receipt.get("classification_matrix_git_blob") ==
            auth.get("classification_matrix_git_blob") and
            source_receipt.get("frozen_bundle_git_blob") == APPROVED_B1_BUNDLE_BLOB,
            "INDEPENDENT_SOURCE_RECEIPT_MISMATCH")
    require(git_blob_sha(git_json_bytes) == PINNED_BLOB,
            "SOURCE_GIT_BLOB_MISMATCH")
    require(len(bundle.get("source_rows", [])) == 382 and
            len(bundle.get("combined", [])) == 198,
            "FROZEN_SOURCE_COUNTS_CHANGED")
    require(all(isinstance(r.get("origin_git_blob"), str) and
                len(r.get("origin_git_blob")) == 40 and
                isinstance(r.get("origin_git_commit"), str) and
                len(r.get("origin_git_commit")) == 40 for r in bundle["source_rows"]),
            "INVALID_SOURCE_ROW_GIT_PIN")
    return "PASS_PINNED_GIT_BYTES_AND_APPROVED_MANIFEST"


def fetch_live_neon_endpoint(api_key, *, timeout_seconds=12):
    """Actual authenticated GET on pinned control plane, no resource mutation."""
    require(bool(api_key), "NEON_CONTROL_PLANE_API_CREDENTIAL_UNAVAILABLE")
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError, URLError
    url = ("https://console.neon.tech/api/v2/projects/" +
           APPROVED_NEON_IDENTITY["project"] + "/endpoints/" +
           APPROVED_NEON_IDENTITY["compute"])
    request = Request(url, headers={"Accept":"application/json",
                                    "Authorization":"Bearer " + api_key}, method="GET")
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            require(response.status == 200, "NEON_CONTROL_PLANE_HTTP_NOT_200")
            document = json.loads(response.read(50000))
    except (HTTPError, URLError, TimeoutError, ValueError) as ex:
        # Do not embed request headers/credentials or error body in receipts.
        raise ReaderGateError("NEON_CONTROL_PLANE_GET_UNAVAILABLE") from ex
    endpoint = document.get("endpoint")
    require(isinstance(endpoint, dict), "NEON_CONTROL_PLANE_MISSING_ENDPOINT")
    return endpoint


def verify_neon_control_plane(endpoint, dsn, prior_pin=None):
    """Compare authenticated live API endpoint metadata to expected independent pin."""
    require(endpoint.get("id") == APPROVED_NEON_IDENTITY["compute"] and
            endpoint.get("project_id") == APPROVED_NEON_IDENTITY["project"] and
            endpoint.get("branch_id") == APPROVED_NEON_IDENTITY["branch"] and
            endpoint.get("type") == "read_only", "WRONG_NEON_PROJECT_BRANCH_COMPUTE")
    host = endpoint.get("host")
    require(isinstance(host,str) and host.startswith(APPROVED_NEON_IDENTITY["compute"] + "."),
            "NEON_CONTROL_PLANE_HOST_MISMATCH")
    if prior_pin is not None:
        require(all(prior_pin.get(k) == v for k, v in APPROVED_NEON_IDENTITY.items()) and
                prior_pin.get("endpoint_host") == host,
                "INDEPENDENT_ENDPOINT_PIN_MISMATCH")
    try:
        dsn_host = urlsplit(dsn).hostname
    except ValueError as ex:
        raise ReaderGateError("INVALID_NEON_DSN") from ex
    require(dsn_host == host and "-pooler" not in host,
            "NEON_DSN_COMPUTE_MISMATCH")
    return "LIVE_AUTHENTICATED_NEON_CONTROL_PLANE_READ_ONLY_MATCHED"


def verify_live_capture(source_capture, live_rows, as_of_utc, max_age_hours=8):
    """Require complete captured transitions and sufficiently fresh publication metadata."""
    require(source_capture.get("source_kind") == "kyiv_digital_live" and
            source_capture.get("publisher_http_status") == 200 and
            source_capture.get("publisher") == "kyiv_digital" and
            source_capture.get("capture_git_blob") and
            source_capture.get("capture_git_commit") and
            isinstance(source_capture.get("transitions"), list),
            "LIVE_CAPTURE_PROVENANCE_REQUIRED")
    asof = datetime.fromisoformat(iso_utc(as_of_utc).replace("Z", "+00:00"))
    fetched = datetime.fromisoformat(iso_utc(source_capture["captured_at_utc"]).replace("Z", "+00:00"))
    age = (asof - fetched).total_seconds()
    require(0 <= age <= max_age_hours * 3600, "STALE_OR_FUTURE_KYIV_DIGITAL_CAPTURE")
    seq = classify_live_sequence(source_capture["transitions"])
    require(seq["status"] == "VALID_COMPLETE", "LIVE_SEQUENCE_INCOMPLETE", seq["faults"])
    actual = Counter(seq["completed_intervals"])
    expected = Counter(interval(r["start"], r["end"]) for r in live_rows)
    require(actual == expected, "LIVE_SEQUENCE_NOT_EQUAL_TO_PINNED_COMPLETED_TAIL",
            {"observed": sum(actual.values()), "expected": sum(expected.values())})
    return {"status": "VALID_COMPLETE", "completed": sum(actual.values()),
            "capture_age_seconds": int(age)}


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


def physical_readonly_snapshot(conn, start_utc, end_utc, *, lab_pg16=False):
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
            if lab_pg16:
                cur.execute("SHOW server_version_num")
                require(160000 <= int(cur.fetchone()["server_version_num"]) < 170000 and
                        meta["recovery"] is False,
                        "DISPOSABLE_PG16_REQUIRED")
            else:
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
    require(len(snapshot.get("episodes", [])) == 382, "FROZEN_PHYSICAL_PARENT_COUNT_CHANGED")
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


def execute_cli(args, *, after_guards=None):
    """Fail before any consumer/result callback. Lab mode is NOT production evidence."""
    import os
    require(not args.result.exists(), "RESULT_PATH_ALREADY_EXISTS_PREVENT_STALE_PUBLICATION")
    bundle_bytes = args.bundle.read_bytes()
    bundle = load_bundle(args.bundle)
    if args.lab_mode:
        require(bool(args.fixture_snapshot) != bool(args.lab_pg16_url),
                "LAB_REQUIRES_EXACTLY_ONE_PHYSICAL_OR_JSON_FIXTURE")
        require(args.approved_bundle is None, "LAB_CANNOT_ASSERT_APPROVED_BUNDLE")
    else:
        require(args.approved_bundle is not None and args.provenance_receipt is not None,
                "APPROVED_SOURCE_MANIFEST_REQUIRED")
        bundle = verify_approved_frozen_bundle(bundle_bytes, args.approved_bundle.read_bytes())
    git_bytes = args.git_json.read_bytes()
    pinned_json = parse_pinned_combined(
        git_bytes, git_blob_sha(git_bytes) if args.lab_mode else PINNED_BLOB, fallback=True)
    if not args.lab_mode:
        verify_git_provenance(bundle,
                              json.loads(args.provenance_receipt.read_text(encoding="utf-8")),
                              git_bytes)
    month = [r for r in pinned_json if iso_utc(r["start"]) >= "2026-09-30T21:00:00.000000Z"
             and iso_utc(r["start"]) < "2026-10-31T22:00:00.000000Z"]
    # Current frozen baseline only: dynamic municipal revisions must obtain a NEW
    # approved pin before this lab/reader can certify consumer output.
    require(Counter((iso_utc(r["start"]), iso_utc(r["end"]), r["source"]) for r in month)
            == Counter((iso_utc(r["start"]), iso_utc(r["end"]), r["source"])
                       for r in bundle["combined"]), "PINNED_COMBINED_SCOPE_DRIFT")
    require(args.previous_municipal is not None and args.september_guard is not None and
            args.live_capture is not None and args.as_of_utc is not None,
            "CLI_MANDATORY_GUARDS_MISSING")
    previous = json.loads(args.previous_municipal.read_text(encoding="utf-8"))
    current = [r for r in bundle["source_rows"] if r["source_kind"] == "official_json"]
    approvals = (json.loads(args.correction_approvals.read_text(encoding="utf-8"))
                 if args.correction_approvals else [])
    require(all(isinstance(c, dict) for c in approvals), "SIGNED_CORRECTION_APPROVAL_REQUIRED")
    source_change_result = verify_source_versions(previous, current, approvals)
    a5 = json.loads(args.september_guard.read_text(encoding="utf-8"))
    a5_result = verify_september_a5_untouched(
        a5["raw_rows"], a5["combined_official"], a5["crosswalk"])
    live_capture = json.loads(args.live_capture.read_text(encoding="utf-8"))
    # Require exactly one source-native captured live parent per pinned fresh
    # combined interval. Frozen minute-side alternative parents are NOT tail.
    live_expected = {(iso_utc(g["start"]), iso_utc(g["end"]))
                     for g in bundle["combined"] if g["source"] == "kyiv_digital_live"}
    tail = [r for r in bundle["source_rows"]
            if r["source_kind"] == "kyiv_digital_live" and
            interval(r["start"], r["end"]) in live_expected]
    require(len(tail) == len(live_expected) and len(live_expected) == 14,
            "FRESH_TAIL_SOURCE_MAPPING_INCOMPLETE")
    live_result = verify_live_capture(live_capture, tail, args.as_of_utc)
    if args.fixture_snapshot:
        snapshot = json.loads(args.fixture_snapshot.read_text(encoding="utf-8"))
        mode = "OFFLINE_FIXTURE_NOT_PG16_OR_NEON"
    else:
        try:
            import psycopg
        except ImportError as ex:
            raise ReaderGateError("PSYCOPG_UNAVAILABLE") from ex
        if args.lab_mode:
            dsn = args.lab_pg16_url
            parsed = urlsplit(dsn)
            require(parsed.hostname in ("127.0.0.1", "localhost", "::1"),
                    "LAB_PG16_MUST_BE_LOOPBACK")
        else:
            dsn = os.environ.get("C6_B1_READONLY_DATABASE_URL")
            require(dsn, "ACCESS_BLOCKED_NO_PROTECTED_NEON_URL")
            require(args.neon_identity is not None, "NEON_CONTROL_PLANE_RECEIPT_REQUIRED")
            endpoint = fetch_live_neon_endpoint(os.environ.get("NEON_API_KEY"))
            verify_neon_control_plane(endpoint, dsn,
                                      json.loads(args.neon_identity.read_text()))
        with psycopg.connect(dsn, autocommit=False, connect_timeout=15) as conn:
            snapshot = physical_readonly_snapshot(conn, args.start_utc, args.end_utc,
                                                  lab_pg16=args.lab_mode)
        mode = "DISPOSABLE_PG16_RO" if args.lab_mode else "LIVE_PYTHON_NEON_REPEATABLE_READ_RO"
    result = run_bundle(bundle, snapshot)
    require(result["status"] == "PASS_ALERTS_ONLY", "UNRESOLVED_DISPLAY_NOT_PUBLISHABLE")
    require(result["enrichment"]["rebinds"] == 0 and
            result["counts"]["classifications"] == 55 and
            result["counts"]["source_links"] == 223,
            "RELATIONSHIP_PRESERVATION_FAILED")
    require(result["counts"]["display"] == 198 and
            result["counts"]["official_display"] == 184 and
            result["counts"]["live_display"] == 14 and
            result["counts"]["suppressed_view_only"] == 184,
            "FROZEN_VIEW_COUNT_FAILED")
    require(result["counts"]["unresolved"] == 0, "UNRESOLVED_ASSOCIATIONS_BLOCK_PUBLICATION")
    # Only the lab receipt may be written; no publication/consumer API is present.
    report = {"execution_mode": mode, "status": result["status"],
              "counts": result["counts"], "watermark": result["watermark"],
              "source_change_guard": source_change_result, "september_a5": a5_result,
              "live_source_guard": live_result,
              "relationship_sha256": sha256_canonical(result["classification_relationships"]),
              "display_intervals_sha256": sha256_canonical(result["display_alerts"]),
              "database_writes": 0, "production_changes": 0,
              "reader_switch": False, "publication_callbacks": 0,
              "source_approval": "LAB_SYNTHETIC_ONLY" if args.lab_mode else "APPROVED_FROZEN_GIT_PIN"}
    if after_guards is not None:
        # A test-only hook: execute after every guard and before *research receipt*.
        after_guards(report)
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)+"\n")
    return report


def main():
    import argparse
    p = argparse.ArgumentParser(description="READ-ONLY C6-OCT184-B2 research, all guards mandatory")
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--approved-bundle", type=Path)
    p.add_argument("--provenance-receipt", type=Path)
    p.add_argument("--git-json", type=Path, required=True)
    p.add_argument("--previous-municipal", type=Path)
    p.add_argument("--correction-approvals", type=Path)
    p.add_argument("--september-guard", type=Path)
    p.add_argument("--live-capture", type=Path)
    p.add_argument("--as-of-utc")
    p.add_argument("--neon-identity", type=Path)
    p.add_argument("--start-utc", default="2026-09-30T21:00:00Z")
    p.add_argument("--end-utc", default="2026-10-31T22:00:00Z")
    p.add_argument("--fixture-snapshot", type=Path)
    p.add_argument("--lab-pg16-url", help="isolated loopback PG16 only; no Neon")
    p.add_argument("--lab-mode", action="store_true", help="synthetic fixture, never approved source")
    p.add_argument("--result", type=Path, required=True)
    args = p.parse_args()
    report = execute_cli(args)
    print(json.dumps({k: report[k] for k in ("execution_mode", "status", "counts")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
