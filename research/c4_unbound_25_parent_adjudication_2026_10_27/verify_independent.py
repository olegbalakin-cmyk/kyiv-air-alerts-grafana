#!/usr/bin/env python3
"""Read-only, fail-closed verification of C4's exact 25 historical UNBOUND records."""
import argparse
import copy
import datetime as dt
import hashlib
import json
import pathlib
import re
import subprocess
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REGISTRY = HERE / "registry.json"
PINNED_PROOF = ("3d10cb3c3509c6945f9c9f3cdf02d8cfae46d143",
                "research/neon_frozen_h1_h2_semantic_unbound_reconciliation_2026-10-11.json",
                "9676e3d559a22ef8989c43604dce85dab95fa38b")
ALLOWED = {"NOT_PROVEN"}
CITY_COUNTS = {"lviv": 3, "sumy": 1, "zaporizhzhia": 1, "kharkiv": 2, "kyiv": 18}


def require(condition, why):
    if not condition:
        raise AssertionError(why)


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], stderr=subprocess.PIPE)


def pinned_blob(commit, path, blob):
    require(re.fullmatch("[a-f0-9]{40}", commit) is not None, "invalid commit")
    require(re.fullmatch("[a-f0-9]{40}", blob) is not None, "invalid blob")
    actual = git("rev-parse", commit + ":" + path).decode().strip()
    require(actual == blob, "commit:path/blob SHA mismatch: " + path)
    return git("cat-file", "blob", blob)


def utc(value):
    require(isinstance(value, str) and
            re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|[+-]\d\d:\d\d)", value),
            "invalid or timezone-naive clock")
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(dt.timezone.utc)


def canon(value):
    return utc(value).isoformat().replace("+00:00", "Z")


def episode_key(city, start, end):
    return hashlib.sha256((city + "|" + canon(start) + "|" + canon(end)).encode()).hexdigest()[:24]


def verify(data, base):
    require(len(data["decisions"]) == 25, "not exactly 25")
    require(data["frozen_unbound_proof"] == {"commit": PINNED_PROOF[0], "path": PINNED_PROOF[1],
             "blob": PINNED_PROOF[2], "snapshot_note": "Historical read-only projection; 25 missing parent rows, not a durable Neon nonexistence claim"},
            "frozen proof pin changed")
    require(data["original_contract_blob"] == "e9dcbdf21551ca086fbf096138f885f453a8c2b0", "parent contract drift")
    original = json.loads(pinned_blob(*PINNED_PROOF))
    reference = original["UNBOUND"]["dispositions"]
    require(len(reference) == 25, "original registry cardinality")
    require(data["sources"] == base["sources"], "source pin table changed")
    require(data["decisions"] == base["decisions"], "immutable research decisions changed")
    require(len(set(x["classification_uid"] for x in data["decisions"])) == 25, "duplicate UID")
    require(len(set(x["classification_key"] for x in data["decisions"])) == 25, "duplicate key")
    require(len(set(x["episode_id"] for x in data["decisions"])) == 25, "duplicate episode")
    require(Counter(x["cohort"] for x in data["decisions"]) == {"H1": 5, "H2": 20}, "cohort mismatch")
    require(dict(Counter(x["city"] for x in data["decisions"])) == CITY_COUNTS, "city mismatch")
    sources = {}
    for p in data["sources"]:
        raw = pinned_blob(p["commit"], p["path"], p["blob"])
        sources[(p["commit"], p["path"], p["blob"])] = json.loads(raw)["episodes"]
    precise = 0
    for index, (row, target) in enumerate(zip(data["decisions"], reference)):
        require(row["ordinal"] == index + 1, "record ordinal changed")
        for field in ("classification_uid", "classification_key", "episode_id", "city", "cohort"):
            require(row[field] == target[field], "frozen identity drift: " + field)
        for field, old in (("accepted_snapshot_start_at", "alert_start_at"), ("accepted_snapshot_end_at", "alert_end_at")):
            require(row[field] == target[old], "frozen clock drift")
        require(row["governing_git_blob"] == target["governing_git_blob"], "governing original proof changed")
        src_key = (row["source_git_commit"], row["source_path"], row["source_git_blob"])
        require(src_key in sources, "unapproved original source pin")
        require(row["source_episode_index"] in range(len(sources[src_key])), "original episode index missing")
        s = sources[src_key][row["source_episode_index"]]
        require(row["original_episode_id"] == s["episode_id"] and
                row["original_alert_start_at"] == s["alert_start"] and
                row["original_alert_end_at"] == s["alert_end"], "source content drift")
        require(utc(s["alert_start"]) < utc(s["alert_end"]), "invalid source interval")
        def snapshot_clock_equals_original(source, snapshot):
            if utc(source) == utc(snapshot):
                return True
            # H1 Lviv frozen snapshot projects milliseconds only.
            # This never authorizes a physical canonical parent binding.
            return (row["city"] == "lviv"
                    and utc(source).isoformat(timespec="milliseconds") ==
                        utc(snapshot).isoformat(timespec="milliseconds")
                    and utc(source).microsecond % 1000 != 0)
        require(snapshot_clock_equals_original(s["alert_start"], row["accepted_snapshot_start_at"]) and
                snapshot_clock_equals_original(s["alert_end"], row["accepted_snapshot_end_at"]),
                "source/snapshot clocks inconsistent beyond documented millisecond projection")
        require(episode_key(row["city"], s["alert_start"], s["alert_end"]) == row["episode_id"],
                "independently recomputed canonical deterministic ID mismatch")
        if row["city"] == "kyiv":
            require(s["episode_id"] != row["episode_id"] and
                    row["historical_episode_id_basis"] == "ORIGINAL_MUNICIPAL_ID_EXACT_INTERVAL_CROSSWALK",
                    "Kyiv municipal crosswalk must be explicit")
        else:
            require(s["episode_id"] == row["episode_id"] and
                    row["historical_episode_id_basis"] == "DIRECT_SOURCE_EPISODE_ID",
                    "historical source identity mismatch")
        precision_loss = canon(s["alert_start"]) != canon(row["accepted_snapshot_start_at"]) or canon(s["alert_end"]) != canon(row["accepted_snapshot_end_at"])
        precise += int(precision_loss)
        require(row["source_vs_snapshot_clock"] ==
                ("SUBMILLISECOND_SOURCE_PRECISION_NOT_IN_SNAPSHOT_PROJECTION" if precision_loss else "MILLISECOND_REPRESENTATION_AGREES"),
                "timestamp precision claim mismatch")
        require(row["historical_parent_row_uuid"] is None and row["historical_parent_row_binding"] in ALLOWED
                and row["individual_decision"] in ALLOWED, "prohibited parent assertion")
        require(row["snapshot_exact_parent_uid_matches"] == 0 and
                row["snapshot_exact_parent_city_interval_matches"] == 0, "snapshot mismatch")
        require(row["permanent_historical_unbound_exception"] == "NOT_ACCEPTED" and
                row["unbound_storage_under_zero_eligible_parents"] == "CONDITIONALLY_PERMITTED",
                "unauthorized exception")
        require(row["contradiction"] == "NOT_ESTABLISHED", "unsupported contradiction")
        require(row["missing_evidence"] and row["reason"] and row["next_action"], "incomplete decision")
    summary = data["summary"]
    for key, value in {"original_identities":25,"h1":5,"h2":20,"historical_source_episode_found":25,
                       "canonical_parent_uuid_proven":0,"parent_binding_approved":0,"individual_not_proven":25,
                       "source_time_precision_mismatch_in_snapshot_projection":precise,
                       "affirmative_contradictions":0,"auto_bindings_allowed":0,
                       "c4":"NOT_PROVEN","neon_writes":0,"production_writes":0}.items():
        require(summary[key] == value, "summary mismatch: "+key)
    return {"status":"PASS", "identities":25, "original_git_episode_keys":25,
            "kyiv_original_municipal_crosswalks":18, "submillisecond_precision_gaps":precise,
            "historical_parent_uuid_proven":0, "unresolved":25}


def mutation_controls(data):
    tests = []
    def mutated(name, fn):
        o = copy.deepcopy(data)
        fn(o)
        try:
            verify(o, data)
        except (AssertionError, ValueError, KeyError, IndexError):
            tests.append(name)
            return
        raise AssertionError("mutation escaped verifier: "+name)
    mutated("removed_record", lambda d:d["decisions"].pop())
    mutated("duplicate_record", lambda d:d["decisions"].append(copy.deepcopy(d["decisions"][-1])))
    mutated("wrong_classification_uid",lambda d:d["decisions"][0].update(classification_uid="forged"))
    mutated("wrong_classification_key",lambda d:d["decisions"][0].update(classification_key="forged"))
    mutated("wrong_episode_id",lambda d:d["decisions"][0].update(episode_id="0"*24))
    mutated("wrong_clock",lambda d:d["decisions"][0].update(original_alert_start_at="2026-09-13T02:32:15Z"))
    mutated("naive_clock",lambda d:d["decisions"][0].update(original_alert_start_at="2026-09-13T02:32:14"))
    mutated("wrong_source_blob",lambda d:d["sources"][0].update(blob="0"*40))
    mutated("wrong_source_commit",lambda d:d["sources"][0].update(commit="0"*40))
    mutated("wrong_source_index",lambda d:d["decisions"][0].update(source_episode_index=0))
    mutated("fuzzy_parent",lambda d:d["decisions"][0].update(historical_parent_row_binding="BOUND"))
    mutated("invented_parent_uuid",lambda d:d["decisions"][0].update(historical_parent_row_uuid="fake-uuid"))
    mutated("false_exception",lambda d:d["decisions"][0].update(permanent_historical_unbound_exception="ACCEPTED"))
    mutated("fake_contradiction",lambda d:d["decisions"][0].update(contradiction="PROVEN"))
    mutated("missing_reason",lambda d:d["decisions"][0].update(reason=""))
    mutated("fake_proof_pin",lambda d:d["frozen_unbound_proof"].update(blob="0"*40))
    mutated("fake_summary",lambda d:d["summary"].update(canonical_parent_uuid_proven=1))
    return tests


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--negative-tests", action="store_true")
    args=parser.parse_args()
    data=json.loads(REGISTRY.read_text(encoding="utf-8"))
    receipt=verify(data,data)
    if args.negative_tests:
        receipt["mutation_controls_rejected"]=mutation_controls(data)
        require(len(receipt["mutation_controls_rejected"]) == 17, "negative coverage missing")
    print(json.dumps(receipt,sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
