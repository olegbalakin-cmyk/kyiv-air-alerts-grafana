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
CAMPAIGN_SUFFIX = pathlib.Path("research/historical_attack_event_backfill/historical-attack-events-v2-2026-09-27")
STATUS_NAME = "historical_attack_event_backfill_status.json"
MONITOR_NAME = "monitor_explosion_candidates.py"
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

def unique_path(pattern: str, kind: str) -> pathlib.Path:
    hits = sorted(p for p in REPO.glob(pattern) if p.is_file())
    if len(hits) != 1:
        raise SystemExit(f"{kind} discovery invariant failed: {len(hits)} matches for {pattern}")
    return hits[0]

def main() -> int:
    campaign_dirs = sorted(p for p in REPO.glob("**/" + CAMPAIGN_SUFFIX.as_posix()) if p.is_dir())
    if len(campaign_dirs) != 1:
        raise SystemExit(f"campaign-dir discovery invariant failed: {len(campaign_dirs)}")
    campaign_dir = campaign_dirs[0]
    batches = sorted(p for p in campaign_dir.rglob("*.json") if p.is_file())
    if len(batches) != EXPECTED_BATCHES:
        raise SystemExit(f"batch-count invariant failed: {len(batches)} != {EXPECTED_BATCHES}")

    head = git("rev-parse", "HEAD").strip()
    base = git("merge-base", IMPLEMENTATION_HEAD, head).strip()
    first = json.loads(batches[0].read_text(encoding="utf-8"))
    status_path = unique_path("**/research/" + STATUS_NAME, "status")
    status = json.loads(status_path.read_text(encoding="utf-8"))

    # Aggregate structural information across the local corpus only.
    keysets = collections.Counter()
    total_bytes = 0
    corpus_hasher = hashlib.sha256()
    for p in batches:
        raw = p.read_bytes()
        total_bytes += len(raw)
        corpus_hasher.update(p.relative_to(REPO).as_posix().encode("utf-8") + b"\0" + raw + b"\0")
        keyset_counts(json.loads(raw), keysets)

    monitor_path = unique_path("**/scripts/" + MONITOR_NAME, "monitor")
    monitor_rel = monitor_path.relative_to(REPO).as_posix()
    current_source = monitor_path.read_text(encoding="utf-8")
    frozen_source = git("show", f"{FROZEN_HEAD}:{monitor_rel}")

    test_dir = monitor_path.parent.parent / "tests"
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

    grep_hash = subprocess.run(
        ["git", "grep", "-n", EXPECTED_ORIGINAL_HASH],
        cwd=REPO, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ).stdout.splitlines()
    grep_case7 = subprocess.run(
        ["git", "grep", "-n", "7f9455ee73cf2aaa84b9d6e3"],
        cwd=REPO, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ).stdout.splitlines()
    grep_case18 = subprocess.run(
        ["git", "grep", "-n", "6069b17ec096cae0912ad9bd"],
        cwd=REPO, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ).stdout.splitlines()

    def source_window(source: str, func_name: str, before: int = 2, after: int = 120) -> str:
        lines = source.splitlines()
        needle = "def " + func_name + "("
        for idx, line in enumerate(lines):
            if line.lstrip().startswith(needle):
                return "\n".join(lines[max(0, idx-before):min(len(lines), idx+after)])
        return ""

    city_status_shapes = {}
    for city, payload in cities.items():
        if isinstance(payload, dict):
            city_status_shapes[city] = {
                "keys": sorted(payload.keys()),
                "value_types": {k: type(v).__name__ for k, v in payload.items()},
                "nested_dict_keys": {
                    k: sorted(v.keys())[:50] for k, v in payload.items() if isinstance(v, dict)
                },
                "list_lengths": {
                    k: len(v) for k, v in payload.items() if isinstance(v, list)
                },
            }

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
        "git_grep_expected_hash": grep_hash[:50],
        "git_grep_case7": grep_case7[:50],
        "git_grep_case18": grep_case18[:50],
        "status_city_shapes": city_status_shapes,
        "current_function_windows": {
            "dated_live_update_event_times": source_window(current_source, "dated_live_update_event_times"),
            "exact_city_classification_evidence": source_window(current_source, "exact_city_classification_evidence"),
            "classify_candidate": source_window(current_source, "classify_candidate", after=220),
            "apply_classification_decision": source_window(current_source, "apply_classification_decision", after=120),
        },
        "frozen_function_windows": {
            "exact_city_classification_evidence": source_window(frozen_source, "exact_city_classification_evidence"),
            "classify_candidate": source_window(frozen_source, "classify_candidate", after=220),
        },
        "source_network_calls": 0,
    }
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(diag, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(jdump(diag))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
