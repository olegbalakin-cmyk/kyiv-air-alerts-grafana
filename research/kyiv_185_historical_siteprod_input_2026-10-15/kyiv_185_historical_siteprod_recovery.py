#!/usr/bin/env python3
"""Frozen, read-only historical Kyiv producer-input lineage audit.

Only local Git objects and GitHub Actions metadata/job logs are inspected.
No monitor, API collector, database client, or publisher requests are invoked.
"""
import argparse
import collections
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = "olegbalakin-cmyk/kyiv-air-alerts-grafana"
PROD = "97ec99389259f8d0cfcecc17a2ff77302bb0615f"
WIP = "567c0aab3aaf98a5b8dd788021a26ece41f083e3"
MAIN = "d425c3475565b4db1c36c472ab967b3283811d43"
PROOF = "e55246eacc5044f5d75ff138a78fe3e01331beea"
LEDGER_PATH = "research/wip_209_independent_lineage_2026-10-15/kyiv_185_source_time_lineage_2026-10-15.json"
LEDGER_SHA = "c007f81f10a242e3a3ee3eb2696d03a11369861b8cb797ca505142449bbe8645"
LEDGER_BLOB = "83d16c43e442c624f8c0edccb2b9b219d57a7c6c"
MANIFEST_SHA = "54ce8c9800739b294a83991f71130ab3c6096742ed861b469c1df2ecf2ec9d76"
ARCHIVE_SHA = "0d10cceb48b6266a67faab90bad27201b7be8537bb244d7008824ffc3227e486"
SOURCE = "kyiv-air-alerts-grafana/data/alerts_combined.json"
STATE = "kyiv-air-alerts-grafana/data/explosion_candidate_monitor_state.json"
WORKFLOW = ".github/workflows/explosion-monitor-wip.yml"
UTC = dt.timezone.utc
SAMPLES = {
    "35481398674": ("639cf3c24b5e87afe53a3838bca5f0a73acebfad", 13),
    "35491668099": ("89f70c1cbf59b4b3c1677003d87f6ab47f46a610", 1),
    "36322442545": ("1bacbc46302f44a79bd0c6125816c3451772daa1", 20),
    "37197458169": ("a5756040c796dc4c7d67b0b3e2c7acd17f6006b5", 7),
    "37224221816": ("c06f032bacd96928881bf3b9dd12d6c204291043", 5),
}
DISPOSITIONS = (
    "EXACT_HISTORICAL_INPUT_AND_PRODUCER_PROVEN",
    "EXACT_HISTORICAL_INPUT_FOUND_RUNTIME_PIN_UNPROVEN",
    "HISTORICAL_INPUT_RECORD_NOT_FOUND",
    "PRODUCER_RUNTIME_EVIDENCE_UNAVAILABLE",
    "AMBIGUOUS_HISTORICAL_INPUT",
)

def cmd(*args, check=True):
    p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if check and p.returncode:
        raise RuntimeError("git/command failed: " + " ".join(map(str, args)) +
                           " " + p.stderr.decode("utf-8", "replace")[:240])
    return p.stdout

def git(*args):
    return cmd("git", *args)

def sha(b):
    return hashlib.sha256(b).hexdigest()

def obj(ref, path):
    return git("show", ref + ":" + path)

def blob(ref, path):
    return git("rev-parse", ref + ":" + path).decode().strip()

def jbytes(data):
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2,
                       separators=(",", ": ")) + "\n").encode("utf-8")

def iso_utc(text):
    t = dt.datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    if t.tzinfo is None:
        raise ValueError("naive datetime")
    return t.astimezone(UTC).isoformat().replace("+00:00", "Z")

def timepoint(text):
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))

def event_id(start, end):
    return sha(("kyiv|" + start + "|" + end).encode("utf-8"))[:24]

def resolve_pointer(doc, pointer):
    v = doc
    for key in pointer.lstrip("/").split("/"):
        key = key.replace("~1", "/").replace("~0", "~")
        v = v[int(key)] if isinstance(v, list) else v[key]
    return v

def load_original():
    raw = obj(PROOF, LEDGER_PATH)
    assert sha(raw) == LEDGER_SHA, "Original independent ledger SHA mismatch"
    assert blob(PROOF, LEDGER_PATH) == LEDGER_BLOB, "Original independent ledger Git blob mismatch"
    ledger = json.loads(raw)
    assert ledger["count"] == 185 and len(ledger["rows"]) == 185
    ids = [r["original_episode_id"] for r in ledger["rows"]]
    assert len(ids) == len(set(ids))
    import zipfile
    path = Path(os.getenv("ORIGINAL_209_ARCHIVE", "original-209-artifact.zip"))
    zbytes = path.read_bytes()
    assert sha(zbytes) == ARCHIVE_SHA, "Original 209-case archive SHA mismatch"
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None, "Original archive CRC failed"
        names = [n for n in z.namelist() if n.endswith("wip_cached_209_identity_manifest_2026-10-15.json")]
        assert len(names) == 1, names
        original = z.read(names[0])
        assert sha(original) == MANIFEST_SHA, "Original 209 manifest SHA mismatch"
        manifest = json.loads(original)
    return ledger, {"sha256": sha(original), "bytes": len(original),
                    "archive_sha256": sha(zbytes), "manifest_items": len(manifest) if isinstance(manifest, list) else None}

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def api(path):
    token = os.environ["GH_TOKEN"]
    url = "https://api.github.com/repos/" + REPO + path
    req = urllib.request.Request(
        url, headers={"Authorization": "Bearer " + token,
                      "Accept": "application/vnd.github+json",
                      "X-GitHub-Api-Version": "2022-11-28",
                      "User-Agent": "read-only-kyiv-185-lineage"})
    op = urllib.request.build_opener(NoRedirect())
    try:
        with op.open(req, timeout=45) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code not in (301, 302, 303, 307, 308):
            raise RuntimeError("GitHub API " + path + " HTTP " + str(e.code))
        url2 = e.headers.get("Location", "")
        assert url2.startswith("https://"), "Unexpected logs redirect scheme"
        # GitHub-provided temporary signed Actions log URL, without any auth header.
        with urllib.request.urlopen(url2, timeout=60) as r:
            return r.read()

def ts_from_log(line):
    m = re.match(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)", line)
    return m.group(1) if m else None

def extract_log(raw):
    lines = raw.decode("utf-8", "replace").splitlines()
    produced = set()
    for ln in lines:
        m = re.search(r"\[multicity-wip-2026-09-16 ([0-9a-f]{7,40})\] Update explosion metric monitor state", ln)
        if m:
            produced.add(m.group(1))
        m = re.search(r"\b([0-9a-f]{7,40})\s+HEAD -> multicity-wip-2026-09-16\b", ln)
        if m:
            produced.add(m.group(1))
    fetch_at = None
    fetched_at = None
    row_count = None
    wip_checkout = None
    for i, ln in enumerate(lines):
        if "Run git fetch origin site-prod" in ln and fetch_at is None:
            fetch_at = ts_from_log(ln)
        if re.search(r"\*\s+branch\s+site-prod\s+-> FETCH_HEAD", ln):
            fetched_at = ts_from_log(ln)
        m = re.search(r"production inputs:\s+\d+\s+cities;\s+(\d+)\s+Kyiv completed alerts", ln)
        if m:
            row_count = int(m.group(1))
        if "[command]/usr/bin/git log -1 --format=%H" in ln and i + 1 < len(lines):
            m = re.search(r"\b([0-9a-f]{40})\b", lines[i + 1])
            if m:
                wip_checkout = m.group(1)
    required = ("git fetch origin site-prod" in "\n".join(lines)
                and "git show origin/site-prod:" + SOURCE in "\n".join(lines)
                and "--kyiv-alerts-file /tmp/prod-kyiv-alerts.json" in "\n".join(lines))
    return {"produced_short_ids": sorted(produced),
            "source_fetch_step_start": fetch_at,
            "source_fetch_completed": fetched_at,
            "runtime_kyiv_row_count": row_count,
            "wip_checkout_commit": wip_checkout,
            "runtime_source_path_and_cli_confirmed": required,
            "runtime_site_prod_sha_logged": None,
            "job_log_sha256": sha(raw)}

def collect(folder):
    folder.mkdir(parents=True, exist_ok=True)
    all_runs = []
    # Only the original workflow, not arbitrary other workflows or network sources.
    for page in range(1, 8):
        query = urllib.parse.urlencode({
            "per_page": 100, "page": page, "created": "2026-09-18..2026-10-15"})
        path = "/actions/workflows/explosion-monitor-wip.yml/runs?" + query
        body = json.loads(api(path))
        subset = body.get("workflow_runs", [])
        all_runs.extend(subset)
        if len(subset) < 100:
            break
    else:
        raise RuntimeError("Action run pagination limit exceeded")
    records = []
    for run in all_runs:
        if run.get("conclusion") != "success":
            continue
        rid = run["id"]
        jobs = json.loads(api("/actions/runs/" + str(rid) + "/jobs?per_page=100")).get("jobs", [])
        for job in jobs:
            if job.get("conclusion") != "success" or job.get("name") != "monitor":
                continue
            try:
                rawlog = api("/actions/jobs/" + str(job["id"]) + "/logs")
                detail = extract_log(rawlog)
            except Exception as exc:
                detail = {"runtime_error": type(exc).__name__ + ": " + str(exc)[:150],
                          "produced_short_ids": []}
            records.append({
                "run_id": rid, "run_url": run.get("html_url"),
                "job_id": job["id"],
                "job_url": job.get("html_url"),
                "run_head_sha": run.get("head_sha"),
                "run_created_at": run.get("created_at"),
                "run_conclusion": run.get("conclusion"),
                "job_conclusion": job.get("conclusion"),
                **detail})
    records.sort(key=lambda x: x["run_id"])
    (folder / "producer_evidence.json").write_bytes(jbytes(records))
    print("PRODUCER_RUNS", len(all_runs), "SUCCESSFUL_JOBS", len(records),
          "COMMIT_PREFIXES", sum(len(x["produced_short_ids"]) for x in records), flush=True)

def files_at_prod():
    hashes = git("log", "--first-parent", "--format=%H", PROD, "--", SOURCE).decode().splitlines()
    result = []
    for h in hashes:
        if not h:
            continue
        commit_time = git("show", "-s", "--format=%cI", h).decode().strip()
        b = blob(h, SOURCE)
        result.append({"commit": h, "commit_time": commit_time, "blob": b})
    assert result
    return result

def read_version(v, cache):
    key = v["blob"]
    if key not in cache:
        data = obj(v["commit"], SOURCE)
        assert git("hash-object", "--stdin") if False else True
        assert sha(data), "empty digest"
        rows = json.loads(data)
        assert isinstance(rows, list)
        cache[key] = rows
    return cache[key]

def matches_group(rows, group):
    idx = collections.defaultdict(list)
    for i, row in enumerate(rows):
        try:
            start, end = iso_utc(row.get("start")), iso_utc(row.get("end"))
            if timepoint(end) <= timepoint(start):
                continue
            idx[(start, end)].append(i)
        except (ValueError, TypeError, AttributeError):
            pass
    found = {}
    for r in group:
        pair = tuple(r["original_times_exact"])
        found[r["original_episode_id"]] = idx.get(pair, [])
    return found

def producer_for_commit(c, evidence):
    candidates = [r for r in evidence if any(c.startswith(prefix)
                  for prefix in r.get("produced_short_ids", []))]
    # A commit must be uniquely linked to an actual completed producer job.
    if len(candidates) != 1:
        return None, {"reason": "producer_run_count_" + str(len(candidates)),
                      "run_candidates": [x["run_id"] for x in candidates]}
    run = candidates[0]
    ok = (run.get("runtime_source_path_and_cli_confirmed") is True and
          run.get("source_fetch_step_start") is not None and
          run.get("source_fetch_completed") is not None and
          run.get("runtime_kyiv_row_count") is not None)
    if not ok:
        return None, {"reason": "source_fetch_or_runtime_job_evidence_missing",
                      "run_candidates": [run["run_id"]]}
    return run, None

def audit(folder, outdir):
    ledger, manifest = load_original()
    all_producers = json.loads((folder / "producer_evidence.json").read_bytes())
    source_versions = files_at_prod()
    lookup = {}
    for r in ledger["rows"]:
        lookup.setdefault(r["first_persisted_git"]["commit"], []).append(r)
    assert len(lookup) == 82 and sum(map(len, lookup.values())) == 185
    prod_rows_raw = obj(PROD, SOURCE)
    prod_rows = json.loads(prod_rows_raw)
    assert blob(PROD, SOURCE) == "e91eff537de69156a9bebd55cec1e1ea160d7b58"
    states = {}
    source_cache = {}
    result = []
    inventory = []
    sample_reproduction = {}
    for c, group in sorted(lookup.items()):
        # Recheck frozen original WIP state and the immutable monitor ID hash.
        cstate_blob = blob(c, STATE)
        assert cstate_blob == group[0]["first_persisted_git"]["state_blob"]
        if cstate_blob not in states:
            states[cstate_blob] = json.loads(obj(c, STATE))
        source_state = states[cstate_blob]
        for x in group:
            frozen = resolve_pointer(source_state, x["first_persisted_git"]["json_pointer"])
            assert frozen["episode_id"] == x["original_episode_id"]
            assert (frozen["alert_start"], frozen["alert_end"]) == tuple(x["original_times_exact"])
            assert event_id(*x["original_times_exact"]) == x["original_episode_id"]
        run, missing = producer_for_commit(c, all_producers)
        selected = None
        ambiguous = []
        candidate_reason = None
        source_fetch_time = None
        runtime_count = None
        workflow_blob = None
        workflow_proved = False
        if run:
            source_fetch_time = run["source_fetch_completed"]
            runtime_count = run["runtime_kyiv_row_count"]
            try:
                wtext = obj(run["run_head_sha"], WORKFLOW).decode("utf-8")
                workflow_blob = blob(run["run_head_sha"], WORKFLOW)
                workflow_proved = ("git show origin/site-prod:" + SOURCE in wtext
                                   and "--kyiv-alerts-file /tmp/prod-kyiv-alerts.json" in wtext)
            except Exception:
                pass
            if not workflow_proved:
                missing = {"reason": "historical_workflow_revision_does_not_prove_source_path",
                           "run_candidates": [run["run_id"]]}
                run = None
        if run:
            at = timepoint(source_fetch_time)
            ordered = [v for v in source_versions
                       if timepoint(v["commit_time"]) <= at]
            # This is a candidate, not an independently pinned runtime commit.
            # Two independent checks: original interval evidence AND log row count.
            eligible = []
            for v in ordered:
                rows = read_version(v, source_cache)
                if len(rows) != runtime_count:
                    continue
                pointers = matches_group(rows, group)
                if all(len(z) == 1 for z in pointers.values()):
                    eligible.append((v, pointers))
            if eligible:
                # Topological newest before fetch; repeated older versions are
                # not independently proven to have been in the runtime.
                selected, pointers = eligible[0]
                # If the most-recent source version contradicts this selection,
                # treat timing-based reconstruction as ambiguous, not proven.
                if ordered and ordered[0]["blob"] != selected["blob"]:
                    candidate_reason = "newer_pre_fetch_source_blob_disagrees_with_log_pair_or_count"
                    ambiguous = [v["commit"] for v in ordered if
                                 timepoint(v["commit_time"]) <= at][:6]
                else:
                    candidate_reason = "latest_pre_fetch_source_version_plus_runtime_count_and_exact_pairs"
            else:
                candidate_reason = "no_pre_fetch_source_version_reconciles_runtime_count_and_all_pairs"
        if run:
            inv = {
                "first_wip_commit": c, "first_persisted_ids": sorted(x["original_episode_id"] for x in group),
                "producer_run_id": run["run_id"], "producer_job_id": run["job_id"],
                "producer_run_url": run["run_url"], "producer_job_url": run["job_url"],
                "producer_run_workflow_head": run["run_head_sha"],
                "producer_workflow_blob": workflow_blob,
                "producer_workflow_source_path_verified": workflow_proved,
                "producer_wip_checkout_commit": run.get("wip_checkout_commit"),
                "producer_commit_prefixes_logged": run["produced_short_ids"],
                "source_fetch_started_at": run["source_fetch_step_start"],
                "source_fetch_completed_at": source_fetch_time,
                "runtime_kyiv_input_rows": runtime_count,
                "producer_log_sha256": run["job_log_sha256"],
                "runtime_site_prod_sha_pin": run["runtime_site_prod_sha_logged"],
                "candidate_source_commit": selected["commit"] if selected else None,
                "candidate_source_blob": selected["blob"] if selected else None,
                "candidate_source_commit_time": selected["commit_time"] if selected else None,
                "candidate_selection_basis": candidate_reason,
                "candidate_conflicting_commits": ambiguous,
                "runtime_input_commit_independently_proven": False,
            }
        else:
            inv = {"first_wip_commit": c, "first_persisted_ids":
                   sorted(x["original_episode_id"] for x in group),
                   "producer_run_id": None, "producer_job_id": None,
                   "missing_producer_evidence": missing,
                   "candidate_source_commit": None,
                   "runtime_input_commit_independently_proven": False}
        inventory.append(inv)
        for x in sorted(group, key=lambda z: z["original_episode_id"]):
            initial = x["first_persisted_git"]
            original = None
            source_matches = []
            if selected:
                rows = read_version(selected, source_cache)
                ids = matches_group(rows, [x])[x["original_episode_id"]]
                for i in ids:
                    sr = rows[i]
                    assert event_id(iso_utc(sr["start"]), iso_utc(sr["end"])) == x["original_episode_id"]
                    source_matches.append({"git_commit": selected["commit"],
                         "git_blob": selected["blob"], "json_pointer": "/" + str(i),
                         "source_fields": {k: sr.get(k) for k in ("start", "end", "duration_minutes", "source")},
                         "parsed_utc": [iso_utc(sr["start"]), iso_utc(sr["end"])]})
                original = source_matches[0] if len(source_matches) == 1 else None
            modern = []
            for candidate in x.get("production_candidates", []):
                p_id = candidate["production_id"]
                candidate_rows = []
                for sr in candidate.get("source_records", []):
                    try:
                        row = resolve_pointer(prod_rows, sr["json_pointer"])
                        pair = [iso_utc(row["start"]), iso_utc(row["end"])]
                        assert event_id(*pair) == p_id, "Modern candidate ID hash mismatch"
                        candidate_rows.append({
                            "git_commit": PROD, "git_blob": blob(PROD, SOURCE),
                            "json_pointer": sr["json_pointer"],
                            "start": row["start"], "end": row["end"],
                            "source": row.get("source"), "episode_id": p_id,
                            "utc_exact": pair,
                            "matches_original_exactly": pair == x["original_times_exact"]})
                    except Exception as exc:
                        candidate_rows.append({"source_record_validation_error": str(exc)[:140]})
                modern.append({"episode_id": p_id, "source_records": candidate_rows,
                               "prior_candidate_same_minute": candidate.get("same_minute_not_instant")})
            if not run:
                disposition = "PRODUCER_RUNTIME_EVIDENCE_UNAVAILABLE"
            elif candidate_reason and candidate_reason.startswith("newer_pre_fetch"):
                disposition = "AMBIGUOUS_HISTORICAL_INPUT"
            elif len(source_matches) != 1:
                disposition = ("AMBIGUOUS_HISTORICAL_INPUT" if len(source_matches) > 1
                               else "HISTORICAL_INPUT_RECORD_NOT_FOUND")
            elif run.get("runtime_site_prod_sha_logged"):
                disposition = "EXACT_HISTORICAL_INPUT_AND_PRODUCER_PROVEN"
            else:
                disposition = "EXACT_HISTORICAL_INPUT_FOUND_RUNTIME_PIN_UNPROVEN"
            assert disposition in DISPOSITIONS
            exact_modern = [v for v in modern for r in v["source_records"]
                            if r.get("matches_original_exactly")]
            modern_equivalence = ("PROVEN_EXACT_INPUT_TIMES_AND_HASH" if original and exact_modern
                                  else "UNRESOLVED")
            changes = []
            if original and modern:
                o_src = original["source_fields"].get("source")
                for m in modern:
                    for a in m["source_records"]:
                        if "utc_exact" not in a:
                            continue
                        t0 = (timepoint(a["utc_exact"][0]) - timepoint(x["original_times_exact"][0])).total_seconds()
                        t1 = (timepoint(a["utc_exact"][1]) - timepoint(x["original_times_exact"][1])).total_seconds()
                        changes.append({"current_episode_id": m["episode_id"],
                            "start_delta_seconds": t0, "end_delta_seconds": t1,
                            "old_source_family": o_src, "new_source_family": a["source"],
                            "original_vs_modern_source_family_changed": o_src != a["source"],
                            "original_vs_modern_boundaries_exact": t0 == 0 and t1 == 0,
                            "same_minute_only_not_identity": bool(m.get("prior_candidate_same_minute"))})
            result.append({
                "original_episode_id": x["original_episode_id"], "first_wip_commit": c,
                "original_wip_state_blob": cstate_blob,
                "original_wip_state_pointer": initial["json_pointer"],
                "original_times_exact_utc": x["original_times_exact"],
                "producer_run_id": inv.get("producer_run_id"),
                "producer_job_id": inv.get("producer_job_id"),
                "producer_source_fetch_completed_at": source_fetch_time,
                "source_disposition": disposition,
                "candidate_runtime_site_prod_commit": selected["commit"] if selected else None,
                "runtime_input_git_sha_independently_pinned": False,
                "historical_source_records": source_matches,
                "candidate_current_production_records": modern,
                "modern_comparison": changes,
                "historical_to_modern_equivalence": modern_equivalence,
                "unresolved_limitation": (
                  "Runtime origin/site-prod SHA not printed; candidate is corroborated by source-fetch time, log row count and exact source pair."
                  if disposition == "EXACT_HISTORICAL_INPUT_FOUND_RUNTIME_PIN_UNPROVEN"
                  else candidate_reason or str(missing)),
            })
        if run and str(run["run_id"]) in SAMPLES:
            sample_sha, sample_n = SAMPLES[str(run["run_id"])]
            assert len(group) == sample_n, "Sample cardinality does not reconcile"
            sample_rows = json.loads(obj(sample_sha, SOURCE))
            sampled = matches_group(sample_rows, group)
            assert all(len(i) == 1 for i in sampled.values()), "Sample original intervals not reproduced"
            assert selected is not None, "Sampled runtime source candidate not found"
            assert selected["blob"] == blob(sample_sha, SOURCE), "Sample runtime source blob mismatch"
            sample_reproduction[str(run["run_id"])] = {
                "expected_site_prod_commit": sample_sha, "observed_source_blob": blob(sample_sha, SOURCE),
                "expected": sample_n, "exact_pair_matches": sum(len(v) for v in sampled.values()),
                "runtime_source_commit_pin_proven": False}
    assert len(result) == 185 and len({x["original_episode_id"] for x in result}) == 185
    assert len(sample_reproduction) == 5, "Five preliminary sample runs were not independently reproduced"
    assert sum(x["exact_pair_matches"] for x in sample_reproduction.values()) == 46
    result.sort(key=lambda x: x["original_episode_id"])
    inv_sorted = sorted(inventory, key=lambda x: x["first_wip_commit"])
    counts = collections.Counter(x["source_disposition"] for x in result)
    summary = {
        "scope": "historic site-prod producer input; no WIP-local substitution",
        "original_kyiv_id_count": 185, "producer_commit_groups": len(lookup),
        "source_disposition_counts": {k: counts.get(k, 0) for k in DISPOSITIONS},
        "historical_exact_source_observations_found": sum(bool(x["historical_source_records"]) for x in result),
        "candidate_not_runtime_sha_pinned": sum(x["source_disposition"] ==
            "EXACT_HISTORICAL_INPUT_FOUND_RUNTIME_PIN_UNPROVEN" for x in result),
        "independently_pinned_runtime_input_count": sum(bool(x["runtime_input_git_sha_independently_pinned"]) for x in result),
        "historical_to_modern_exact_identity_proven": sum(x["historical_to_modern_equivalence"].startswith("PROVEN") for x in result),
        "historical_to_modern_identity_unresolved": sum(x["historical_to_modern_equivalence"] == "UNRESOLVED" for x in result),
        "independently_proven_timestamp_transformations": 0,
        "material_boundary_changes_over_60s": sum(any(abs(z.get(k, 0)) > 60
                    for z in x["modern_comparison"] for k in ("start_delta_seconds", "end_delta_seconds"))
                    for x in result),
        "observed_source_family_changes": sum(any(z["original_vs_modern_source_family_changed"]
                    for z in x["modern_comparison"]) for x in result),
        "five_preliminary_groups_reproduced": sample_reproduction,
        "original_manifest_sha256": manifest["sha256"],
        "original_archive_sha256": manifest["archive_sha256"],
        "historic_source_version_count": len(source_versions),
        "original_209_manifest_not_mutated": True,
        "historical_episode_ids_not_mutated": True,
        "wip_activation": "NO-GO",
        "historical_input_recovery_gate": (
            "PASS" if counts.get("EXACT_HISTORICAL_INPUT_AND_PRODUCER_PROVEN", 0) == 185
            else "PARTIAL"),
        "historical_to_production_identity_gate": (
            "PROVEN" if all(x["historical_to_modern_equivalence"].startswith("PROVEN") for x in result)
            else "PARTIAL" if any(x["historical_to_modern_equivalence"].startswith("PROVEN") for x in result)
            else "UNRESOLVED"),
    }
    safety = {
        "frozen_refs": {"main": MAIN, "wip": WIP, "site-prod": PROD, "prior_proof": PROOF},
        "input_sha256": {"original_209_manifest": manifest["sha256"],
                         "original_209_archive": manifest["archive_sha256"],
                         "prior_kyiv_185_ledger": LEDGER_SHA,
                         "frozen_production_source": sha(prod_rows_raw),
                         "frozen_producer_api_evidence": sha((folder / "producer_evidence.json").read_bytes())},
        "input_git_blobs": {"prior_kyiv_185_ledger": LEDGER_BLOB,
                            "frozen_site_prod_source": blob(PROD, SOURCE)},
        "scope_guards": {"ukrainealarm_requests": 0, "neon_connections": 0,
                         "publisher_requests": 0, "classifier_runs": 0,
                         "production_operational_writes": 0,
                         "wip_operational_writes": 0,
                         "main_operational_writes": 0,
                         "only_local_git_and_github_actions_log_reads": True},
        "no_timing_based_runtime_git_sha_promotion": True,
        "no_unsupported_minute_level_identity_promotion": True,
        "wip_activation": "NO-GO",
    }
    outdir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "kyiv_185_original_source_recovery_ledger.json": {"rows": result, "count": len(result)},
        "historical_source_revision_inventory.json": {
            "producer_runs": inv_sorted,
            "unique_historical_source_blobs_selected": sorted(set(x["candidate_source_blob"]
                                                                 for x in inv_sorted if x.get("candidate_source_blob"))),
            "sample_groups": sample_reproduction},
        "provenance_reconciliation_report.json": summary,
        "frozen_safety_and_reproducibility.json": safety,
    }
    for name, value in outputs.items():
        (outdir / name).write_bytes(jbytes(value))
    sums = {k: {"bytes": len((outdir / k).read_bytes()), "sha256": sha((outdir / k).read_bytes())}
            for k in sorted(outputs)}
    (outdir / "result_hashes.json").write_bytes(jbytes(sums))
    print("AUDIT", json.dumps(summary, sort_keys=True, ensure_ascii=False), flush=True)
    print("OUTPUT_HASHES", json.dumps(sums, sort_keys=True), flush=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("collect", "audit"))
    parser.add_argument("--folder", default="/tmp/kyiv-185-producer-evidence")
    parser.add_argument("--outdir", default="/tmp/kyiv-185-output")
    args = parser.parse_args()
    if args.mode == "collect":
        collect(Path(args.folder))
    else:
        audit(Path(args.folder), Path(args.outdir))

if __name__ == "__main__":
    main()
