#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import psycopg
from psycopg.types.json import Jsonb

CLASSIFICATION_KEY_VERSION = "attack-event-classification-key-v2"
ATTACK_EVENT_KEY_VERSION = "attack-event-key-v1"
SOURCE_LINK_KEY_VERSION = "attack-event-source-link-key-v1"
EVENT_GRAIN = "HISTORICAL_ALERT_EPISODE"

AUTHORITATIVE_CLASSIFIER_BLOB = "778469b74c2aa807d851cf2c2ee35cf4aa785589"
CLASSIFIER_METHODOLOGY_VERSION = "historical-attack-event-air-defense-action-v2"
NORMALIZATION_VERSION = "historical-attack-event-observation-v2"

ORIGIN_REPOSITORY = "olegbalakin-cmyk/kyiv-air-alerts-grafana"
ORIGIN_KIND = "shared_live_attack_event_canonical_persistence_v1"
MONITOR_RELATIVE_PATH = "kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py"

POSITIVE_VERDICTS = {"STRICT_EVENT_POSITIVE", "SENSITIVITY_EVENT_POSITIVE"}
STATUS_TO_VERDICT = {
    "approved_strict": "STRICT_EVENT_POSITIVE",
    "approved_sensitivity": "SENSITIVITY_EVENT_POSITIVE",
}

_HEX24 = re.compile(r"^[0-9a-f]{24}$")
_HEX40 = re.compile(r"^[0-9a-f]{40}$")


class PersistenceContractError(RuntimeError):
    pass


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _tuple_sha256(value: list[Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return None
    return dt.astimezone(timezone.utc)


def utc_microseconds(value: Any) -> str:
    dt = value if isinstance(value, datetime) else _parse_dt(value)
    if dt is None:
        raise PersistenceContractError(f"invalid timezone-aware timestamp: {value!r}")
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _git_blob_sha(path: Path) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    header = f"blob {len(raw)}\0".encode("ascii")
    return hashlib.sha1(header + raw).hexdigest()


def _origin_context() -> dict[str, Any]:
    commit = str(
        os.environ.get("GITHUB_SHA")
        or os.environ.get("ATTACK_EVENT_ORIGIN_COMMIT_SHA")
        or ""
    ).strip()
    if not _HEX40.fullmatch(commit):
        raise PersistenceContractError(
            "canonical persistence requires a 40-hex origin commit in "
            "GITHUB_SHA or ATTACK_EVENT_ORIGIN_COMMIT_SHA"
        )
    ref = str(
        os.environ.get("GITHUB_REF_NAME")
        or os.environ.get("ATTACK_EVENT_ORIGIN_REF")
        or ""
    ).strip()
    if not ref:
        raise PersistenceContractError(
            "canonical persistence requires GITHUB_REF_NAME or ATTACK_EVENT_ORIGIN_REF"
        )
    run_id_raw = str(os.environ.get("GITHUB_RUN_ID") or "").strip()
    run_id = int(run_id_raw) if run_id_raw.isdigit() else None
    monitor_path = Path(__file__).with_name("monitor_explosion_candidates.py")
    monitor_blob = _git_blob_sha(monitor_path)
    origin = {
        "kind": ORIGIN_KIND,
        "repository": ORIGIN_REPOSITORY,
        "ref": ref,
        "commit": commit,
        "monitor_path": MONITOR_RELATIVE_PATH,
        "monitor_blob": monitor_blob,
        "classifier_blob": AUTHORITATIVE_CLASSIFIER_BLOB,
        "classifier_methodology_version": CLASSIFIER_METHODOLOGY_VERSION,
        "normalization_version": NORMALIZATION_VERSION,
    }
    return {
        "ref": ref,
        "commit": commit,
        "run_id": run_id,
        "monitor_blob": monitor_blob,
        "origin_provenance": origin,
        "origin_provenance_sha256": canonical_sha256(origin),
    }


def _episode_refs(item: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    evidence = item.get("classification_evidence")
    if isinstance(evidence, dict):
        value = evidence.get("classification_episode_id")
        if value:
            refs.add(str(value))
    value = item.get("matched_episode_id")
    if value:
        refs.add(str(value))
    for value in item.get("matched_episode_ids") or []:
        if value:
            refs.add(str(value))
    return refs


def _item_event_types(item: dict[str, Any]) -> list[str]:
    values: set[str] = set()
    for value in item.get("event_types") or []:
        if str(value).strip():
            values.add(str(value).strip())
    evidence = item.get("classification_evidence")
    if isinstance(evidence, dict):
        for value in evidence.get("event_types") or []:
            if str(value).strip():
                values.add(str(value).strip())
    return sorted(values)


def _residual_qa(rows: list[dict[str, Any]]) -> list[str]:
    qa: set[str] = set()
    for row in rows:
        codes = {str(x) for x in row.get("classification_reason_codes") or []}
        evidence = row.get("classification_evidence")
        evidence = evidence if isinstance(evidence, dict) else {}
        temporal = evidence.get("temporal_binding")
        temporal = temporal if isinstance(temporal, dict) else {}
        temporal_code = str(temporal.get("code") or "")
        if "MATCH_AMBIGUOUS" in codes or temporal_code == "MATCH_AMBIGUOUS":
            qa.add("TEMPORAL_AMBIGUITY")
        exact = evidence.get("exact_city")
        if not isinstance(exact, dict):
            exact = evidence.get("exact_city_evidence")
        exact_present = bool(exact.get("present")) if isinstance(exact, dict) else False
        if str(row.get("status") or "") == "needs_review" and not exact_present:
            qa.add("CITY_AMBIGUITY")
        if "MULTI_INCIDENT_CONTEXT_RISK" in codes or "MULTI_INCIDENT" in codes:
            qa.add("MULTI_INCIDENT_CONTEXT_RISK")
        if "AIR_CONTEXT_NOT_LINKED_TO_EVENT" in codes:
            qa.add("MULTI_INCIDENT_CONTEXT_RISK")
        if not str(row.get("url") or "").strip():
            qa.add("SOURCE_REFERENCE_INCOMPLETE")
        if any("PROVENANCE" in code for code in codes):
            qa.add("PROVENANCE_REQUIRED")
    return sorted(qa)


def _review_provenance(rows: list[dict[str, Any]]) -> dict[str, Any]:
    reviewed = []
    for row in rows:
        value = row.get("review_provenance")
        if not isinstance(value, dict) or not value:
            continue
        reviewed.append(
            {
                "observation_id": str(row.get("candidate_id") or ""),
                "review_provenance": value,
            }
        )
    reviewed.sort(
        key=lambda x: (
            x["observation_id"],
            canonical_sha256(x["review_provenance"]),
        )
    )
    return {"observations": reviewed} if reviewed else {}


def _normalized_source_content(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_url": str(row.get("url") or "") or None,
        "resolved_url": str(row.get("resolved_url") or "") or None,
        "title": str(row.get("title") or ""),
        "snippet": str(row.get("snippet") or ""),
        "matched_text_excerpt": str(row.get("matched_text_excerpt") or ""),
        "publisher": str(row.get("publisher") or ""),
        "publisher_url": str(row.get("publisher_url") or ""),
        "published_at": str(row.get("published_at") or "") or None,
    }


def _source_timestamp(row: dict[str, Any]) -> tuple[datetime | None, str, str | None]:
    raw = str(row.get("published_at") or "").strip()
    if not raw:
        return None, "ABSENT_IN_ACCEPTED_SOURCE", None
    parsed = _parse_dt(raw)
    if parsed is None:
        return None, "UNPARSEABLE_IN_ACCEPTED_SOURCE", raw
    return parsed, "MATERIALIZED", None


def _telegram_identity(row: dict[str, Any]) -> tuple[str | None, int | None]:
    url = str(row.get("url") or "").strip()
    source = str(row.get("source") or "")
    if "telegram" not in source.lower() and "t.me/" not in url:
        return None, None
    try:
        parts = [x for x in urlparse(url).path.split("/") if x]
        if len(parts) >= 2 and parts[-1].isdigit():
            return parts[-2], int(parts[-1])
    except Exception:
        pass
    return None, None


def _event_time_from_evidence(evidence: dict[str, Any]) -> datetime | None:
    temporal = evidence.get("temporal_binding")
    if not isinstance(temporal, dict):
        return None
    return _parse_dt(temporal.get("event_time"))


def _source_row(
    row: dict[str, Any],
    *,
    classification_key: str,
    origin: dict[str, Any],
) -> dict[str, Any]:
    observation_id = str(row.get("candidate_id") or "").strip()
    if not observation_id:
        raise PersistenceContractError("evidence observation lacks candidate_id")
    evidence = row.get("classification_evidence")
    evidence = evidence if isinstance(evidence, dict) else {}
    content_sha = canonical_sha256(_normalized_source_content(row))
    source_link_key = _tuple_sha256(
        [
            SOURCE_LINK_KEY_VERSION,
            classification_key,
            observation_id,
            content_sha,
        ]
    )
    source_type = str(row.get("source") or "").strip() or None
    source_type_state = (
        "MATERIALIZED" if source_type else "UNMATERIALIZED_IN_ACCEPTED_SOURCE"
    )
    source_timestamp, timestamp_state, timestamp_raw = _source_timestamp(row)
    telegram_channel, telegram_message_id = _telegram_identity(row)
    excerpt = (
        str(row.get("matched_text_excerpt") or "").strip()
        or str(row.get("snippet") or "").strip()
        or str(row.get("title") or "").strip()
        or None
    )
    if excerpt is not None:
        excerpt = excerpt[:12000]
    retrieval = {
        "source": source_type,
        "discovery_basis": row.get("discovery_basis"),
        "resolved_url": row.get("resolved_url"),
        "matching_outcome": row.get("matching_outcome"),
        "matching_reason": row.get("matching_reason"),
        "matched_episode_id": row.get("matched_episode_id"),
        "matched_episode_ids": list(row.get("matched_episode_ids") or []),
        "trigger_episode_ids": list(row.get("trigger_episode_ids") or []),
        "trigger_check_labels": list(row.get("trigger_check_labels") or []),
        "first_discovered_at": row.get("first_discovered_at"),
    }
    source_origin = dict(origin["origin_provenance"])
    source_origin["observation_id"] = observation_id
    source_origin["candidate_content_sha256"] = content_sha
    return {
        "source_link_key_version": SOURCE_LINK_KEY_VERSION,
        "source_link_key": source_link_key,
        "observation_id": observation_id,
        "source_family": str(row.get("publisher_url") or "").strip() or None,
        "source_type": source_type,
        "source_type_state": source_type_state,
        "source_url": str(row.get("url") or "").strip() or None,
        "telegram_channel": telegram_channel,
        "telegram_message_id": telegram_message_id,
        "source_timestamp": source_timestamp,
        "source_timestamp_state": timestamp_state,
        "source_timestamp_raw": timestamp_raw,
        "event_timestamp_if_stated": _event_time_from_evidence(evidence),
        "excerpt": excerpt,
        "content_sha256": content_sha,
        "content_hash_basis": "NORMALIZED_EVIDENCE",
        "observation_classification_outcome": (
            str(row.get("status") or "").strip() or None
        ),
        "classification_episode_id": (
            str(evidence.get("classification_episode_id") or "").strip() or None
        ),
        "evidence_payload": evidence,
        "retrieval_provenance": retrieval,
        "origin_artifact_path": MONITOR_RELATIVE_PATH,
        "origin_git_ref": origin["ref"],
        "origin_git_blob_sha": origin["monitor_blob"],
        "raw_object_path": None,
        "origin_provenance": source_origin,
        "origin_provenance_sha256": canonical_sha256(source_origin),
    }


def build_episode_classification(
    episode: dict[str, Any],
    queue: list[dict[str, Any]],
    *,
    origin: dict[str, Any] | None = None,
) -> dict[str, Any]:
    origin = origin or _origin_context()
    episode_id = str(episode.get("episode_id") or "").strip()
    city_key = str(episode.get("city_key") or "").strip()
    if not _HEX24.fullmatch(episode_id):
        raise PersistenceContractError(f"invalid logical episode id: {episode_id!r}")
    if not city_key:
        raise PersistenceContractError("episode city_key missing")
    start = _parse_dt(episode.get("alert_start"))
    end = _parse_dt(episode.get("alert_end"))
    if start is None or end is None or end <= start:
        raise PersistenceContractError(f"invalid episode interval for {episode_id}")

    related = [
        row
        for row in queue
        if isinstance(row, dict)
        and str(row.get("city_key") or "") == city_key
        and episode_id in _episode_refs(row)
    ]
    strict = [
        row
        for row in related
        if str(row.get("status") or "") == "approved_strict"
        and str(row.get("matched_episode_id") or "") == episode_id
    ]
    sensitivity = [
        row
        for row in related
        if str(row.get("status") or "") == "approved_sensitivity"
        and str(row.get("matched_episode_id") or "") == episode_id
    ]
    review = [
        row for row in related if str(row.get("status") or "") == "needs_review"
    ]
    qa_reasons = _residual_qa(related)
    if strict:
        verdict = "STRICT_EVENT_POSITIVE"
    elif sensitivity:
        verdict = "SENSITIVITY_EVENT_POSITIVE"
    elif review or qa_reasons:
        verdict = "NEEDS_REVIEW"
    else:
        verdict = "NO_CONFIRMED_EVENT"

    event_types = sorted(
        {
            event_type
            for row in related
            for event_type in _item_event_types(row)
        }
    )
    reason_codes = sorted(
        {
            str(code)
            for row in related
            for code in row.get("classification_reason_codes") or []
            if str(code).strip()
        }
    )
    review_provenance = _review_provenance(related)
    review_sha = (
        canonical_sha256(review_provenance) if review_provenance else None
    )

    start_us = utc_microseconds(start)
    end_us = utc_microseconds(end)
    source_rows_unkeyed = []
    evidence_membership = []
    for row in sorted(
        related,
        key=lambda x: (
            str(x.get("candidate_id") or ""),
            str(x.get("url") or ""),
            str(x.get("title") or ""),
        ),
    ):
        normalized = _normalized_source_content(row)
        content_sha = canonical_sha256(normalized)
        observation_id = str(row.get("candidate_id") or "").strip()
        if not observation_id:
            raise PersistenceContractError(
                f"related evidence for {episode_id} lacks candidate_id"
            )
        evidence_membership.append([observation_id, content_sha])
        source_rows_unkeyed.append(row)
    evidence_membership.sort(key=lambda x: (x[0], x[1]))
    evidence_set_sha256 = _tuple_sha256(evidence_membership)

    qa_reasons_state = "MATERIALIZED"
    classification_tuple = [
        CLASSIFICATION_KEY_VERSION,
        city_key,
        episode_id,
        start_us,
        end_us,
        verdict,
        json.dumps(event_types, ensure_ascii=False, separators=(",", ":")),
        qa_reasons_state,
        json.dumps(qa_reasons, ensure_ascii=False, separators=(",", ":")),
        AUTHORITATIVE_CLASSIFIER_BLOB,
        CLASSIFIER_METHODOLOGY_VERSION,
        NORMALIZATION_VERSION,
        evidence_set_sha256,
        review_sha,
    ]
    classification_key = _tuple_sha256(classification_tuple)

    source_rows = [
        _source_row(
            row,
            classification_key=classification_key,
            origin=origin,
        )
        for row in source_rows_unkeyed
    ]

    is_event = verdict in POSITIVE_VERDICTS
    positive_tier = (
        "STRICT"
        if verdict == "STRICT_EVENT_POSITIVE"
        else "SENSITIVITY"
        if verdict == "SENSITIVITY_EVENT_POSITIVE"
        else None
    )
    human_review_state = (
        "NEEDS_REVIEW"
        if verdict == "NEEDS_REVIEW"
        else "REVIEWED_EVIDENCE"
        if review_provenance
        else "NONE"
    )
    attack_event_key = _tuple_sha256(
        [
            ATTACK_EVENT_KEY_VERSION,
            EVENT_GRAIN,
            city_key,
            episode_id,
            start_us,
            end_us,
        ]
    )

    return {
        "classification_key_version": CLASSIFICATION_KEY_VERSION,
        "classification_key": classification_key,
        "historical_episode_id": episode_id,
        "city_key": city_key,
        "alert_type": "AIR",
        "alert_start_at": start,
        "alert_end_at": end,
        "alert_start_utc_microseconds": start_us,
        "alert_end_utc_microseconds": end_us,
        "verdict": verdict,
        "is_event": is_event,
        "positive_tier": positive_tier,
        "event_types": event_types,
        "qa_reasons_state": qa_reasons_state,
        "qa_reasons": qa_reasons,
        "classifier_reason_codes": reason_codes,
        "classifier_blob_sha": AUTHORITATIVE_CLASSIFIER_BLOB,
        "classifier_methodology_version": CLASSIFIER_METHODOLOGY_VERSION,
        "normalization_version": NORMALIZATION_VERSION,
        "evidence_set_sha256": evidence_set_sha256,
        "review_provenance_sha256": review_sha,
        "human_review_state": human_review_state,
        "review_provenance": review_provenance,
        "originating_frozen_case_id": None,
        "originating_frozen_case_id_state": "NOT_APPLICABLE",
        "origin_repository": ORIGIN_REPOSITORY,
        "origin_ref": origin["ref"],
        "origin_commit_sha": origin["commit"],
        "origin_artifact_path": MONITOR_RELATIVE_PATH,
        "origin_artifact_blob_sha": origin["monitor_blob"],
        "origin_target_state_sha256": None,
        "origin_workflow_run_id": origin["run_id"],
        "classified_at": datetime.now(timezone.utc),
        "origin_provenance": origin["origin_provenance"],
        "origin_provenance_sha256": origin["origin_provenance_sha256"],
        "attack_event_key_version": ATTACK_EVENT_KEY_VERSION,
        "attack_event_key": attack_event_key,
        "event_grain": EVENT_GRAIN,
        "source_rows": source_rows,
        "accepted_evidence_membership": evidence_membership,
    }


def _parent_binding(cur, record: dict[str, Any]) -> str:
    cur.execute(
        """
        SELECT episode_uid
        FROM public.alert_episodes
        WHERE legacy_episode_id = %s
          AND city_key = %s
          AND alert_type = 'AIR'
          AND episode_state = 'closed'
          AND canonicalization_version = 'alert-canonicalization-v1'
          AND start_at = %s
          AND end_at = %s
        """,
        (
            record["historical_episode_id"],
            record["city_key"],
            record["alert_start_at"],
            record["alert_end_at"],
        ),
    )
    rows = cur.fetchall()
    if len(rows) != 1:
        raise PersistenceContractError(
            "live classification requires exactly one canonical alert_episodes parent: "
            f"{record['city_key']}:{record['historical_episode_id']} matches={len(rows)}"
        )
    return str(rows[0][0])


def _current_tip(cur, record: dict[str, Any]) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT
            c.classification_uid,
            c.classification_key,
            c.verdict,
            c.origin_provenance
        FROM public.attack_event_classifications c
        WHERE c.city_key = %s
          AND c.historical_episode_id = %s
          AND c.alert_start_at = %s
          AND c.alert_end_at = %s
          AND NOT EXISTS (
              SELECT 1
              FROM public.attack_event_classifications n
              WHERE n.supersedes_classification_uid = c.classification_uid
          )
        ORDER BY c.created_at, c.classification_uid
        """,
        (
            record["city_key"],
            record["historical_episode_id"],
            record["alert_start_at"],
            record["alert_end_at"],
        ),
    )
    rows = cur.fetchall()
    if len(rows) > 1:
        raise PersistenceContractError(
            "classification revision chain has multiple current tips for "
            f"{record['city_key']}:{record['historical_episode_id']}"
        )
    if not rows:
        return None
    return {
        "classification_uid": str(rows[0][0]),
        "classification_key": str(rows[0][1]),
        "verdict": str(rows[0][2]),
        "origin_provenance": rows[0][3] if isinstance(rows[0][3], dict) else {},
    }


def _existing_classification(cur, key: str) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT
            classification_uid, classification_key_version, classification_key,
            historical_episode_id, city_key, alert_start_at, alert_end_at,
            verdict, is_event, positive_tier, event_types, qa_reasons_state,
            qa_reasons, classifier_reason_codes, classifier_blob_sha,
            classifier_methodology_version, normalization_version,
            evidence_set_sha256, review_provenance_sha256
        FROM public.attack_event_classifications
        WHERE classification_key = %s
        """,
        (key,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    columns = [
        "classification_uid", "classification_key_version", "classification_key",
        "historical_episode_id", "city_key", "alert_start_at", "alert_end_at",
        "verdict", "is_event", "positive_tier", "event_types", "qa_reasons_state",
        "qa_reasons", "classifier_reason_codes", "classifier_blob_sha",
        "classifier_methodology_version", "normalization_version",
        "evidence_set_sha256", "review_provenance_sha256",
    ]
    return dict(zip(columns, row))


def _assert_existing_classification(
    existing: dict[str, Any],
    record: dict[str, Any],
) -> None:
    expected = {
        "classification_key_version": record["classification_key_version"],
        "classification_key": record["classification_key"],
        "historical_episode_id": record["historical_episode_id"],
        "city_key": record["city_key"],
        "verdict": record["verdict"],
        "is_event": record["is_event"],
        "positive_tier": record["positive_tier"],
        "event_types": list(record["event_types"]),
        "qa_reasons_state": record["qa_reasons_state"],
        "qa_reasons": record["qa_reasons"],
        "classifier_reason_codes": list(record["classifier_reason_codes"]),
        "classifier_blob_sha": record["classifier_blob_sha"],
        "classifier_methodology_version": record["classifier_methodology_version"],
        "normalization_version": record["normalization_version"],
        "evidence_set_sha256": record["evidence_set_sha256"],
        "review_provenance_sha256": record["review_provenance_sha256"],
    }
    for key, value in expected.items():
        actual = existing.get(key)
        if key in {"event_types", "classifier_reason_codes"}:
            actual = list(actual or [])
        if key == "qa_reasons" and actual is not None:
            actual = list(actual)
        if actual != value:
            raise PersistenceContractError(
                f"existing classification key semantic conflict on {key}"
            )
    if utc_microseconds(existing["alert_start_at"]) != record["alert_start_utc_microseconds"]:
        raise PersistenceContractError("existing classification start bound conflict")
    if utc_microseconds(existing["alert_end_at"]) != record["alert_end_utc_microseconds"]:
        raise PersistenceContractError("existing classification end bound conflict")


def _insert_classification(
    cur,
    record: dict[str, Any],
    *,
    alert_episode_uid: str,
    supersedes_uid: str | None,
    revision_reason: str | None,
    correction_provenance: dict[str, Any],
) -> tuple[str, bool]:
    cur.execute(
        """
        INSERT INTO public.attack_event_classifications (
            classification_key_version, classification_key,
            historical_episode_id, city_key, alert_type,
            alert_start_at, alert_end_at, verdict, is_event, positive_tier,
            event_types, qa_reasons_state, qa_reasons, classifier_reason_codes,
            classifier_blob_sha, classifier_methodology_version, normalization_version,
            evidence_set_sha256, review_provenance_sha256, human_review_state,
            review_provenance, originating_frozen_case_id,
            originating_frozen_case_id_state, binding_state, alert_episode_uid,
            origin_repository, origin_ref, origin_commit_sha, origin_artifact_path,
            origin_artifact_blob_sha, origin_target_state_sha256, origin_workflow_run_id,
            classified_at, supersedes_classification_uid, revision_reason,
            correction_provenance, persisted_by_run_id,
            origin_provenance, origin_provenance_sha256
        ) VALUES (
            %s,%s,%s,%s,%s,
            %s,%s,%s,%s,%s,
            %s,%s,%s,%s,
            %s,%s,%s,
            %s,%s,%s,
            %s,%s,
            %s,'BOUND',%s,
            %s,%s,%s,%s,
            %s,%s,%s,
            %s,%s,%s,
            %s,NULL,
            %s,%s
        )
        ON CONFLICT (classification_key) DO NOTHING
        RETURNING classification_uid
        """,
        (
            record["classification_key_version"],
            record["classification_key"],
            record["historical_episode_id"],
            record["city_key"],
            record["alert_type"],
            record["alert_start_at"],
            record["alert_end_at"],
            record["verdict"],
            record["is_event"],
            record["positive_tier"],
            record["event_types"],
            record["qa_reasons_state"],
            Jsonb(record["qa_reasons"]),
            record["classifier_reason_codes"],
            record["classifier_blob_sha"],
            record["classifier_methodology_version"],
            record["normalization_version"],
            record["evidence_set_sha256"],
            record["review_provenance_sha256"],
            record["human_review_state"],
            Jsonb(record["review_provenance"]),
            record["originating_frozen_case_id"],
            record["originating_frozen_case_id_state"],
            alert_episode_uid,
            record["origin_repository"],
            record["origin_ref"],
            record["origin_commit_sha"],
            record["origin_artifact_path"],
            record["origin_artifact_blob_sha"],
            record["origin_target_state_sha256"],
            record["origin_workflow_run_id"],
            record["classified_at"],
            supersedes_uid,
            revision_reason,
            Jsonb(correction_provenance),
            Jsonb(record["origin_provenance"]),
            record["origin_provenance_sha256"],
        ),
    )
    inserted = cur.fetchone()
    if inserted is not None:
        return str(inserted[0]), True
    existing = _existing_classification(cur, record["classification_key"])
    if existing is None:
        raise PersistenceContractError(
            "classification insert conflicted but deterministic row is unavailable"
        )
    _assert_existing_classification(existing, record)
    return str(existing["classification_uid"]), False


def _ensure_event(
    cur,
    record: dict[str, Any],
    *,
    classification_uid: str,
    alert_episode_uid: str,
    correction_provenance: dict[str, Any],
) -> tuple[bool, bool]:
    cur.execute(
        """
        SELECT attack_event_uid, attack_event_key, event_status, current_classification_uid,
               city_key, historical_episode_id, alert_start_at, alert_end_at
        FROM public.attack_events
        WHERE city_key=%s AND historical_episode_id=%s
        """,
        (record["city_key"], record["historical_episode_id"]),
    )
    row = cur.fetchone()
    positive = bool(record["is_event"])
    if row is None:
        if not positive:
            return False, False
        cur.execute(
            """
            INSERT INTO public.attack_events (
                attack_event_key_version, attack_event_key, event_grain,
                historical_episode_id, city_key, alert_type,
                alert_start_at, alert_end_at, event_status,
                current_classification_uid, binding_state, alert_episode_uid,
                correction_provenance, created_by_run_id, updated_by_run_id
            ) VALUES (
                %s,%s,%s,%s,%s,'AIR',%s,%s,'ACTIVE',%s,'BOUND',%s,%s,NULL,NULL
            )
            ON CONFLICT (attack_event_key) DO NOTHING
            RETURNING attack_event_uid
            """,
            (
                record["attack_event_key_version"],
                record["attack_event_key"],
                record["event_grain"],
                record["historical_episode_id"],
                record["city_key"],
                record["alert_start_at"],
                record["alert_end_at"],
                classification_uid,
                alert_episode_uid,
                Jsonb(correction_provenance),
            ),
        )
        inserted = cur.fetchone()
        if inserted is not None:
            return True, False
        cur.execute(
            """
            SELECT attack_event_uid, attack_event_key, event_status,
                   current_classification_uid, city_key, historical_episode_id,
                   alert_start_at, alert_end_at
            FROM public.attack_events
            WHERE attack_event_key=%s
            """,
            (record["attack_event_key"],),
        )
        row = cur.fetchone()
        if row is None:
            raise PersistenceContractError(
                "event insert conflicted but deterministic event is unavailable"
            )

    (
        _event_uid,
        existing_key,
        existing_status,
        existing_current_uid,
        existing_city,
        existing_episode_id,
        existing_start,
        existing_end,
    ) = row
    if (
        str(existing_key) != record["attack_event_key"]
        or str(existing_city) != record["city_key"]
        or str(existing_episode_id) != record["historical_episode_id"]
        or utc_microseconds(existing_start) != record["alert_start_utc_microseconds"]
        or utc_microseconds(existing_end) != record["alert_end_utc_microseconds"]
    ):
        raise PersistenceContractError("stable attack-event identity conflict")

    target_status = "ACTIVE" if positive else "WITHDRAWN"
    if (
        str(existing_status) == target_status
        and str(existing_current_uid) == classification_uid
    ):
        return False, False

    cur.execute(
        """
        UPDATE public.attack_events
        SET event_status=%s,
            current_classification_uid=%s,
            binding_state='BOUND',
            alert_episode_uid=%s,
            correction_provenance=%s,
            updated_by_run_id=NULL,
            updated_at=now()
        WHERE attack_event_key=%s
        """,
        (
            target_status,
            classification_uid,
            alert_episode_uid,
            Jsonb(correction_provenance),
            record["attack_event_key"],
        ),
    )
    if cur.rowcount != 1:
        raise PersistenceContractError("stable attack-event update lost its target row")
    return False, True


def _ensure_sources(
    cur,
    record: dict[str, Any],
    *,
    classification_uid: str,
) -> int:
    inserted_count = 0
    for source in record["source_rows"]:
        cur.execute(
            """
            INSERT INTO public.attack_event_sources (
                source_link_key_version, source_link_key, classification_uid,
                observation_id, source_family, source_type, source_type_state,
                source_url, telegram_channel, telegram_message_id,
                source_timestamp, source_timestamp_state, source_timestamp_raw,
                event_timestamp_if_stated, excerpt,
                content_sha256, content_hash_basis,
                observation_classification_outcome, classification_episode_id,
                evidence_payload, retrieval_provenance,
                origin_artifact_path, origin_git_ref, origin_git_blob_sha,
                raw_object_path, origin_provenance, origin_provenance_sha256
            ) VALUES (
                %s,%s,%s,
                %s,%s,%s,%s,
                %s,%s,%s,
                %s,%s,%s,
                %s,%s,
                %s,%s,
                %s,%s,
                %s,%s,
                %s,%s,%s,
                %s,%s,%s
            )
            ON CONFLICT (source_link_key) DO NOTHING
            RETURNING attack_event_source_uid
            """,
            (
                source["source_link_key_version"],
                source["source_link_key"],
                classification_uid,
                source["observation_id"],
                source["source_family"],
                source["source_type"],
                source["source_type_state"],
                source["source_url"],
                source["telegram_channel"],
                source["telegram_message_id"],
                source["source_timestamp"],
                source["source_timestamp_state"],
                source["source_timestamp_raw"],
                source["event_timestamp_if_stated"],
                source["excerpt"],
                source["content_sha256"],
                source["content_hash_basis"],
                source["observation_classification_outcome"],
                source["classification_episode_id"],
                Jsonb(source["evidence_payload"]),
                Jsonb(source["retrieval_provenance"]),
                source["origin_artifact_path"],
                source["origin_git_ref"],
                source["origin_git_blob_sha"],
                source["raw_object_path"],
                Jsonb(source["origin_provenance"]),
                source["origin_provenance_sha256"],
            ),
        )
        inserted = cur.fetchone()
        if inserted is not None:
            inserted_count += 1
            continue
        cur.execute(
            """
            SELECT classification_uid, observation_id, content_sha256
            FROM public.attack_event_sources
            WHERE source_link_key=%s
            """,
            (source["source_link_key"],),
        )
        existing = cur.fetchone()
        if existing is None:
            raise PersistenceContractError(
                "source-link conflict without deterministic source row"
            )
        if (
            str(existing[0]) != classification_uid
            or str(existing[1]) != source["observation_id"]
            or str(existing[2]) != source["content_sha256"]
        ):
            raise PersistenceContractError("existing source-link semantic conflict")
    return inserted_count


def persist_episode_classification(
    conn,
    record: dict[str, Any],
    *,
    fault_after: str | None = None,
) -> dict[str, Any]:
    lock_key = (
        f"{record['city_key']}|{record['historical_episode_id']}|"
        f"{record['alert_start_utc_microseconds']}|{record['alert_end_utc_microseconds']}"
    )
    with conn.transaction():
        cur = conn.cursor()
        cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (lock_key,))
        parent_uid = _parent_binding(cur, record)
        current = _current_tip(cur, record)
        existing = _existing_classification(cur, record["classification_key"])

        if existing is not None:
            _assert_existing_classification(existing, record)
            existing_uid = str(existing["classification_uid"])
            if current is not None and current["classification_uid"] != existing_uid:
                raise PersistenceContractError(
                    "deterministic classification exists but is not the current revision tip"
                )
            classification_uid = existing_uid
            classification_inserted = False
            revision = False
            correction = {}
        else:
            if current is not None:
                current_origin = current.get("origin_provenance") or {}
                if current_origin.get("kind") != ORIGIN_KIND:
                    raise PersistenceContractError(
                        "refusing to revise a pre-existing non-live/frozen classification "
                        f"for {record['city_key']}:{record['historical_episode_id']}"
                    )
                correction = {
                    "kind": "LIVE_FOLLOWUP_RECLASSIFICATION",
                    "previous_classification_uid": current["classification_uid"],
                    "previous_classification_key": current["classification_key"],
                    "previous_verdict": current["verdict"],
                }
                supersedes_uid = current["classification_uid"]
                revision_reason = "LIVE_FOLLOWUP_RECLASSIFICATION"
                revision = True
            else:
                correction = {}
                supersedes_uid = None
                revision_reason = None
                revision = False
            classification_uid, classification_inserted = _insert_classification(
                cur,
                record,
                alert_episode_uid=parent_uid,
                supersedes_uid=supersedes_uid,
                revision_reason=revision_reason,
                correction_provenance=correction,
            )

        if fault_after == "classification":
            raise RuntimeError("FORCED_PERSISTENCE_FAILURE_AFTER_CLASSIFICATION")

        event_inserted, event_updated = _ensure_event(
            cur,
            record,
            classification_uid=classification_uid,
            alert_episode_uid=parent_uid,
            correction_provenance=correction,
        )

        if fault_after == "event":
            raise RuntimeError("FORCED_PERSISTENCE_FAILURE_AFTER_EVENT")

        source_inserts = _ensure_sources(
            cur,
            record,
            classification_uid=classification_uid,
        )

        return {
            "classification_uid": classification_uid,
            "classification_key": record["classification_key"],
            "classification_inserted": classification_inserted,
            "revision_inserted": bool(classification_inserted and revision),
            "verdict": record["verdict"],
            "event_inserted": event_inserted,
            "event_updated": event_updated,
            "source_inserts": source_inserts,
            "source_count": len(record["source_rows"]),
        }


def persist_due_episode_classifications(
    *,
    queue: list[dict[str, Any]],
    due: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]],
    coverage_by_city: dict[str, bool],
    dsn: str | None = None,
    connection=None,
) -> dict[str, Any]:
    city_keys = sorted(due)
    result: dict[str, Any] = {
        "enabled": bool(connection is not None or dsn),
        "cities_with_due_checks": city_keys,
        "episodes_considered": 0,
        "episodes_persisted": 0,
        "episodes_skipped_incomplete_coverage": 0,
        "classification_inserts": 0,
        "classification_revisions": 0,
        "event_inserts": 0,
        "event_updates": 0,
        "source_inserts": 0,
        "verdicts": {},
        "records": [],
    }
    if connection is None and not dsn:
        result["reason"] = "ATTACK_EVENT_DATABASE_URL_NOT_CONFIGURED"
        return result

    origin = _origin_context()
    own_connection = connection is None
    conn = connection or psycopg.connect(str(dsn), autocommit=False)
    try:
        for city_key in city_keys:
            city_due = due.get(city_key) or []
            coverage_complete = bool(coverage_by_city.get(city_key))
            for episode, _check in city_due:
                result["episodes_considered"] += 1
                if not coverage_complete:
                    result["episodes_skipped_incomplete_coverage"] += 1
                    continue
                record = build_episode_classification(
                    episode,
                    queue,
                    origin=origin,
                )
                persisted = persist_episode_classification(conn, record)
                result["episodes_persisted"] += 1
                result["classification_inserts"] += int(
                    persisted["classification_inserted"]
                )
                result["classification_revisions"] += int(
                    persisted["revision_inserted"]
                )
                result["event_inserts"] += int(persisted["event_inserted"])
                result["event_updates"] += int(persisted["event_updated"])
                result["source_inserts"] += int(persisted["source_inserts"])
                verdict = str(record["verdict"])
                result["verdicts"][verdict] = int(
                    result["verdicts"].get(verdict, 0)
                ) + 1
                result["records"].append(
                    {
                        "city_key": record["city_key"],
                        "episode_id": record["historical_episode_id"],
                        "classification_key": record["classification_key"],
                        "verdict": verdict,
                        "classification_inserted": persisted[
                            "classification_inserted"
                        ],
                        "revision_inserted": persisted["revision_inserted"],
                        "event_inserted": persisted["event_inserted"],
                        "event_updated": persisted["event_updated"],
                        "source_inserts": persisted["source_inserts"],
                    }
                )
    finally:
        if own_connection:
            conn.close()
    return result
