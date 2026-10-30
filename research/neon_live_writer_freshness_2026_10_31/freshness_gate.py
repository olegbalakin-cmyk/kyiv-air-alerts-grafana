#!/usr/bin/env python3
"""Publish gate only. Synthetic tests are not physical Neon proof."""
from __future__ import annotations
import copy
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from uuid import UUID

HEX64 = re.compile(r"^[a-f0-9]{64}$")
UTC = timezone.utc

class GateClosed(ValueError):
    pass

def utc(value):
    date = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if date.tzinfo is None:
        raise GateClosed("NAIVE_TIMESTAMP")
    return date.astimezone(UTC)

def require(cond, code):
    if not cond:
        raise GateClosed(code)

def gate(evidence, *, max_age_seconds=21600):
    """Permit only a physically received, same-branch and freshly read-back episode.
    generated_at is NOT the canonical as-of timestamp.
    """
    source = evidence["source"]
    writer = evidence["writer"]
    readback = evidence["readback"]
    output = evidence["output"]
    now = utc(evidence["evaluated_at_utc"])

    require(source.get("http_status") == 200 and source.get("parsed") is True, "SOURCE_UNVERIFIED")
    require(bool(HEX64.fullmatch(source.get("raw_sha256", ""))), "SOURCE_RAW_HASH_INVALID")
    require(bool(HEX64.fullmatch(source.get("source_record_key", ""))), "SOURCE_IDENTITY_INVALID")
    require(source.get("completed") is True, "NO_COMPLETED_EPISODE")
    source_at = utc(source["captured_at_utc"])
    event_end = utc(source["event_end_utc"])
    require(event_end <= source_at, "EVENT_AFTER_CAPTURE")
    require(0 <= (now - source_at).total_seconds() <= max_age_seconds, "STALE_SOURCE_CAPTURE")

    require(writer.get("transaction_status") == "succeeded", "INGEST_NOT_COMMITTED")
    require(writer.get("isolated_branch_verified") is True, "BRANCH_NOT_VERIFIED")
    branch = writer.get("branch_id")
    require(isinstance(branch, str) and branch.startswith("br-"), "BRANCH_ID_INVALID")
    require(branch not in {"br-wandering-sunset-b5835alw","br-bold-mode-b5rub8pq"}, "PRODUCTION_OR_SHADOW_BRANCH")
    commit_at = utc(writer["committed_at_utc"])
    require(source_at <= commit_at <= now, "BAD_COMMIT_ORDER_OR_FUTURE")
    require((now - commit_at).total_seconds() <= max_age_seconds, "STALE_DB_COMMIT")
    try:
        episode_uuid = str(UUID(writer["episode_uuid"]))
        observation_uuid = str(UUID(writer["source_observation_uuid"]))
    except (ValueError, AttributeError, TypeError, KeyError):
        raise GateClosed("MISSING_PHYSICAL_UUID") from None

    require(readback.get("independent_connection") is True and readback.get("transaction_read_only") is True, "READBACK_NOT_INDEPENDENT_READONLY")
    require(readback.get("branch_id") == branch, "READBACK_WRONG_BRANCH")
    require(readback.get("episode_uuid") == episode_uuid, "EPISODE_UUID_MISMATCH")
    require(readback.get("source_observation_uuid") == observation_uuid, "OBSERVATION_UUID_MISMATCH")
    require(readback.get("source_record_key") == source["source_record_key"], "READBACK_SOURCE_IDENTITY_MISMATCH")
    require(readback.get("ingestion_status") == "succeeded", "READBACK_COMMIT_NOT_DURABLE")
    read_at = utc(readback["at_utc"])
    require(commit_at <= read_at <= now, "READBACK_ORDER_OR_FUTURE")

    require(output.get("branch_id") == branch and output.get("contains_episode_uuid") is True, "RENDER_NOT_FROM_READBACK")
    require(output.get("contains_source_provenance") is True, "RENDER_SOURCE_PROVENANCE_MISSING")
    require(bool(HEX64.fullmatch(output.get("site_json_sha256", ""))), "RENDER_BYTE_HASH_MISSING")
    generated_at = utc(output["generated_at_utc"])
    data_as_of = utc(output["source_data_as_of_utc"])
    require(read_at <= generated_at <= now, "RENDER_NOT_AFTER_READBACK")
    require(data_as_of == source_at, "FALSE_FRESHNESS_TIMESTAMP")
    require(output.get("unverified_fallback") is False, "LEGACY_FALLBACK_NOT_AUTHORIZED")
    return {"verdict": "PASS_IF_ALL_EVIDENCE_IS_PHYSICAL", "branch_id": branch,
            "source_checked_at": source["captured_at_utc"],
            "generation_time": output["generated_at_utc"],
            "episode_uuid": episode_uuid}

def self_test():
    now = datetime(2026, 10, 31, 0, 0, tzinfo=UTC)
    def t(delta):
        return (now + timedelta(seconds=delta)).isoformat().replace("+00:00","Z")
    u1 = "c4c916e3-94db-4413-880a-dda4b699ddf6"
    u2 = "0b8f814a-9820-44bd-83d3-4a37995042fe"
    good = {"evaluated_at_utc":t(0),
        "source":{"http_status":200,"parsed":True,"raw_sha256":"a"*64,
                  "source_record_key":"b"*64,"completed":True,
                  "captured_at_utc":t(-100), "event_end_utc":t(-86400)},
        "writer":{"transaction_status":"succeeded","isolated_branch_verified":True,
                  "branch_id":"br-isolated-test-fixture",
                  "committed_at_utc":t(-90),"episode_uuid":u1,"source_observation_uuid":u2},
        "readback":{"independent_connection":True,"transaction_read_only":True,
                    "branch_id":"br-isolated-test-fixture","episode_uuid":u1,
                    "source_observation_uuid":u2,"source_record_key":"b"*64,
                    "ingestion_status":"succeeded","at_utc":t(-80)},
        "output":{"branch_id":"br-isolated-test-fixture","contains_episode_uuid":True,
                  "contains_source_provenance":True,"site_json_sha256":"c"*64,
                  "generated_at_utc":t(-70),"source_data_as_of_utc":t(-100),
                  "unverified_fallback":False}}
    gate(good)
    scenarios = {
        "stale_http_receipt":("source","captured_at_utc",t(-26000),"STALE_SOURCE_CAPTURE"),
        "http_failure":("source","http_status",503,"SOURCE_UNVERIFIED"),
        "source_identity_not_valid":("source","source_record_key","bad","SOURCE_IDENTITY_INVALID"),
        "closed_event_in_future":("source","event_end_utc",t(10),"EVENT_AFTER_CAPTURE"),
        "stale_committed_ingest":("writer","committed_at_utc",t(-27000),"BAD_COMMIT_ORDER_OR_FUTURE"),
        "failed_commit":("writer","transaction_status","failed","INGEST_NOT_COMMITTED"),
        "parent_shadow_rejected":("writer","branch_id","br-bold-mode-b5rub8pq","PRODUCTION_OR_SHADOW_BRANCH"),
        "independent_readback_required":("readback","independent_connection",False,"READBACK_NOT_INDEPENDENT_READONLY"),
        "different_episode_uuid":("readback","episode_uuid",u2,"EPISODE_UUID_MISMATCH"),
        "different_source_record":("readback","source_record_key","d"*64,"READBACK_SOURCE_IDENTITY_MISMATCH"),
        "readback_failed_commit":("readback","ingestion_status","running","READBACK_COMMIT_NOT_DURABLE"),
        "unverified_render":("output","contains_episode_uuid",False,"RENDER_NOT_FROM_READBACK"),
        "generation_is_not_source_time":("output","source_data_as_of_utc",t(-70),"FALSE_FRESHNESS_TIMESTAMP"),
        "legacy_fallback_rejected":("output","unverified_fallback",True,"LEGACY_FALLBACK_NOT_AUTHORIZED"),
    }
    outcomes = {"synthetic_happy_path":"PASS"}
    for name,(group,key,value,expected) in scenarios.items():
        candidate = copy.deepcopy(good)
        candidate[group][key] = value
        try:
            gate(candidate)
        except GateClosed as exc:
            require(str(exc) == expected, "WRONG_GATE_REASON_"+name)
            outcomes[name] = "PASS_REJECTED_"+str(exc)
        else:
            raise AssertionError("UNEXPECTED_GATE_OPEN_"+name)
    # An old completed alert DOES NOT imply a stale source when a verified recent
    # source check and durable checkpoint exist. The HTTP freshness clock is separate.
    require(utc(good["source"]["event_end_utc"]) < now - timedelta(hours=12),
            "OLD_ALERT_FIXTURE_NOT_OLD")
    return {"test_count":1+len(scenarios),"passed":1+len(scenarios),
            "status":"PASS_SYNTHETIC_ONLY", "outcomes":outcomes,
            "proof_boundary":"No real HTTP, database or site generator is executed by this self-test."}

if __name__ == "__main__":
    print(json.dumps(self_test(),sort_keys=True))
