#!/usr/bin/env python3
"""Offline parity and incident dedup regression for the historical main Kyiv-only generator."""
from __future__ import annotations
import copy
import csv
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

BASE = "375e69351e6a5aee1be16892821f7cdde2a8f21a"
PROD = "68629fdae5534ec3a136e666bcb7d5c84dcd05aa"
PREFIX = "kyiv-air-alerts-grafana/"
SCRIPT = "scripts/update_casualties.py"
REV = "data/casualties/revisions.csv"
JSON = "data/dashboard_data.json"
INPUTS = (SCRIPT, REV, JSON, "data/casualties/baseline_monthly.csv",
          "data/casualties/review_queue.json")
HERE = Path(__file__).resolve().parent
PROOF = HERE / "proof"
INCIDENT = "incident:kyiv:2026-10-10:morning-kab"
PROOF_ID = "sha256:" + ("a" * 64)
CREDIT_PROOF = "git:" + BASE + ":kyiv-air-alerts-grafana/data/casualties/baseline_monthly.csv"

def git(ref, path):
    return subprocess.check_output(["git", "show", ref + ":" + path])

def digest(data):
    return hashlib.sha256(data).hexdigest()

def stable(data):
    obj = copy.deepcopy(data)
    obj.get("casualties", {}).get("meta", {}).pop("generated_at", None)
    return obj

def make_revision_csv(data, extra):
    src = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
    fields = list(src.fieldnames or [])
    for name in ("city_key", "candidate_ids", "incident_id", "count_kind",
                 "baseline_credited", "identity_proof", "credited_proof"):
        if name not in fields:
            fields.append(name)
    dst = io.StringIO()
    out = csv.DictWriter(dst, fieldnames=fields, lineterminator="\n")
    out.writeheader()
    for item in [*src, *extra]:
        out.writerow({name: item.get(name, "") for name in fields})
    return dst.getvalue().encode("utf-8")

def record(n, *, incident=INCIDENT, candidate="candidate-main-morning",
           timestamp="2026-10-15T16:00:00+03:00", kind="cumulative",
           credited=0, **changes):
    result = {
        "record_id": f"fixture:{incident}:{n}:{timestamp}",
        "city_key": "kyiv",
        "observed_at": timestamp,
        "attack_date": "2026-10-10",
        "deaths_delta": str(n),
        "status": "confirmed",
        "source_name": "PINNED OFFLINE FIXTURE",
        "source_url": "https://example.invalid/fixtures/" + candidate,
        "note": "Offline proof handles only; no actual evidence or publication",
        "candidate_ids": candidate,
        "incident_id": incident,
        "count_kind": kind,
        "baseline_credited": str(credited),
        "identity_proof": (PROOF_ID if incident == INCIDENT
                           else "sha256:" + digest(incident.encode("utf-8"))),
        "credited_proof": CREDIT_PROOF,
    }
    result.update(changes)
    return result

def run(name, tmp, inputs, extra=None, *, generator=None, expect_error=None):
    work = tmp / name
    for path, value in inputs.items():
        dest = work / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(value)
    (work / SCRIPT).write_bytes(generator or git("HEAD", PREFIX + SCRIPT))
    if extra is not None:
        (work / REV).write_bytes(make_revision_csv(inputs[REV], extra))
    proc = subprocess.run([sys.executable, SCRIPT, "--no-network"], cwd=work,
                          capture_output=True, text=True, timeout=60,
                          env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    if expect_error:
        assert proc.returncode != 0 and expect_error in proc.stderr, (
            name, proc.returncode, proc.stderr[-1300:])
        return None
    assert proc.returncode == 0, (name, proc.stderr[-2000:])
    return json.loads((work / JSON).read_text(encoding="utf-8"))

def total(doc):
    return sum(int(x["deaths"]) for x in doc["casualties"]["monthly"])

def month(doc, key):
    return next((x for x in doc["casualties"]["monthly"] if x["month"] == key), None)

def write_json(name, value):
    PROOF.mkdir(parents=True, exist_ok=True)
    (PROOF / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")

def main():
    frozen = {name: git(BASE, PREFIX + name) for name in INPUTS}
    protected = {name: digest(value) for name, value in frozen.items()}
    checks = []
    def check(name, actual, expected=True):
        checks.append({"name": name, "result": "PASS" if actual == expected else "FAIL",
                       "actual": actual, "expected": expected})
    def rejected(name, tmp, rows, message):
        run(name, tmp, frozen, rows, expect_error=message)
        check(name, True)

    x18 = record(18, timestamp="2026-10-10T16:00:00+03:00")
    x20 = record(20, timestamp="2026-10-12T16:00:00+03:00")
    x23 = record(23, timestamp="2026-10-15T16:00:00+03:00")
    with tempfile.TemporaryDirectory(prefix="casualty_main_adoption_") as directory:
        tmp = Path(directory)
        original = run("original-main", tmp, frozen, generator=frozen[SCRIPT])
        control = run("patched-main", tmp, frozen)
        one = run("0-to-23", tmp, frozen, [x23])
        eighteen = run("only-18", tmp, frozen, [x18])
        twenty_three = run("only-23", tmp, frozen, [x23])
        eighteen_to_23 = run("18-to-23", tmp, frozen, [x18, x23])
        twenty_three_to_23 = run(
            "23-to-23", tmp, frozen,
            [x23, record(23, timestamp="2026-10-17T16:00:00+03:00")])
        triple = run("18-20-23", tmp, frozen, [x18, x20, x23])

        check("original_main_equivalence", stable(control) == stable(original))
        check("original_revisions_empty", frozen[REV].decode().strip().splitlines() ==
              ["record_id,observed_at,attack_date,deaths_delta,status,source_name,source_url,note"])
        check("pinned_2026_baseline", sum(r["deaths"] for r in control["casualties"]["monthly"]
                                         if r["month"].startswith("2026-")) == 153)
        check("0_to_23", total(one) - total(control), 23)
        check("18_to_23", total(eighteen_to_23) - total(eighteen), 5)
        check("23_to_23", total(twenty_three_to_23) - total(twenty_three), 0)
        check("18_20_23_total", month(triple, "2026-10")["deaths"], 23)
        check("october_created", month(one, "2026-10")["deaths"], 23)
        check("previous_months_unchanged", [
            r for r in one["casualties"]["monthly"] if r["month"] < "2026-10"] ==
            control["casualties"]["monthly"])
        check("unrelated_dashboard_unchanged", {
            k: v for k, v in stable(control).items() if k != "casualties"
        } == {
            k: v for k, v in stable(one).items() if k != "casualties"
        })
        check("outbound_schema_unchanged",
              set(control["casualties"]) == set(one["casualties"]) and
              set(month(one, "2026-10")) == set(month(control, "2026-08")))
        later = record(7, incident="incident:kyiv:2026-10-10:afternoon",
                       candidate="distinct-afternoon",
                       timestamp="2026-10-11T16:00:00+03:00")
        same_day = run("different-same-day", tmp, frozen, [x23, later])
        check("independent_same_day", month(same_day, "2026-10")["deaths"], 30)
        next_day = run("different-next-day", tmp, frozen, [
            x23, record(7, incident="incident:kyiv:2026-10-11:afternoon",
                        candidate="distinct-next-day",
                        timestamp="2026-10-12T16:00:00+03:00",
                        attack_date="2026-10-11")])
        check("independent_next_day", month(next_day, "2026-10")["deaths"], 30)
        delta = run("single-delta", tmp, frozen, [record(3, kind="delta")])
        check("single_verified_delta", total(delta) - total(control), 3)

        rejected("reused_candidate_blocked", tmp, [
            x23, dict(later, candidate_ids=x23["candidate_ids"])],
                 "Ambiguous candidate_id across incidents")
        rejected("reused_source_blocked", tmp, [
            x23, dict(later, source_url=x23["source_url"])],
                 "Ambiguous source_url across incidents")
        rejected("reused_identity_proof_blocked", tmp, [
            x23, dict(later, identity_proof=x23["identity_proof"])],
                 "Ambiguous identity_proof across incidents")
        rejected("missing_identity_blocked", tmp, [
            dict(x23, incident_id="")], "missing documented incident identity")
        rejected("missing_credit_blocked", tmp, [
            dict(x23, baseline_credited="")], "undocumented baseline_credited")
        rejected("excess_baseline_credit_blocked", tmp, [
            dict(x23, baseline_credited="18")], "Unproven baseline credit")
        rejected("downward_cumulative_blocked", tmp, [
            x23, record(20, timestamp="2026-10-16T16:00:00+03:00")],
                 "Downward/ambiguous cumulative update")
        rejected("unordered_cumulative_blocked", tmp, [
            x23, record(20, timestamp=x23["observed_at"])],
                 "Downward/ambiguous cumulative update")
        rejected("duplicate_record_id_blocked", tmp, [x23, x23],
                 "Duplicate casualty revision record_id")
        rejected("multiple_deltas_blocked", tmp, [
            record(2, kind="delta"),
            record(3, kind="delta", timestamp="2026-10-16T16:00:00+03:00")],
                 "Multiple incremental records")
        rejected("conflicting_count_kind_blocked", tmp, [
            x23, record(2, kind="delta", timestamp="2026-10-16T16:00:00+03:00")],
                 "Conflicting identity/credited provenance")
        rejected("invalid_kind_blocked", tmp, [
            dict(x23, count_kind="unknown")], "invalid count_kind")
        rejected("negative_count_blocked", tmp, [
            dict(x23, deaths_delta="-1")], "negative death count")
        rejected("missing_identity_proof_blocked", tmp, [
            dict(x23, identity_proof="")], "missing immutable identity_proof")
        rejected("missing_credit_proof_blocked", tmp, [
            dict(x23, credited_proof="")], "missing immutable credited_proof")
        rejected("missing_source_blocked", tmp, [
            dict(x23, source_url="")], "missing source/candidate provenance")
        rejected("missing_candidate_blocked", tmp, [
            dict(x23, candidate_ids="")], "missing source/candidate provenance")
        rejected("missing_timezone_blocked", tmp, [
            dict(x23, observed_at="2026-11-12T10:00:00")],
                 "observed_at must include timezone")
        rejected("foreign_city_blocked", tmp, [
            dict(x23, city_key="sumy")], "non-Kyiv city_key")
        rejected("legacy_unapproved_blocked", tmp, [
            dict(x23, incident_id="", record_id="fixture:unapproved")],
                 "missing documented incident identity")

        repeat_dir = tmp / "0-to-23"
        cmd = subprocess.run([sys.executable, SCRIPT, "--no-network"],
                             cwd=repeat_dir, capture_output=True, text=True, timeout=60)
        repeated = json.loads((repeat_dir / JSON).read_text(encoding="utf-8"))
        check("idempotent_repeat", cmd.returncode == 0 and
              stable(repeated) == stable(one))
        (repeat_dir / REV).write_bytes(frozen[REV])
        cmd = subprocess.run([sys.executable, SCRIPT, "--no-network"],
                             cwd=repeat_dir, capture_output=True, text=True, timeout=60)
        restored = json.loads((repeat_dir / JSON).read_text(encoding="utf-8"))
        check("rollback_to_frozen_data", cmd.returncode == 0 and
              stable(restored) == stable(control))
    check("all_frozen_inputs_unchanged", {
        name: digest(git(BASE, PREFIX + name)) for name in INPUTS
    } == protected)
    failures = [x["name"] for x in checks if x["result"] != "PASS"]
    write_json("checks.json", checks)
    write_json("input_sha256.json", protected)
    write_json("scenario_summary.json", {
        "source_main": BASE, "source_siteprod": PROD,
        "baseline_total": total(control), "with_23": total(one),
        "delta_18_to_23": total(eighteen_to_23) - total(eighteen),
        "duplicate_23_to_23": total(twenty_three_to_23) - total(twenty_three),
        "test_cases": len(checks), "failed": failures,
        "live_publication": False,
    })
    PROOF.mkdir(parents=True, exist_ok=True)
    (PROOF / "FINAL_REPORT.md").write_text(
        "# Main Kyiv-only dedup offline regression\n\n"
        + f"Base main: {BASE}\n\n"
        + f"PASS: {len(checks) - len(failures)}, FAIL: {len(failures)}\n\n"
        + "Only temporary generated data; no production or source HTTP.\n\n"
        + "Site-prod multicity and pinned Sumy +1 independently exercised in the "
          "separate original 25-check reference suite.\n\n"
        + ("Failures: " + ", ".join(failures) if failures else "No failures.")
        + "\n", encoding="utf-8")
    proof_files = sorted(f for f in PROOF.iterdir() if f.is_file() and f.name != "SHA256SUMS")
    (PROOF / "SHA256SUMS").write_text(
        "".join(digest(f.read_bytes()) + "  " + f.name + "\n" for f in proof_files),
        encoding="utf-8")
    print(f"CHECKS_PASS={len(checks) - len(failures)}")
    print(f"CHECKS_FAIL={len(failures)}")
    print(f"FAILED={failures}")
    if failures:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
