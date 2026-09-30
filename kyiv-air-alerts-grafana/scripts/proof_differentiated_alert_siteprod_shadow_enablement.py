#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FREEZE_DIR = ROOT / "proof_http_freeze"
RESULT_PATH = Path(os.environ.get("PROOF_RESULT_PATH", tempfile.gettempdir() + "/differentiated_alert_shadow_proof.json"))
FIXED_NOW = os.environ.get("PROOF_FIXED_NOW") or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
PROOF_SCHEMA = os.environ.get("PROOF_DIFFERENTIATED_SCHEMA", "differentiated_alert_shadow_proof_20260930")
REPO = os.environ.get("GITHUB_REPOSITORY", "olegbalakin-cmyk/kyiv-air-alerts-grafana")
SENSITIVE_KEYS = (
    "DIFFERENTIATED_ALERT_SHADOW_DATABASE_URL",
    "PHASE1_PROD_SHADOW_DATABASE_URL",
    "PHASE1_DATABASE_URL",
    "UKRAINEALARM_API_TOKEN",
    "NEON_API_KEY",
)
DYNAMIC_JSON_KEYS = {
    "generated_at", "generated_at_utc", "last_attempt_at", "last_checked_at",
    "last_successful_fetch_at", "checked_at", "fetched_at", "run_started_at", "run_finished_at",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(*args: str, cwd: Path = ROOT.parent) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def safe_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ)
    env.update({
        "PYTHONPATH": str(FREEZE_DIR) + os.pathsep + env.get("PYTHONPATH", ""),
        "PROOF_FIXED_NOW": FIXED_NOW,
        "PHASE1_DB_SHADOW": "0",
        "UKRAINEALARM_MIN_INTERVAL_SECONDS": "0",
    })
    if extra:
        env.update(extra)
    return env


def run(cmd: list[str], cwd: Path, env: dict[str, str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    p = subprocess.run(cmd, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print("$", " ".join(cmd), "->", p.returncode, flush=True)
    if p.stdout:
        print("\n".join(p.stdout.splitlines()[-12:]), flush=True)
    if check and p.returncode != 0:
        raise RuntimeError(f"command failed ({p.returncode}): {' '.join(cmd)}\n{p.stdout[-4000:]}")
    return p


def pipeline(workdir: Path, env: dict[str, str]) -> list[str]:
    logs: list[str] = []
    def step(*cmd: str):
        p = run(list(cmd), workdir, env)
        logs.append(p.stdout or "")
    step(sys.executable, "tests/test_update_fallback.py")
    step(sys.executable, "scripts/validate_bridge_checkpoint.py", "self-test")
    step(sys.executable, "scripts/update_data.py")
    step(sys.executable, "scripts/add_weekly_breakdown.py")
    step(sys.executable, "scripts/render_dashboard.py", "--repository", REPO, "--branch", "site-prod", "--prefix", "kyiv-air-alerts-grafana")
    step(sys.executable, "scripts/add_weekly_panels.py")
    step(sys.executable, "scripts/add_duration_unit_switch.py")
    step(sys.executable, "scripts/expand_multicity_production.py")
    step(sys.executable, "scripts/extend_remaining_proxies.py")
    bridge_before = workdir.parent / (workdir.name + "_ukrainealarm_bridge_before.json")
    shutil.copy2(workdir / "data/ukrainealarm_bridge.json", bridge_before)
    step(sys.executable, "scripts/apply_ukrainealarm_bridge.py")
    bridge_diag = workdir.parent / (workdir.name + "_ukrainealarm_bridge_fetch.json")
    step(
        sys.executable, "scripts/validate_bridge_checkpoint.py", "validate",
        "--candidate", "data/ukrainealarm_bridge.json",
        "--summary", "data/dashboard_data.json",
        "--baseline", str(bridge_before),
        "--diagnostic", str(bridge_diag),
    )
    step(sys.executable, "scripts/add_sevastopol_exact.py")
    step(sys.executable, "scripts/apply_site_rolling_7d.py")
    step(sys.executable, "scripts/update_casualties.py")
    step(sys.executable, "scripts/configure_full_city_dashboard.py")
    step(sys.executable, "scripts/add_casualty_panel.py")
    step(sys.executable, "scripts/postprocess_compact_dashboard_qa.py")
    step(sys.executable, "scripts/reconcile_bridge_freshness.py")
    qa = json.loads((workdir / "data/dashboard_qa.json").read_text(encoding="utf-8"))
    data = json.loads((workdir / "data/dashboard_data.json").read_text(encoding="utf-8"))
    assert qa.get("ok") is True, qa
    assert len(data.get("multicity_meta", {}).get("production_city_keys", [])) == 23
    assert data.get("multicity_meta", {}).get("effective_freshness", {}).get("fully_continuous") is True
    return logs


def strip_dynamic(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: strip_dynamic(v) for k, v in sorted(value.items()) if k not in DYNAMIC_JSON_KEYS}
    if isinstance(value, list):
        return [strip_dynamic(v) for v in value]
    return value


def semantic_hash(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    raw_hash = sha256_bytes(raw)
    if path.suffix.lower() == ".json":
        try:
            obj = json.loads(raw.decode("utf-8-sig"))
        except Exception:
            return raw_hash, raw_hash
        normalized = json.dumps(strip_dynamic(obj), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        return raw_hash, sha256_bytes(normalized)
    return raw_hash, raw_hash


def publication_manifest(workdir: Path) -> dict[str, dict[str, str]]:
    paths = [p for p in sorted((workdir / "data").rglob("*")) if p.is_file()]
    dash = workdir / "grafana/dashboard.json"
    if dash.exists():
        paths.append(dash)
    out = {}
    for path in paths:
        raw_hash, semantic = semantic_hash(path)
        out[path.relative_to(workdir).as_posix()] = {"raw_sha256": raw_hash, "semantic_sha256": semantic}
    return out


def compare_manifests(a: dict, b: dict) -> dict[str, Any]:
    names = sorted(set(a) | set(b))
    raw = [n for n in names if a.get(n, {}).get("raw_sha256") != b.get(n, {}).get("raw_sha256")]
    semantic = [n for n in names if a.get(n, {}).get("semantic_sha256") != b.get(n, {}).get("semantic_sha256")]
    return {"file_count": len(names), "raw_mismatches": raw, "semantic_mismatches": semantic, "semantic_delta_count": len(semantic)}


def parent_air(workdir: Path) -> list[tuple[str, str, str]]:
    rows = json.loads((workdir / "data/alerts_combined.json").read_text(encoding="utf-8"))
    return sorted((str(r.get("start")), str(r.get("end")), str(r.get("source"))) for r in rows)


def public_db_state(dsn: str) -> dict[str, Any]:
    import psycopg
    with psycopg.connect(dsn) as conn:
        counts = {}
        for table in ("ingestion_runs", "alert_episodes", "alert_episode_sources", "ingestion_checkpoints"):
            counts[table] = int(conn.execute(f"SELECT count(*) FROM public.{table}").fetchone()[0])
        meta = conn.execute("""
          SELECT md5(string_agg(format('%I.%I|%I|%s|%s|%s', table_schema, table_name, column_name, data_type, is_nullable, COALESCE(column_default,'')), E'\\n' ORDER BY table_schema, table_name, ordinal_position))
          FROM information_schema.columns WHERE table_schema='public'
        """).fetchone()[0]
        tables = [r[0] for r in conn.execute("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname='public' ORDER BY tablename")]
    return {"counts": counts, "schema_meta_md5": meta, "tables": tables}


def proof_schema_state(dsn: str) -> dict[str, Any]:
    import psycopg
    with psycopg.connect(dsn) as conn:
        tables = [r[0] for r in conn.execute("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname=%s ORDER BY tablename", (PROOF_SCHEMA,))]
        columns = [list(r) for r in conn.execute("SELECT table_name,column_name,data_type,is_nullable FROM information_schema.columns WHERE table_schema=%s ORDER BY table_name,ordinal_position", (PROOF_SCHEMA,))]
    return {"schema": PROOF_SCHEMA, "tables": tables, "columns": columns}


def scan_credentials(texts: list[str]) -> list[str]:
    hits = []
    for key in SENSITIVE_KEYS:
        value = os.environ.get(key, "").strip()
        if value:
            for i, text in enumerate(texts):
                if value in text:
                    hits.append(f"{key}@{i}")
                    break
    return hits


def test_counts(env: dict[str, str]) -> dict[str, Any]:
    p = run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_differentiated_alert*.py"], ROOT, env)
    m = re.search(r"Ran\s+(\d+)\s+tests?", p.stdout or "")
    fallback = run([sys.executable, "tests/test_update_fallback.py"], ROOT, env)
    checkpoint = run([sys.executable, "scripts/validate_bridge_checkpoint.py", "self-test"], ROOT, env)
    return {
        "differentiated_unittest": {"count": int(m.group(1)) if m else None, "passed": p.returncode == 0},
        "production_update_fallback": {"count": 1, "passed": fallback.returncode == 0},
        "bridge_checkpoint_selftest": {"count": 1, "passed": checkpoint.returncode == 0},
    }


def main() -> int:
    dsn = os.environ.get("DIFFERENTIATED_ALERT_SHADOW_DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError("DIFFERENTIATED_ALERT_SHADOW_DATABASE_URL secret is required for proof")
    temp = Path(tempfile.mkdtemp(prefix="diff-alert-proof-"))
    fixture = temp / "frozen_http.json"
    result: dict[str, Any] = {
        "proof_run_id": os.environ.get("GITHUB_RUN_ID"),
        "proof_branch": os.environ.get("GITHUB_REF_NAME"),
        "proof_head": git("rev-parse", "HEAD"),
        "site_prod_base": os.environ.get("PROOF_SITEPROD_BASE"),
        "fixed_now": FIXED_NOW,
        "proof_schema": PROOF_SCHEMA,
    }
    all_logs: list[str] = []
    public_before = public_db_state(dsn)
    result["pre_proof_db_inventory"] = public_before
    result["tests"] = test_counts(safe_env({"PROOF_HTTP_MODE": ""}))

    pristine = ROOT
    copies = {name: temp / name for name in ("capture", "off", "on", "failure", "source_failure", "retry")}
    for target in copies.values():
        shutil.copytree(pristine, target)

    capture_env = safe_env({
        "PROOF_HTTP_MODE": "capture",
        "PROOF_HTTP_FIXTURE": str(fixture),
        "DIFFERENTIATED_ALERT_SHADOW": "0",
    })
    p = run([sys.executable, "-c", "import requests; r=requests.get('https://kyiv.digital/open-api/air-alert/state', timeout=20); r.raise_for_status(); print(len(r.content))"], copies["capture"], capture_env)
    all_logs.append(p.stdout or "")
    all_logs.extend(pipeline(copies["capture"], capture_env))
    frozen = json.loads(fixture.read_text(encoding="utf-8"))
    result["frozen_inputs"] = {
        "fixture_sha256": sha256_bytes(fixture.read_bytes()),
        "request_count": len(frozen),
        "requests": {k: sha256_bytes(base64.b64decode(v["body_b64"])) for k, v in sorted(frozen.items())},
    }

    replay_base = {
        "PROOF_HTTP_MODE": "replay",
        "PROOF_HTTP_FIXTURE": str(fixture),
        "DIFFERENTIATED_ALERT_SHADOW_OBSERVED_AT": FIXED_NOW,
        "DIFFERENTIATED_ALERT_SHADOW_DB_BRANCH": os.environ.get("DIFFERENTIATED_ALERT_SHADOW_DB_BRANCH", ""),
        "DIFFERENTIATED_ALERT_SHADOW_INPUT_SHA": os.environ.get("PROOF_SITEPROD_BASE", ""),
    }
    off_diag = temp / "off_diag.json"
    off_env = safe_env({**replay_base, "DIFFERENTIATED_ALERT_SHADOW": "0", "DIFFERENTIATED_ALERT_SHADOW_DIAGNOSTIC": str(off_diag)})
    all_logs.extend(pipeline(copies["off"], off_env))
    result["off_result"] = {"diagnostic_created": off_diag.exists(), "feature_flag": "0"}

    on_diag = temp / "on_diag.json"
    on_env = safe_env({
        **replay_base,
        "DIFFERENTIATED_ALERT_SHADOW": "1",
        "DIFFERENTIATED_ALERT_SHADOW_SCHEMA": PROOF_SCHEMA,
        "DIFFERENTIATED_ALERT_SHADOW_DIAGNOSTIC": str(on_diag),
    })
    all_logs.extend(pipeline(copies["on"], on_env))
    on_result = json.loads(on_diag.read_text(encoding="utf-8"))
    result["on_result"] = on_result

    off_manifest = publication_manifest(copies["off"])
    publication = compare_manifests(off_manifest, publication_manifest(copies["on"]))
    result["publication_comparison"] = publication
    pa = parent_air(copies["off"])
    pb = parent_air(copies["on"])
    parent_equal = pa == pb
    result["parent_air_comparison"] = {
        "off_sha256": sha256_bytes(json.dumps(pa, separators=(",", ":")).encode()),
        "on_sha256": sha256_bytes(json.dumps(pb, separators=(",", ":")).encode()),
        "created": 0 if parent_equal else None,
        "deleted": 0 if parent_equal else None,
        "split": 0 if parent_equal else None,
        "merged": 0 if parent_equal else None,
        "start_shift": 0 if parent_equal else None,
        "end_shift": 0 if parent_equal else None,
        "episode_identity_delta": 0 if parent_equal else None,
        "equal": parent_equal,
    }
    result["attack_event_comparison"] = {
        "mode": "deterministic_parent_input_identity_and_no_feedback",
        "strict_delta": 0 if parent_equal else None,
        "sensitivity_delta": 0 if parent_equal else None,
        "qa_delta": 0 if parent_equal else None,
        "episode_level_classification_delta": 0 if parent_equal else None,
        "classifier_semantics_modified": False,
    }

    retry_diag = temp / "retry_diag.json"
    retry_env = safe_env({**on_env, "DIFFERENTIATED_ALERT_SHADOW_DIAGNOSTIC": str(retry_diag)})
    p = run([sys.executable, "scripts/update_data.py"], copies["retry"], retry_env)
    all_logs.append(p.stdout or "")
    retry_result = json.loads(retry_diag.read_text(encoding="utf-8"))
    result["idempotency"] = retry_result

    fail_diag = temp / "fail_diag.json"
    fail_env = safe_env({
        **replay_base,
        "DIFFERENTIATED_ALERT_SHADOW": "1",
        "DIFFERENTIATED_ALERT_SHADOW_DATABASE_URL": "postgresql://invalid:invalid@127.0.0.1:1/invalid?connect_timeout=1",
        "DIFFERENTIATED_ALERT_SHADOW_SCHEMA": PROOF_SCHEMA,
        "DIFFERENTIATED_ALERT_SHADOW_DIAGNOSTIC": str(fail_diag),
    })
    all_logs.extend(pipeline(copies["failure"], fail_env))
    fail_result = json.loads(fail_diag.read_text(encoding="utf-8"))
    fail_cmp = compare_manifests(off_manifest, publication_manifest(copies["failure"]))
    result["forced_persistence_failure"] = {"diagnostic": fail_result, "publication": fail_cmp, "parent_equal": parent_air(copies["failure"]) == pa}

    source_diag = temp / "source_fail_diag.json"
    source_env = safe_env({
        **on_env,
        "DIFFERENTIATED_ALERT_SHADOW_DIAGNOSTIC": str(source_diag),
        "DIFFERENTIATED_ALERT_SHADOW_KYIV_JSON": str(copies["source_failure"] / "missing-kyiv.json"),
        "DIFFERENTIATED_ALERT_SHADOW_UKRAINEALARM_JSON": str(copies["source_failure"] / "tests/fixtures/differentiated_alert_shadow/ukrainealarm_overlap_stored_raw_2026-09-14.json"),
        "DIFFERENTIATED_ALERT_SHADOW_ALERTS_IN_UA_JSON": str(copies["source_failure"] / "tests/fixtures/differentiated_alert_shadow/alerts_in_ua_stored_raw_2026-09-16.json"),
    })
    all_logs.extend(pipeline(copies["source_failure"], source_env))
    source_result = json.loads(source_diag.read_text(encoding="utf-8"))
    source_cmp = compare_manifests(off_manifest, publication_manifest(copies["source_failure"]))
    result["forced_source_failure"] = {"diagnostic": source_result, "publication": source_cmp, "parent_equal": parent_air(copies["source_failure"]) == pa}

    sys.path.insert(0, str(ROOT / "scripts"))
    from differentiated_alert_postgres import PostgresShadowStore
    import proof_differentiated_alert_shadow_ingestion as shadow
    store = PostgresShadowStore(dsn, PROOF_SCHEMA)
    before_rollback = store.counts()
    payload = json.loads((ROOT / "tests/fixtures/differentiated_alert_shadow/kyiv_live_raw_2026-09-29_111347.json").read_text(encoding="utf-8"))
    dt = datetime.fromisoformat(FIXED_NOW.replace("Z", "+00:00")) + timedelta(seconds=17)
    rec = shadow.canonicalize_kyiv(payload, observed_at=dt.isoformat().replace("+00:00", "Z"), target_city_key="kyiv", raw_object_path="$ROLLBACK_PROOF")
    rec = shadow.bind(rec, [])
    rollback_error = None
    try:
        store.persist(rec, fail_after_snapshot=True)
    except Exception as exc:
        rollback_error = type(exc).__name__
    after_rollback = store.counts()
    store.close()
    result["postgres_transaction_rollback"] = {"before": before_rollback, "after": after_rollback, "error_type": rollback_error, "pass": before_rollback == after_rollback and rollback_error is not None}
    result["proof_schema_state"] = proof_schema_state(dsn)
    result["proof_schema_isolated"] = result["proof_schema_state"].get("tables") == ["alert_state_snapshot", "alert_threat_observation"]

    public_after = public_db_state(dsn)
    result["post_proof_public_db_inventory"] = public_after
    result["phase1_public_unchanged"] = public_before == public_after
    result["implementation_blobs"] = {
        p: git("hash-object", p, cwd=ROOT.parent)
        for p in [
            "kyiv-air-alerts-grafana/scripts/update_data.py",
            "kyiv-air-alerts-grafana/scripts/differentiated_alert_shadow_runtime.py",
            "kyiv-air-alerts-grafana/scripts/differentiated_alert_postgres.py",
            "kyiv-air-alerts-grafana/scripts/proof_differentiated_alert_schema_v2.py",
            "kyiv-air-alerts-grafana/scripts/proof_differentiated_alert_shadow_ingestion.py",
        ]
    }
    credential_hits = scan_credentials(all_logs + [fixture.read_text(encoding="utf-8"), json.dumps(result, ensure_ascii=False)])
    result["credentials_exposure"] = {"count": len(credential_hits), "hits": credential_hits}

    gates = {
        "default_off": os.environ.get("DIFFERENTIATED_ALERT_SHADOW", "").strip().lower() not in {"1", "true", "yes", "on"},
        "off_zero_differentiated_work": not result["off_result"]["diagnostic_created"],
        "on_persists_real_child_evidence": bool(on_result.get("attempted") and on_result.get("sources", {}).get("kyiv", {}).get("status") == "SUCCEEDED" and (on_result.get("inserted_snapshots", 0) > 0 or on_result.get("existing_snapshots", 0) > 0)),
        "publication_equivalence": publication["semantic_delta_count"] == 0,
        "parent_air_equivalence": parent_equal,
        "attack_event_equivalence": parent_equal,
        "exact_replay_idempotency": bool(retry_result.get("exact_retry") and retry_result.get("inserted_snapshots") == 0 and retry_result.get("inserted_observations") == 0),
        "persistence_failure_fail_open": fail_result.get("status") == "FAILED" and fail_cmp["semantic_delta_count"] == 0 and parent_air(copies["failure"]) == pa,
        "source_failure_isolation": source_result.get("status") == "PARTIAL_FAILURE" and source_result.get("sources", {}).get("kyiv", {}).get("status") == "FAILED" and source_result.get("sources", {}).get("ukrainealarm", {}).get("status") == "SUCCEEDED" and source_result.get("sources", {}).get("alerts_in_ua", {}).get("status") == "SUCCEEDED" and source_cmp["semantic_delta_count"] == 0,
        "postgres_transaction_rollback": result["postgres_transaction_rollback"]["pass"],
        "proof_schema_isolated": result["proof_schema_isolated"],
        "fresh_regressions": all(v.get("passed") for v in result["tests"].values()),
        "phase1_public_unchanged": result["phase1_public_unchanged"],
        "credentials_exposure_zero": len(credential_hits) == 0,
    }
    result["gates"] = gates
    result["verdict"] = "PROOF_GREEN" if all(gates.values()) else "PROOF_BLOCKED"
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": result["verdict"], "gates": gates}, indent=2, sort_keys=True))
    return 0 if result["verdict"] == "PROOF_GREEN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
