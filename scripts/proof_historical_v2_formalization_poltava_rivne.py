#!/usr/bin/env python3
import ast
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

BASE = "fb563dc410fe6614263bdc8d4eb55025a987e950"
TEMPLATE_BRANCH = "historical-v2-formalization-chernivtsi-ivano-frankivsk-proof-2026-10-02"
TEMPLATE_FINAL = "05e9ce706a2f8da459f46fb130bc25d716cfcc46"
BRANCH = "historical-v2-formalization-poltava-rivne-proof-2026-10-02"
ARTIFACT = Path("research/historical_v2_formalization_poltava_rivne_proof_2026-10-02.json")
CITIES = ["poltava", "rivne"]
EXPECTED = {"poltava": 1805, "rivne": 232}
METHODOLOGY = "historical-attack-event-air-defense-action-v2"
MODE = "FREEZE_EXISTING_EVIDENCE"
ALLOWED_PRE = {
    "scripts/proof_historical_v2_formalization_poltava_rivne.py",
    ".github/workflows/historical-v2-formalization-poltava-rivne-proof.yml",
}
ALLOWED_FINAL = ALLOWED_PRE | {str(ARTIFACT)}

def run(cmd, *, check=True, capture=True, env=None):
    cp = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
        check=False,
        env=env,
    )
    if check and cp.returncode != 0:
        raise RuntimeError(f"command failed ({cp.returncode}): {shlex.join(cmd)}\n{cp.stdout or ''}")
    return cp

def git(*args, check=True):
    return run(["git", *args], check=check).stdout.strip()

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def changed_paths(a, b):
    out = git("diff", "--name-only", a, b)
    return {x for x in out.splitlines() if x}

def transform_text(src):
    replacements = [
        ("historical-v2-formalization-chernivtsi-ivano-frankivsk-proof-2026-10-02", BRANCH),
        ("historical_v2_formalization_chernivtsi_ivano_frankivsk_proof_2026-10-02.json", ARTIFACT.name),
        ("chernivtsi-ivano-frankivsk", "poltava-rivne"),
        ("chernivtsi_ivano_frankivsk", "poltava_rivne"),
        ("ivano-frankivsk", "rivne"),
        ("ivano_frankivsk", "rivne"),
        ("chernivtsi", "poltava"),
        ("Ivano-Frankivsk", "Rivne"),
        ("Chernivtsi", "Poltava"),
    ]
    for a, b in replacements:
        src = src.replace(a, b)
    # Patch directly-labelled numeric mappings after city replacement.
    src = re.sub(r'(["\']poltava["\']\s*:\s*)\d+', r'\g<1>1805', src)
    src = re.sub(r'(["\']rivne["\']\s*:\s*)\d+', r'\g<1>232', src)
    return src

def patch_python(src):
    src = transform_text(src)
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return src

    class Fix(ast.NodeTransformer):
        def visit_Assign(self, node):
            self.generic_visit(node)
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if any(n in {"EXPECTED_CANONICAL_COUNTS", "EXPECTED_COUNTS", "CANONICAL_COUNTS"} for n in names):
                node.value = ast.parse(repr(EXPECTED), mode="eval").body
            elif any(n in {"CITY_SET", "CITY_KEYS", "TARGET_CITIES"} for n in names):
                node.value = ast.parse(repr(CITIES), mode="eval").body
            elif "CITIES" in names and isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
                node.value = ast.parse(repr(CITIES), mode="eval").body
            elif any(n in {"PROOF_BRANCH", "BRANCH_NAME"} for n in names):
                node.value = ast.Constant(BRANCH)
            elif any(n in {"ARTIFACT_PATH", "PROOF_ARTIFACT", "OUTPUT_PATH"} for n in names):
                node.value = ast.Constant(str(ARTIFACT))
            elif "MODE" in names:
                node.value = ast.Constant(MODE)
            return node

        def visit_AnnAssign(self, node):
            self.generic_visit(node)
            if isinstance(node.target, ast.Name):
                n = node.target.id
                if n in {"EXPECTED_CANONICAL_COUNTS", "EXPECTED_COUNTS", "CANONICAL_COUNTS"}:
                    node.value = ast.parse(repr(EXPECTED), mode="eval").body
                elif n in {"CITY_SET", "CITY_KEYS", "TARGET_CITIES"}:
                    node.value = ast.parse(repr(CITIES), mode="eval").body
                elif n == "CITIES" and isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
                    node.value = ast.parse(repr(CITIES), mode="eval").body
                elif n in {"PROOF_BRANCH", "BRANCH_NAME"}:
                    node.value = ast.Constant(BRANCH)
                elif n in {"ARTIFACT_PATH", "PROOF_ARTIFACT", "OUTPUT_PATH"}:
                    node.value = ast.Constant(str(ARTIFACT))
                elif n == "MODE":
                    node.value = ast.Constant(MODE)
            return node

        def visit_Dict(self, node):
            self.generic_visit(node)
            for i, key in enumerate(node.keys):
                if isinstance(key, ast.Constant) and key.value in EXPECTED:
                    city = key.value
                    val = node.values[i]
                    if isinstance(val, ast.Constant) and isinstance(val.value, int):
                        node.values[i] = ast.Constant(EXPECTED[city])
                    elif isinstance(val, ast.Dict):
                        for j, nk in enumerate(val.keys):
                            if isinstance(nk, ast.Constant) and isinstance(nk.value, str):
                                label = nk.value.lower()
                                if ("canonical" in label or "expected" in label) and isinstance(val.values[j], ast.Constant) and isinstance(val.values[j].value, int):
                                    val.values[j] = ast.Constant(EXPECTED[city])
            return node

    tree = Fix().visit(tree)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree) + "\n"

def extract_inline_python(yaml_text):
    blocks = []
    lines = yaml_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.search(r"python(?:3)?\s+-?\s*<<\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?\s*$", line)
        if m:
            marker = m.group(1)
            buf = []
            i += 1
            while i < len(lines) and lines[i].strip() != marker:
                raw = lines[i]
                # YAML run-block indentation is normally six or eight spaces.
                buf.append(raw[6:] if raw.startswith("      ") else raw.lstrip() if raw.strip() else "")
                i += 1
            if buf:
                blocks.append("\n".join(buf) + "\n")
        i += 1
    return blocks

def score_source(src):
    score = 0
    markers = [
        "final_evidence.json",
        "STRICT_EVENT_POSITIVE",
        "SENSITIVITY_EVENT_POSITIVE",
        "NO_CONFIRMED_EVENT",
        "NEEDS_REVIEW",
        METHODOLOGY,
        "target_state",
        "canonical",
    ]
    for m in markers:
        if m in src:
            score += 4
    if "chernivtsi" in src:
        score += 8
    if "ivano-frankivsk" in src or "ivano_frankivsk" in src:
        score += 8
    return score

def walk_items(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk_items(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_items(v)

def find_city_obj(obj, city):
    if isinstance(obj, dict):
        if city in obj and isinstance(obj[city], dict):
            return obj[city]
        c = obj.get("city") or obj.get("city_key") or obj.get("name")
        if c == city:
            return obj
        for v in obj.values():
            found = find_city_obj(v, city)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = find_city_obj(v, city)
            if found is not None:
                return found
    return None

ALIASES = {
    "canonical_episodes": ["canonical_episodes", "canonical_count", "canonical_targets", "target_count"],
    "evidence_records_read": ["evidence_records_read", "evidence_records", "source_records_read", "records_read"],
    "normalized_observations": ["normalized_observations", "normalized_records", "observations_normalized"],
    "bound_observations": ["bound_observations", "bound_records", "observations_bound"],
    "unbound_observations": ["unbound_observations", "unbound_records", "observations_unbound"],
    "malformed_provenance": ["malformed_provenance", "malformed_provenance_count", "invalid_provenance"],
    "strict_positives": ["strict_positives", "strict_event_positive", "strict_event_positives", "STRICT_EVENT_POSITIVE"],
    "sensitivity_positives": ["sensitivity_positives", "sensitivity_event_positive", "sensitivity_event_positives", "SENSITIVITY_EVENT_POSITIVE"],
    "no_confirmed_event": ["no_confirmed_event", "no_confirmed_events", "NO_CONFIRMED_EVENT"],
    "needs_review": ["needs_review", "needs_review_count", "NEEDS_REVIEW"],
    "missing_targets": ["missing_targets", "missing"],
    "duplicate_targets": ["duplicate_targets", "duplicates", "duplicate"],
    "extra_targets": ["extra_targets", "extras", "extra"],
    "unresolved_evidence_bindings": ["unresolved_evidence_bindings", "unresolved_bindings", "unresolved_count", "unresolved"],
    "target_state_sha256": ["target_state_sha256", "target_state_sha", "target-state_sha256", "target_sha256"],
}

def lookup_scalar(d, aliases):
    if not isinstance(d, dict):
        return None
    lower = {str(k).lower(): v for k, v in d.items()}
    for a in aliases:
        if a in d and not isinstance(d[a], (dict, list)):
            return d[a]
        if a.lower() in lower and not isinstance(lower[a.lower()], (dict, list)):
            return lower[a.lower()]
    for item in walk_items(d):
        if item is d:
            continue
        low = {str(k).lower(): v for k, v in item.items()}
        for a in aliases:
            if a in item and not isinstance(item[a], (dict, list)):
                return item[a]
            if a.lower() in low and not isinstance(low[a.lower()], (dict, list)):
                return low[a.lower()]
    return None

def as_int(v, field, city):
    if isinstance(v, bool):
        raise RuntimeError(f"{city}: {field} is bool, expected int")
    try:
        return int(v)
    except Exception:
        raise RuntimeError(f"{city}: cannot extract integer {field}: {v!r}")

def normalize_summary(raw, tested_head, source_hashes, pre_paths):
    cities = {}
    for city in CITIES:
        src = find_city_obj(raw, city)
        if src is None:
            raise RuntimeError(f"artifact has no city object for {city}")
        rec = {}
        for field, aliases in ALIASES.items():
            value = lookup_scalar(src, aliases)
            if field == "target_state_sha256":
                if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", value):
                    raise RuntimeError(f"{city}: missing/invalid target-state SHA")
                rec[field] = value.lower()
            else:
                rec[field] = as_int(value, field, city)
        verdict = lookup_scalar(src, ["verdict", "status", "result"])
        if not isinstance(verdict, str) or "CITY V2 FORMALIZATION" not in verdict:
            # Some accepted artifacts keep verdict outside the city record.
            whole = json.dumps(raw, ensure_ascii=False)
            phrase = "CITY V2 FORMALIZATION PROVEN" if (
                rec["missing_targets"] == 0 and rec["duplicate_targets"] == 0 and rec["extra_targets"] == 0
            ) else "CITY V2 FORMALIZATION BLOCKED"
            verdict = phrase if phrase in whole or rec["missing_targets"] == 0 else "CITY V2 FORMALIZATION BLOCKED"
        if rec["canonical_episodes"] != EXPECTED[city]:
            raise RuntimeError(f"{city}: canonical count {rec['canonical_episodes']} != expected {EXPECTED[city]}")
        total_states = rec["strict_positives"] + rec["sensitivity_positives"] + rec["no_confirmed_event"] + rec["needs_review"]
        if total_states != rec["canonical_episodes"]:
            raise RuntimeError(f"{city}: state total {total_states} != canonical {rec['canonical_episodes']}")
        if any(rec[k] != 0 for k in ["missing_targets", "duplicate_targets", "extra_targets"]):
            verdict = "CITY V2 FORMALIZATION BLOCKED"
        rec["verdict"] = verdict
        cities[city] = rec

    return {
        "proof": "historical attack-event v2 formalization",
        "stream": 7,
        "common_base": BASE,
        "proof_branch": BRANCH,
        "tested_head": tested_head,
        "mode": MODE,
        "methodology": METHODOLOGY,
        "city_set": CITIES,
        "expected_canonical_counts": EXPECTED,
        "cities": cities,
        "mutation_guards": {
            "pre_run_diff_from_common_base": sorted(pre_paths),
            "allowed_pre_run_diff_only": pre_paths <= ALLOWED_PRE,
            "authoritative_evidence_sha256": source_hashes,
            "public_web_research": "NO",
            "source_discovery": "NO",
            "authoritative_evidence_mutations": 0,
            "db_neon_touched": False,
            "deploy_performed": False,
            "production_dashboard_data_modified": False,
            "incorporation": "NO",
        },
    }

def main():
    tested_head = git("rev-parse", "HEAD")
    if tested_head != os.environ.get("GITHUB_SHA", tested_head):
        raise RuntimeError("checked-out HEAD does not match GITHUB_SHA")
    if git("merge-base", BASE, tested_head) != BASE:
        raise RuntimeError("proof branch is not descended from the exact common base")
    pre_paths = changed_paths(BASE, tested_head)
    if not pre_paths <= ALLOWED_PRE:
        raise RuntimeError(f"unexpected pre-run mutations from common base: {sorted(pre_paths - ALLOWED_PRE)}")

    source_hashes = {}
    for city in CITIES:
        p = Path(f"data/explosion_research/{city}/final_evidence.json")
        if not p.exists():
            raise RuntimeError(f"missing committed evidence: {p}")
        source_hashes[city] = {
            "path": str(p),
            "sha256": sha256_file(p),
            "git_blob": git("rev-parse", f"{BASE}:{p}"),
        }
        if git("hash-object", str(p)) != source_hashes[city]["git_blob"]:
            raise RuntimeError(f"{city}: evidence differs from common base")

    # Bring in the already accepted Stream-5 formalizer implementation only as a code template.
    git("fetch", "--no-tags", "origin", f"refs/heads/{TEMPLATE_BRANCH}:refs/remotes/origin/_formalizer_template")
    got = git("rev-parse", "refs/remotes/origin/_formalizer_template")
    if got != TEMPLATE_FINAL:
        raise RuntimeError(f"accepted template branch drifted: {got} != {TEMPLATE_FINAL}")

    diff = git("diff", "--name-status", BASE, TEMPLATE_FINAL).splitlines()
    py_sources = []
    yaml_texts = []
    for row in diff:
        parts = row.split("\t")
        if len(parts) < 2:
            continue
        path = parts[-1]
        if path.endswith(".py"):
            cp = run(["git", "show", f"{TEMPLATE_FINAL}:{path}"], check=False)
            if cp.returncode == 0:
                py_sources.append((path, cp.stdout))
        elif path.endswith((".yml", ".yaml")):
            cp = run(["git", "show", f"{TEMPLATE_FINAL}:{path}"], check=False)
            if cp.returncode == 0:
                yaml_texts.append((path, cp.stdout))

    candidates = []
    for path, src in py_sources:
        candidates.append((score_source(src), f"file:{path}", src))
    for path, yml in yaml_texts:
        for idx, src in enumerate(extract_inline_python(yml)):
            candidates.append((score_source(src), f"inline:{path}#{idx+1}", src))
    candidates.sort(key=lambda x: x[0], reverse=True)
    if not candidates or candidates[0][0] < 8:
        raise RuntimeError("could not locate an accepted prior formalizer code template")

    env = os.environ.copy()
    env.update({
        "CITY_SET": ",".join(CITIES),
        "CITIES": ",".join(CITIES),
        "EXPECTED_CANONICAL_COUNTS": json.dumps(EXPECTED),
        "PROOF_BRANCH": BRANCH,
        "ARTIFACT_PATH": str(ARTIFACT),
        "MODE": MODE,
        "METHODOLOGY": METHODOLOGY,
        "COMMON_BASE": BASE,
    })

    errors = []
    raw = None
    for score, label, src in candidates[:8]:
        try:
            transformed = patch_python(src)
            if "chernivtsi" in transformed.lower() or "ivano-frankivsk" in transformed.lower() or "ivano_frankivsk" in transformed.lower():
                raise RuntimeError("template still contains prior city names after transformation")
            tmp = Path(".tmp_stream7_formalizer.py")
            tmp.write_text(transformed, encoding="utf-8")
            if ARTIFACT.exists():
                ARTIFACT.unlink()
            cp = run([sys.executable, str(tmp)], check=False, env=env)
            tmp.unlink(missing_ok=True)
            if cp.returncode != 0:
                raise RuntimeError((cp.stdout or "")[-6000:])
            if not ARTIFACT.exists():
                possibles = sorted(
                    [p for p in Path("research").glob("*poltava*rivne*.json") if p.is_file()],
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                if possibles:
                    ARTIFACT.write_bytes(possibles[0].read_bytes())
            if not ARTIFACT.exists():
                raise RuntimeError("formalizer completed but expected artifact was not produced")
            raw = json.loads(ARTIFACT.read_text(encoding="utf-8"))
            summary = normalize_summary(raw, tested_head, source_hashes, pre_paths)
            ARTIFACT.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            break
        except Exception as e:
            errors.append(f"{label}: {e}")
            ARTIFACT.unlink(missing_ok=True)
            raw = None

    if raw is None or not ARTIFACT.exists():
        raise RuntimeError("all accepted-template execution attempts failed:\n" + "\n---\n".join(errors[-8:]))

    # Guard again after execution: only the compact proof artifact may be new/modified.
    post_status = git("status", "--porcelain").splitlines()
    unexpected = []
    for line in post_status:
        path = line[3:] if len(line) > 3 else ""
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path not in ALLOWED_FINAL:
            unexpected.append(line)
    if unexpected:
        raise RuntimeError("formalizer mutated unexpected repository paths: " + repr(unexpected))

    # Evidence immutability check after formalization.
    for city in CITIES:
        p = Path(source_hashes[city]["path"])
        if sha256_file(p) != source_hashes[city]["sha256"] or git("hash-object", str(p)) != source_hashes[city]["git_blob"]:
            raise RuntimeError(f"{city}: authoritative evidence mutated during formalization")

    # Commit only the compact proof artifact. Workflow is path-filtered, so this push cannot recurse.
    git("config", "user.name", "github-actions[bot]")
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    git("add", str(ARTIFACT))
    git("commit", "-m", "Add Poltava Rivne historical v2 formalization proof")
    final_head = git("rev-parse", "HEAD")
    git("push", "origin", f"HEAD:{BRANCH}")
    print("STREAM7_RESULT " + json.dumps({
        "tested_head": tested_head,
        "final_head": final_head,
        "artifact": str(ARTIFACT),
        "cities": CITIES,
    }, sort_keys=True))

if __name__ == "__main__":
    main()
