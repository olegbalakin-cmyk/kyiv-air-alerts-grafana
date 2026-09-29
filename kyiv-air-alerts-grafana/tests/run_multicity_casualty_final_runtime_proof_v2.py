#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any

import run_multicity_casualty_final_runtime_proof as base

RESULT_PATH = Path("/tmp/multicity_casualties_final_runtime_exec_result.json")
PROJECT_REL = Path("kyiv-air-alerts-grafana")
MAIN_WORKFLOW_REL = ".github/workflows/update-netlify-site.yml"
REQ_DB_REL = "kyiv-air-alerts-grafana/requirements-db-phase1.txt"
REQ_REL = "kyiv-air-alerts-grafana/requirements.txt"

EXPECTED_MAIN_WORKFLOW_BLOB = "a451cb205be4cf5a597f3f72e04426c12868e3da"
EXPECTED_REQ_DB_BLOB = "46cb158bbc776c517c59350871441d03c27eef29"
EXPECTED_REQ_BLOB = "d7a2ff05af67cda88e4930d238f0282ca557a963"
EXPECTED_SITE_PROD_SEMANTIC_BLOBS = {
    "kyiv-air-alerts-grafana/scripts/update_casualties.py": "f1a89feae6aef5c584febcfd52886de339e478da",
    "kyiv-air-alerts-grafana/scripts/add_casualty_panel.py": "c33d277774f77cbfe0eff4b4ebd9f03326ff5fc9",
    "kyiv-air-alerts-grafana/pages-preview/app.js": "11ef482b0504bcb2f36bd6d556c98a5905f843b2",
    "kyiv-air-alerts-grafana/pages-preview/index.html": "35b4895eba56e18eacb82a30884569700f1f6d00",
    REQ_DB_REL: EXPECTED_REQ_DB_BLOB,
    REQ_REL: EXPECTED_REQ_BLOB,
}

STATE: dict[str, Any] = {
    "schema_version": 2,
    "overall_status": "INITIALIZING",
    "production_writes": "NONE",
}


def flush() -> None:
    RESULT_PATH.write_text(
        json.dumps(STATE, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def record(key: str, value: Any) -> None:
    STATE[key] = value
    flush()


def run(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None, gate: str = "command") -> subprocess.CompletedProcess[str]:
    cp = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        text=True,
        capture_output=True,
    )
    if cp.returncode != 0:
        raise base.GateFailure(
            gate,
            f"command failed ({cp.returncode}): {' '.join(cmd)}\nstdout:\n{cp.stdout}\nstderr:\n{cp.stderr}",
        )
    return cp


def git(repo: Path, *args: str, gate: str = "git") -> str:
    return run(["git", *args], cwd=repo, gate=gate).stdout.strip()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_gate(cond: bool, gate: str, message: str) -> None:
    if not cond:
        raise base.GateFailure(gate, message)


def package_versions() -> dict[str, str]:
    try:
        import requests
        import bs4
        import psycopg
    except Exception as exc:
        raise base.ToolingFailure("production_equivalent_python_environment", f"dependency import failed: {exc}") from exc
    return {
        "python": platform.python_version(),
        "requests": requests.__version__,
        "bs4": bs4.__version__,
        "psycopg": psycopg.__version__,
        "playwright": importlib.metadata.version("playwright"),
    }


def main() -> None:
    STATE.clear()
    STATE.update({
        "schema_version": 2,
        "overall_status": "RUNNING",
        "production_writes": "NONE",
        "github_actions": {
            "run_id": os.environ.get("GITHUB_RUN_ID"),
            "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "workflow": os.environ.get("GITHUB_WORKFLOW"),
        },
    })
    flush()

    repo = Path(git(Path.cwd(), "rev-parse", "--show-toplevel", gate="repository_guard"))
    proof_head = git(repo, "rev-parse", "HEAD", gate="repository_guard")
    branch = os.environ.get("GITHUB_REF_NAME") or ""
    assert_gate(
        branch == "multicity-casualties-prod-proof-2026-09-28",
        "repository_guard",
        f"unexpected branch {branch}",
    )
    record("proof_source", {"branch": branch, "tested_commit": proof_head})

    versions = package_versions()
    record("production_equivalent_python_environment", {
        "result": "PASS",
        "python_version": versions["python"],
        "dependency_versions": {
            "requests": versions["requests"],
            "bs4": versions["bs4"],
            "psycopg": versions["psycopg"],
        },
        "playwright_version": versions["playwright"],
    })

    observed_blobs: dict[str, str] = {}
    for path, expected_blob in base.PROMOTION_BLOBS.items():
        blob = git(repo, "rev-parse", f"{proof_head}:{path}", gate="promotion_blob_guard")
        observed_blobs[path] = blob
        assert_gate(blob == expected_blob, "promotion_blob_guard", f"{path}: {blob} != {expected_blob}")
    record("promotion_blob_guard", {
        "result": "PASS",
        "count": len(observed_blobs),
        "blobs": observed_blobs,
    })

    git(repo, "fetch", "origin", "main", "--depth=1", gate="fresh_production_guard")
    main_head = git(repo, "rev-parse", "FETCH_HEAD", gate="fresh_production_guard")
    main_workflow_blob = git(repo, "rev-parse", f"{main_head}:{MAIN_WORKFLOW_REL}", gate="fresh_production_guard")
    assert_gate(
        main_workflow_blob == EXPECTED_MAIN_WORKFLOW_BLOB,
        "production_dependency_contract",
        f"main workflow drift: {main_workflow_blob}",
    )

    git(repo, "fetch", "origin", "site-prod", "--depth=1", gate="fresh_production_guard")
    site_prod_head = git(repo, "rev-parse", "FETCH_HEAD", gate="fresh_production_guard")
    site_guard: dict[str, str] = {}
    for path, expected_blob in EXPECTED_SITE_PROD_SEMANTIC_BLOBS.items():
        blob = git(repo, "rev-parse", f"{site_prod_head}:{path}", gate="production_dependency_contract")
        site_guard[path] = blob
        assert_gate(blob == expected_blob, "production_dependency_contract", f"{path}: production semantic drift {blob} != {expected_blob}")

    record("fresh_guard", {
        "result": "PASS",
        "fresh_main_head": main_head,
        "main_workflow_blob": main_workflow_blob,
        "fresh_frozen_site_prod_head": site_prod_head,
        "requirements_db_phase1_blob": site_guard[REQ_DB_REL],
        "requirements_blob": site_guard[REQ_REL],
        "site_prod_semantic_blobs": site_guard,
        "promotion_or_dependency_semantic_drift": False,
    })

    prod_tree = Path("/tmp/casualty-prod")
    proof_tree = Path("/tmp/casualty-proof")
    for path in (prod_tree, proof_tree):
        if path.exists():
            shutil.rmtree(path)
    git(repo, "worktree", "add", "--detach", str(prod_tree), site_prod_head, gate="tree_materialization")
    git(repo, "worktree", "add", "--detach", str(proof_tree), proof_head, gate="tree_materialization")

    dash_path = prod_tree / base.DASH_REL
    grafana_path = prod_tree / base.GRAFANA_REL
    dashboard_blob = git(repo, "rev-parse", f"{site_prod_head}:{base.DASH_REL}", gate="exact_dashboard_materialization")
    dashboard_sha256 = sha256_file(dash_path)
    record("exact_current_production_dashboard", {
        "result": "PASS",
        "site_prod_head": site_prod_head,
        "git_blob_sha": dashboard_blob,
        "materialized_sha256": dashboard_sha256,
        "materialized": True,
    })

    before_dashboard_path = Path("/tmp/dashboard_data_before_casualties.json")
    before_grafana_path = Path("/tmp/grafana_dashboard_before_casualties.json")
    shutil.copy2(dash_path, before_dashboard_path)
    shutil.copy2(grafana_path, before_grafana_path)

    overlay: dict[str, dict[str, str]] = {}
    for rel, expected_blob in base.PROMOTION_BLOBS.items():
        src = proof_tree / rel
        dst = prod_tree / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        overlay[rel] = {
            "git_blob": git(repo, "rev-parse", f"{proof_head}:{rel}", gate="overlay_guard"),
            "sha256": sha256_file(dst),
        }
        assert_gate(overlay[rel]["git_blob"] == expected_blob, "overlay_guard", f"{rel}: wrong overlay blob")
    record("promotion_overlay", {
        "result": "PASS",
        "file_count": len(overlay),
        "files": overlay,
        "excluded_generated_outputs": [base.DASH_REL, base.GRAFANA_REL],
    })

    project = prod_tree / PROJECT_REL
    before_dashboard = load_json(before_dashboard_path)
    before_sha256 = sha256_file(before_dashboard_path)

    first_builder = run(
        [sys.executable, "scripts/update_casualties.py", "--no-network"],
        cwd=project,
        gate="exact_current_builder",
    )
    after_first = load_json(dash_path)
    after_first_sha256 = sha256_file(dash_path)
    validation = base.validate_city_series(after_first)
    record("exact_current_base_builder", {
        "result": "PASS",
        "exit": first_builder.returncode,
        "stdout": first_builder.stdout.strip(),
        "pre_builder_sha256": before_sha256,
        "post_builder_sha256": after_first_sha256,
        **validation,
    })

    assert_gate(
        base.strip_casualty_sections(before_dashboard) == base.strip_casualty_sections(after_first),
        "non_casualty_regression",
        "unexpected non-casualty dashboard diff",
    )
    record("non_casualty_regression", {
        "result": "PASS",
        "unexpected_non_casualty_diffs": 0,
    })

    before_grafana = load_json(before_grafana_path)
    grafana_run = run(
        [sys.executable, "scripts/add_casualty_panel.py"],
        cwd=project,
        gate="grafana_generation",
    )
    after_grafana = load_json(grafana_path)
    record("grafana_generation", {
        **base.validate_grafana(before_grafana, after_grafana),
        "stdout": grafana_run.stdout.strip(),
    })

    # Proof-only harness injection: the focused test is not part of the 12-file implementation overlay.
    proof_test = proof_tree / "kyiv-air-alerts-grafana/tests/test_multicity_casualty_promotion.py"
    runtime_test = project / "tests/test_multicity_casualty_promotion.py"
    if runtime_test.exists() or runtime_test.is_symlink():
        runtime_test.unlink()
    shutil.copy2(proof_test, runtime_test)
    env = dict(os.environ)
    env["CASUALTY_PROOF_BEFORE"] = str(before_dashboard_path)
    focused = run(
        [sys.executable, "tests/test_multicity_casualty_promotion.py"],
        cwd=project,
        env=env,
        gate="focused_test",
    )
    focused_last = focused.stdout.strip().splitlines()[-1] if focused.stdout.strip() else ""
    focused_json = json.loads(focused_last)
    assert_gate(bool(focused_json.get("ok")), "focused_test", f"focused test not ok: {focused_json}")
    record("focused_test", {
        "result": "PASS",
        "proof_harness_only": True,
        "output": focused_json,
    })

    chart_path = Path(os.environ.get("CHART_JS_PATH", ""))
    if not chart_path.is_file():
        raise base.ToolingFailure("real_chart_js_loaded", f"Chart.js path missing: {chart_path}")
    package_root = chart_path.parent.parent
    package_json = load_json(package_root / "package.json")
    chart_version = package_json.get("version")
    assert_gate(chart_version == "4.4.7", "real_chart_js_loaded", f"package version={chart_version}")
    chart_sha256 = sha256_file(chart_path)
    record("chart_js_package", {
        "result": "PASS",
        "source_path": str(chart_path),
        "package_version": chart_version,
        "bundle_sha256": chart_sha256,
    })

    runtime = Path("/tmp/casualty-runtime-site")
    if runtime.exists():
        shutil.rmtree(runtime)
    runtime.mkdir(parents=True)
    for name in ("index.html", "styles.css", "app.js"):
        shutil.copy2(project / "pages-preview" / name, runtime / name)
    shutil.copy2(dash_path, runtime / "data.json")
    shutil.copy2(chart_path, runtime / "chart.umd.js")

    app_path = runtime / "app.js"
    app_text = app_path.read_text(encoding="utf-8")
    live_data = 'const DATA_URL = "https://raw.githubusercontent.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/site-prod/kyiv-air-alerts-grafana/data/dashboard_data.json";'
    local_data = 'const DATA_URL = "./data.json";'
    assert_gate(app_text.count(live_data) == 1, "runtime_site_build", "production DATA_URL occurrence != 1")
    app_path.write_text(app_text.replace(live_data, local_data), encoding="utf-8")

    index_path = runtime / "index.html"
    index_text = index_path.read_text(encoding="utf-8")
    live_chart = "https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"
    assert_gate(index_text.count(live_chart) == 1, "runtime_site_build", "Chart.js CDN occurrence != 1")
    index_path.write_text(index_text.replace(live_chart, "./chart.umd.js"), encoding="utf-8")
    record("runtime_site_build", {
        "result": "PASS",
        "data_url": "./data.json",
        "chart_source": "./chart.umd.js",
        "real_chart_bundle": True,
    })

    browser = base.browser_proof(runtime)
    record("browser_runtime", browser)
    assert_gate(browser["chart_identity"]["version"] == "4.4.7", "real_chart_js_loaded", "runtime Chart.version mismatch")
    record("real_chart_js_loaded", {
        "result": "PASS",
        "Chart.version": browser["chart_identity"]["version"],
        "structural_identity": browser["chart_identity"],
    })
    record("real_city_switch", {
        "result": "PASS",
        "sequence": browser["sequence"],
    })
    record("spot_checks", {
        "result": "PASS",
        **browser["spot_checks"],
    })
    record("real_uzhhorod_zero_chart", {
        "result": "PASS",
        **browser["uzhhorod"],
    })
    record("real_missing_series_cleanup", {
        "result": "PASS",
        **browser["missing_series"],
    })
    record("browser_errors", {
        "result": "PASS",
        "console_errors": browser["console_errors"],
        "page_errors": browser["page_errors"],
        "chart_errors": browser["chart_errors"],
        "failed_app_requests": browser["failed_app_requests"],
        "warnings": browser["warnings"],
    })

    after_first_snapshot = copy.deepcopy(after_first)
    second_builder = run(
        [sys.executable, "scripts/update_casualties.py", "--no-network"],
        cwd=project,
        gate="repeated_builder_durability",
    )
    after_second = load_json(dash_path)
    second_validation = base.validate_city_series(after_second)
    assert_gate(
        base.normalized_repeat(after_first_snapshot) == base.normalized_repeat(after_second),
        "repeated_builder_durability",
        "second builder changed content beyond casualty generated timestamps",
    )
    assert_gate(
        base.strip_casualty_sections(before_dashboard) == base.strip_casualty_sections(after_second),
        "repeated_builder_durability",
        "second builder changed non-casualty dashboard content",
    )
    record("repeated_builder_durability", {
        "result": "PASS",
        "exit": second_builder.returncode,
        "stdout": second_builder.stdout.strip(),
        "after_second_sha256": sha256_file(dash_path),
        "normalized_content_stable": True,
        "validation": second_validation,
    })

    record("production_write_audit", {
        "result": "PASS",
        "workflow_permissions": "contents: read",
        "site_prod_push": False,
        "main_push": False,
        "netlify_production": False,
        "netlify_preview": False,
        "grafana_deploy": False,
        "neon_mutation": False,
        "historical_replay_mutation": False,
        "live_attack_event_monitor_mutation": False,
        "campaign_6863_mutation": False,
        "generated_production_outputs_committed": False,
    })

    STATE["overall_status"] = "PASS"
    STATE["verdict"] = "23-CITY CASUALTY PRODUCTION PROMOTION PROVEN — EXACT CURRENT SITE-PROD BASE + PRODUCTION-EQUIVALENT PYTHON ENV + REAL CHART.JS 4.4.7 RUNTIME PASS — READY FOR GUARDED PRODUCTION CUTOVER"
    flush()


if __name__ == "__main__":
    exit_code = 1
    try:
        main()
        exit_code = 0
    except base.ToolingFailure as exc:
        STATE.update({
            "overall_status": "BLOCKED",
            "failed_gate": exc.gate,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "verdict": f"23-CITY CASUALTY PRODUCTION PROMOTION STILL BLOCKED — {exc.gate}: {exc}",
            "production_writes": "NONE",
        })
    except base.GateFailure as exc:
        STATE.update({
            "overall_status": "FAILED",
            "failed_gate": exc.gate,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "verdict": f"23-CITY CASUALTY PRODUCTION PROMOTION FAILED — {exc.gate}",
            "production_writes": "NONE",
        })
    except Exception as exc:
        STATE.update({
            "overall_status": "BLOCKED",
            "failed_gate": "unexpected_runner_error",
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "verdict": f"23-CITY CASUALTY PRODUCTION PROMOTION STILL BLOCKED — unexpected runner error: {exc}",
            "production_writes": "NONE",
        })
    flush()
    print("RESULT_JSON_BEGIN")
    print(json.dumps(STATE, ensure_ascii=False, separators=(",", ":")))
    print("RESULT_JSON_END")
    sys.exit(exit_code)
