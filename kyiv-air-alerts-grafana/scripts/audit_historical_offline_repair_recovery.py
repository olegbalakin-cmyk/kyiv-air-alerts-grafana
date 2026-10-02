#!/usr/bin/env python3
from __future__ import annotations

import ast
import collections
import hashlib
import json
import os
import pathlib
import subprocess
import sys
from typing import Any

REPO = pathlib.Path(__file__).resolve().parents[2]
CAMPAIGN_REL = pathlib.Path("research/historical_attack_event_backfill/historical-attack-events-v2-2026-09-27")
STATUS_REL = pathlib.Path("research/historical_attack_event_backfill_status.json")
MONITOR_REL = pathlib.Path("kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py")
OUT_REL = pathlib.Path("research/historical_offline_repair_recovery_scan_2026-10-02.json")
FROZEN_HEAD = "71cb6f6fbe856cc7b96759310fe9cc9c71cc0453"
IMPLEMENTATION_HEAD = "a208892ef6ba1437e8cfb2244e6863f1203803db"
EXPECTED_BATCHES = 139
EXPECTED_TARGETS = 6863
EXPECTED_ORIGINAL_HASH = "cb9ca2a98fbc1d40e067da84666bf9d7c458bf69436b43876aeced9cabdedd11"

def jdump(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO, text=True)

def summarize_paths(obj: Any, prefix: str = "$", depth: int = 0, max_depth: int = 4, out=None):
    if out is None:
        out = collections.Counter()
    if depth > max_depth:
        return out
    if isinstance(obj, dict):
        out[prefix + "::<dict>"] += 1
        for k, v in obj.items():
            summarize_paths(v, prefix + "." + str(k), depth + 1, max_depth, out)
    elif isinstance(obj, list):
        out[prefix + "::<list>"] += len(obj)
        if obj:
            summarize_paths(obj[0], prefix + "[]", depth + 1, max_depth, out)
    else:
        out[prefix + "::<" + type(obj).__name__ + ">"] += 1
    return out

def keyset_counts(obj: Any, counts=None):
    if counts is None:
        counts = collections.Counter()
    if isinstance(obj, dict):
        ks = tuple(sorted(map(str, obj.keys())))
        counts[ks] += 1
        for v in obj.values():
            keyset_counts(v, counts)
    elif isinstance(obj, list):
        for v in obj:
            keyset_counts(v, counts)
    return counts

def ast_signatures(source: str):
    tree = ast.parse(source)
    rows = []
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = n.name
            if any(tok in name.lower() for tok in ("class", "parse", "time", "city", "match", "bind", "episode", "observ", "candidate")):
                args = [a.arg for a in n.args.posonlyargs + n.args.args + n.args.kwonlyargs]
                rows.append({"name": name, "args": args, "lineno": n.lineno})
    return sorted(rows, key=lambda x: (x["lineno"], x["name"]))

def main() -> int:
    campaign_dir = REPO / CAMPAIGN_REL
    batches = sorted(p for p in campaign_dir.glob("*.json") if p.is_file())
    if len(batches) != EXPECTED_BATCHES:
        raise SystemExit(f"batch-count invariant failed: {len(batches)} != {EXPECTED_BATCHES}")

    head = git("rev-parse", "HEAD").strip()
    base = git("merge-base", IMPLEMENTATION_HEAD, head).strip()
    first = json.loads(batches[0].read_text(encoding="utf-8"))
    status = json.loads((REPO / STATUS_REL).read_text(encoding="utf-8"))

    # Aggregate structural information across the local corpus only.
    keysets = collections.Counter()
    total_bytes = 0
    corpus_hasher = hashlib.sha256()
    for p in batches:
        raw = p.read_bytes()
        total_bytes += len(raw)
        corpus_hasher.update(p.relative_to(REPO).as_posix().encode("utf-8") + b"\0" + raw + b"\0")
        keyset_counts(json.loads(raw), keysets)

    current_source = (REPO / MONITOR_REL).read_text(encoding="utf-8")
    frozen_source = git("show", f"{FROZEN_HEAD}:{MONITOR_REL.as_posix()}")

    test_dir = REPO / "kyiv-air-alerts-grafana/tests"
    proof_tests = []
    for p in sorted(test_dir.glob("*historical*proof*.py")):
        try:
            src = p.read_text(encoding="utf-8")
            names = [n.name for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef)]
            proof_tests.append({"path": p.relative_to(REPO).as_posix(), "functions": names})
        except Exception as exc:
            proof_tests.append({"path": p.relative_to(REPO).as_posix(), "error": repr(exc)})

    cities = status.get("cities", {}) if isinstance(status, dict) else {}
    city_shapes = {}
    total_episode_states = 0
    for city, c in cities.items():
        states = c.get("episode_states", []) if isinstance(c, dict) else []
        total_episode_states += len(states) if isinstance(states, list) else 0
        if isinstance(states, list) and states:
            city_shapes[city] = sorted(states[0].keys())

    diag = {
        "mode": "diagnostic_preflight",
        "head": head,
        "implementation_head": IMPLEMENTATION_HEAD,
        "implementation_is_ancestor": base == IMPLEMENTATION_HEAD,
        "frozen_head_exists": git("cat-file", "-t", FROZEN_HEAD).strip() == "commit",
        "batch_count": len(batches),
        "batch_total_bytes": total_bytes,
        "campaign_input_digest": corpus_hasher.hexdigest(),
        "first_batch_structural_paths": dict(summarize_paths(first)),
        "common_recursive_dict_keysets": [
            {"count": count, "keys": list(keys)}
            for keys, count in keysets.most_common(40)
        ],
        "status_top_keys": sorted(status.keys()) if isinstance(status, dict) else [],
        "status_city_keys": sorted(cities.keys()) if isinstance(cities, dict) else [],
        "status_episode_state_total": total_episode_states,
        "status_episode_state_shapes": city_shapes,
        "monitor_current_candidate_functions": ast_signatures(current_source),
        "monitor_frozen_candidate_functions": ast_signatures(frozen_source),
        "proof_tests": proof_tests,
        "source_network_calls": 0,
    }
    out = REPO / OUT_REL
    out.write_text(json.dumps(diag, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(jdump(diag))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
