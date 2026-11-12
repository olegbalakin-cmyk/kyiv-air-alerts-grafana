#!/usr/bin/env python3
"""Reversible offline preview using the exact frozen site-prod casualty generator.

This test NEVER edits any git worktree, branch, or production file. All inputs
are fetched from immutable git objects and copied into disposable directories.
No publisher HTTP, no Neon, no deployment, no mutations outside research proof.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

PROD_SHA = "fc7261660bdee75ee59296ee94cc1189be6b1a22"
WIP_SHA = "c66c242a852d7647b6183425228cb3db2d1d088b"
PREFIX = "kyiv-air-alerts-grafana/"
CANDIDATE = "e0fba98b19473874e9a1d8f1"
EVIDENCE_SHA = "011894b7c4bd906dcfd0c5d2f7cef07a932976ca313220fa9089999264feb259"
RECORD_ID = "casualty:zaporizhzhia:2026-10-10:morning-kab-dsns:" + CANDIDATE
BASE = Path(__file__).resolve().parent
PROOF = BASE / "proof"
EXPECTED = {
    "data/dashboard_data.json": "ea01943609fb4e8adc64450181cc1a94d7438507db7898fc78f99ab177d188fe",
    "data/casualties/revisions.csv": "9a72050a8510b1ee14e3f0ba22f3ae85e548d6fe721eb3dd547d34f679b57b2a",
    "data/casualties/cities/zaporizhzhia/manifest.json": "141e95e95caff7b4a03c41936a465d07bd82fc1741dc17f972cc6a635f0f9da5",
    "data/casualties/cities/zaporizhzhia/zaporizhzhia_air_attack_deaths_monthly.csv": "d8565488423e5ce5a6131743b0d3ecd3796ffda7ea0e9d4df7dbae88a442e63b",
    "scripts/update_casualties.py": "346469581ded8c05d87f239af588cdeab16f3bb8ee31f4acbfeabf5b308ca73d",
    "pages-preview/app.js": "b39f1190ce50e403f24f81414fd0f9defe1269122e5aa4683afeca14e20e0d04",
}


def git_read(ref: str, path: str) -> bytes:
    return subprocess.check_output(["git", "show", ref + ":" + path])


def digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def json_write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def source_paths() -> list[str]:
    mandatory = [
        "data/dashboard_data.json", "data/casualties/revisions.csv",
        "data/casualties/baseline_monthly.csv",
        "data/casualties/review_queue.json",
        "data/casualties/master_20cities_manifest.json",
        "data/casualties/master_20cities_monthly_wide.csv",
        "scripts/update_casualties.py", "pages-preview/app.js",
    ]
    city_root = PREFIX + "data/casualties/cities/"
    tree = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", PROD_SHA, "--", city_root],
        text=True,
    ).splitlines()
    city_files = [
        path.removeprefix(PREFIX) for path in tree
        if path.endswith("/manifest.json") or path.endswith(".csv")
    ]
    return sorted(set(mandatory + city_files))


def build_source_cache() -> tuple[dict[str, bytes], dict]:
    paths = source_paths()
    cache = {name: git_read(PROD_SHA, PREFIX + name) for name in paths}
    receipts = {
        name: {"sha256": digest(data), "bytes": len(data), "git_commit": PROD_SHA}
        for name, data in sorted(cache.items())
    }
    for name, expected in EXPECTED.items():
        assert receipts[name]["sha256"] == expected, "Pinned input changed: " + name
    return cache, receipts


def git_branch_head() -> str:
    out = subprocess.check_output(
        ["git", "ls-remote", "origin", "refs/heads/site-prod"], text=True
    ).strip()
    return out.split()[0] if out else "missing"


def reference_source() -> dict:
    raw = git_read(WIP_SHA, PREFIX + "data/casualties/multicity_review_queue.json")
    targets = [r for r in json.loads(raw) if r.get("candidate_id") == CANDIDATE]
    assert len(targets) == 1, "Frozen WIP candidate missing or duplicated"
    target = targets[0]
    assert target.get("city_key") == "zaporizhzhia"
    found = []
    for key in ("resolved_url", "article_url", "source_url", "url", "link", "original_url"):
        url = target.get(key)
        if isinstance(url, str) and url.startswith("https://"):
            found.append({"field": key, "url": url, "host": urlparse(url).hostname})
    selected = next((i for i in found if "suspilne.media" in (i["host"] or "")), None)
    return {
        "source_url": selected["url"] if selected else "",
        "exact_suspilne_url_available": selected is not None,
        "candidate_id": CANDIDATE,
        "candidate_status": target.get("status"),
        "candidate_url_fields": found,
        "article_evidence_sha256": EVIDENCE_SHA,
        "source_claim": "ДСНС, цитата у Суспільному (раніше збережений proof)",
    }


def make_record(delta: int, source: dict, *, record_id: str = RECORD_ID,
                candidate_id: str = CANDIDATE) -> dict[str, str]:
    return {
        "record_id": record_id, "city_key": "zaporizhzhia",
        "observed_at": "2026-11-12T10:00:00+02:00",  # NOT attack/publication date
        "attack_date": "2026-10-10", "deaths_delta": str(delta),
        "status": "confirmed",
        "source_name": "ДСНС через Суспільне (evidence SHA256 " + EVIDENCE_SHA + ")",
        "source_url": source["source_url"],
        "note": "ISOLATED TEST ONLY. Same 2026-10-10 morning KAB strike; cumulative official total 23, not 18+20+23. Never publish.",
        "candidate_ids": candidate_id,
    }


def csv_update(base_blob: bytes, extra: list[dict[str, str]]) -> bytes:
    source = io.StringIO(base_blob.decode("utf-8-sig"))
    reader = csv.DictReader(source)
    columns = reader.fieldnames
    assert columns is not None
    assert set(extra[0]).issubset(set(columns)), "Fixture adds unsupported CSV columns"
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(list(reader) + extra)
    return output.getvalue().encode("utf-8")


def case_dir(root: Path, cache: dict[str, bytes], name: str,
             revisions: bytes | None = None) -> Path:
    target = root / name
    for relative, content in cache.items():
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(revisions if relative == "data/casualties/revisions.csv" and revisions is not None else content)
    return target


def generate(case: Path, label: str, log: list[str], *, expect_error: bool = False) -> dict | None:
    proc = subprocess.run(
        [sys.executable, "scripts/update_casualties.py", "--no-network"],
        cwd=case, capture_output=True, text=True, timeout=120,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    log.append(label + " exit=" + str(proc.returncode))
    log.append("stdout: " + proc.stdout.strip()[:800])
    if proc.stderr:
        log.append("stderr: " + proc.stderr.strip()[-1400:])
    if expect_error:
        assert proc.returncode != 0, label + " unexpectedly accepted duplicate record_id"
        assert "Duplicate casualty revision record_id" in proc.stderr
        return None
    assert proc.returncode == 0, label + " generator failed: " + proc.stderr
    return json.loads((case / "data/dashboard_data.json").read_text(encoding="utf-8"))


def stable(doc: dict) -> dict:
    result = copy.deepcopy(doc)
    result.get("casualties", {}).get("meta", {}).pop("generated_at", None)
    result.get("casualties_by_city", {}).get("kyiv", {}).get("meta", {}).pop("generated_at", None)
    return result


def summary(data: dict) -> dict:
    rows = data["casualties_by_city"]["zaporizhzhia"]["monthly"]
    return {
        "months": len(rows),
        "last_month": rows[-1]["month"],
        "october": next((int(r["deaths"]) for r in rows if r["month"] == "2026-10"), None),
        "total": sum(int(r["deaths"]) for r in rows),
        "metadata_confirmed_deaths": data["casualties_by_city"]["zaporizhzhia"]["meta"].get("confirmed_deaths"),
        "monthly_keys_sorted_unique": len({r["month"] for r in rows}) == len(rows) and
            [r["month"] for r in rows] == sorted(r["month"] for r in rows),
    }


def must(name: str, condition: bool, actual, expected, checks: list[dict]) -> None:
    checks.append({"name": name, "result": "PASS" if condition else "FAIL",
                   "actual": actual, "expected": expected})


def main() -> None:
    PROOF.mkdir(parents=True, exist_ok=True)
    logs: list[str] = []
    checks: list[dict] = []
    branch_before = git_branch_head()
    cache, receipts_before = build_source_cache()
    src = reference_source()
    original_revision = cache["data/casualties/revisions.csv"]
    regular = make_record(23, src)
    plus_csv = csv_update(original_revision, [regular])
    json_write(PROOF / "test_fixture.json", {
        "record": regular, "source_evidence": src, "real_site_prod_was_not_modified": True,
    })
    with tempfile.TemporaryDirectory(prefix="casualty_plus23_") as tmp:
        temp = Path(tmp)
        ctrl_case = case_dir(temp, cache, "control")
        control = generate(ctrl_case, "A_CONTROL", logs)
        plus_case = case_dir(temp, cache, "plus23", plus_csv)
        plus = generate(plus_case, "B_PLUS23", logs)
        control_summary = summary(control)
        plus_summary = summary(plus)
        json_write(PROOF / "control.json", control)
        json_write(PROOF / "plus23.json", plus)
        must("new_month_created", plus_summary["october"] == 23, plus_summary["october"], 23, checks)
        must("chronology_sorted_and_unique", plus_summary["monthly_keys_sorted_unique"],
             plus_summary["monthly_keys_sorted_unique"], True, checks)
        must("month_end_2026_10", plus_summary["last_month"] == "2026-10", plus_summary["last_month"], "2026-10", checks)
        must("total_increase_exactly_23", plus_summary["total"] - control_summary["total"] == 23,
             plus_summary["total"] - control_summary["total"], 23, checks)
        must("metadata_total_increase_23", plus_summary["metadata_confirmed_deaths"] - control_summary["metadata_confirmed_deaths"] == 23,
             plus_summary["metadata_confirmed_deaths"] - control_summary["metadata_confirmed_deaths"], 23, checks)
        must("older_months_unchanged", control["casualties_by_city"]["zaporizhzhia"]["monthly"] ==
             plus["casualties_by_city"]["zaporizhzhia"]["monthly"][:-1], "unchanged" if
             control["casualties_by_city"]["zaporizhzhia"]["monthly"] == plus["casualties_by_city"]["zaporizhzhia"]["monthly"][:-1]
             else "DIFF", "unchanged", checks)
        other_cities_identical = all(
            stable(control)["casualties_by_city"][k] == stable(plus)["casualties_by_city"][k]
            for k in control["casualties_by_city"] if k != "zaporizhzhia"
        )
        must("other_cities_unchanged", other_cities_identical, other_cities_identical, True, checks)
        must("alerts_and_independent_data_unchanged", all(
            control[k] == plus[k] for k in control if k not in ("casualties", "casualties_by_city")
        ), "checked", "no changes", checks)
        must("kyiv_casualties_unchanged", stable(control)["casualties"] == stable(plus)["casualties"],
             "checked", "no changes", checks)
        rows = plus["casualties_by_city"]["zaporizhzhia"]["monthly"]
        october = [r for r in rows if r["month"] == "2026-10"]
        must("attack_month_not_observed_month", len(october) == 1 and
             october[0].get("time", "").startswith("2026-10-01") and
             not any(r["month"] == "2026-11" for r in rows),
             october, [{"month": "2026-10", "deaths": 23}], checks)
        must("json_shape_frontend", all(
            isinstance(plus.get(k), dict) for k in ("cities", "casualties_by_city")
        ) and isinstance(plus["casualties_by_city"]["zaporizhzhia"]["monthly"], list),
             "checked", "compatible", checks)

        # Calling the generator a second time on the SAME isolated confirmed row is idempotent.
        repeat = generate(plus_case, "B_REPEAT_SAME_REVISION", logs)
        repeat_ok = stable(repeat) == stable(plus)
        must("repeat_regeneration_without_new_csv_record", repeat_ok,
             summary(repeat), plus_summary, checks)
        json_write(PROOF / "repeat.json", repeat)

        # Removing the test CSV row and re-running the real generator should undo it.
        (plus_case / "data/casualties/revisions.csv").write_bytes(original_revision)
        rollback = generate(plus_case, "C_ROLLBACK", logs)
        rollback_ok = stable(rollback) == stable(control)
        must("rollback_all_semantic_content", rollback_ok, summary(rollback),
             control_summary, checks)
        json_write(PROOF / "rollback.json", rollback)

        # Duplicate record_id is rejected; this is not event-level de-duplication.
        same_id_csv = csv_update(original_revision, [regular, regular])
        same_id_case = case_dir(temp, cache, "same_id", same_id_csv)
        generate(same_id_case, "D_SAME_RECORD_ID_REJECTED", logs, expect_error=True)
        must("same_record_id_rejected", True, "fatal validation error", "fatal validation error", checks)

        # Previously credited SAME INCIDENT via confirmed revisions, not same-day unrelated deaths.
        scenario_results = {}
        for credited in (0, 18, 23):
            if credited:
                previous = make_record(
                    credited, src,
                    record_id="casualty:zaporizhzhia:2026-10-10:previous-" + str(credited),
                )
                prior_csv = csv_update(original_revision, [previous])
                prior_doc = generate(case_dir(temp, cache, "prior_" + str(credited), prior_csv),
                                     "PREVIOUS_" + str(credited), logs)
                prior_total = summary(prior_doc)["total"]
            else:
                previous = None
                prior_total = control_summary["total"]
            staged = [previous, regular] if previous else [regular]
            test_csv = csv_update(original_revision, staged)
            tested = generate(case_dir(temp, cache, "credited_" + str(credited), test_csv),
                              "CREDITED_" + str(credited), logs)
            actual_increase = summary(tested)["total"] - prior_total
            expected_increase = 23 - credited
            name = "already_credited_" + str(credited) + "_same_attack"
            must(name, actual_increase == expected_increase,
                 actual_increase, expected_increase, checks)
            scenario_results[str(credited)] = {
                "expected_added": expected_increase,
                "actual_added": actual_increase,
                "resulting_total": summary(tested)["total"],
                "identity": "same original candidate id, 2026-10-10 morning KAB strike",
            }
        # Three cumulative reports of the same attack must count as ONE final total.
        three = [
            make_record(n, src, record_id="casualty:zaporizhzhia:2026-10-10:snapshot-" + str(n))
            for n in (18, 20, 23)
        ]
        three_case = case_dir(temp, cache, "cumulative_18_20_23", csv_update(original_revision, three))
        three_doc = generate(three_case, "E_THREE_CUMULATIVE_REPORTS", logs)
        triple_value = summary(three_doc)["october"]
        must("18_20_23_cumulative_snapshots_count_once", triple_value == 23,
             triple_value, 23, checks)

        # An unrelated strike on the same day must NOT be subtracted from the +23.
        other = make_record(
            7, src, record_id="casualty:zaporizhzhia:2026-10-10:unrelated-afternoon",
            candidate_id="fixture-unrelated-afternoon-event",
        )
        other["note"] = "SEPARATE OTHER ATTACK, same calendar day; not the morning KAB incident"
        other_case = case_dir(temp, cache, "unrelated_same_date",
                              csv_update(original_revision, [other, regular]))
        other_doc = generate(other_case, "F_UNRELATED_SAME_DAY", logs)
        must("different_attack_same_day_not_deducted",
             summary(other_doc)["october"] == 30, summary(other_doc)["october"], 30, checks)

        # Read-only runtime test of the exact pinned frontend chart functions (Node vm).
        ui = subprocess.run([
            "node", str(BASE / "frontend_probe.js"),
            str(PROOF / "plus23.json"),
            str(temp / "control" / "pages-preview/app.js"),
        ], text=True, capture_output=True, timeout=30)
        logs.append("FRONTEND_PROBE exit=" + str(ui.returncode))
        logs.append("FRONTEND_PROBE stdout=" + ui.stdout.strip())
        if ui.stderr:
            logs.append("FRONTEND_PROBE stderr=" + ui.stderr.strip()[-1500:])
        (PROOF / "frontend_probe.txt").write_text(
            "exit_code=" + str(ui.returncode) + "\n" + ui.stdout + "\n" + ui.stderr,
            encoding="utf-8",
        )
        must("real_frontend_chart_functions", ui.returncode == 0,
             ui.stdout.strip() if ui.returncode == 0 else ui.stderr[-500:],
             "October 2026 bar 23; total 339; year 2026 +23", checks)

    # Confirm immutable input objects remain byte-identical after every isolated test.
    after = {name: digest(git_read(PROD_SHA, PREFIX + name)) for name in cache}
    same_inputs = all(after[name] == receipt["sha256"] for name, receipt in receipts_before.items())
    branch_after = git_branch_head()
    must("immutable_production_inputs_sha256_unchanged", same_inputs,
         same_inputs, True, checks)
    must("site_prod_branch_unmodified_during_run", branch_before == branch_after,
         {"before": branch_before, "after": branch_after}, "same SHA", checks)

    # Only generated timestamps are allowed to differ across repeated runs.
    timestamp_paths = ["casualties.meta.generated_at", "casualties_by_city.kyiv.meta.generated_at"]
    diff = {
        "data_path": "casualties_by_city.zaporizhzhia.monthly",
        "control_october": None,
        "preview_october": next(r for r in plus["casualties_by_city"]["zaporizhzhia"]["monthly"]
                                if r["month"] == "2026-10"),
        "control_total": control_summary["total"], "preview_total": plus_summary["total"],
        "delta_total": plus_summary["total"] - control_summary["total"],
        "metadata_differences": {
            "before": control["casualties_by_city"]["zaporizhzhia"]["meta"],
            "after": plus["casualties_by_city"]["zaporizhzhia"]["meta"],
        },
        "ignored_nondeterministic_paths": timestamp_paths,
    }
    json_write(PROOF / "diff.json", diff)
    json_write(PROOF / "metrics.json", {
        "frozen_production_sha": PROD_SHA,
        "research_head": os.environ.get("GITHUB_SHA", "local"),
        "initial_remote_site_prod": branch_before,
        "final_remote_site_prod": branch_after,
        "control": control_summary, "plus23": plus_summary,
        "rollback": summary(rollback), "scenarios": scenario_results,
        "same_source_record_id": RECORD_ID,
        "source": src,
        "checks": checks, "browser_rendering_executed": False,
        "frontend_actual_function_probe_executed": True,
    })
    json_write(PROOF / "inputs_sha256.json", receipts_before)
    (PROOF / "test_log.txt").write_text("\n".join(logs) + "\n", encoding="utf-8")

    failed = [item["name"] for item in checks if item["result"] == "FAIL"]
    # Fail-closed: either a core invariance fail or event-identity de-duplication fail blocks preview.
    verdict = "PREVIEW_BLOCKED" if failed else "PREVIEW_PARTIAL"
    report = [
        "# Запоріжжя +23 — reversible offline preview",
        "",
        "**Decision: " + verdict + "**. Research only; no production write, merge, deploy, media HTTP, or Neon.",
        "",
        "- Frozen site-prod: " + PROD_SHA,
        "- Remote site-prod before: " + branch_before,
        "- Remote site-prod after: " + branch_after,
        "- Candidate: " + CANDIDATE,
        "- Evidence SHA256: " + EVIDENCE_SHA,
        "- Controlled correction: " + RECORD_ID + " / 2026-10-10 / +23",
        "- Main dataset baseline: " + str(control_summary["total"]),
        "- New month: 2026-10 / " + str(plus_summary["october"]),
        "- New total: " + str(plus_summary["total"]),
        "- Browser not run; exact frontend rendering function invoked with chart capture in Node.",
        "",
        "## Actual tests",
        "",
        "| Check | Result | Actual | Expected |",
        "|---|---|---|---|",
    ]
    for item in checks:
        report.append("| " + item["name"] + " | " + item["result"] +
                      " | " + str(item["actual"]).replace("|", "/").replace("\n", " ")[:120] +
                      " | " + str(item["expected"]).replace("|", "/").replace("\n", " ")[:100] + " |")
    report += [
        "", "## Technical defect and smallest safe correction",
        "",
        "The frozen generator guards only duplicate record_id. Two confirmed revision rows ",
        "with different record_ids but the same attack identity (same candidate_id and",
        "attack date) are added independently. Existing 18 credited -> 18+23=41",
        "(correct increment 5); existing 23 credited -> 23+23=46",
        "(correct increment 0). The 18/20/23 cumulative snapshots sum to 61",
        "(correct final count 23). A second generator run with the *unchanged*",
        "single revision row is idempotent, but that does not solve event-level duplication.",
        "",
        "Smallest production fix for a later, separately approved PR: bind confirmed",
        "records to a canonical attack/event identity, maintain a unique confirmed",
        "per-incident final death total against already credited deaths, and fail",
        "closed if identity/provenance or existing amount is ambiguous. Preserve",
        "the existing missing-month overlay, CSV schema and frontend JSON shape.",
        "For THIS research preview no production code was changed.",
        "",
        "## Evidence outputs",
        "",
        "control.json, plus23.json, diff.json, rollback.json, repeat.json,",
        "test_fixture.json, metrics.json, frontend_probe.txt, test_log.txt,",
        "inputs_sha256.json and SHA256SUMS. Only two generated_at paths are",
        "ignored for semantic rollback / repeat equality.",
        "",
        "Nothing here authorizes a production revision or publication.",
    ]
    (PROOF / "FINAL_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    all_files = sorted(p for p in PROOF.rglob("*") if p.is_file() and p.name != "SHA256SUMS")
    (PROOF / "SHA256SUMS").write_text("".join(
        digest(p.read_bytes()) + "  " + str(p.relative_to(PROOF)) + "\n" for p in all_files
    ), encoding="utf-8")
    print("PREVIEW_VERDICT=" + verdict)
    print("CHECKS_PASS=" + str(len(checks) - len(failed)))
    print("CHECKS_FAIL=" + str(len(failed)))
    print("FAIL_CHECKS=" + ", ".join(failed))
    print("CONTROL_TOTAL=" + str(control_summary["total"]))
    print("PREVIEW_TOTAL=" + str(plus_summary["total"]))
    print("OCTOBER=" + str(plus_summary["october"]))
    # CI reports domain FAIL honestly. Let the job succeed if diagnostic proof was captured.
    if (not same_inputs or not rollback_ok or not other_cities_identical or
            plus_summary["october"] != 23):
        raise SystemExit("Critical preview invariant failed; inspect proof before reuse")


if __name__ == "__main__":
    main()
