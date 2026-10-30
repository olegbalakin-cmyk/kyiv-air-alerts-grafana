#!/usr/bin/env python3
"""Reproduce and causally account for recovered parity, entirely offline.

Requires a clean site-prod checkout at SITE_SHA and requests/beautifulsoup4.
Never calls a producer main(), database, or HTTP endpoint. All output is outside
the reference checkout. A counterfactual is diagnostic, never a data repair.
"""
from __future__ import annotations

import argparse
import collections
import copy
import csv
import dataclasses
import difflib
import hashlib
import importlib.metadata
import io
import json
import platform
import socket
import subprocess
import sys
import types
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent
SITE_SHA = "0ecbb291e8f443f7ab366bc4ac033d096f2c44f4"
CUTOFF = "2026-10-30T15:27:55.138400Z"
EXTRA_PINS = {
    "data/owner_accepted_air_corrections.json": "c6c371d9c8eb18b866cda59bcc05424e184945aa",
    "scripts/owner_air_corrections.py": "f8e85afc6b01b9c0fbf34b3ba8de1d975c86f097",
    "../research/c6_oct184_b1_source_priority_2026_10_29/source_priority_reader.py": "890769995627aa15e43743ef7cd5b24d54b1c59c",
    "../research/c6_oct184_b1_source_priority_2026_10_29/frozen_october_382_198_bundle.json": "fbad2b5318818b9c4bc9940e691de5f32fcdf283",
}


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def digest(path):
    raw = Path(path).read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def blob(path):
    raw = Path(path).read_bytes()
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def differences(a, b, path="$"):
    """Exact independent walk: no tolerance, truncation, or city-name waiver."""
    out = {}
    if type(a) is not type(b):
        out[path] = [a, b]
    elif isinstance(a, dict):
        for key in sorted(a.keys() | b.keys()):
            p = path + "." + key
            if key not in a or key not in b:
                out[p] = [a.get(key, "<MISSING>"), b.get(key, "<MISSING>")]
            else:
                out.update(differences(a[key], b[key], p))
    elif isinstance(a, list):
        if len(a) != len(b):
            out[path + ".length"] = [len(a), len(b)]
        for i in range(max(len(a), len(b))):
            p = path + f"[{i}]"
            if i >= len(a) or i >= len(b):
                out[p] = [a[i] if i < len(a) else "<MISSING>", b[i] if i < len(b) else "<MISSING>"]
            else:
                out.update(differences(a[i], b[i], p))
    elif a != b:
        out[path] = [a, b]
    return out


def no_network(*args, **kwargs):
    raise RuntimeError("Network access prohibited in offline parity verification")


def child_replay(argv):
    import runpy
    socket.create_connection = no_network
    socket.socket.connect = no_network
    socket.socket.connect_ex = no_network
    sys.path.insert(0, str(HERE))
    sys.argv = [str(HERE / "replay.py"), *argv]
    runpy.run_path(str(HERE / "replay.py"), run_name="__main__")


def verify_loader_patch(site, mods, correction, proof):
    """Run the real legacy loader on controlled local CSV, before/after patch."""
    source = (site / "scripts/build_time_of_day_heatmap.py").read_text()
    patched = source.replace(
        "from update_data import Alert, TZ, http_session\n",
        "from update_data import Alert, TZ, http_session\nfrom owner_air_corrections import apply_owner_accepted_air_corrections\n",
    ).replace("    return exact, proxy, proxy_cfg\n", "    apply_owner_accepted_air_corrections(exact)\n    return exact, proxy, proxy_cfg\n")
    assert patched != source and patched.count("apply_owner_accepted_air_corrections(exact)") == 1
    patch = "".join(difflib.unified_diff(source.splitlines(True), patched.splitlines(True),
        fromfile="a/kyiv-air-alerts-grafana/scripts/build_time_of_day_heatmap.py",
        tofile="b/kyiv-air-alerts-grafana/scripts/build_time_of_day_heatmap.py"))
    (proof / "derived_owner_correction.patch").write_text(patch)
    module = types.ModuleType("isolated_patched_derived_loader")
    module.__file__ = str(site / "scripts/build_time_of_day_heatmap.py")
    exec(compile(patched, module.__file__, "exec"), module.__dict__)
    old = correction["expected_previous_interval"]
    accepted = correction["accepted_interval"]

    def run(loader, end):
        text = io.StringIO()
        fields = ["level", "hromada", "oblast", "started_at", "finished_at"]
        writer = csv.DictWriter(text, fieldnames=fields)
        writer.writeheader()
        writer.writerow({"level": "hromada", "hromada": correction["hromada"],
                         "started_at": old["start_at"], "finished_at": end})
        response = types.SimpleNamespace(content=text.getvalue().encode("utf-8"), raise_for_status=lambda: None)
        original = loader.http_session
        loader.http_session = lambda: types.SimpleNamespace(get=lambda *a, **k: response)
        try:
            return loader.load_historical_source()[0]["kharkiv"][0]
        finally:
            loader.http_session = original

    from replay import aware
    legacy = run(mods["build_time_of_day_heatmap"], old["end_at"])
    fixed = run(module, old["end_at"])
    assert legacy.end.astimezone(aware(old["end_at"]).tzinfo) == aware(old["end_at"])
    assert fixed.end.astimezone(aware(accepted["end_at"]).tzinfo) == aware(accepted["end_at"])
    assert run(module, accepted["end_at"]).end == fixed.end
    rejected = False
    try:
        run(module, "2025-03-05T22:00:00+02:00")
    except ValueError:
        rejected = True
    assert rejected
    return {"legacy_loader_omits_accepted_correction": True, "patched_loader_applies_correction": True,
            "already_corrected_is_idempotent": True, "unexpected_source_boundary_fails_closed": True,
            "production_file_modified": False}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--site", type=Path, required=True)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--reuse-replays", action="store_true", help="Analysis only, using already executed replay outputs")
    args = ap.parse_args()
    site, work = args.site.resolve(), args.work.resolve()
    if work.is_relative_to(site) or site.is_relative_to(work):
        raise ValueError("Reference checkout and research output must be separate")
    work.mkdir(parents=True, exist_ok=True)
    proof = work / "proof"
    proof.mkdir(exist_ok=True)
    tests = {}
    for name, expected in read(HERE / "proof/recovery/recovery_sha256_manifest.json").items():
        assert digest(HERE / name) == expected, name
    tests["recovered_manifest_16_of_16"] = True
    assert subprocess.check_output(["git", "-C", str(site), "rev-parse", "HEAD"], text=True).strip() == SITE_SHA
    for relative, expected in EXTRA_PINS.items():
        p = RESEARCH / relative.removeprefix("../research/") if relative.startswith("../research/") else site / relative
        assert blob(p) == expected, relative
    tests["extra_source_and_B2_pins"] = True
    subprocess.run([sys.executable, str(HERE / "unpack_inputs.py")], cwd=work, check=True)
    sys.path[:0] = [str(HERE), str(work / "inputs/adapter/C6-22CITY-READER-01")]
    import adapter
    import replay
    import requests
    requests.sessions.Session.request = no_network
    socket.create_connection = no_network
    socket.socket.connect = no_network
    socket.socket.connect_ex = no_network
    common = ["--site", str(site), "--reference-sha", SITE_SHA,
              "--accepted-adapter", str(work / "inputs/adapter/C6-22CITY-READER-01"),
              "--research", str(RESEARCH), "--rows", str(work / "inputs/current-physical-rows.json"),
              "--receipt", str(work / "inputs/current-physical-receipt.json"),
              "--classifications", str(work / "inputs/class-snapshot.json"), "--cutoff", CUTOFF,
              "--corroborating-http", str(work / "inputs/http/entity_bytes.bin"),
              "--http-evidence", str(work / "inputs/http_evidence.json")]
    for mode in ("replayed", "control"):
        if not args.reuse_replays:
            command = [sys.executable, str(Path(__file__).resolve()), "--_replay-child", *common, "--output", str(work / mode)]
            if mode == "replayed":
                command.extend(["--dst-plan", str(work / "inputs/dst_plan.json")])
            print("Executing offline " + mode + " replay", flush=True)
            with (proof / (mode + ".log")).open("w") as log:
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
        assert read(work / mode / "machine_verdict.json")["dst_simulation"] == (mode == "replayed")
    for name in ("full_diff.json", "22city_diff.json", "machine_verdict.json", "dst_projection_plan.json"):
        assert (work / "replayed" / name).read_bytes() == (HERE / "proof/recovery" / name).read_bytes(), name
    tests["recovered_reports_byte_identical"] = True
    assert read(work / "control/22city_diff.json")["total_diff_items"] == 0
    assert read(work / "replayed/22city_diff.json")["total_diff_items"] == 366
    tests["direct_diff_zero_control_366_DST_projection"] = True
    published = {"dashboard": read(site / "data/dashboard_data.json"), "derived": read(site / "data/site_derived.json")}
    versions = {mode: {"dashboard": read(work / mode / "site/dashboard_data.json"),
                       "derived": read(work / mode / "site/site_derived.json")} for mode in ("replayed", "control")}
    all_diffs = {}
    for mode, values in versions.items():
        d = differences(values["dashboard"], published["dashboard"])
        d.update(differences(values["derived"], published["derived"], "$.site_derived"))
        assert set(d) == {r["json_path"] for r in read(work / mode / "full_diff.json")}
        all_diffs[mode] = d
    assert len(all_diffs["replayed"]) == 1354 and len(all_diffs["control"]) == 1691
    tests["complete_exact_independent_diff_no_tolerance"] = True

    rows = read(work / "inputs/current-physical-rows.json")
    receipt = read(work / "inputs/current-physical-receipt.json")
    classes = read(work / "inputs/class-snapshot.json")
    assert classes["snapshot"] == receipt["snapshot"]
    assert all(r["alert_type"] == "AIR" and r["episode_state"] == "closed"
               and replay.aware(r["end_at"]) <= replay.aware(CUTOFF) for r in rows)
    tests["closed_AIR_cutoff_and_classification_snapshot_consistent"] = True
    plan = read(work / "inputs/dst_plan.json")
    projected, operations = replay.apply_dst_preview(rows, plan)
    bridge = read(site / "data/ukrainealarm_bridge.json")
    assert blob(site / "data/ukrainealarm_bridge.json") == subprocess.check_output(
        ["git", "-C", str(site), "rev-parse", "HEAD:kyiv-air-alerts-grafana/data/ukrainealarm_bridge.json"], text=True).strip()
    source_tokens = {(r["city_key"], replay.aware(r["start"]), replay.aware(r["end"])) for r in bridge["events"] if r["alert_type"] == "AIR"}
    witnesses, duration_deltas = [], {}
    for op in operations:
        delta = 0
        for r in op["proposed"]:
            assert (op["city"], replay.aware(r["start_utc"]), replay.aware(r["end_utc"])) in source_tokens
            delta += (replay.aware(r["end_utc"]) - replay.aware(r["start_utc"])).total_seconds()
            witnesses.append({"city": op["city"], **r})
        if op["old"]:
            delta -= (replay.aware(op["old"]["end_utc"]) - replay.aware(op["old"]["start_utc"])).total_seconds()
        duration_deltas[op["city"]] = round(delta, 6)
    save(proof / "dst_source_witnesses.json", {"bridge_git_blob": blob(site / "data/ukrainealarm_bridge.json"),
          "proposed_intervals_found_exactly_in_pinned_source": witnesses, "duration_deltas_seconds": duration_deltas,
          "physical_Neon_repair": "NOT_EXECUTED"})
    tests["seven_DST_intervals_corroborated_by_pinned_bridge"] = True

    # Change ONLY the accepted historical Kharkiv boundary back to the old one.
    # If this exactly reproduces published derived fields, those differences
    # cannot be attributed to the October DST intervention.
    mods = adapter.import_site_modules(site)
    heat = mods["build_time_of_day_heatmap"]
    update = mods["update_data"]
    merged, _ = adapter.merged_input_by_city([r for r in projected if r["city_key"] != "kyiv"])
    alerts = [update.Alert(s, e, "offline_counterfactual") for s, e in merged["kharkiv"]]
    correction = read(site / "data/owner_accepted_air_corrections.json")
    accepted, old = correction["accepted_interval"], correction["expected_previous_interval"]
    matches = [i for i, a in enumerate(alerts) if a.start == replay.aware(accepted["start_at"]) and a.end == replay.aware(accepted["end_at"])]
    assert len(matches) == 1
    alerts[matches[0]] = dataclasses.replace(alerts[matches[0]], end=replay.aware(old["end_at"]))
    reference_heat = published["derived"]["time_of_day_heatmap_test"]["cities"]["kharkiv"]
    start, end = date.fromisoformat(reference_heat["coverage_start"]), date.fromisoformat(reference_heat["analysis_end"])
    counter_heat = {p: heat.period_heatmap(alerts, start, end, n) for p, n in heat.PERIODS.items()}
    reference_exploration = published["derived"]["explorations"]["cities"]["kharkiv"]
    counter_exploration = heat.build_exploration_city(alerts, start, end, label=reference_exploration["label"], source_type=reference_exploration["source_type"])
    assert counter_heat == reference_heat["periods"]
    assert counter_exploration == reference_exploration
    tests["single_C4_KH_06_counterfactual_exactly_reproduces_published_derived"] = True
    save(proof / "kharkiv_counterfactual.json", {"case": correction["case"], "accepted": accepted, "previous": old,
          "published_heatmap_equals_old_interval_counterfactual": True,
          "published_exploration_equals_old_interval_counterfactual": True,
          "candidate_uses_accepted_interval": True, "raw_primary_Telegram_export": "NOT_INCLUDED_NOT_REAUDITED"})
    tests["derived_loader_patch"] = verify_loader_patch(site, mods, correction, proof)

    classified = []
    for path, (candidate, reference) in all_diffs["replayed"].items():
        baseline_pair = all_diffs["control"].get(path)
        if path.endswith((".generated_at", ".partial_through")):
            category = "cutoff_metadata"
            assert baseline_pair == [candidate, reference]
        elif path == "$.site_derived.meta.source":
            category = "research_marker"
        elif path.startswith(("$.site_derived.time_of_day_heatmap_test.cities.kharkiv.", "$.site_derived.explorations.cities.kharkiv.")):
            category = "legacy_derived_omits_accepted_C4_KH_06"
        else:
            # Every remaining path is equal to publication without DST plan.
            assert path not in all_diffs["control"], path
            category = "expected_DST_projection"
        classified.append({"json_path": path, "category": category, "candidate": candidate, "published": reference})
    counts = dict(collections.Counter(r["category"] for r in classified))
    assert counts == {"cutoff_metadata": 49, "expected_DST_projection": 847,
                      "legacy_derived_omits_accepted_C4_KH_06": 457, "research_marker": 1}, counts
    tests["all_1354_paths_causally_accounted"] = True
    tests["alerts_combined_semantic_parity"] = sorted((replay.token(r, "start", "end"), r.get("source")) for r in read(work / "replayed/site/alerts_combined.json")) == sorted((replay.token(r, "start", "end"), r.get("source")) for r in read(site / "data/alerts_combined.json"))
    assert tests["alerts_combined_semantic_parity"]
    save(proof / "classified_full_diff.json", classified)
    save(proof / "control_machine_verdict.json", read(work / "control/machine_verdict.json"))
    save(proof / "tests.json", tests)
    verdict = {"checkpoint": "C6-RECOVERED-PARITY-VERIFICATION-02", "status": "PASS_BOUNDED_OFFLINE_PARITY_ACCOUNTING",
               "reference_sha": SITE_SHA, "cutoff": CUTOFF, "physical_rows": len(rows), "projected_rows": len(projected),
               "direct_22city_control": 0, "direct_22city_projected": 366,
               "full_control_diff": 1691, "full_projected_diff": 1354,
               "classified_counts": counts, "unexplained_paths": 0,
               "legacy_generator_defects": 1, "research_patch_tests": "PASS; patch not deployed",
               "physical_DST_cases_still_open": 4, "candidate": "READY_FOR_BOUNDED_RESEARCH_PREVIEW_WITH_DST_SIMULATION",
               "production_cutover_allowed": False, "neon_mutations": 0,
               "remaining_evidence_limits": ["No fresh Neon query or ingestion receipt proof", "Historical Kyiv selection and auxiliary files still Git-backed", "Raw complete historical upstream CSV not frozen; full source-to-site regeneration not asserted", "Browser/CSV, freshness, source switch and rollback not executed in this task"],
               "python": platform.python_version(), "dependencies": {n: importlib.metadata.version(n) for n in ("requests", "beautifulsoup4")}}
    save(proof / "machine_verdict.json", verdict)
    save(proof / "sha256_manifest.json", {str(p.relative_to(work)): digest(p) for p in sorted(work.rglob("*")) if p.is_file() and p.name != "sha256_manifest.json" and "__pycache__" not in p.parts})
    print(json.dumps(verdict), flush=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--_replay-child":
        child_replay(sys.argv[2:])
    else:
        main()
