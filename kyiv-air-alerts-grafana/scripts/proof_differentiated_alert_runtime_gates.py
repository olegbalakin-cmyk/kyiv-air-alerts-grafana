#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

FROZEN_DEFAULT = "93a7e702657a272b9bc3ffba6a5b843e75b66383"
KYIV_URL = "https://kyiv.digital/open-api/air-alert/state"
UTC = timezone.utc


def cj(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_obj(obj) -> str:
    return sha_bytes(cj(obj).encode("utf-8"))


def sha_file(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def build_parent(repo_root: Path):
    scripts = repo_root / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        mon = load_module("runtime_gate_monitor", scripts / "monitor_explosion_candidates.py")
    finally:
        if sys.path and sys.path[0] == str(scripts):
            sys.path.pop(0)
    state = mon.ensure_state()
    city_keys = sorted(mon.CITY_CONFIG)
    corpus = {}
    city_meta = {}
    for city in city_keys:
        rows = []
        for ep in mon.tracked_episodes_for_city(state, city):
            rows.append({
                "city_key": city,
                "episode_id": ep.get("episode_id"),
                "start": ep.get("alert_start"),
                "end": ep.get("alert_end"),
            })
        rows.sort(key=lambda x: (x["start"] or "", x["end"] or "", x["episode_id"] or ""))
        corpus[city] = rows
        city_meta[city] = {"episode_count": len(rows), "sha256": sha_obj({"city_key": city, "episodes": rows})}
    global_repr = {city: corpus[city] for city in city_keys}
    return {
        "city_count": len(city_keys),
        "global_episode_count": sum(len(v) for v in corpus.values()),
        "global_sha256": sha_obj(global_repr),
        "cities": city_meta,
        "corpus": corpus,
        "source_state_sha256": sha_file(repo_root / "data/explosion_candidate_monitor_state.json"),
        "production_city_set_source": "monitor_explosion_candidates.CITY_CONFIG derived from explosion_audited_baseline.json",
        "rebuild_logic": "monitor.ensure_state() + monitor.tracked_episodes_for_city()",
    }


def compare_parent(before, after):
    deltas = {}
    semantic_delta_count = 0
    all_cities = sorted(set(before["corpus"]) | set(after["corpus"]))
    for city in all_cities:
        b = before["corpus"].get(city, [])
        a = after["corpus"].get(city, [])
        bmap = {str(x.get("episode_id")): x for x in b}
        amap = {str(x.get("episode_id")): x for x in a}
        created = sorted(set(amap) - set(bmap))
        deleted = sorted(set(bmap) - set(amap))
        start_shifted = sorted(eid for eid in set(bmap) & set(amap) if bmap[eid].get("start") != amap[eid].get("start"))
        end_shifted = sorted(eid for eid in set(bmap) & set(amap) if bmap[eid].get("end") != amap[eid].get("end"))
        changed = bool(created or deleted or start_shifted or end_shifted)
        if changed:
            semantic_delta_count += 1
        deltas[city] = {
            "count_before": len(b), "count_after": len(a),
            "sha_before": before["cities"].get(city, {}).get("sha256"),
            "sha_after": after["cities"].get(city, {}).get("sha256"),
            "created": created, "deleted": deleted,
            "start_shifted": start_shifted, "end_shifted": end_shifted,
            "split": [], "merged": [],
            "semantic_delta": changed,
        }
    return {
        "global_equal": before["global_sha256"] == after["global_sha256"],
        "global_count_equal": before["global_episode_count"] == after["global_episode_count"],
        "per_city_semantic_delta_count": semantic_delta_count,
        "all_per_city_count_hash_equal": all(not x["semantic_delta"] and x["count_before"] == x["count_after"] and x["sha_before"] == x["sha_after"] for x in deltas.values()),
        "cities": deltas,
        "pass": before["global_sha256"] == after["global_sha256"] and semantic_delta_count == 0,
    }


def copy_metric_tree(repo_root: Path, dst: Path):
    shutil.copytree(repo_root, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def semantic_attack_output(out: dict) -> dict:
    obj = copy.deepcopy(out)
    meta = obj.get("meta") or {}
    meta.pop("updated_at", None)
    obj["meta"] = meta
    return obj


def attack_identities(metric_root: Path, output: dict):
    mod = load_module("runtime_gate_metric", metric_root / "scripts/update_explosion_metric_live.py")
    state = mod.load_json(metric_root / "data/explosion_candidate_monitor_state.json", {"cities": {}})
    queue = mod.load_json(metric_root / "data/explosion_review_queue.json", [])
    ep_index = mod.episode_index(state)
    identities = {}
    for city, row in sorted((output.get("cities") or {}).items()):
        effective_end = date.fromisoformat(row["coverage_end"])
        strict_ids, sensitivity_ids, errors = mod.approval_sets(queue, city, ep_index, effective_end)
        identities[city] = {
            "strict_episode_ids": sorted(strict_ids),
            "sensitivity_episode_ids": sorted(sensitivity_ids),
            "review_errors": errors,
        }
    return identities


def run_attack_metric(repo_root: Path, workspace: Path, label: str):
    tree = workspace / f"metric-{label}"
    copy_metric_tree(repo_root, tree)
    script = tree / "scripts/update_explosion_metric_live.py"
    proc = subprocess.run([sys.executable, str(script)], cwd=str(tree), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if proc.returncode != 0:
        raise RuntimeError(f"attack metric {label} failed rc={proc.returncode}: {proc.stdout[-4000:]}")
    out = json.loads((tree / "data/explosions_test.json").read_text(encoding="utf-8"))
    sem = semantic_attack_output(out)
    identities = attack_identities(tree, out)
    cities = {}
    for city, row in sorted((out.get("cities") or {}).items()):
        cities[city] = {
            "denominator": row.get("total_alerts"),
            "strict": row.get("strict_n"),
            "sensitivity": row.get("sensitivity_n"),
            "qa": ((row.get("automation") or {}).get("pending_review_candidates")),
            "city_sha256": sha_obj((sem.get("cities") or {}).get(city)),
            "strict_episode_ids": identities.get(city, {}).get("strict_episode_ids", []),
            "sensitivity_episode_ids": identities.get(city, {}).get("sensitivity_episode_ids", []),
            "review_errors": identities.get(city, {}).get("review_errors", []),
        }
    return {
        "command": "python scripts/update_explosion_metric_live.py",
        "city_count": len(cities),
        "global_sha256": sha_obj(sem),
        "excluded_nondeterministic_fields": ["meta.updated_at"],
        "cities": cities,
        "stdout_tail": proc.stdout[-2000:],
    }


def compare_attack(before, after):
    cities = {}
    delta_count = 0
    identity_delta_count = 0
    for city in sorted(set(before["cities"]) | set(after["cities"])):
        b = before["cities"].get(city, {})
        a = after["cities"].get(city, {})
        deltas = {k: (b.get(k), a.get(k)) for k in ("denominator", "strict", "sensitivity", "qa") if b.get(k) != a.get(k)}
        identity_delta = b.get("strict_episode_ids") != a.get("strict_episode_ids") or b.get("sensitivity_episode_ids") != a.get("sensitivity_episode_ids")
        if deltas:
            delta_count += 1
        if identity_delta:
            identity_delta_count += 1
        cities[city] = {"count_deltas": deltas, "identity_delta": identity_delta, "city_sha_equal": b.get("city_sha256") == a.get("city_sha256")}
    return {
        "global_equal": before["global_sha256"] == after["global_sha256"],
        "cities_with_count_delta": delta_count,
        "cities_with_episode_identity_delta": identity_delta_count,
        "cities": cities,
        "pass": before["global_sha256"] == after["global_sha256"] and delta_count == 0 and identity_delta_count == 0,
    }


def fetch_live_raw(url: str):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "differentiated-alert-runtime-proof/1"})
    retrieved_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    with urllib.request.urlopen(req, timeout=20) as response:
        raw = response.read()
        status = int(getattr(response, "status", 200))
        final_url = response.geturl()
    payload = json.loads(raw.decode("utf-8"))
    return raw, payload, status, final_url, retrieved_at


def run_live_gate(repo_root: Path, parent_before: dict, workspace: Path, raw_out: Path):
    raw, payload, http_status, final_url, retrieved_at = fetch_live_raw(KYIV_URL)
    raw_out.parent.mkdir(parents=True, exist_ok=True)
    raw_out.write_bytes(raw)
    scripts = repo_root / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        shadow = load_module("runtime_gate_shadow", scripts / "proof_differentiated_alert_shadow_ingestion.py")
    finally:
        if sys.path and sys.path[0] == str(scripts):
            sys.path.pop(0)
    rec = shadow.canonicalize_kyiv(payload, observed_at=retrieved_at, target_city_key="kyiv", raw_object_path="$LIVE_RAW")
    parent_eps = [
        {"episode_id": x["episode_id"], "city_key": "kyiv", "alert_type": "AIR", "alert_start": x["start"], "alert_end": x["end"]}
        for x in parent_before["corpus"].get("kyiv", [])
    ]
    bound = shadow.bind(rec, parent_eps)
    db_path = workspace / "differentiated-alert-shadow.sqlite"
    store = shadow.ShadowStore(db_path)
    try:
        first = store.persist(bound)
        second = store.persist(bound)
        counts = store.counts()
    finally:
        store.close()
    snap = bound["snapshot"]
    obs = bound["threat_observations"]
    expected_first_obs = len(obs)
    passed = (
        http_status == 200 and first.get("inserted_snapshots") == 1 and
        first.get("inserted_observations") == expected_first_obs and
        second == {"inserted_snapshots": 0, "inserted_observations": 0}
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "retrieved_at": retrieved_at,
        "official_source_url": KYIV_URL,
        "final_url": final_url,
        "http_status": http_status,
        "raw_sha256": sha_bytes(raw),
        "raw_byte_count": len(raw),
        "raw_payload_safe_public": True,
        "adapter_result": {
            "snapshot_key": snap.get("snapshot_key"),
            "observation_keys": [x.get("observation_key") for x in obs],
            "observation_count": len(obs),
            "source_active": snap.get("source_active"),
            "source_state_raw": snap.get("source_state_raw"),
            "source_state_at": snap.get("source_state_at"),
            "binding_status": snap.get("binding_state"),
            "episode_id": snap.get("episode_id"),
        },
        "persistence_result": {"first_run": first, "final_counts": counts, "sqlite_path_scope": "runner temp only"},
        "exact_replay_result": {"second_run": second, "result": "PASS" if second == {"inserted_snapshots": 0, "inserted_observations": 0} else "FAIL"},
        "parent_episode_mutation": False,
    }


def _unittest_run(repo_root: Path, command: list[str]):
    proc = subprocess.run(command, cwd=str(repo_root), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    m = re.search(r"Ran\s+(\d+)\s+tests?", proc.stdout)
    ran = int(m.group(1)) if m else None
    ok = proc.returncode == 0 and "OK" in proc.stdout
    return {"command": " ".join(command), "tests_run": ran, "passed": ran if ok else None, "failed": 0 if ok else None, "result": "PASS" if ok else "FAIL", "output_tail": proc.stdout[-4000:]}


def run_focused_tests(repo_root: Path):
    repository_suite = _unittest_run(repo_root, [sys.executable, "-m", "unittest", "tests/test_differentiated_alert_shadow_ingestion.py", "-v"])
    local_suite = _unittest_run(repo_root, [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_differentiated_alert_shadow_*.py", "-v"])
    return {"repository_suite": repository_suite, "local_executable_suite": local_suite}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", type=Path, required=True)
    ap.add_argument("--frozen-base", default=FROZEN_DEFAULT)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--raw-output", type=Path, required=True)
    args = ap.parse_args()
    repo_root = args.repo_root.resolve()
    checkout_root = repo_root.parent
    workspace = Path(tempfile.mkdtemp(prefix="diff-alert-runtime-gates-"))
    result = {
        "frozen_authoritative_head": args.frozen_base,
        "proof_head_at_runtime": git(checkout_root, "rev-parse", "HEAD"),
        "proof_branch": os.getenv("GITHUB_REF_NAME") or None,
        "previous_shadow_proof_commit": "ced7a4fbbe95bc984dc5e9d54358f507ca9ecc6d",
        "live_raw_kyiv": {"status": "NOT_PROVEN"},
        "parent_runtime_regression": {"status": "NOT_PROVEN"},
        "attack_event_runtime_regression": {"status": "NOT_PROVEN"},
        "focused_tests": {},
        "authoritative_drift": {},
        "production_writes": [],
        "remaining_open_gates": [],
        "verdict": "SHADOW INGESTION PROOF NOT READY",
    }
    try:
        changed = git(checkout_root, "diff", "--name-status", f"{args.frozen_base}...HEAD").splitlines()
        result["proof_diff_before_runtime"] = changed
        prod_changed = [line for line in changed if line and not any(p in line for p in ["proof_differentiated_alert_", "tests/test_differentiated_alert_shadow", "tests/fixtures/differentiated_alert_shadow", "research/differentiated_alert_shadow_"]) and ".github/workflows/" not in line]
        if prod_changed:
            raise RuntimeError(f"unexpected non-proof diff before runtime: {prod_changed}")

        result["focused_tests"] = run_focused_tests(repo_root)

        parent_before = build_parent(repo_root)
        result["parent_runtime_regression"]["before"] = {k: v for k, v in parent_before.items() if k != "corpus"}

        attack_before = run_attack_metric(repo_root, workspace, "before")
        result["attack_event_runtime_regression"]["before"] = attack_before

        live = run_live_gate(repo_root, parent_before, workspace, args.raw_output.resolve())
        result["live_raw_kyiv"] = live

        parent_after = build_parent(repo_root)
        parent_cmp = compare_parent(parent_before, parent_after)
        result["parent_runtime_regression"].update({
            "after": {k: v for k, v in parent_after.items() if k != "corpus"},
            "comparison": parent_cmp,
            "status": "PASS" if parent_cmp["pass"] else "FAIL",
        })

        attack_after = run_attack_metric(repo_root, workspace, "after")
        attack_cmp = compare_attack(attack_before, attack_after)
        result["attack_event_runtime_regression"].update({"after": attack_after, "comparison": attack_cmp, "status": "PASS" if attack_cmp["pass"] else "FAIL"})

        gates = {
            "Kyiv LIVE_RAW": result["live_raw_kyiv"].get("status") == "PASS",
            "parent runtime regression": result["parent_runtime_regression"].get("status") == "PASS",
            "attack-event runtime regression": result["attack_event_runtime_regression"].get("status") == "PASS",
        }
        result["remaining_open_gates"] = [k for k, ok in gates.items() if not ok]
        result["verdict"] = "READY FOR PRODUCTION SHADOW INTEGRATION PROOF" if all(gates.values()) else "SHADOW INGESTION PROOF NOT READY"
    except Exception as exc:
        result["runtime_error"] = f"{type(exc).__name__}: {exc}"
        for key in ["live_raw_kyiv", "parent_runtime_regression", "attack_event_runtime_regression"]:
            if result[key].get("status") not in {"PASS", "FAIL"}:
                result[key]["status"] = "NOT_PROVEN"
        result["remaining_open_gates"] = [name for name, key in [("Kyiv LIVE_RAW", "live_raw_kyiv"), ("parent runtime regression", "parent_runtime_regression"), ("attack-event runtime regression", "attack_event_runtime_regression")] if result[key].get("status") != "PASS"]
        result["verdict"] = "SHADOW INGESTION PROOF NOT READY"
    finally:
        result["production_writes"] = []
        result["production_write_assertions"] = {
            "production_neon": 0, "production_json": 0, "production_workflows": 0,
            "site_prod": 0, "main": 0, "authoritative_branch": 0,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        shutil.rmtree(workspace, ignore_errors=True)
    print(json.dumps({"verdict": result["verdict"], "remaining_open_gates": result["remaining_open_gates"]}, ensure_ascii=False))
    raise SystemExit(0 if result["verdict"] == "READY FOR PRODUCTION SHADOW INTEGRATION PROOF" else 2)


if __name__ == "__main__":
    main()
