#!/usr/bin/env python3
from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CITY_SET = ("vinnytsia", "zhytomyr")
EXPECTED = {"vinnytsia": 362, "zhytomyr": 685}
COMMON_BASE = "fb563dc410fe6614263bdc8d4eb55025a987e950"
METHODOLOGY = "historical-attack-event-air-defense-action-v2"
ARTIFACT = REPO_ROOT / "research" / "historical_v2_formalization_vinnytsia_zhytomyr_proof_2026-10-02.json"

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True).strip()

def summarize_node(node: Any) -> dict[str, Any]:
    if isinstance(node, dict):
        return {"type": "dict", "keys": sorted(map(str, node.keys()))[:80], "len": len(node)}
    if isinstance(node, list):
        sample_keys = []
        for item in node[:20]:
            if isinstance(item, dict):
                sample_keys = sorted(map(str, item.keys()))[:80]
                break
        return {"type": "list", "len": len(node), "sample_keys": sample_keys}
    return {"type": type(node).__name__}

def selected_city_node(obj: Any, city: str) -> Any | None:
    if not isinstance(obj, dict):
        return None
    direct_keys = [city, city.replace("_", "-")]
    for k in direct_keys:
        if k in obj:
            return obj[k]
    for container in ("cities", "city_data", "episodes_by_city", "alerts_by_city", "canonical_by_city", "data"):
        value = obj.get(container)
        if isinstance(value, dict):
            for k in direct_keys:
                if k in value:
                    return value[k]
    return None

def count_episode_like(node: Any) -> tuple[int, list[str]]:
    if isinstance(node, list):
        keys = set()
        for item in node[:50]:
            if isinstance(item, dict):
                keys.update(map(str, item.keys()))
        return len(node), sorted(keys)[:100]
    if isinstance(node, dict):
        for k in ("episodes", "alerts", "records", "items", "data"):
            if isinstance(node.get(k), list):
                return len(node[k]), sorted({kk for x in node[k][:50] if isinstance(x, dict) for kk in map(str, x.keys())})[:100]
    return -1, []

def root_json_candidates() -> list[Path]:
    data = ROOT / "data"
    preferred = [
        data / "explosion_audited_baseline.json",
        data / "ukrainealarm_bridge.json",
        data / "alerts_combined.json",
        data / "sevastopol_events.json",
    ]
    names = []
    for p in data.glob("*.json"):
        low = p.name.lower()
        if any(t in low for t in ("alert", "episode", "baseline", "bridge", "source")):
            names.append(p)
    seen = set()
    out = []
    for p in preferred + sorted(names):
        if p.exists() and p not in seen:
            seen.add(p)
            out.append(p)
    return out

def monitor_ast_summary() -> dict[str, Any]:
    path = ROOT / "scripts" / "monitor_explosion_candidates.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    relevant = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            n = node.name.lower()
            if any(t in n for t in ("histor", "evidence", "observ", "classif", "bind", "episode", "alert", "temporal", "provenance")):
                relevant.append({
                    "name": node.name,
                    "args": [a.arg for a in node.args.args],
                })
    return {
        "sha256": sha256_file(path),
        "relevant_callables": relevant,
    }

def main() -> int:
    git("merge-base", "--is-ancestor", COMMON_BASE, "HEAD")
    head = git("rev-parse", "HEAD")
    canonical_probe: dict[str, Any] = {c: [] for c in CITY_SET}
    for path in root_json_candidates():
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            continue
        for city in CITY_SET:
            node = selected_city_node(obj, city)
            if node is None:
                continue
            count, keys = count_episode_like(node)
            canonical_probe[city].append({
                "path": str(path.relative_to(REPO_ROOT)),
                "node": summarize_node(node),
                "episode_like_count": count,
                "record_keys": keys,
            })

    evidence_probe: dict[str, Any] = {}
    input_hashes: dict[str, str] = {}
    for city in CITY_SET:
        path = ROOT / "data" / "explosion_research" / city / "final_evidence.json"
        if not path.exists():
            evidence_probe[city] = {"missing": True}
            continue
        input_hashes[str(path.relative_to(REPO_ROOT))] = sha256_file(path)
        obj = json.loads(path.read_text(encoding="utf-8"))
        evidence_probe[city] = summarize_node(obj)
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, (dict, list)):
                    evidence_probe[city].setdefault("children", {})[str(k)] = summarize_node(v)

    result = {
        "schema_version": 1,
        "proof": "historical-v2-formalization-vinnytsia-zhytomyr-proof-2026-10-02",
        "common_base": COMMON_BASE,
        "tested_head": head,
        "city_set": list(CITY_SET),
        "mode": "FREEZE_EXISTING_EVIDENCE",
        "methodology_version": METHODOLOGY,
        "expected_canonical_counts": EXPECTED,
        "probe": {
            "canonical_candidates": canonical_probe,
            "evidence_shapes": evidence_probe,
            "classifier_ast": monitor_ast_summary(),
        },
        "authoritative_input_sha256": input_hashes,
        "verdict": "PROBE_ONLY_NEEDS_MECHANICAL_MAPPING",
        "mutation_guards": {
            "public_web_research": "NO",
            "source_discovery": "NO",
            "db_neon": "UNTOUCHED",
            "deploy": "NO",
            "production_dashboard_data": "UNTOUCHED",
            "authoritative_evidence_mutations": 0,
            "incorporation": "NO",
        },
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
