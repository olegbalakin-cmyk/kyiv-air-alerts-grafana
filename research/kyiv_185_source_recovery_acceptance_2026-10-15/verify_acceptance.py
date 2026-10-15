#!/usr/bin/env python3
"""Independent, offline/Git-only Kyiv 185 historical source acceptance.

Only immutable Git data and GitHub Actions run/artifact/log APIs are used.
No production collectors, publishers, Neon, Netlify or classifiers.
"""
import collections
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile

REPO = "olegbalakin-cmyk/kyiv-air-alerts-grafana"
MAIN = "d425c3475565b4db1c36c472ab967b3283811d43"
PROD = "97ec99389259f8d0cfcecc17a2ff77302bb0615f"
WIP = "567c0aab3aaf98a5b8dd788021a26ece41f083e3"
PRIOR = "e55246eacc5044f5d75ff138a78fe3e01331beea"
ORIGINAL_ZIP = "8db33e580f6e88c5a7aaa6eb327a8c87c2ec9c5d90b1cb81472528a91ae75f50"
MANIFEST_ZIP = "0d10cceb48b6266a67faab90bad27201b7be8537bb244d7008824ffc3227e486"
MANIFEST_SHA = "54ce8c9800739b294a83991f71130ab3c6096742ed861b469c1df2ecf2ec9d76"
PRIOR_LEDGER_SHA = "c007f81f10a242e3a3ee3eb2696d03a11369861b8cb797ca505142449bbe8645"
PREVIOUS_LEDGER_PATH = "research/wip_209_independent_lineage_2026-10-15/kyiv_185_source_time_lineage_2026-10-15.json"
SOURCE = "kyiv-air-alerts-grafana/data/alerts_combined.json"
STATE = "kyiv-air-alerts-grafana/data/explosion_candidate_monitor_state.json"
WORKFLOW = ".github/workflows/explosion-monitor-wip.yml"
OUT = Path("research/kyiv_185_source_recovery_acceptance_2026-10-15")
PROOF_ROOT = "kyiv-185-proof/a/"
EVID_ROOT = "kyiv-185-producer-evidence/"
ORIGINALS = {
    "kyiv_185_original_source_recovery_ledger.json": "1391cdbc2688a08a5caa06ee4735f6d56ace7553b7183b4130314c6758770127",
    "historical_source_revision_inventory.json": "5eb740f8277a946b1e5cf8814b6db94451c1df7845629d2299929b88508f625e",
    "provenance_reconciliation_report.json": "864c25ea1485b086cdf232210103af179c97d9e785d0982b89351a6c2b25681a",
    "frozen_safety_and_reproducibility.json": "d4dcf1123872cc547fcd44d06c1d622cd344bc31e7c2a515d6b2c107fa904394",
    "result_hashes.json": "2992511fd86bc4e9bc0603db40714698ab05a2a5958c694e00f2e820f5bd5baf",
    "producer_evidence.json": "953194bb53dcf4dfa1e929e657c65db75fb78821a7bd6c7af418097d5422d529",
}
SAMPLE = {
    35481398674: ("639cf3c24b5e87afe53a3838bca5f0a73acebfad", 13),
    35491668099: ("89f70c1cbf59b4b3c1677003d87f6ab47f46a610", 1),
    36322442545: ("1bacbc46302f44a79bd0c6125816c3451772daa1", 20),
    37197458169: ("a5756040c796dc4c7d67b0b3e2c7acd17f6006b5", 7),
    37224221816: ("c06f032bacd96928881bf3b9dd12d6c204291043", 5),
}
START_CUTOFF = "2026-09-18T00:00:00Z"
RUN_CUTOFF = "2026-10-15T11:56:48Z"
cache = {}

def digest(data):
    return hashlib.sha256(data).hexdigest()

def check(value, message):
    if not value:
        raise AssertionError(message)

def git(*args):
    p = subprocess.run(["git", *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.stdout

def at(ref, path):
    return git("show", ref + ":" + path)

def object_sha(ref, path):
    return git("rev-parse", ref + ":" + path).decode().strip()

def blob_content(sha):
    if sha not in cache:
        cache[sha] = git("cat-file", "blob", sha)
    return cache[sha]

def decoded_at(ref, path, expected_blob=None):
    sha = object_sha(ref, path)
    if expected_blob:
        check(sha == expected_blob, "Git path blob differs: " + ref + ":" + path)
    return json.loads(blob_content(sha))

def emit_json(path, value):
    data = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.write_bytes(data)
    return digest(data)

def ptr(data, pointer):
    item = data
    for tok in pointer.split("/")[1:]:
        tok = tok.replace("~1", "/").replace("~0", "~")
        item = item[int(tok)] if isinstance(item, list) else item[tok]
    return item

def utc(s):
    d = dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
    text = d.isoformat().replace("+00:00", "Z")
    if d.microsecond == 0:
        text = text.replace(".000000Z", "Z")
    return text

def event_id(times):
    return hashlib.sha256(("kyiv|" + times[0] + "|" + times[1]).encode("utf-8")).hexdigest()[:24]

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def github(path):
    req = urllib.request.Request(
        "https://api.github.com/repos/" + REPO + path,
        headers={"Authorization": "Bearer " + os.environ["GH_TOKEN"],
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "kyiv185-independent-source-acceptance"})
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=60) as res:
            return res.read()
    except urllib.error.HTTPError as e:
        if e.code not in (301, 302, 303, 307, 308):
            raise RuntimeError("GitHub API failure " + path + " HTTP " + str(e.code))
        url = e.headers.get("Location", "")
        check(url.startswith("https://"), "Unsafe GitHub artifact/log redirect")
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "kyiv185-audit"}), timeout=90) as res:
            return res.read()

def artifact(id_number, expected_hash):
    raw = github("/actions/artifacts/" + str(id_number) + "/zip")
    check(digest(raw) == expected_hash, "Original ZIP digest mismatch")
    return zipfile.ZipFile(__import__("io").BytesIO(raw))

def current_workflow_runs():
    rows = []
    for page in range(1, 8):
        encoded = urllib.parse.urlencode({
            "per_page": 100, "page": page, "created": "2026-09-18..2026-10-15"})
        result = json.loads(github("/actions/workflows/explosion-monitor-wip.yml/runs?" + encoded))
        subset = result.get("workflow_runs", [])
        rows.extend(x for x in subset if START_CUTOFF <= x["created_at"] <= RUN_CUTOFF)
        if len(subset) < 100:
            break
    return {x["id"]: x for x in rows}

def build():
    # Check exact frozen parent and immutable historical commits are Git-resolvable.
    for ref in [MAIN, PROD, WIP, PRIOR]:
        git("cat-file", "-e", ref + "^{commit}")
    zip1 = artifact(11970440256, ORIGINAL_ZIP)
    expected_names = {PROOF_ROOT + name for name in ORIGINALS if name != "producer_evidence.json"}
    expected_names.add(EVID_ROOT + "producer_evidence.json")
    check(set(zip1.namelist()) == expected_names, "Unexpected or absent producer archive member")
    check(zip1.testzip() is None, "Original ZIP CRC failure")
    originals = {}
    for name, expected in ORIGINALS.items():
        prefix = EVID_ROOT if name == "producer_evidence.json" else PROOF_ROOT
        data = zip1.read(prefix + name)
        check(digest(data) == expected, "Original evidence JSON sha mismatch: " + name)
        originals[name] = data
    parsed = {k: json.loads(v) for k, v in originals.items()}
    stored_hashes = parsed["result_hashes.json"]
    for name, info in stored_hashes.items():
        check(name in originals and info["sha256"] == digest(originals[name])
              and info["bytes"] == len(originals[name]), "Original hash inventory contradiction " + name)
    check(len(stored_hashes) == 4, "Unexpected original hash manifest")

    zip2 = artifact(11956428181, MANIFEST_ZIP)
    manifest_members = [x for x in zip2.namelist() if x.endswith("wip_cached_209_identity_manifest_2026-10-15.json")]
    check(len(manifest_members) == 1 and zip2.testzip() is None, "Manifest archive or CRC failure")
    manifest_raw = zip2.read(manifest_members[0])
    check(digest(manifest_raw) == MANIFEST_SHA, "Original manifest bytes mismatch")
    manifest = json.loads(manifest_raw)
    check(manifest["count"] == 209 and len(manifest["rows"]) == 209, "Invalid original 209 population")
    mrows = {r["original_episode_id"]: r for r in manifest["rows"] if r["city"] == "kyiv"}
    check(len(mrows) == 185, "Original manifest Kyiv population not 185")

    prior_raw = at(PRIOR, PREVIOUS_LEDGER_PATH)
    check(digest(prior_raw) == PRIOR_LEDGER_SHA, "Frozen predecessor lineage digest mismatch")
    prior = json.loads(prior_raw)
    prow = {r["original_episode_id"]: r for r in prior["rows"]}
    check(len(prow) == 185, "Original prior 185 lineage cardinality failed")
    records = parsed["kyiv_185_original_source_recovery_ledger.json"]["rows"]
    check(len(records) == 185, "Recovery ledger count failed")
    rows = {r["original_episode_id"]: r for r in records}
    check(len(rows) == 185 and set(rows) == set(mrows) == set(prow),
          "185 Kyiv IDs not equal to frozen manifest and predecessor")

    original_state = decoded_at(WIP, STATE, manifest["source_blobs"]["wip:explosion_candidate_monitor_state.json"])
    for id_number, rec in rows.items():
        m = mrows[id_number]
        p = prow[id_number]
        times = rec["original_times_exact_utc"]
        check([m["original_alert_start_exact"], m["original_alert_end_exact"]] == times,
              "Original manifest timestamp mismatch " + id_number)
        check(p["original_times_exact"] == times, "Prior 185 lineage timestamp mismatch " + id_number)
        check(event_id(times) == id_number and m["hash_contract"]["original_id"] == id_number,
              "Original episode SHA-256 ID mismatch " + id_number)
        first = p["first_persisted_git"]
        check(rec["first_wip_commit"] == first["commit"] and
              rec["original_wip_state_blob"] == first["state_blob"] and
              rec["original_wip_state_pointer"] == first["json_pointer"],
              "Original first-persistence pointer changed " + id_number)
        cp = m["original_git_location"]["json_pointer"]
        original_episode = ptr(original_state, cp)
        check(original_episode["episode_id"] == id_number and
              [original_episode["alert_start"], original_episode["alert_end"]] == times,
              "WIP original frozen observation changed " + id_number)
        first_state = decoded_at(first["commit"], STATE, first["state_blob"])
        exact = ptr(first_state, first["json_pointer"])
        check(exact["episode_id"] == id_number and
              [exact["alert_start"], exact["alert_end"]] == times,
              "First persistence WIP Git pointer invalid " + id_number)
        check(rec["runtime_input_git_sha_independently_pinned"] is False and
              rec["historical_to_modern_equivalence"] == "UNRESOLVED",
              "An unsupported runtime or modern identity promotion exists")

    # Independent source history: do not assume selected version is the runtime SHA.
    sha_list = git("log", "--first-parent", "--format=%H", PROD, "--", SOURCE).decode().splitlines()
    check(len(sha_list) == 118, "Historical source revision count changed")
    versions = []
    unique_blobs = {}
    for commit in sha_list:
        b = object_sha(commit, SOURCE)
        t = git("show", "-s", "--format=%cI", commit).decode().strip()
        versions.append({"commit": commit, "blob": b, "time": dt.datetime.fromisoformat(t)})
        unique_blobs[b] = commit
    pair_indexes = {}
    def source_index(b):
        if b not in pair_indexes:
            data = json.loads(blob_content(b))
            check(isinstance(data, list), "Source blob is not JSON list")
            lookup = collections.defaultdict(list)
            for i, item in enumerate(data):
                try:
                    times = (utc(item["start"]), utc(item["end"]))
                    if dt.datetime.fromisoformat(times[1].replace("Z", "+00:00")) > dt.datetime.fromisoformat(times[0].replace("Z", "+00:00")):
                        lookup[times].append(i)
                except (KeyError, ValueError, TypeError, AttributeError):
                    pass
            pair_indexes[b] = (data, lookup)
        return pair_indexes[b]

    evidence = parsed["producer_evidence.json"]
    check(len(evidence) == 150 and len({r["job_id"] for r in evidence}) == 150,
          "Producer successful jobs count/uniqueness mismatch")
    check(all(r["job_conclusion"] == "success" and r["run_conclusion"] == "success" for r in evidence),
          "Non-success producer in receipt set")
    check(sum(len(r.get("produced_short_ids", [])) for r in evidence) == 168,
          "Producer output commit prefix accounting mismatch")
    api_runs = current_workflow_runs()
    check(len(api_runs) == 172, "Independent GitHub API count is not 172, found " + str(len(api_runs)))
    check(all(r["run_id"] in api_runs for r in evidence),
          "Producer success job absent in bounded original workflow run set")
    groups = collections.defaultdict(list)
    for id_number, r in rows.items():
        groups[r["first_wip_commit"]].append(r)
    inventory = parsed["historical_source_revision_inventory.json"]
    groups_inv = {v["first_wip_commit"]: v for v in inventory["producer_runs"]}
    check(len(groups) == len(groups_inv) == 82 and set(groups) == set(groups_inv),
          "First-persistence WIP group population mismatch")
    check(len(inventory["unique_historical_source_blobs_selected"]) == 78,
          "Unique historical source blob count mismatch")
    disposition = collections.Counter()
    normalized = []
    missing = []
    for commit, group in sorted(groups.items()):
        inv = groups_inv[commit]
        rec_ids = sorted(r["original_episode_id"] for r in group)
        check(rec_ids == inv["first_persisted_ids"], "Inventory WIP groups disagree")
        producers = [p for p in evidence
                     if any(commit.startswith(short) for short in p.get("produced_short_ids", []))]
        if len(producers) != 1 or inv["producer_run_id"] is None:
            check(inv["producer_run_id"] is None and inv["producer_job_id"] is None,
                  "Ambiguous or missing job incorrectly attached to WIP group")
            eligible = None
            run = None
        else:
            run = producers[0]
            check(inv["producer_run_id"] == run["run_id"] and inv["producer_job_id"] == run["job_id"],
                  "Producer run/job reference is inconsistent")
            check(run["runtime_source_path_and_cli_confirmed"] and
                  run["runtime_site_prod_sha_logged"] is None and
                  inv["runtime_site_prod_sha_pin"] is None,
                  "Unjustified producer input SHA pin or source path")
            check(run["runtime_kyiv_row_count"] is not None and run["source_fetch_completed"],
                  "Producer fetch details missing")
            script = at(run["run_head_sha"], WORKFLOW).decode("utf-8")
            check("git show origin/site-prod:" + SOURCE in script and
                  "--kyiv-alerts-file /tmp/prod-kyiv-alerts.json" in script,
                  "Workflow at producer execution head did not read site-prod")
            check(inv["producer_workflow_blob"] == object_sha(run["run_head_sha"], WORKFLOW),
                  "Producer workflow Git blob identity invalid")
            at_time = dt.datetime.fromisoformat(run["source_fetch_completed"].replace("Z", "+00:00"))
            candidates = []
            before = [v for v in versions if v["time"] <= at_time]
            for ver in before:
                data, ix = source_index(ver["blob"])
                if len(data) != run["runtime_kyiv_row_count"]:
                    continue
                if all(len(ix.get(tuple(r["original_times_exact_utc"]), [])) == 1 for r in group):
                    candidates.append(ver)
            check(candidates, "No historical source version independently corroborates group " + commit)
            eligible = candidates[0]
            check(before and eligible["blob"] == before[0]["blob"],
                  "Newer historical source contradicts selected record " + commit)
            check(eligible["commit"] == inv["candidate_source_commit"] and
                  eligible["blob"] == inv["candidate_source_blob"],
                  "Independent timing/pair/row-count source reconstruction differs")
        for row in group:
            id_number = row["original_episode_id"]
            source_observations = row["historical_source_records"]
            if run is None:
                check(not source_observations and row["producer_run_id"] is None and
                      row["source_disposition"] == "PRODUCER_RUNTIME_EVIDENCE_UNAVAILABLE",
                      "Seven-case unavailable producer disposition inconsistent")
                historical_candidates = []
                # Exhaust all 118 Git preserved first-parent historical production revisions.
                for ver in versions:
                    data, ix = source_index(ver["blob"])
                    indexes = ix.get(tuple(row["original_times_exact_utc"]), [])
                    for idx in indexes:
                        historical_candidates.append({"git_commit": ver["commit"],
                                                      "git_blob": ver["blob"],
                                                      "json_pointer": "/" + str(idx)})
                availability = ("EXACT_SOURCE_RECORD_EXISTS_IN_HISTORICAL_GIT_UNPINNED"
                                if historical_candidates else
                                "NO_EXACT_RECORD_IN_118_HISTORICAL_SITE_PROD_REVISIONS")
                missing.append({
                    "original_episode_id": id_number,
                    "exact_start_utc": row["original_times_exact_utc"][0],
                    "exact_end_utc": row["original_times_exact_utc"][1],
                    "first_wip_commit": commit,
                    "first_wip_state_blob": row["original_wip_state_blob"],
                    "first_wip_state_pointer": row["original_wip_state_pointer"],
                    "producer_run_id": None,
                    "producer_job_id": None,
                    "historical_source_candidates": historical_candidates,
                    "historical_source_record_status": availability,
                    "git_evidence_searched": {"site_prod_source_revision_count": len(versions),
                                              "first_persistence_state_checked": True,
                                              "producer_evidence_jobs": len(evidence)},
                    "missing_proof_element": "No uniquely attributable successful historical WIP producer runtime receipt for first-persistence group; exact production runtime Git input cannot be assigned",
                    "not_missing_real_world_alert_assertion": True,
                    "next_narrow_opportunity": "Search existing immutable first-persistence Actions job/commit logs for an attributable site-prod source SHA receipt; do not replay external sources or synthesize alerts",
                })
                disposition["PRODUCER_RUNTIME_EVIDENCE_UNAVAILABLE"] += 1
            else:
                check(len(source_observations) == 1 and row["producer_run_id"] == run["run_id"] and
                      row["producer_job_id"] == run["job_id"],
                      "Recovered source or Actions producer identity mismatch")
                original = source_observations[0]
                check(original["git_commit"] == eligible["commit"] and
                      original["git_blob"] == eligible["blob"],
                      "Recovered historical Git source revision mismatch")
                check(object_sha(original["git_commit"], SOURCE) == original["git_blob"],
                      "Referenced historical Git blob SHA mismatch")
                data, ix = source_index(original["git_blob"])
                idxs = ix.get(tuple(row["original_times_exact_utc"]), [])
                check(len(idxs) == 1 and original["json_pointer"] == "/" + str(idxs[0]),
                      "Historical JSON pointer not independently confirmed")
                sr = ptr(data, original["json_pointer"])
                check([utc(sr["start"]), utc(sr["end"])] == row["original_times_exact_utc"] and
                      original["source_fields"] == {k: sr.get(k) for k in ("start", "end", "duration_minutes", "source")},
                      "Historical source fields/times inconsistent")
                check(row["source_disposition"] == "EXACT_HISTORICAL_INPUT_FOUND_RUNTIME_PIN_UNPROVEN",
                      "Recovered episode disposition overclaims runtime evidence")
                disposition["EXACT_HISTORICAL_INPUT_FOUND_RUNTIME_PIN_UNPROVEN"] += 1
            normalized.append({
                "original_episode_id": id_number,
                "first_wip_commit": commit,
                "first_wip_state_blob": row["original_wip_state_blob"],
                "first_wip_state_pointer": row["original_wip_state_pointer"],
                "original_times_exact_utc": row["original_times_exact_utc"],
                "source_disposition": row["source_disposition"],
                "source_records": source_observations,
                "candidate_runtime_source_sha": row["candidate_runtime_site_prod_commit"],
                "producer_run_id": row["producer_run_id"],
                "producer_job_id": row["producer_job_id"],
                "producer_job_url": inv.get("producer_job_url"),
                "producer_workflow_head": inv.get("producer_run_workflow_head"),
                "runtime_sha_pinned": False,
                "historical_to_current_identity": "UNRESOLVED",
            })
    check(dict(disposition) == {
        "EXACT_HISTORICAL_INPUT_FOUND_RUNTIME_PIN_UNPROVEN": 178,
        "PRODUCER_RUNTIME_EVIDENCE_UNAVAILABLE": 7}, "Independently derived 178/7 mismatch")
    check(len(missing) == 7, "Seven unresolved case population mismatch")
    check(sum(bool(r["historical_source_records"]) for r in rows.values()) == 178,
          "Source-record proof cardinality incorrect")

    # All five predecessor samples, checked against separately pinned historical blobs.
    sample_results = {}
    for run_id, (source_commit, cardinality) in SAMPLE.items():
        matched = [r for r in rows.values() if r["producer_run_id"] == run_id]
        check(len(matched) == cardinality, "Five-group row count mismatch " + str(run_id))
        expect_blob = object_sha(source_commit, SOURCE)
        sr, idx = source_index(expect_blob)
        check(all(len(idx.get(tuple(r["original_times_exact_utc"]), [])) == 1 for r in matched),
              "Original five-group exact source match mismatch " + str(run_id))
        check(all(r["historical_source_records"][0]["git_blob"] == expect_blob for r in matched),
              "Five-group source Git blob mismatch")
        inventory_sample = inventory["sample_groups"][str(run_id)]
        check(inventory_sample["expected_site_prod_commit"] == source_commit and
              inventory_sample["observed_source_blob"] == expect_blob and
              inventory_sample["exact_pair_matches"] == cardinality,
              "Original sample reconciliation file conflicts")
        sample_results[str(run_id)] = {"exact_matches": cardinality,
                                       "source_commit": source_commit,
                                       "source_blob": expect_blob,
                                       "producer_runtime_sha_pinned": False}

    # Safely verify available original job logs for the five sample producer runs.
    five_log_checks = {}
    for run_id in SAMPLE:
        producer = next(r for r in evidence if r["run_id"] == run_id)
        data = github("/actions/jobs/" + str(producer["job_id"]) + "/logs")
        check(digest(data) == producer["job_log_sha256"],
              "Original Actions job log SHA-256 changed/failed " + str(run_id))
        text = data.decode("utf-8", "replace")
        check("git show origin/site-prod:" + SOURCE in text and
              "--kyiv-alerts-file /tmp/prod-kyiv-alerts.json" in text,
              "Five sample producer logs omit site-prod input evidence")
        five_log_checks[str(run_id)] = {"job_id": producer["job_id"],
                                        "sha256": digest(data), "job_url": producer["job_url"]}
    for data in originals.values():
        check(not re.search(rb"(?:ghp_[0-9A-Za-z]{20,}|github_pat_[0-9A-Za-z_]{20,}|Authorization:\s*Bearer\s+[0-9A-Za-z._-]{20,})", data, re.I),
              "Potential credential in original JSON: refuses Git preservation")
    check(all(r["runtime_input_git_sha_independently_pinned"] is False for r in rows.values()),
          "Any runtime input SHA pinned unexpectedly")
    check(all(r["historical_to_modern_equivalence"] == "UNRESOLVED" for r in rows.values()),
          "Any modern identity transfer unexpectedly accepted")
    check(parsed["provenance_reconciliation_report.json"]["historical_exact_source_observations_found"] == 178,
          "Original summary inconsistent with reconstruction")
    check(parsed["frozen_safety_and_reproducibility.json"]["wip_activation"] == "NO-GO",
          "Original no-activation scope absent")
    # No historical, production, or WIP path touched: all write files are under OUT.
    OUT.mkdir(parents=True, exist_ok=True)
    for name, data in originals.items():
        (OUT / name).write_bytes(data)
    missing.sort(key=lambda r: r["original_episode_id"])
    normalized.sort(key=lambda r: r["original_episode_id"])
    missing_hash = emit_json(OUT / "seven_unresolved_cases.json", {
        "scope": "seven producer-evidence gaps; not a statement that real alerts were absent",
        "count": len(missing), "cases": missing})
    index_hash = emit_json(OUT / "source_producer_evidence_index.json", {
        "scope": "source record and producer evidence only; no current-ID compatibility",
        "count": len(normalized), "rows": normalized})
    receipt = {
        "verdict": "PASS",
        "bounded_acceptance": "KYIV 185 HISTORICAL SITE-PROD INPUT RECOVERY = PARTIAL — ACCEPTED",
        "original_zip_sha256": ORIGINAL_ZIP,
        "original_209_manifest_zip_sha256": MANIFEST_ZIP,
        "original_209_manifest_sha256": MANIFEST_SHA,
        "predecessor_lineage_sha256": PRIOR_LEDGER_SHA,
        "frozen_refs": {"main_preflight": MAIN, "site_prod_comparator": PROD,
                        "wip_original": WIP, "lineage_proof": PRIOR},
        "all_185_original_ids_manifest_equal": True,
        "exact_historical_source_matches": 178,
        "producer_evidence_gaps": 7,
        "producer_first_wip_groups": 82,
        "original_producer_runs_inspected": len(api_runs),
        "successful_producer_jobs": len(evidence),
        "producer_commit_prefixes": sum(len(x.get("produced_short_ids", [])) for x in evidence),
        "historical_production_source_revisions": len(versions),
        "selected_historical_source_blobs": len(inventory["unique_historical_source_blobs_selected"]),
        "runtime_git_sha_pins": 0,
        "modern_id_equivalence_proven": 0,
        "five_historical_groups": sample_results,
        "five_producer_job_logs_verified": five_log_checks,
        "unresolved_source_status_counts": dict(collections.Counter(x["historical_source_record_status"] for x in missing)),
        "source_family_or_city_grain_promotions": 0,
        "review_or_classification_transfers": 0,
        "production_or_wip_writes": 0,
        "ukrainealarm_requests": 0,
        "publisher_requests": 0,
        "neon_connections_or_writes": 0,
        "wip_activation": "NO-GO",
        "original_evidence_sha256": ORIGINALS,
        "seven_unresolved_register_sha256": missing_hash,
        "normalized_evidence_index_sha256": index_hash,
        "github_actions_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_actions_run_url": "https://github.com/" + REPO + "/actions/runs/" + os.environ.get("GITHUB_RUN_ID", ""),
    }
    emit_json(OUT / "independent_acceptance_receipt.json", receipt)
    print(json.dumps({"decision": receipt["verdict"], "source_matches": 178, "missing": 7,
                      "runtime_sha_pins": 0, "modern_identity": 0, "producer_runs": len(api_runs),
                      "seven_source_status": receipt["unresolved_source_status_counts"]}, indent=2))

def readback():
    check((OUT / "independent_acceptance_receipt.json").exists(), "Acceptance not frozen in Git")
    original = json.loads((OUT / "independent_acceptance_receipt.json").read_bytes())
    check(original["verdict"] == "PASS", "Acceptance receipt not PASS")
    for name, h in ORIGINALS.items():
        check(digest(at("HEAD", str(OUT / name))) == h, "Git committed original hash differs " + name)
        check((OUT / name).read_bytes() == at("HEAD", str(OUT / name)),
              "Original bytes altered in checkout " + name)
    for name, field in [
        ("seven_unresolved_cases.json", "seven_unresolved_register_sha256"),
        ("source_producer_evidence_index.json", "normalized_evidence_index_sha256")]:
        gitdata = at("HEAD", str(OUT / name))
        check(digest(gitdata) == original[field], "Git derivative checksum mismatch " + name)
        check(gitdata == (OUT / name).read_bytes(), "Readback mismatch " + name)
    data = at("HEAD", str(OUT / "independent_acceptance_receipt.json"))
    check(digest(data) == digest((OUT / "independent_acceptance_receipt.json").read_bytes()),
          "Final independent receipt read-back mismatch")
    register = json.loads(at("HEAD", str(OUT / "seven_unresolved_cases.json")))
    idx = json.loads(at("HEAD", str(OUT / "source_producer_evidence_index.json")))
    check(register["count"] == len(register["cases"]) == 7 and
          idx["count"] == len(idx["rows"]) == 185, "Frozen register/index row counts wrong")
    changed = git("diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").decode().splitlines()
    check(all(name.startswith(str(OUT) + "/") for name in changed),
          "Evidence freeze commit changed any operational, review or upstream paths: " + str(changed))
    print("IMMUTABLE_GIT_READBACK PASS; original six JSON byte-for-byte; derivatives and receipt verified")
    print("FREEZE_COMMIT", git("rev-parse", "HEAD").decode().strip())
    for name in list(ORIGINALS) + ["seven_unresolved_cases.json", "source_producer_evidence_index.json", "independent_acceptance_receipt.json"]:
        print("GIT_BLOB", name, object_sha("HEAD", str(OUT / name)))

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("verify", "readback"):
        sys.exit("Usage: verify_acceptance.py verify|readback")
    if sys.argv[1] == "verify":
        build()
    else:
        readback()
