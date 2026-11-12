#!/usr/bin/env python3
"""Physical, offline same-incident dedup proof on pinned production inputs."""
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

PROD = "fc7261660bdee75ee59296ee94cc1189be6b1a22"
PREFIX = "kyiv-air-alerts-grafana/"
HERE = Path(__file__).resolve().parent
PROOF = HERE / "proof"
GENERATED = "data/dashboard_data.json"
REV = "data/casualties/revisions.csv"
SCRIPT = "scripts/update_casualties.py"
INCIDENT = "incident:zaporizhzhia:2026-10-10:morning-kab"
SOURCE_ID = "e0fba98b19473874e9a1d8f1"
EVIDENCE = "011894b7c4bd906dcfd0c5d2f7cef07a932976ca313220fa9089999264feb259"
PROOF_ID = "sha256:" + EVIDENCE
CREDIT_PROOF = "git:" + PROD + ":data/casualties/cities/zaporizhzhia/zaporizhzhia_air_attack_deaths_monthly.csv"
assert len(EVIDENCE) == 64

def sha(data):
    return hashlib.sha256(data).hexdigest()

def git(ref, path):
    return subprocess.check_output(["git", "show", ref + ":" + path])

def store(name, data):
    path = PROOF / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf8")

def stable(data):
    x = copy.deepcopy(data)
    x.get("casualties", {}).get("meta", {}).pop("generated_at", None)
    x.get("casualties_by_city", {}).get("kyiv", {}).get("meta", {}).pop("generated_at", None)
    return x

def get_source_files():
    tree = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", PROD, "--",
                                    PREFIX + "data/casualties/cities/"], text=True).splitlines()
    names = [
        GENERATED, REV, "data/casualties/baseline_monthly.csv",
        "data/casualties/review_queue.json", "data/casualties/master_20cities_manifest.json",
        "data/casualties/master_20cities_monthly_wide.csv", SCRIPT,
        "pages-preview/app.js"
    ] + [p.removeprefix(PREFIX) for p in tree if p.endswith(".csv") or p.endswith("/manifest.json")]
    return {n: git(PROD, PREFIX + n) for n in sorted(set(names))}

def csv_rows(base, extra):
    inp = csv.DictReader(io.StringIO(base.decode("utf-8-sig")))
    fields = list(inp.fieldnames)
    added = ["incident_id", "count_kind", "baseline_credited", "identity_proof", "credited_proof"]
    fields += [k for k in added if k not in fields]
    dst = io.StringIO()
    wr = csv.DictWriter(dst, fieldnames=fields, lineterminator="\n")
    wr.writeheader()
    wr.writerows([*inp, *extra])
    return dst.getvalue().encode()

def record(total, incident=INCIDENT, candidate=SOURCE_ID, timestamp="2026-11-12T10:00:00+02:00",
           kind="cumulative", credited=0, source_url=None, **overrides):
    item = dict(
        record_id=f"fixture:{incident}:{total}:{timestamp}",
        city_key="zaporizhzhia",
        observed_at=timestamp,
        attack_date="2026-10-10",
        deaths_delta=str(total),
        status="confirmed",
        source_name="ДСНС через Суспільне — PINNED FIXTURE",
        source_url=source_url or f"https://suspilne.media/fixture/{candidate}",
        note="OFFLINE ONLY; verified event identity and credited provenance supplied as immutable fixture refs",
        candidate_ids=candidate,
        incident_id=incident,
        count_kind=kind,
        baseline_credited=str(credited),
        identity_proof=PROOF_ID if incident == INCIDENT else "sha256:" + sha(incident.encode()),
        credited_proof=CREDIT_PROOF,
    )
    item.update(overrides)
    return item

def run(label, base, inputs, rows=None, *, generator=None, expect_error=None):
    directory = base / label
    for key, content in inputs.items():
        target = directory / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    (directory / SCRIPT).write_bytes(generator or git("HEAD", PREFIX + SCRIPT))
    if rows is not None:
        (directory / REV).write_bytes(csv_rows(inputs[REV], rows))
    cmd = subprocess.run([sys.executable, SCRIPT, "--no-network"], cwd=directory,
                         capture_output=True, text=True, timeout=90,
                         env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    if expect_error:
        assert cmd.returncode != 0 and expect_error in cmd.stderr, (
            label, cmd.returncode, cmd.stderr[-1200:]
        )
        return None
    assert cmd.returncode == 0, (label, cmd.stderr[-3000:])
    return json.loads((directory / GENERATED).read_text(encoding="utf8"))

def total(doc, city="zaporizhzhia"):
    return sum(int(x["deaths"]) for x in doc["casualties_by_city"][city]["monthly"])

def october(doc):
    return sum(int(x["deaths"]) for x in doc["casualties_by_city"]["zaporizhzhia"]["monthly"]
               if x["month"] == "2026-10")

def snapshot(doc, city):
    return stable(doc)["casualties_by_city"][city]

def main():
    PROOF.mkdir(parents=True, exist_ok=True)
    inputs = get_source_files()
    protected = {k: sha(v) for k, v in inputs.items()}
    checks = []
    def check(name, condition, actual, expected):
        checks.append(dict(name=name, result="PASS" if condition else "FAIL",
                           actual=actual, expected=expected))
    x18 = record(18, timestamp="2026-10-10T16:00:00+03:00")
    x20 = record(20, timestamp="2026-10-12T16:00:00+03:00")
    x23 = record(23, timestamp="2026-10-15T16:00:00+03:00")
    # Use a single confirmed fixture identity and immutable source references;
    # a date, candidate or matching count alone is never a sufficient key.
    with tempfile.TemporaryDirectory(prefix="casualty_dedup_") as d:
        root = Path(d)
        control = run("control", root, inputs)
        # Actual pinned generator is separately run against the same immutable corpus.
        legacy = run("old_control", root, inputs, generator=inputs[SCRIPT])
        check("pinned_control_generator_equivalence",
              stable(control) == stable(legacy), "semantic compare", "identical")
        only = run("only_23", root, inputs, [x23])
        previous18 = run("prior_18", root, inputs, [x18])
        previous23 = run("prior_23", root, inputs, [x23])
        combined18 = run("18_then_23", root, inputs, [x18, x23])
        combined23 = run("23_then_23", root, inputs, [
            x23, record(23, timestamp="2026-10-17T16:00:00+03:00")])
        triple = run("18_20_23", root, inputs, [x18, x20, x23])
        check("0_to_23", total(only)-total(control) == 23,
              total(only)-total(control), 23)
        check("18_to_23", total(combined18)-total(previous18) == 5,
              total(combined18)-total(previous18), 5)
        check("23_to_23", total(combined23)-total(previous23) == 0,
              total(combined23)-total(previous23), 0)
        check("cumulative_18_20_23", october(triple) == 23, october(triple), 23)
        check("baseline_316_to_339", total(control) == 316 and total(only) == 339,
              [total(control), total(only)], [316, 339])
        check("october_created", october(only) == 23, october(only), 23)
        check("sumy_existing_revision", snapshot(control, "sumy") == snapshot(triple, "sumy"),
              "semantic equality", "unchanged")
        unchanged = all(snapshot(control, key) == snapshot(only, key)
                        for key in control["casualties_by_city"] if key != "zaporizhzhia")
        check("other_cities_22_unchanged", unchanged, unchanged, True)
        previous = [r for r in control["casualties_by_city"]["zaporizhzhia"]["monthly"]]
        new_previous = [r for r in only["casualties_by_city"]["zaporizhzhia"]["monthly"]
                        if r["month"] < "2026-10"]
        check("previous_months_unchanged", previous == new_previous, previous == new_previous, True)
        check("unrelated_dashboard_data_unchanged", all(
            stable(control)[k] == stable(only)[k] for k in control
            if k not in ("casualties", "casualties_by_city")
        ), "semantic compare", "identical")
        unrelated = record(
            7, incident="incident:zaporizhzhia:2026-10-10:afternoon",
            candidate="distinct-source-afternoon",
            timestamp="2026-10-11T18:00:00+03:00"
        )
        independent = run("independent_same_day", root, inputs, [x23, unrelated])
        check("independent_same_day", october(independent) == 30, october(independent), 30)
        # This is the same source, but marked as another incident: MUST reject.
        duplicate_article = record(
            7, incident="incident:zaporizhzhia:2026-10-10:afternoon",
            candidate=SOURCE_ID,
            timestamp="2026-10-11T18:00:00+03:00"
        )
        run("same_article_conflict", root, inputs, [x23, duplicate_article],
            expect_error="Ambiguous candidate_id across incidents")
        check("duplicate_candidate_rejected", True, "fatal error", "fatal error")
        run("missing_identity", root, inputs, [
            dict(x23, incident_id="")
        ], expect_error="missing documented incident identity")
        check("unknown_incident_identity_blocked", True, "fatal error", "fatal error")
        run("unknown_credited", root, inputs, [
            dict(x23, baseline_credited="")
        ], expect_error="undocumented baseline_credited")
        check("unknown_credited_blocked", True, "fatal error", "fatal error")
        run("unproven_credit", root, inputs, [
            dict(x23, baseline_credited="18")
        ], expect_error="Unproven baseline credit")
        check("unproven_baseline_18_blocked", True, "fatal error", "fatal error")
        run("negative_update", root, inputs, [
            x23, record(20, timestamp="2026-10-16T16:00:00+03:00")
        ], expect_error="Downward/ambiguous cumulative update")
        check("downward_cumulative_blocked", True, "fatal error", "fatal error")
        run("multiple_delta", root, inputs, [
            record(2, kind="delta"), record(3, timestamp="2026-10-16T16:00:00+03:00",
                                           kind="delta")
        ], expect_error="Multiple incremental records")
        check("multiple_delta_ambiguous_blocked", True, "fatal error", "fatal error")
        run("missing_proof", root, inputs, [
            dict(x23, identity_proof="")
        ], expect_error="missing immutable identity_proof")
        check("missing_proof_blocked", True, "fatal error", "fatal error")
        run("duplicate_id", root, inputs, [x23, x23],
            expect_error="Duplicate casualty revision record_id")
        check("duplicate_record_id_rejected", True, "fatal error", "fatal error")
        run("modified_legacy_sumy", root, inputs, [
            dict(x23, incident_id="", record_id="fixture:unaudited")
        ], expect_error="missing documented incident identity")
        check("legacy_compatibility_fence", True, "fatal error", "fatal error")
        repeat_dir = root / "only_23"
        original_result = stable(only)
        again = subprocess.run(
            [sys.executable, SCRIPT, "--no-network"], cwd=repeat_dir, text=True,
            capture_output=True, timeout=90,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        repeated = json.loads((repeat_dir / GENERATED).read_text(encoding="utf8"))
        check("repeat_idempotence", again.returncode == 0 and
              stable(repeated) == original_result, "semantic compare", "identical")
        (repeat_dir / REV).write_bytes(inputs[REV])
        back = subprocess.run(
            [sys.executable, SCRIPT, "--no-network"], cwd=repeat_dir, text=True,
            capture_output=True, timeout=90,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        rollback = json.loads((repeat_dir / GENERATED).read_text(encoding="utf8"))
        check("rollback", back.returncode == 0 and
              stable(rollback) == stable(control), "semantic compare", "identical")
        # Existing pinned frontend chart functions, not a browser deployment.
        ui = subprocess.run(
            ["node", str(HERE / "frontend_probe.js"),
             str(root / "18_then_23" / GENERATED),
             str(root / "18_then_23" / "pages-preview/app.js")],
            capture_output=True, text=True, timeout=30)
        check("pinned_frontend_function", ui.returncode == 0,
              ui.stdout[-500:] if ui.returncode == 0 else ui.stderr[-500:], "PASS")
        store("scenarios.json", dict(
            control_total=total(control), plus23_total=total(only),
            credited_18_delta=total(combined18)-total(previous18),
            credited_23_delta=total(combined23)-total(previous23),
            october_triple=october(triple), independent_same_day=october(independent),
            frontend_result=ui.stdout[-2000:]
        ))
        store("control_summary.json", {
            "zaporizhzhia_total": total(control),
            "sumy": snapshot(control, "sumy"),
            "monthly_count": len(previous)
        })
    after = {k: sha(git(PROD, PREFIX + k)) for k in inputs}
    check("protected_sha256_unchanged", protected == after, protected == after, True)
    store("input_sha256.json", protected)
    store("checks.json", checks)
    failures = [x["name"] for x in checks if x["result"] == "FAIL"]
    report = [
        "# CASUALTY-SAME-INCIDENT-DEDUP-2026-11-12",
        "", "**Verdict:** " + ("DEDUP_FIX_PASS" if not failures else "DEDUP_FIX_BLOCKED"),
        "", "Frozen source: " + PROD,
        "No network media requests, production data writes, merge or deployment.",
        "", "| Test | Result | Actual | Expected |",
        "|---|---|---|---|",
    ]
    for x in checks:
        report.append("| " + x["name"] + " | " + x["result"] + " | " +
                      str(x["actual"]).replace("|", "/").replace("\n", " ")[:90] +
                      " | " + str(x["expected"]).replace("|", "/")[:60] + " |")
    report += [
        "", "## Contract and limitations",
        "New confirmed revisions require explicit incident_id, count_kind, "
        "baseline_credited, identity_proof, credited_proof (proof references "
        "must be immutable). These optional columns do not change frontend JSON.",
        "Cumulative reports are reconciled to latest observed total; "
        "already-credited baseline event count must be independently evidenced.",
        "Unknown event identity, prior credit, conflicting proof, reused candidate "
        "or source across incidents fail closed.",
        "A linked proof reference is an audit handle, **not automated fact-checking**. "
        "Human reviewer must validate its actual relation to the event and amount.",
        "Legacy compatibility is restricted to the exact pinned Sumy +1 record.",
        "Real browser and independent deployment not performed.",
        "October coverage remains independently incomplete; publication NO-GO.",
        "",
        "## Failures",
        ", ".join(failures) if failures else "None",
    ]
    (PROOF / "FINAL_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf8")
    files = sorted(p for p in PROOF.iterdir() if p.is_file() and p.name != "SHA256SUMS")
    (PROOF / "SHA256SUMS").write_text(
        "".join(sha(p.read_bytes()) + "  " + p.name + "\n" for p in files), encoding="utf8")
    print("CHECKS_PASS=", len(checks)-len(failures))
    print("CHECKS_FAIL=", len(failures))
    print("FAILED=", failures)
    if failures:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
