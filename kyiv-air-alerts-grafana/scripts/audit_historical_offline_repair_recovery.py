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


    # Targeted local-only diagnostics for canonical target-state serialization and controls.
    frozen_states = []
    frozen_state_examples = {}
    for city, payload in cities.items():
        if city == "kyiv" or not isinstance(payload, dict):
            continue
        state_map = payload.get("episode_states") or {}
        if not isinstance(state_map, dict):
            continue
        for episode_id, state_payload in state_map.items():
            frozen_states.append((city, episode_id, state_payload))
            if len(frozen_state_examples) < 6:
                frozen_state_examples[f"{city}:{episode_id}"] = state_payload
    frozen_states.sort(key=lambda x: (x[0], x[1]))

    state_rows_variants = {}
    def add_variant(name, rows):
        payload = jdump(rows).encode("utf-8")
        state_rows_variants[name] = sha256_bytes(payload)

    add_variant("city_episode_state_payload", [
        {"city_key": cty, "episode_id": eid, "state": sp}
        for cty, eid, sp in frozen_states
    ])
    add_variant("city_episode_state_string", [
        {"city_key": cty, "episode_id": eid, "state": (sp.get("state") if isinstance(sp, dict) else sp)}
        for cty, eid, sp in frozen_states
    ])
    add_variant("city_episode_outcome_string", [
        {"city": cty, "episode_id": eid, "outcome": (sp.get("state") if isinstance(sp, dict) else sp)}
        for cty, eid, sp in frozen_states
    ])
    add_variant("triples", [
        [cty, eid, (sp.get("state") if isinstance(sp, dict) else sp)]
        for cty, eid, sp in frozen_states
    ])
    add_variant("state_dict_nested", {
        cty: {eid: (sp.get("state") if isinstance(sp, dict) else sp)
              for c, eid, sp in frozen_states if c == cty}
        for cty in sorted({x[0] for x in frozen_states})
    })


    # Brute-force a bounded family of explicit canonical-state serializations.
    simple_rows = [
        {"city_key": cty, "episode_id": eid, "state": (sp.get("state") if isinstance(sp, dict) else sp)}
        for cty, eid, sp in frozen_states
    ]
    hash_search_matches = []
    row_field_variants = [
        ("city_key", "episode_id", "state"),
        ("city", "episode_id", "state"),
        ("city_key", "episode_id", "outcome"),
        ("city", "episode_id", "outcome"),
        ("city_key", "episode_id", "classifier_result"),
        ("city", "episode_id", "classifier_result"),
    ]
    for city_field, id_field, state_field in row_field_variants:
        rows = [{city_field:r["city_key"], id_field:r["episode_id"], state_field:r["state"]} for r in simple_rows]
        objects = [
            ("list", rows),
            ("wrapped_targets", {"targets": rows}),
            ("wrapped_target_states", {"target_states": rows}),
            ("wrapped_episode_states", {"episode_states": rows}),
        ]
        for obj_name, obj in objects:
            for sort_keys in (True, False):
                for ensure_ascii in (True, False):
                    for compact in (True, False):
                        kwargs = {"sort_keys":sort_keys, "ensure_ascii":ensure_ascii}
                        if compact:
                            kwargs["separators"] = (",", ":")
                        raw = json.dumps(obj, **kwargs)
                        for suffix in ("", "\n"):
                            h = sha256_bytes((raw+suffix).encode("utf-8"))
                            if h == EXPECTED_ORIGINAL_HASH:
                                hash_search_matches.append({
                                    "kind":"json", "fields":[city_field,id_field,state_field],
                                    "object":obj_name, "sort_keys":sort_keys,
                                    "ensure_ascii":ensure_ascii, "compact":compact,
                                    "newline":bool(suffix)
                                })
    for sep_name, sep in (("tab","\t"),("comma",","),("pipe","|")):
        for order_name, order in (
            ("city_id_state", ("city_key","episode_id","state")),
            ("id_city_state", ("episode_id","city_key","state")),
        ):
            raw = "\n".join(sep.join(str(r[k]) for k in order) for r in simple_rows)
            for final_nl in (False, True):
                h=sha256_bytes((raw+("\n" if final_nl else "")).encode("utf-8"))
                if h == EXPECTED_ORIGINAL_HASH:
                    hash_search_matches.append({"kind":"delimited","sep":sep_name,"order":order_name,"newline":final_nl})


    state_rows_status_fields = []
    for cty, eid, sp in frozen_states:
        spd = sp if isinstance(sp, dict) else {"state": sp}
        state_rows_status_fields.append({
            "city_key": cty,
            "episode_id": eid,
            "batch": spd.get("batch"),
            "observation_count": spd.get("observation_count"),
            "state": spd.get("state"),
        })
    status_field_hash_variants = {}
    status_field_sets = [
        ("city_episode_batch_obs_state", ["city_key","episode_id","batch","observation_count","state"]),
        ("city_episode_batch_state", ["city_key","episode_id","batch","state"]),
        ("city_episode_obs_state", ["city_key","episode_id","observation_count","state"]),
        ("city_episode_state", ["city_key","episode_id","state"]),
    ]
    for name, fields in status_field_sets:
        rows = [{k:r.get(k) for k in fields} for r in state_rows_status_fields]
        for sort_keys in (True, False):
            for compact in (True, False):
                raw = json.dumps(rows, ensure_ascii=False, sort_keys=sort_keys, **({"separators":(",",":")} if compact else {}))
                status_field_hash_variants[f"{name}|sort={sort_keys}|compact={compact}"] = sha256_bytes(raw.encode("utf-8"))


    ordering_hash_matches = []
    frozen_city_order = [c for c in (status.get("frozen_cities") or []) if c in cities and c != "kyiv"]
    if not frozen_city_order:
        frozen_city_order = [c for c in cities.keys() if c != "kyiv"]
    orderings = {}
    # Frozen status insertion order.
    orderings["status_insertion"] = [
        (cty, eid, sp)
        for cty in frozen_city_order
        for eid, sp in ((cities.get(cty) or {}).get("episode_states") or {}).items()
    ]
    # Explicit frozen episode-id order retained in each city status.
    orderings["frozen_episode_ids"] = [
        (cty, eid, ((cities.get(cty) or {}).get("episode_states") or {}).get(eid))
        for cty in frozen_city_order
        for eid in ((cities.get(cty) or {}).get("frozen_episode_ids") or [])
    ]
    # Global lexical fallback.
    orderings["lexical"] = frozen_states

    for ordering_name, ordered in orderings.items():
        bases = []
        for cty,eid,sp in ordered:
            spd = sp if isinstance(sp, dict) else {"state":sp}
            bases.append({
                "city_key":cty, "city":cty, "episode_id":eid,
                "batch":spd.get("batch"), "observation_count":spd.get("observation_count"),
                "state":spd.get("state"), "qa_reasons":spd.get("qa_reasons"),
                "attempts":spd.get("attempts")
            })
        fieldsets = [
            ["city_key","episode_id","state"],
            ["city_key","episode_id","batch","observation_count","state"],
            ["city_key","episode_id","batch","observation_count","qa_reasons","state"],
            ["city_key","episode_id","attempts","batch","observation_count","qa_reasons","state"],
            ["city","episode_id","state"],
            ["episode_id","state"],
        ]
        for fields in fieldsets:
            rows=[{k:r.get(k) for k in fields} for r in bases]
            for sort_keys in (True,False):
                for compact in (True,False):
                    raw=json.dumps(rows,ensure_ascii=False,sort_keys=sort_keys,**({"separators":(",",":")} if compact else {}))
                    for nl in ("","\n"):
                        h=sha256_bytes((raw+nl).encode("utf-8"))
                        if h==EXPECTED_ORIGINAL_HASH:
                            ordering_hash_matches.append({
                                "ordering":ordering_name,"fields":fields,"sort_keys":sort_keys,
                                "compact":compact,"newline":bool(nl)
                            })

    episode_rows_all=[]
    for p in batches:
        batch=json.loads(p.read_text(encoding="utf-8"))
        for er in batch.get("episode_results") or []:
            episode_rows_all.append(dict(er))
    episode_rows_all.sort(key=lambda r:(str(r.get("city") or ""),str(r.get("episode_id") or "")))
    episode_result_hash_variants={}
    for name, rows in [
        ("full_episode_results", episode_rows_all),
        ("core_episode_results", [
            {k:r.get(k) for k in ("city","episode_id","alert_start","alert_end","classifier_result")}
            for r in episode_rows_all
        ]),
        ("core_with_sources", [
            {k:r.get(k) for k in ("city","episode_id","alert_start","alert_end","classifier_result","source_observation_ids")}
            for r in episode_rows_all
        ]),
    ]:
        for sort_keys in (True,False):
            for compact in (True,False):
                raw=json.dumps(rows,ensure_ascii=False,sort_keys=sort_keys,**({"separators":(",",":")} if compact else {}))
                h=sha256_bytes(raw.encode("utf-8"))
                episode_result_hash_variants[f"{name}|sort={sort_keys}|compact={compact}"]=h
                if h==EXPECTED_ORIGINAL_HASH:
                    ordering_hash_matches.append({"ordering":"episode_results_lexical","variant":name,"sort_keys":sort_keys,"compact":compact})


    # Test the accepted sample-freeze target record schema over the full universe.
    er_by_key = {}
    for er in episode_rows_all:
        er_by_key[(str(er.get("city") or ""), str(er.get("episode_id") or ""))] = er
    sample_schema_hashes = {}
    sample_schema_matches = []
    for ordering_name, ordered in orderings.items():
        rows=[]
        for cty,eid,sp in ordered:
            spd=sp if isinstance(sp,dict) else {"state":sp}
            er=er_by_key.get((cty,eid)) or {}
            rows.append({
                "city_key":cty,
                "episode_id":eid,
                "alert_start":er.get("alert_start"),
                "alert_end":er.get("alert_end"),
                "original_batch":spd.get("batch"),
                "original_observation_count":spd.get("observation_count"),
                "final_outcome":spd.get("state"),
            })
        for sort_keys in (True,False):
            for compact in (True,False):
                raw=json.dumps(rows,ensure_ascii=False,sort_keys=sort_keys,**({"separators":(",",":")} if compact else {}))
                for nl in ("","\n"):
                    key=f"{ordering_name}|sort={sort_keys}|compact={compact}|nl={bool(nl)}"
                    h=sha256_bytes((raw+nl).encode("utf-8"))
                    sample_schema_hashes[key]=h
                    if h==EXPECTED_ORIGINAL_HASH:
                        sample_schema_matches.append(key)

    control_obs = {}
    case18_obs = []
    classifier_results = collections.Counter()
    obs_count = 0
    for p in batches:
        batch = json.loads(p.read_text(encoding="utf-8"))
        for er in batch.get("episode_results") or []:
            classifier_results[str(er.get("classifier_result"))] += 1
        for obs in batch.get("observations") or []:
            obs_count += 1
            oid = str(obs.get("observation_id") or "")
            if oid == "7f9455ee73cf2aaa84b9d6e3":
                control_obs["case7"] = {"batch": p.relative_to(REPO).as_posix(), "observation": obs}
            if str(obs.get("classification_episode_id") or "") == "6069b17ec096cae0912ad9bd" or "6069b17ec096cae0912ad9bd" in json.dumps(obs.get("candidate_matching") or {}):
                case18_obs.append({"batch": p.relative_to(REPO).as_posix(), "observation": obs})
        for er in batch.get("episode_results") or []:
            if str(er.get("episode_id") or "") == "6069b17ec096cae0912ad9bd":
                control_obs["case18_target"] = {"batch": p.relative_to(REPO).as_posix(), "episode_result": er}

    # Also capture observations in the case-18 batch whose text contains the newly accepted locative.
    for p in batches:
        if "sevastopol" not in p.as_posix():
            continue
        batch = json.loads(p.read_text(encoding="utf-8"))
        if any(str(er.get("episode_id") or "") == "6069b17ec096cae0912ad9bd" for er in batch.get("episode_results") or []):
            for obs in batch.get("observations") or []:
                if "севастополе" in str(obs.get("excerpt") or "").casefold():
                    case18_obs.append({"batch": p.relative_to(REPO).as_posix(), "observation": obs})

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
        "target_state_count": len(frozen_states),
        "target_state_examples": frozen_state_examples,
        "target_hash_variants": state_rows_variants,
        "target_hash_search_matches": hash_search_matches,
        "status_field_hash_variants": status_field_hash_variants,
        "ordering_hash_matches": ordering_hash_matches,
        "episode_result_hash_variants": episode_result_hash_variants,
        "frozen_city_order": frozen_city_order,
        "sample_schema_hashes": sample_schema_hashes,
        "sample_schema_matches": sample_schema_matches,
        "classifier_result_counts": dict(classifier_results),
        "observation_count_direct": obs_count,
        "control_records": control_obs,
        "case18_relevant_observations": case18_obs,
        "git_grep_case7": grep_case7[:50],
        "git_grep_case18": grep_case18[:50],
        "status_city_shapes": city_status_shapes,
        "current_function_windows": {
            "classification_text": source_window(current_source, "classification_text", after=80),
            "classification_segments": source_window(current_source, "classification_segments", after=80),
            "match_candidate_to_episodes": source_window(current_source, "match_candidate_to_episodes", after=100),
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
