#!/usr/bin/env python3
"""Independent immutable-Git C4 parent-writer adjudication checker; no Neon access."""
import copy
import datetime as dt
import hashlib
import json
import pathlib
import subprocess
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent
REGISTRY = HERE / "registry.json"
SHA_RE = __import__("re").compile(r"^[0-9a-f]{40}$")

def require(ok, message):
    if not ok:
        raise AssertionError(message)

def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], stderr=subprocess.PIPE)

def pinned(source):
    sha, path, blob = source["commit"], source["path"], source["blob"]
    require(bool(SHA_RE.fullmatch(sha) and SHA_RE.fullmatch(blob)), "invalid Git SHA")
    require(git("rev-parse", sha + ":" + path).decode().strip() == blob, "Git blob pin mismatch: " + path)
    return git("cat-file", "blob", blob)

def utc(s):
    value = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    require(value.tzinfo is not None, "naive timestamp")
    return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")

def key(city, start, end):
    return hashlib.sha256((city + "|" + utc(start) + "|" + utc(end)).encode()).hexdigest()[:24]

def check(d):
    src = d["sources"]
    required = {"accepted_registry", "frozen_cohort", "phase1_migration", "canonical_core",
                "multicity_payload", "multicity_writer", "kyiv_producer", "kyiv_producer_output",
                "multicity_source", "phase1_lviv", "lviv_pre_repair_readback", "lviv_repair_plan",
                "permanent_lviv_repair", "permanent_multicity"}
    require(set(src) == required, "unexpected or missing evidence source")
    for s in src.values():
        pinned(s)
    original = json.loads(pinned(src["accepted_registry"]))["decisions"]
    require(len(original) == len(d["records"]) == 25, "25 case cardinality")
    proof = json.loads(pinned(src["permanent_multicity"]))
    require(proof["bootstrap"]["run"] == d["historical_writer_contract"]["multicity"]["bootstrap_run"], "bootstrap run mismatch")
    require(proof["bootstrap"]["parents"] == 27966 and proof["bootstrap"]["inserted"] == 27840
            and proof["bootstrap"]["existing"] == 126, "bootstrap provenance mismatch")
    lviv_old = json.loads(pinned(src["lviv_pre_repair_readback"]))["lviv_compatibility"]["mismatches"]
    lviv = json.loads(pinned(src["lviv_repair_plan"]))["repair_plan"]
    permanent = json.loads(pinned(src["permanent_lviv_repair"]))["permanent_lviv_repair"]["repaired_episode_uid_to_legacy_episode_id"]
    producer = json.loads(pinned(src["kyiv_producer_output"]))
    require(isinstance(producer, list), "Kyiv producer expected list")
    producer_pairs = {(utc(row["start"]), utc(row["end"])) for row in producer}
    require(len(d["actions"]) == 5, "Actions witnesses count")
    proven = 0
    materialized = 0
    counts = Counter()
    for index, (row, prior) in enumerate(zip(d["records"], original), 1):
        require(row["ordinal"] == index, "ordinal drift")
        require(row["classification_uid"] == prior["classification_uid"], "classification UID drift")
        require(row["classification_key"] == prior["classification_key"], "classification key drift")
        require(row["city"] == prior["city"] and row["cohort"] == prior["cohort"], "cohort/city drift")
        require(row["historical_source_id"] == prior["original_episode_id"], "original source ID drift")
        require(row["deterministic_original_id"] == prior["episode_id"], "canonical ID drift")
        require(row["original_start_at"] == prior["original_alert_start_at"]
                and row["original_end_at"] == prior["original_alert_end_at"], "original clock drift")
        require(key(row["city"], row["original_start_at"], row["original_end_at"]) == row["deterministic_original_id"],
                "canonical SHA24 rule mismatch")
        w = row["source_witness"]
        for field, sourcefield in (("commit", "source_git_commit"), ("blob", "source_git_blob"),
                                   ("path", "source_path"), ("index", "source_episode_index")):
            require(w[field] == prior[sourcefield], "historical source-witness drift")
        require(row["case_end_before_permanent_bootstrap"] is True, "writer interval not established")
        require(row["required_parent_contract"] == {"alert_type":"AIR","episode_state":"closed",
                "canonicalization_version":"alert-canonicalization-v1","exact_original_interval":True}, "eligibility contract drift")
        require(row["current_eligible_exact_original_parent_uid"] is None
                and row["parent_binding_approved"] is False
                and row["permanent_unbound_exception_accepted"] is False, "unproven parent binding/exception")
        if row["city"] == "lviv":
            matched = [x for x in lviv_old if x["neon"]["legacy_episode_id"] == row["deterministic_original_id"]
                       and x["neon"]["start_at"] == row["original_start_at"]
                       and x["neon"]["end_at"] == row["original_end_at"]]
            require(len(matched) == 1, "no exact pre-repair Lviv parent")
            uid = matched[0]["neon"]["episode_uid"]
            repair = [x for x in lviv if x["episode_uid"] == uid]
            require(len(repair) == 1 and repair[0]["old"]["start_at"] == row["original_start_at"]
                    and repair[0]["old"]["end_at"] == row["original_end_at"], "repair old-interval mismatch")
            require(permanent.get(uid) == repair[0]["new"]["legacy_episode_id"], "permanent Neon repair not evidenced")
            require(uid == row["historical_physical_parent_uid"], "historical physical UID mismatch")
            require(row["cause"] == "HISTORICAL_PARENT_MATERIALIZED_THEN_IDENTITY_SUPERSEDED"
                    and row["cause_proven"] is True, "Lviv materialization decision drift")
            materialized += 1
            proven += 1
        elif row["city"] == "kyiv":
            require((utc(row["original_start_at"]), utc(row["original_end_at"])) not in producer_pairs,
                    "Kyiv exact original interval actually present in Oct1 producer")
            require(row["historical_physical_parent_uid"] is None
                    and row["cause"] == "CONFIRMED_ORIGINAL_VS_WRITER_TIMESTAMP_IDENTITY_MISMATCH"
                    and row["cause_proven"] is True, "Kyiv mismatch or false parent")
            require(row["writer_exact_old_identity"] == "ABSENT_FROM_PROVEN_OCT1_PRODUCER_OUTPUT",
                    "writer input coverage overstated")
            proven += 1
        else:
            require(row["historical_physical_parent_uid"] is None
                    and row["cause"] == "NOT_PROVEN" and row["cause_proven"] is False,
                    "unproven cause promoted")
        counts[row["city"]] += 1
    require(counts == {"lviv":3,"sumy":1,"zaporizhzhia":1,"kharkiv":2,"kyiv":18}, "city accounting")
    s = d["summary"]
    require(s["proven_specific_historical_nonmatch_mechanism"] == proven == 21, "21 bounded reasons")
    require(s["proven_historical_physical_parent_uuid"] == materialized == 3, "3 historical materialized parents")
    require(s["cause_not_proven"] == 25-proven == 4, "4 unresolved mechanisms")
    require(s["parent_admissions_unresolved"] == 25 and s["c4"] == "NOT_PROVEN", "C4 false PASS")
    return {"cases":25,"proven_historical_mechanism":proven,"historical_parent_uuids":materialized,
            "root_cause_not_proven":25-proven,"current_parent_admissions_unresolved":25}

def negative_tests(original):
    mutations = [
        lambda d: d["records"].pop(),
        lambda d: d["records"][0].update(classification_uid="00000000-0000-0000-0000-000000000000"),
        lambda d: d["records"][0].update(original_start_at="2026-09-13T02:32:14.172Z"),
        lambda d: d["records"][0].update(historical_physical_parent_uid="bad-uuid"),
        lambda d: d["records"][7].update(current_eligible_exact_original_parent_uid="00000000-0000-0000-0000-000000000000"),
        lambda d: d["records"][7].update(parent_binding_approved=True),
        lambda d: d["records"][4].update(cause="OUTSIDE_WRITER_RANGE",cause_proven=True),
        lambda d: d["sources"]["canonical_core"].update(blob="0"*40),
        lambda d: d["historical_writer_contract"]["multicity"].update(bootstrap_run=1),
        lambda d: d["summary"].update(proven_historical_physical_parent_uuid=25),
    ]
    for idx, tamper in enumerate(mutations, 1):
        candidate = copy.deepcopy(original)
        tamper(candidate)
        try:
            check(candidate)
        except (AssertionError, ValueError, KeyError):
            continue
        raise AssertionError("negative mutation unexpectedly accepted: " + str(idx))
    return len(mutations)

def main():
    data = json.loads(REGISTRY.read_text(encoding="utf8"))
    print(json.dumps({"verify":"PASS",**check(data),"negative_rejections":negative_tests(data)},sort_keys=True))

if __name__ == "__main__":
    main()
