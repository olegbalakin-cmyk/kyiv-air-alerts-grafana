#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
PRODUCTION_ROOT = Path(os.environ["PRODUCTION_ROOT"]).resolve()
ARTIFACT = ROOT / "research" / "casualty_review_promotion_production_integration_proof_2026-10-08.json"
INTEGRATION_BRANCH = "casualty-review-promotion-production-integration-2026-10-08"
INTEGRATION_BASE_SITE_PROD_SHA = "1b7214223e5d6539ae298c8da5903538b3bae25b"
ISOLATED_COMMIT = "6222ce2ca9837284ccf6759d1c2e81b3a33f6dc2"
ISOLATED_UPDATE_BLOB = "5cbcced1402be3d5707e8b1510186a98d150b2ff"
ISOLATED_REVIEW_BLOB = "57c67af1ce108222c9a8dc0fefe34d67f9d0e23e"
ISOLATED_TEST_BLOB = "8c09c60b6a9ee1067b1bb241435a1f26ed3e79bb"
ISOLATED_REVISIONS_BLOB = "8c4674db505b5cccfcd240c6474f8e0e92919c80"
PRE_REPAIR_UPDATE_BLOB = "32c9f99b17a1d8da5f11d862b9825370366060ee"
REQUIRED_BASELINE_BLOBS = {
    "kyiv": ("kyiv-air-alerts-grafana/data/casualties/baseline_monthly.csv", "52238c1e72bdba3b06fc0c0469d699f018d8e353"),
    "master_20city": ("kyiv-air-alerts-grafana/data/casualties/master_20cities_monthly_wide.csv", "f3b7fdf6750e12d7b9af05ffd094bb47aa9ed801"),
    "odesa": ("kyiv-air-alerts-grafana/data/casualties/cities/odesa/odesa_air_attack_deaths_monthly.csv", "b51a2cd204b3a3c977025e7acd9311ba98e3a317"),
    "zaporizhzhia": ("kyiv-air-alerts-grafana/data/casualties/cities/zaporizhzhia/zaporizhzhia_air_attack_deaths_monthly.csv", "1b32d8808069b4499fda35b092fd56f51c64583f"),
    "kherson": ("kyiv-air-alerts-grafana/data/casualties/cities/kherson/kherson_air_attack_deaths_monthly.csv", "5520e34c5d0696a167ed0eea378a8648c8836c49"),
}
QUEUE_PATH = "kyiv-air-alerts-grafana/data/casualties/multicity_review_queue.json"
REVISION_HEADER = "record_id,city_key,observed_at,attack_date,deaths_delta,status,source_name,source_url,note,candidate_ids\n"


def run(cmd: list[str], *, cwd: Path | None = None, input_bytes: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd or REPO_ROOT),
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )


def git_text(*args: str) -> str:
    return run(["git", *args], cwd=REPO_ROOT).stdout.decode("utf-8").strip()


def git_bytes(*args: str) -> bytes:
    return run(["git", *args], cwd=REPO_ROOT).stdout


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_revision_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def canonical_month_map(dashboard: dict) -> dict[str, int]:
    out: dict[str, int] = {}
    cities = dashboard.get("casualties_by_city") or {}
    for city_key, series in cities.items():
        for row in series.get("monthly") or []:
            month = str(row.get("month") or "")
            key = f"{city_key}|{month}"
            if key in out:
                raise AssertionError(f"duplicate city/month row: {key}")
            out[key] = int(row.get("deaths") or 0)
    return out


def canonical_month_hash(month_map: dict[str, int]) -> str:
    payload = json.dumps(month_map, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(payload)


def dashboard_schema_ok(before: dict, after: dict) -> bool:
    if set(before) != set(after):
        return False
    before_cities = before.get("casualties_by_city")
    after_cities = after.get("casualties_by_city")
    if not isinstance(before_cities, dict) or not isinstance(after_cities, dict):
        return False
    if set(before_cities) != set(after_cities):
        return False
    for city in before_cities:
        if not isinstance(after_cities[city], dict):
            return False
        if not isinstance(after_cities[city].get("monthly"), list):
            return False
        for row in after_cities[city]["monthly"]:
            if not isinstance(row, dict) or not {"time", "month", "deaths"}.issubset(row):
                return False
    if not isinstance(after.get("casualties"), dict):
        return False
    if not isinstance(after["casualties"].get("monthly"), list):
        return False
    return True


def run_builder(root: Path) -> str:
    proc = run([sys.executable, "scripts/update_casualties.py", "--no-network"], cwd=root)
    return proc.stdout.decode("utf-8", errors="replace")


def review_cli(root: Path, queue: Path, revisions: Path, *args: str) -> dict:
    proc = run(
        [
            sys.executable,
            str(root / "scripts" / "review_casualty_candidates.py"),
            "--queue",
            str(queue),
            "--revisions",
            str(revisions),
            *args,
        ],
        cwd=root,
    )
    return json.loads(proc.stdout.decode("utf-8"))


def copy_scenario_root(source: Path, destination: Path) -> None:
    (destination / "scripts").mkdir(parents=True)
    (destination / "data").mkdir(parents=True)
    shutil.copy2(source / "scripts" / "update_casualties.py", destination / "scripts" / "update_casualties.py")
    shutil.copy2(source / "scripts" / "review_casualty_candidates.py", destination / "scripts" / "review_casualty_candidates.py")
    shutil.copy2(source / "data" / "dashboard_data.json", destination / "data" / "dashboard_data.json")
    shutil.copytree(source / "data" / "casualties", destination / "data" / "casualties")


def write_queue(path: Path, items: list[dict]) -> None:
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def candidate(candidate_id: str, city_key: str, url: str) -> dict:
    return {
        "candidate_id": candidate_id,
        "city_key": city_key,
        "city": city_key,
        "status": "needs_review",
        "url": url,
        "title": f"Synthetic candidate {candidate_id}",
        "snippet": "Synthetic fixture only; explicit human disposition is required.",
        "first_discovered_at": "2026-10-08T10:00:00Z",
        "last_seen_at": "2026-10-08T10:00:00Z",
        "trigger_episode_ids": ["synthetic-episode"],
        "trigger_check_labels": ["24h"],
    }


def main() -> None:
    integration_head = git_text("rev-parse", "HEAD")
    main_head = git_text("rev-parse", "origin/main")
    site_prod_head = git_text("rev-parse", "origin/site-prod")
    wip_head = git_text("rev-parse", "origin/multicity-wip-2026-09-16")

    integrated_blobs = {
        "update_casualties.py": git_text("rev-parse", "HEAD:kyiv-air-alerts-grafana/scripts/update_casualties.py"),
        "review_casualty_candidates.py": git_text("rev-parse", "HEAD:kyiv-air-alerts-grafana/scripts/review_casualty_candidates.py"),
        "test_casualty_review_promotion.py": git_text("rev-parse", "HEAD:kyiv-air-alerts-grafana/tests/test_casualty_review_promotion.py"),
        "revisions.csv": git_text("rev-parse", "HEAD:kyiv-air-alerts-grafana/data/casualties/revisions.csv"),
    }
    expected_integrated_blobs = {
        "update_casualties.py": ISOLATED_UPDATE_BLOB,
        "review_casualty_candidates.py": ISOLATED_REVIEW_BLOB,
        "test_casualty_review_promotion.py": ISOLATED_TEST_BLOB,
        "revisions.csv": ISOLATED_REVISIONS_BLOB,
    }
    isolated_semantics_preserved = integrated_blobs == expected_integrated_blobs
    assert isolated_semantics_preserved, (integrated_blobs, expected_integrated_blobs)

    site_prod_pre_repair_blob = git_text("rev-parse", "origin/site-prod:kyiv-air-alerts-grafana/scripts/update_casualties.py")
    assert site_prod_pre_repair_blob == PRE_REPAIR_UPDATE_BLOB, site_prod_pre_repair_blob

    workflow_blobs = {
        "casualty_monitor": git_text("rev-parse", "origin/main:.github/workflows/casualty-monitor-wip.yml"),
        "production_update": git_text("rev-parse", "origin/main:.github/workflows/update-netlify-site.yml"),
        "legacy_main_update": git_text("rev-parse", "origin/main:.github/workflows/update.yml"),
    }
    casualty_monitor_text = git_bytes("show", "origin/main:.github/workflows/casualty-monitor-wip.yml").decode("utf-8")
    production_update_text = git_bytes("show", "origin/main:.github/workflows/update-netlify-site.yml").decode("utf-8")
    assert "ref: multicity-wip-2026-09-16" in casualty_monitor_text
    assert "python scripts/monitor_casualty_candidates.py" in casualty_monitor_text
    assert "ref: site-prod" in production_update_text
    assert "python scripts/update_casualties.py" in production_update_text
    assert "git push origin HEAD:site-prod" in production_update_text

    workflow_paths = git_text("ls-tree", "-r", "--name-only", "origin/main", ".github/workflows").splitlines()
    scheduled_auto_confirm_hits: list[dict] = []
    for path in workflow_paths:
        text_value = git_bytes("show", f"origin/main:{path}").decode("utf-8", errors="replace")
        if "schedule:" not in text_value:
            continue
        if (
            "review_casualty_candidates.py" in text_value
            or "promote_reviewed" in text_value
            or re.search(r"--status(?:=|\s+)confirmed\b", text_value)
        ):
            scheduled_auto_confirm_hits.append({"path": path})
    scheduled_can_auto_confirm = bool(scheduled_auto_confirm_hits)
    assert not scheduled_can_auto_confirm, scheduled_auto_confirm_hits

    queue_bytes = git_bytes("show", f"origin/multicity-wip-2026-09-16:{QUEUE_PATH}")
    queue_blob = git_text("rev-parse", f"origin/multicity-wip-2026-09-16:{QUEUE_PATH}")
    queue = json.loads(queue_bytes.decode("utf-8"))
    status_counts = dict(sorted(Counter(str(item.get("status") or "<missing>") for item in queue if isinstance(item, dict)).items()))
    needs_review = [item for item in queue if isinstance(item, dict) and item.get("status") == "needs_review"]
    needs_with_source_url = sum(1 for item in needs_review if item.get("url") or item.get("source_url"))
    needs_with_review_disposition = sum(1 for item in needs_review if item.get("review_disposition"))
    needs_with_approval_like_fields = sum(
        1
        for item in needs_review
        if item.get("record_id") or item.get("attack_date") or item.get("deaths_delta")
    )

    baseline_blobs = {}
    integrated_baseline_blobs = {}
    historical_baseline_blobs_changed = False
    for key, (path, expected) in REQUIRED_BASELINE_BLOBS.items():
        prod_blob = git_text("rev-parse", f"origin/site-prod:{path}")
        head_blob = git_text("rev-parse", f"HEAD:{path}")
        baseline_blobs[key] = prod_blob
        integrated_baseline_blobs[key] = head_blob
        if prod_blob != expected or head_blob != expected:
            historical_baseline_blobs_changed = True
    assert not historical_baseline_blobs_changed, (baseline_blobs, integrated_baseline_blobs)

    prod_revisions_bytes = git_bytes("show", "origin/site-prod:kyiv-air-alerts-grafana/data/casualties/revisions.csv")
    prod_revision_rows_before = max(0, len(prod_revisions_bytes.decode("utf-8-sig").splitlines()) - 1)
    assert prod_revision_rows_before == 0, prod_revision_rows_before

    before_dashboard = read_json(PRODUCTION_ROOT / "data" / "dashboard_data.json")
    before_months = canonical_month_map(before_dashboard)
    before_city_keys = set((before_dashboard.get("casualties_by_city") or {}).keys())
    assert len(before_city_keys) == 23, len(before_city_keys)
    before_noncasualty = {k: v for k, v in before_dashboard.items() if k not in {"casualties", "casualties_by_city"}}
    before_noncasualty_hash = sha256_bytes(json.dumps(before_noncasualty, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))

    zero_build_stdout = run_builder(PRODUCTION_ROOT)
    after_dashboard = read_json(PRODUCTION_ROOT / "data" / "dashboard_data.json")
    after_months = canonical_month_map(after_dashboard)
    after_city_keys = set((after_dashboard.get("casualties_by_city") or {}).keys())
    zero_mismatches = [key for key in sorted(set(before_months) | set(after_months)) if before_months.get(key) != after_months.get(key)]
    assert before_city_keys == after_city_keys and len(after_city_keys) == 23
    assert not zero_mismatches, zero_mismatches[:10]
    assert len(after_months) == len(before_months)
    after_noncasualty = {k: v for k, v in after_dashboard.items() if k not in {"casualties", "casualties_by_city"}}
    after_noncasualty_hash = sha256_bytes(json.dumps(after_noncasualty, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    assert before_noncasualty_hash == after_noncasualty_hash
    schema_regression = not dashboard_schema_ok(before_dashboard, after_dashboard)
    assert not schema_regression

    with tempfile.TemporaryDirectory(prefix="casualty-real-queue-") as tempdir:
        temp = Path(tempdir)
        queue_copy = temp / "multicity_review_queue.json"
        queue_copy.write_bytes(queue_bytes)
        filtered_queue = temp / "needs_review_only.json"
        write_queue(filtered_queue, needs_review)
        revisions = temp / "revisions.csv"
        revisions.write_text(REVISION_HEADER, encoding="utf-8")
        queue_sha_before = sha256_bytes(queue_copy.read_bytes())
        summary = review_cli(ROOT, filtered_queue, revisions, "promote")
        queue_sha_after = sha256_bytes(queue_copy.read_bytes())
        real_needs_revision_rows = len(read_revision_rows(revisions))
        assert summary["canonical_records_added"] == 0
        assert real_needs_revision_rows == 0
        assert queue_sha_before == queue_sha_after

    with tempfile.TemporaryDirectory(prefix="casualty-synthetic-") as tempdir:
        scenario = Path(tempdir) / "root"
        copy_scenario_root(PRODUCTION_ROOT, scenario)
        revisions = scenario / "data" / "casualties" / "revisions.csv"
        revisions.write_text(REVISION_HEADER, encoding="utf-8")
        queue_path = scenario / "data" / "casualties" / "multicity_review_queue.json"
        write_queue(queue_path, [candidate("synthetic-prod-canary-a", "odesa", "https://media.example/synthetic-a")])
        scenario_before = canonical_month_map(read_json(scenario / "data" / "dashboard_data.json"))
        target_key = "odesa|2026-09"
        review_cli(
            scenario,
            queue_path,
            revisions,
            "review",
            "--candidate-id", "synthetic-prod-canary-a",
            "--city-key", "odesa",
            "--status", "confirmed",
            "--record-id", "synthetic:odesa:2026-09-20:production-integration",
            "--attack-date", "2026-09-20",
            "--deaths-delta", "2",
            "--source-name", "Synthetic official confirmation fixture",
            "--source-url", "https://official.example/synthetic-odesa",
            "--note", "temporary production-path canary only",
        )
        first_promotion = review_cli(scenario, queue_path, revisions, "promote")
        rows_first = read_revision_rows(revisions)
        assert len(rows_first) == 1
        assert first_promotion["canonical_records_added"] == 1
        run_builder(scenario)
        first_months = canonical_month_map(read_json(scenario / "data" / "dashboard_data.json"))
        synthetic_delta = first_months[target_key] - scenario_before[target_key]
        assert synthetic_delta == 2
        unrelated_first = [
            key for key in scenario_before
            if key != target_key and first_months.get(key) != scenario_before.get(key)
        ]
        assert not unrelated_first, unrelated_first[:10]

        second_promotion = review_cli(scenario, queue_path, revisions, "promote")
        rows_second = read_revision_rows(revisions)
        run_builder(scenario)
        second_months = canonical_month_map(read_json(scenario / "data" / "dashboard_data.json"))
        synthetic_rerun_additional_delta = second_months[target_key] - first_months[target_key]
        assert second_promotion["canonical_records_added"] == 0
        assert second_promotion["ledger_changed"] is False
        assert len(rows_second) == 1
        assert synthetic_rerun_additional_delta == 0
        assert second_months == first_months

    with tempfile.TemporaryDirectory(prefix="casualty-duplicate-media-") as tempdir:
        scenario = Path(tempdir) / "root"
        copy_scenario_root(PRODUCTION_ROOT, scenario)
        revisions = scenario / "data" / "casualties" / "revisions.csv"
        revisions.write_text(REVISION_HEADER, encoding="utf-8")
        queue_path = scenario / "data" / "casualties" / "multicity_review_queue.json"
        write_queue(
            queue_path,
            [
                candidate("synthetic-media-a", "sumy", "https://media-a.example/item"),
                candidate("synthetic-media-b", "sumy", "https://media-b.example/item"),
            ],
        )
        scenario_before = canonical_month_map(read_json(scenario / "data" / "dashboard_data.json"))
        target_key = "sumy|2026-09"
        for cid, source_url in (
            ("synthetic-media-a", "https://official-a.example/sumy"),
            ("synthetic-media-b", "https://official-b.example/sumy"),
        ):
            review_cli(
                scenario,
                queue_path,
                revisions,
                "review",
                "--candidate-id", cid,
                "--city-key", "sumy",
                "--status", "confirmed",
                "--record-id", "synthetic:sumy:2026-09-22:duplicate-media",
                "--attack-date", "2026-09-22",
                "--deaths-delta", "2",
                "--source-name", f"Synthetic confirmation {cid}",
                "--source-url", source_url,
            )
        duplicate_first = review_cli(scenario, queue_path, revisions, "promote")
        duplicate_rows = read_revision_rows(revisions)
        assert duplicate_first["canonical_records_added"] == 1
        assert len(duplicate_rows) == 1
        provenance = {item for item in duplicate_rows[0]["candidate_ids"].split("|") if item}
        duplicate_media_provenance_preserved = provenance == {"synthetic-media-a", "synthetic-media-b"}
        assert duplicate_media_provenance_preserved
        run_builder(scenario)
        first_months = canonical_month_map(read_json(scenario / "data" / "dashboard_data.json"))
        duplicate_monthly_increment = first_months[target_key] - scenario_before[target_key]
        assert duplicate_monthly_increment == 2
        duplicate_second = review_cli(scenario, queue_path, revisions, "promote")
        run_builder(scenario)
        second_months = canonical_month_map(read_json(scenario / "data" / "dashboard_data.json"))
        assert duplicate_second["canonical_records_added"] == 0
        assert duplicate_second["ledger_changed"] is False
        assert second_months[target_key] == first_months[target_key]
        duplicate_media_delta_count = len(duplicate_rows)

    real_revision_rows_after = max(0, len(git_bytes("show", "origin/site-prod:kyiv-air-alerts-grafana/data/casualties/revisions.csv").decode("utf-8-sig").splitlines()) - 1)
    assert real_revision_rows_after == 0

    result = {
        "verdict": "CASUALTY REVIEW/PROMOTION PRODUCTION INTEGRATION = PROVEN",
        "integration_branch": INTEGRATION_BRANCH,
        "integration_head_before_artifact_commit": integration_head,
        "integration_base_site_prod_sha": INTEGRATION_BASE_SITE_PROD_SHA,
        "isolated_repair_commit": ISOLATED_COMMIT,
        "isolated_semantics_preserved": isolated_semantics_preserved,
        "integrated_blobs": integrated_blobs,
        "authoritative_refs": {
            "main_head_at_proof": main_head,
            "site_prod_head_at_proof": site_prod_head,
            "multicity_wip_head_at_proof": wip_head,
            "workflow_blobs": workflow_blobs,
            "multicity_review_queue_blob": queue_blob,
            "production_pre_repair_update_blob": site_prod_pre_repair_blob,
        },
        "authoritative_lineage": {
            "multicity_casualty_monitor": {
                "workflow_branch": "main",
                "workflow": ".github/workflows/casualty-monitor-wip.yml",
                "checkout_branch": "multicity-wip-2026-09-16",
                "queue": QUEUE_PATH,
            },
            "casualty_monthly_aggregation": {
                "workflow_branch": "main",
                "workflow": ".github/workflows/update-netlify-site.yml",
                "checkout_branch": "site-prod",
                "script": "kyiv-air-alerts-grafana/scripts/update_casualties.py",
            },
            "dashboard_generation": {
                "branch": "site-prod",
                "file": "kyiv-air-alerts-grafana/data/dashboard_data.json",
                "workflow": ".github/workflows/update-netlify-site.yml",
            },
            "publication": {
                "workflow_branch": "main",
                "workflow": ".github/workflows/update-netlify-site.yml",
                "published_branch": "site-prod",
                "commit_step": "Commit updated production data",
            },
            "secondary_legacy_main_grafana_workflow": ".github/workflows/update.yml",
        },
        "production_trace": [
            "data/casualties/revisions.csv",
            "scripts/update_casualties.py:load_revisions",
            "baseline family: Kyiv baseline_monthly.csv / master_20cities_monthly_wide.csv / validated Odesa-Zaporizhzhia-Kherson city CSVs",
            "scripts/update_casualties.py:build_monthly + apply_city_revision_overlay",
            "data/dashboard_data.json:casualties + casualties_by_city",
            ".github/workflows/update-netlify-site.yml:configure_full_city_dashboard.py + add_casualty_panel.py",
            ".github/workflows/update-netlify-site.yml:git push origin HEAD:site-prod",
        ],
        "production_aggregation_consumes_revisions_ledger": True,
        "scheduled_workflow_can_auto_confirm_candidate": scheduled_can_auto_confirm,
        "scheduled_auto_confirm_hits": scheduled_auto_confirm_hits,
        "real_queue": {
            "records_audited": len(queue),
            "status_counts": status_counts,
            "needs_review_records": len(needs_review),
            "needs_review_with_source_url": needs_with_source_url,
            "needs_review_with_review_disposition": needs_with_review_disposition,
            "needs_review_with_approval_like_fields": needs_with_approval_like_fields,
            "needs_review_records_producing_revisions": real_needs_revision_rows,
            "source_blob": queue_blob,
            "read_only": True,
            "real_candidate_status_changes": 0,
        },
        "zero_ledger_regression": {
            "cities_compared": len(before_city_keys),
            "city_month_values_compared": len(before_months),
            "mismatches": len(zero_mismatches),
            "before_month_hash": canonical_month_hash(before_months),
            "after_month_hash": canonical_month_hash(after_months),
            "noncasualty_payload_unchanged": before_noncasualty_hash == after_noncasualty_hash,
            "dashboard_schema_regression": schema_regression,
            "builder_stdout": zero_build_stdout.strip(),
        },
        "synthetic_confirmed_canary": {
            "delta": synthetic_delta,
            "rerun_additional_delta": synthetic_rerun_additional_delta,
            "revision_rows_after_first": len(rows_first),
            "revision_rows_after_second": len(rows_second),
            "unrelated_city_month_changes": 0,
        },
        "duplicate_media_synthetic_canary": {
            "delta_count": duplicate_media_delta_count,
            "monthly_increment": duplicate_monthly_increment,
            "provenance_preserved": duplicate_media_provenance_preserved,
            "rerun_additional_delta": 0,
        },
        "historical_baseline_blobs": baseline_blobs,
        "historical_baseline_blobs_on_integration_branch": integrated_baseline_blobs,
        "historical_baseline_blobs_changed": historical_baseline_blobs_changed,
        "production_dashboard_schema_regression": schema_regression,
        "real_candidate_mutations": 0,
        "real_revision_rows_before": prod_revision_rows_before,
        "real_revision_rows_after": real_revision_rows_after,
        "real_revision_rows_added": 0,
        "real_casualty_total_changes": 0,
        "production_historical_total_changes": 0,
        "historical_backfill_started": False,
        "production_deployment_performed": False,
        "remaining_blocker": "NONE; first real human confirmation remains intentionally not performed",
        "mutation_confirmation": "ZERO REAL CANDIDATE/LEDGER/CASUALTY MUTATIONS; integration branch and temporary proof state only",
    }

    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
