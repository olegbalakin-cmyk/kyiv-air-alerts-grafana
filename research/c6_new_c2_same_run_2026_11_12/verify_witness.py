#!/usr/bin/env python3
"""Fail-closed offline verifier for the separately obtained live-Neon SQL witness."""
import argparse
import datetime
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile

BUNDLE_SHA = "927343c620c1d55438823ad9203a16e986f540a816b35790d496200fe861944f"
MANIFEST_SHA = "5c3e2326eeb98ae6e90234183764525483e64fbc6a203b20dda8deb685d9b501"
C2_RUN = 43262387718
WORKFLOW_SHA = "375e69351e6a5aee1be16892821f7cdde2a8f21a"
INPUT_SHA = "68629fdae5534ec3a136e666bcb7d5c84dcd05aa"
BRANCH = "br-bold-mode-b5rub8pq"
CORPUS_SHA = "a90bf403c6ac1ded943af2bf16b66a407ad9e4e67d2a365691c3704d4cde6e87"

def digest(b):
    return hashlib.sha256(b).hexdigest()

def require(c, label):
    if not c:
        raise ValueError(label)

def dt(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(datetime.timezone.utc)

def normalized(s):
    return dt(s).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

def verify(outer_path, witness_path):
    witness = json.loads(Path(witness_path).read_text())
    require(witness["branch_id"] == BRANCH and witness["project_id"] == "green-cake-44216048", "WRONG_NEON_BRANCH")
    require(witness["stale_inventory_sha"] == "958bc6e679a77d7145d76ab713858f2e2b335319", "STALE_EVIDENCE_DRIFT")
    require(witness["stale_rows"] == 262 and witness["total_rows"] == 33529, "RAW_ROW_COUNT_DRIFT")
    witness_cities = {r["city_key"]: r for r in witness["cities"]}
    require(len(witness_cities) == 23 and witness["canonical_rows"] == 33267, "WITNESS_INCOMPLETE")
    with ZipFile(outer_path) as outer:
        blob = outer.read("c2-shadow-inputs.zip")
        require(digest(blob) == BUNDLE_SHA, "BUNDLE_SHA_MISMATCH")
        require(outer.read("c2-shadow-inputs.zip.sha256").decode().split()[0] == BUNDLE_SHA, "SIDECAR_SHA_MISMATCH")
    with ZipFile(io.BytesIO(blob)) as z:
        require(digest(z.read("manifest.json")) == MANIFEST_SHA, "MANIFEST_SHA_MISMATCH")
        m = json.loads(z.read("manifest.json"))
        for name, sha in m["files"].items():
            require(digest(z.read(name)) == sha, "FILE_SHA_MISMATCH:" + name)
        require((m["github_run_id"], m["github_run_attempt"], m["workflow_sha"], m["input_sha"], m["db_branch"]) ==
            (C2_RUN, 1, WORKFLOW_SHA, INPUT_SHA, BRANCH), "RUN_PROVENANCE_MISMATCH")
        receipt = json.loads(z.read("receipt.json"))
        status = json.loads(z.read("status.json"))
        payload = json.loads(z.read("payload.json"))
        dashboard = json.loads(z.read("site_data/dashboard_data.json"))
        require(receipt["canonical_episode_count"] == 33267 and receipt["corpus_sha256"] == CORPUS_SHA, "C2_CORPUS_RECEIPT_BAD")
        require(receipt["status"] == "succeeded" and receipt["run_id"] == m["canonical_run_id"], "C2_WRITER_RECEIPT_BAD")
        require(status["canonical_persistence_status"] == "NEON_SUCCEEDED" and status["canonical_receipt_validated"] is True, "C2_PERSISTENCE_NOT_CONFIRMED")
        keys = dashboard["multicity_meta"]["production_city_keys"]
        require(len(keys) == 23 and set(keys) == set(payload["cities"]) == set(witness_cities), "CITY_SET_MISMATCH")
        all_episodes = []
        for city in keys:
            block = payload["cities"][city]
            rows = []
            for r in sorted(block["episodes"], key=lambda x: x["legacy_episode_id"]):
                require(r["city_key"] == city and r["alert_type"] == "AIR" and r["episode_state"] == "closed" and r["canonicalization_version"] == "alert-canonicalization-v1", "BAD_EPISODE:" + city)
                require(dt(r["end_at"]) > dt(r["start_at"]), "BAD_INTERVAL:" + city)
                rows.append("|".join((r["legacy_episode_id"], city, r["alert_type"], r["episode_state"],
                    r["canonicalization_version"], normalized(r["start_at"]), normalized(r["end_at"]))))
            require(len(rows) == block["episode_count"], "C2_CITY_COUNT_BAD:" + city)
            require(len(rows) == witness_cities[city]["count"] and digest("\n".join(rows).encode()) == witness_cities[city]["sha256"], "NEON_SEVEN_FIELD_PARITY_BAD:" + city)
            all_episodes.extend(block["episodes"])
        require(len(all_episodes) == 33267 and len({r["legacy_episode_id"] for r in all_episodes}) == 33267, "CANONICAL_ROWS_MISSING_OR_DUPLICATE")
        serial = {"canonicalization_version":"alert-canonicalization-v1","production_city_keys":keys,"episodes":all_episodes}
        require(digest(json.dumps(serial, sort_keys=True, ensure_ascii=False, separators=(",",":"), allow_nan=False).encode()) == CORPUS_SHA, "CANONICAL_CORPUS_SHA_DRIFT")
        captures = payload["historical_source_receipts"]
        require(set(captures) == set(keys), "HISTORY_RECEIPTS_MISSING")
        for city in keys:
            r = captures[city]
            require(r["github_run_id"] == C2_RUN and r["github_run_attempt"] == 1 and r["workflow_sha"] == WORKFLOW_SHA and r["input_sha"] == INPUT_SHA, "HISTORY_RUN_MISMATCH:" + city)
            require(r["continuity_verified"] is True and r["continuity_reason"] == "history_reaches_previous_poll" and r["source_sha256"] and r["pages"], "HISTORY_CONTINUITY_UNPROVEN:" + city)
            require(r["publication_allowed"] is False, "UNEXPECTED_PUBLICATION_GRANT")
        kpi = dashboard["historical_daily_kpi"]["meta"]
        require(kpi["source_dashboard_generated_at"] == dashboard["meta"]["generated_at"] and kpi["verified_count"] == 23 and set(kpi["verified_cities"]) == set(keys), "KPI_GENERATION_DRIFT")
        alerts = json.loads(z.read("site_data/alerts_combined.json"))
        require(len(alerts) == len(payload["cities"]["kyiv"]["episodes"]) == 2857, "KYIV_INTERVALS_MISMATCH")
        require(isinstance(dashboard["casualties"], dict) and isinstance(dashboard["casualties_by_city"], dict), "CASUALTY_METADATA_MISSING")
    return {"NEW_C2_EPISODE_NEON_PARITY":"PASS", "NEW_C2_NEON_JSON_PARITY":"BLOCKED",
        "reason":"New-run physical Neon six-JSON generator has not been executed; this verifies same-run C2 versus live Neon SQL only",
        "c2_run":C2_RUN,"c2_attempt":1,"city_parity":"23/23","episode_parity":"33267/33267",
        "older_superseded_rows_retained":262,"unexplained_differences":0,
        "historical_source_continuity":"23/23","dashboard_kpi_generation":"MATCH",
        "kyiv_intervals":2857,"casualty_auxiliary":"PRESERVED_IN_C2_INPUT",
        "new_neon_six_json":"NOT_GENERATED","production_publication":False,
        "GLOBAL_CUTOVER":"NO","DST_CORRECTION":"OFF"}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact",required=True)
    ap.add_argument("--witness",required=True)
    ap.add_argument("--out",required=True)
    args = ap.parse_args()
    try:
        proof = verify(args.artifact,args.witness)
    except Exception as exc:
        proof = {"NEW_C2_EPISODE_NEON_PARITY":"BLOCKED","NEW_C2_NEON_JSON_PARITY":"BLOCKED",
            "reason":str(exc),"production_publication":False,"GLOBAL_CUTOVER":"NO","DST_CORRECTION":"OFF"}
    path = Path(args.out)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(proof,indent=2,sort_keys=True,ensure_ascii=False)+"\n")
    print(path.read_text())
    print("PROOF_SHA256="+digest(path.read_bytes()))
    if proof["NEW_C2_EPISODE_NEON_PARITY"] != "PASS":
        raise SystemExit(1)
