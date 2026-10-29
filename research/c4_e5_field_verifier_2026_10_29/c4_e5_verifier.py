#!/usr/bin/env python3
"""C4-E5 fail-closed H1/H2 exact-field verifier. No DB access or mutations.

Based on the accepted C4-E3 required-field contract. Every FROZEN_AUTHORITY_VERIFIED
field must resolve to its pinned Git object and exact JSON pointer. No Neon field
may supply the expectation. All six actual files require a transaction receipt.
"""
import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

COHORTS = ("H1", "H2")
KINDS = ("classifications", "sources", "events")
KEY = {"classifications": "classification_key", "sources": "source_link_key", "events": "attack_event_key"}
UID = {"classifications": "classification_uid", "sources": "attack_event_source_uid", "events": "attack_event_uid"}
DENOMINATORS = {"H1": (6863, 2340, 119), "H2": (19542, 1429, 961)}
FIELDS = {
 "classifications": ("classification_uid classification_key_version classification_key historical_episode_id city_key alert_type alert_start_at alert_end_at verdict is_event positive_tier event_types qa_reasons_state qa_reasons classifier_reason_codes classifier_blob_sha classifier_methodology_version normalization_version evidence_set_sha256 review_provenance_sha256 human_review_state origin_provenance_sha256 binding_state alert_episode_uid").split(),
 "sources": ("attack_event_source_uid source_link_key_version source_link_key classification_key observation_id source_family source_type source_url telegram_channel telegram_message_id source_timestamp event_timestamp_if_stated excerpt content_sha256 content_hash_basis observation_classification_outcome classification_episode_id evidence_payload retrieval_provenance origin_provenance_sha256").split(),
 "events": ("attack_event_uid attack_event_key_version attack_event_key event_grain historical_episode_id city_key alert_type alert_start_at alert_end_at event_status current_classification_key binding_state alert_episode_uid").split()
}
TIMES = {"alert_start_at", "alert_end_at", "source_timestamp", "event_timestamp_if_stated"}
SET_ARRAYS = {"event_types", "classifier_reason_codes"}
JSON_VALUES = {"qa_reasons", "evidence_payload", "retrieval_provenance"}
AUTH_STATES = {"FROZEN_AUTHORITY_VERIFIED", "REPLAY_DERIVED_ONLY", "ORIGINAL_PROVENANCE_MISSING", "NOT_OBSERVABLE"}
REQUIRED = tuple((cohort, kind) for cohort in COHORTS for kind in KINDS)
SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")

def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)

def normalize(field, value):
    if value is None:
        return None
    if field in TIMES:
        if not isinstance(value, str):
            raise ValueError("timestamp-not-string")
        t = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if t.tzinfo is None or t.utcoffset() is None:
            raise ValueError("timezone-naive")
        return t.astimezone(dt.timezone.utc).isoformat(timespec="microseconds")
    if field in SET_ARRAYS:
        if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
            raise ValueError("invalid-set-array")
        if len(value) != len(set(value)):
            raise ValueError("duplicate-set-member")
        return sorted(value)
    if field in JSON_VALUES:
        if isinstance(value, str):
            value = json.loads(value)
        return canonical(value)
    return value

def sha256_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()

def load_jsonl(path):
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, 1):
            if line.strip():
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError(f"{path}:{line_number}:row-not-object")
                rows.append(row)
    return rows

def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

class GitAuthority:
    def __init__(self, repo):
        self.repo = Path(repo)
        self.cache = {}
    def blob(self, commit, path, sha):
        if not (isinstance(commit, str) and GIT_SHA.fullmatch(commit) and
                isinstance(sha, str) and GIT_SHA.fullmatch(sha) and
                isinstance(path, str) and not path.startswith("/") and ".." not in Path(path).parts):
            raise ValueError("missing-or-invalid-frozen-ref")
        pair = (commit, path, sha)
        if pair not in self.cache:
            actual = subprocess.check_output(
                ["git", "-C", str(self.repo), "rev-parse", f"{commit}:{path}"],
                stderr=subprocess.DEVNULL, timeout=20).decode().strip()
            if actual != sha:
                raise ValueError("git-tree-blob-hash-mismatch")
            raw = subprocess.check_output(
                ["git", "-C", str(self.repo), "cat-file", "blob", sha],
                stderr=subprocess.DEVNULL, timeout=30)
            self.cache[pair] = raw
        return self.cache[pair]
    def field(self, row, field):
        auth = row.get("_field_authority", {}).get(field)
        if not isinstance(auth, dict):
            raise ValueError("field-provenance-missing")
        status = auth.get("status")
        if status not in AUTH_STATES:
            raise ValueError("invalid-field-authority-status")
        if status != "FROZEN_AUTHORITY_VERIFIED":
            raise ValueError("field-not-frozen-authority:" + status)
        commit = auth.get("commit", row.get("_frozen_git_commit"))
        path = auth.get("path", row.get("_frozen_git_path"))
        sha = auth.get("blob", row.get("_frozen_git_blob"))
        raw = self.blob(commit, path, sha)
        pointer = auth.get("json_pointer")
        if not isinstance(pointer, str) or not pointer.startswith("/"):
            raise ValueError("frozen-json-pointer-missing")
        try:
            data = json.loads(raw)
            for part in pointer.split("/")[1:]:
                part = part.replace("~1", "/").replace("~0", "~")
                data = data[int(part)] if isinstance(data, list) else data[part]
        except (ValueError, IndexError, KeyError, TypeError, UnicodeError) as exc:
            raise ValueError("frozen-json-pointer-not-resolved") from exc
        try:
            if normalize(field, data) != normalize(field, row[field]):
                raise ValueError("frozen-blob-value-mismatch")
        except (ValueError, TypeError) as exc:
            raise ValueError("frozen-blob-value-mismatch:" + str(exc)) from exc
        return True

def same_session(receipt, begin):
    return (isinstance(receipt, dict)
        and all(receipt.get(k) == begin.get(k) and begin.get(k) not in (None, "")
                for k in ("snapshot_id", "backend_pid", "transaction_timestamp", "client_nonce"))
        and receipt.get("transaction_read_only") == "on"
        and receipt.get("transaction_isolation") == "repeatable read"
        and receipt.get("pg_is_in_recovery") is True)

def snapshot_proof(inputs):
    path = inputs / "c4_e5_neon_snapshot_manifest.json"
    issues = []
    if not path.exists():
        return False, {}, ["SNAPSHOT_RECEIPT_MISSING"]
    try:
        m = load_json(path)
        begin = m.get("begin", {})
        if not (isinstance(begin, dict) and same_session(begin, begin)):
            issues.append("SNAPSHOT_BEGIN_UNVERIFIED")
        if not same_session(m.get("end"), begin) or m.get("transaction_completion") != "COMMIT_OK":
            issues.append("SNAPSHOT_END_OR_COMMIT_UNVERIFIED")
        if not (m.get("project_id") == "green-cake-44216048"
                and m.get("branch_id") == "br-bold-mode-b5rub8pq"
                and m.get("compute_id") == "ep-calm-rice-b5073ypp"
                and m.get("database_name") == "neondb"
                and m.get("compute_type") == "read_only"):
            issues.append("SNAPSHOT_TARGET_IDENTITY_UNVERIFIED")
        exports = m.get("exports")
        if not isinstance(exports, list) or len(exports) != 6:
            issues.append("SNAPSHOT_INCOMPLETE_EXPORT_RECEIPTS")
            exports = []
        found = {}
        for item in exports:
            name = item.get("name") if isinstance(item, dict) else None
            if name in found:
                issues.append("SNAPSHOT_DUPLICATE_RECEIPT")
            found[name] = item
        for i, (cohort, kind) in enumerate(REQUIRED):
            name = f"{cohort}_{kind}_neon.jsonl"
            r = found.get(name)
            path = inputs / name
            if (not isinstance(r, dict) or r.get("seq") != i
                    or r.get("completed") is not True
                    or not same_session(r.get("before"), begin)
                    or not same_session(r.get("after"), begin)
                    or not (isinstance(r.get("sql_sha256"), str)
                            and SHA256.fullmatch(r["sql_sha256"]))):
                issues.append("SNAPSHOT_EXPORT_RECEIPT_INVALID:" + name)
                continue
            if not path.exists():
                issues.append("SNAPSHOT_EXPORT_FILE_MISSING:" + name)
                continue
            if r.get("sha256") != sha256_file(path) or r.get("bytes") != path.stat().st_size:
                issues.append("SNAPSHOT_EXPORT_HASH_MISMATCH:" + name)
                continue
            if r.get("rows") != len(load_jsonl(path)):
                issues.append("SNAPSHOT_EXPORT_ROW_TRUNCATED:" + name)
        return not issues, m, issues
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        return False, {}, ["SNAPSHOT_MANIFEST_MALFORMED:" + str(exc)]

def compare(inputs, output, repo=".", fixture=False):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    inputs = Path(inputs)
    git = GitAuthority(repo)
    issues, mismatches, notprovable = [], [], []
    observed = Counter()
    full = True
    expected, actual = {}, {}
    denominators = {x: (1, 1, 1) for x in COHORTS} if fixture else DENOMINATORS

    def record(cohort, kind, uid, field, ev, av, category, blob=None, evidence_status="CONFIRMED"):
        entry = {"cohort": cohort, "kind": kind, "UID": str(uid), "field": field,
                 "frozen_value": canonical(ev), "neon_value": canonical(av),
                 "git_blob": blob or "", "category": category, "evidence_status": evidence_status}
        if category.startswith("NOT_PROVABLE") or evidence_status != "CONFIRMED":
            notprovable.append(entry)
        else:
            mismatches.append(entry)
        observed[category] += 1

    gm_path = inputs / "c4_e5_git_authority_manifest.json"
    gm = {}
    if gm_path.exists():
        try:
            gm = load_json(gm_path)
        except (json.JSONDecodeError, TypeError):
            issues.append("GIT_MANIFEST_MALFORMED")
    else:
        issues.append("GIT_MANIFEST_MISSING")

    snapshot_ok, snapshot, ss_issues = snapshot_proof(inputs)
    issues.extend(ss_issues)
    if fixture:
        issues.append("SYNTHETIC_FIXTURE_ONLY")

    for cohort, kind in REQUIRED:
        efile = inputs / f"{cohort}_{kind}_expected.jsonl"
        afile = inputs / f"{cohort}_{kind}_neon.jsonl"
        tag = f"{cohort}/{kind}"
        if not efile.exists() or not afile.exists():
            full = False
            record(cohort, kind, "*", "file", efile.exists(), afile.exists(),
                   "NOT_PROVABLE_MISSING_COMPLETE_EXPORT", evidence_status="NOT_PROVABLE")
            continue
        try:
            e = load_jsonl(efile)
            a = load_jsonl(afile)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            full = False
            record(cohort, kind, "*", "JSONL", str(exc), None,
                   "NOT_PROVABLE_MALFORMED_EXPORT", evidence_status="NOT_PROVABLE")
            continue
        expected[(cohort, kind)] = e
        actual[(cohort, kind)] = a
        ix = KINDS.index(kind)
        if len(e) != denominators[cohort][ix] or len(a) != denominators[cohort][ix]:
            full = False
            record(cohort, kind, "*", "denominator", denominators[cohort][ix],
                   {"git": len(e), "neon": len(a)}, "WRONG_COHORT_DENOMINATOR")
        listed_digest = gm.get("expected_sha256", {}).get(efile.name)
        if listed_digest != sha256_file(efile):
            full = False
            record(cohort, kind, "*", "expected_sha256", listed_digest,
                   sha256_file(efile), "NOT_PROVABLE_GIT_EXPECTATION_DIGEST",
                   evidence_status="NOT_PROVABLE")
        ef = Counter(r.get(KEY[kind]) for r in e)
        af = Counter(r.get(KEY[kind]) for r in a)
        for label, rows in (("git", e), ("neon", a)):
            keys = [r.get(UID[kind]) for r in rows]
            for ident, count in Counter(keys).items():
                if ident is None or count != 1:
                    record(cohort, kind, ident, UID[kind], "unique", count,
                           "DUPLICATE_UID_" + label.upper())
        for label, counts in (("git", ef), ("neon", af)):
            for ident, count in counts.items():
                if ident is None or count != 1:
                    record(cohort, kind, ident, KEY[kind], "unique", count,
                           "DUPLICATE_KEY_" + label.upper())
        emap = {r.get(KEY[kind]): r for r in e}
        amap = {r.get(KEY[kind]): r for r in a}
        for ident in emap.keys() - amap.keys():
            record(cohort, kind, ident, KEY[kind], ident, None, "MISSING_IN_NEON",
                   emap[ident].get("_frozen_git_blob"))
        for ident in amap.keys() - emap.keys():
            record(cohort, kind, ident, KEY[kind], None, ident, "EXTRA_IN_NEON")
        for ident in emap.keys() & amap.keys():
            er, ar = emap[ident], amap[ident]
            c, p, b = (er.get(x) for x in ("_frozen_git_commit", "_frozen_git_path", "_frozen_git_blob"))
            try:
                git.blob(c, p, b)
            except (ValueError, OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
                record(cohort, kind, ident, "_frozen_git_blob", b, None,
                       "NOT_PROVABLE_FROZEN_BLOB_INVALID", b, "NOT_PROVABLE")
            for field in FIELDS[kind]:
                if field not in er or field not in ar:
                    record(cohort, kind, ident, field, er.get(field, "<ABSENT>"),
                           ar.get(field, "<ABSENT>"), "NOT_PROVABLE_REQUIRED_FIELD_ABSENT",
                           b, "NOT_PROVABLE")
                    continue
                try:
                    git.field(er, field)
                except (ValueError, OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                    record(cohort, kind, ident, field, er.get(field), ar.get(field),
                           "NOT_PROVABLE_FIELD_AUTHORITY:" + str(exc), b, "NOT_PROVABLE")
                try:
                    if normalize(field, er[field]) != normalize(field, ar[field]):
                        cat = "FIELD_MISMATCH"
                        if kind == "sources" and field in ("classification_key", "observation_id"):
                            cat = "SOURCE_MEMBERSHIP_MISMATCH"
                        if kind == "events" and field == "current_classification_key":
                            cat = "EVENT_TIP_MISMATCH"
                        if kind == "classifications" and field in ("historical_episode_id", "alert_episode_uid"):
                            cat = "IDENTITY_OR_PARENT_MISMATCH"
                        record(cohort, kind, ident, field, er[field], ar[field], cat, b)
                except (ValueError, TypeError, json.JSONDecodeError) as exc:
                    record(cohort, kind, ident, field, er[field], ar[field],
                           "NORMALIZATION_REJECTED:" + str(exc), b)

    # Cross-record source membership, event tips and binding state are checked by
    # exact classification key; no inner join with the nullable alert parent.
    for cohort in COHORTS:
        if not all((cohort, k) in expected and (cohort, k) in actual for k in KINDS):
            full = False
            continue
        for side_name, side in (("Git", expected), ("Neon", actual)):
            cl = {r.get("classification_key"): r for r in side[(cohort, "classifications")]}
            for s in side[(cohort, "sources")]:
                if s.get("classification_key") not in cl:
                    record(cohort, "sources", s.get("source_link_key"), "classification_key",
                           "existing classification", s.get("classification_key"),
                           "SOURCE_MEMBERSHIP_MISMATCH_" + side_name.upper())
            for event in side[(cohort, "events")]:
                tip = event.get("current_classification_key")
                if tip not in cl:
                    record(cohort, "events", event.get("attack_event_key"), "current_classification_key",
                           "existing current tip", tip, "EVENT_TIP_MISMATCH_" + side_name.upper())
                elif cl[tip].get("binding_state") != event.get("binding_state"):
                    record(cohort, "events", event.get("attack_event_key"), "binding_state",
                           cl[tip].get("binding_state"), event.get("binding_state"),
                           "EVENT_TIP_BINDING_MISMATCH_" + side_name.upper())

    reg_path = inputs / "c4_e5_unbound_25.json"
    if reg_path.exists():
        try:
            reg = load_json(reg_path)
            limit = 1 if fixture else 25
            if not isinstance(reg, list) or len(reg) != limit or len({r["classification_uid"] for r in reg}) != limit:
                issues.append("UNBOUND_REGISTRY_DENOMINATOR_INVALID")
            else:
                for entry in reg:
                    cohort, uid = entry["cohort"], entry["classification_uid"]
                    for side_name, side in (("expected", expected), ("actual", actual)):
                        rows = [r for r in side.get((cohort, "classifications"), [])
                                if r.get("classification_uid") == uid]
                        if len(rows) != 1 or rows[0].get("binding_state") != "UNBOUND" or rows[0].get("alert_episode_uid") is not None:
                            record(cohort, "UNBOUND", uid, "binding_state/alert_episode_uid",
                                   "UNBOUND/NULL", rows, "UNBOUND_CLASSIFICATION_LOST")
                    for kind, field, registry_field in (("sources", "classification_key", "source_link_keys"),
                                                         ("events", "current_classification_key", "event_keys")):
                        ck = entry.get("classification_key")
                        for side_name, side in (("expected", expected), ("actual", actual)):
                            related = sorted(r.get(KEY[kind]) for r in side.get((cohort, kind), [])
                                             if r.get(field) == ck)
                            if related != sorted(entry.get(registry_field, [])):
                                record(cohort, "UNBOUND", uid, registry_field,
                                       entry.get(registry_field, []), related,
                                       "UNBOUND_RELATIONSHIP_MISMATCH_" + side_name.upper())
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            issues.append("UNBOUND_REGISTRY_MALFORMED")
    else:
        issues.append("UNBOUND_REGISTRY_MISSING")

    # Never emit false zeros without six complete, independently evidenced sets.
    counters = ("missing_in_neon", "extra_in_neon", "duplicate_keys", "field_mismatches",
                "source_membership_mismatches", "event_tip_mismatches",
                "not_provable_fields", "pending_owner_parent_exceptions")
    complete_inputs = full and snapshot_ok and not issues and all((c,k) in expected for c,k in REQUIRED)
    summary = {x: None for x in counters}
    if complete_inputs:
        summary = {
         "missing_in_neon": sum(v for k,v in observed.items() if k == "MISSING_IN_NEON"),
         "extra_in_neon": sum(v for k,v in observed.items() if k == "EXTRA_IN_NEON"),
         "duplicate_keys": sum(v for k,v in observed.items() if k.startswith("DUPLICATE_")),
         "field_mismatches": sum(v for k,v in observed.items() if k in ("FIELD_MISMATCH", "IDENTITY_OR_PARENT_MISMATCH")),
         "source_membership_mismatches": sum(v for k,v in observed.items() if k.startswith("SOURCE_MEMBERSHIP")),
         "event_tip_mismatches": sum(v for k,v in observed.items() if k.startswith("EVENT_TIP")),
         "not_provable_fields": len(notprovable),
         "pending_owner_parent_exceptions": 25,
        }
    verdict = "C4_E5_PARTIAL"
    if complete_inputs and mismatches:
        verdict = "C4_E5_MISMATCHES_CONFIRMED"
    if complete_inputs and not mismatches and not notprovable and not fixture:
        verdict = "C4_E5_NONPARENT_FIELD_PARITY_PROVEN_EXCEPTIONS_PENDING"
    result = {"verdict": verdict, "complete_six_exports": complete_inputs,
              "snapshot_receipts_verified": snapshot_ok, "issues": issues,
              "global_counters": summary, "observed_categories": dict(observed),
              "mismatch_rows_observed": len(mismatches),
              "not_provable_rows_observed": len(notprovable),
              "C4_OWNER_EXCEPTIONS_ACCEPTED": "0/25",
              "C4_PRODUCTION_RELEASE_AUTHORIZED": "NO",
              "NEON_AUTHORITY_ACTIVE": "NO",
              "PRODUCTION_CUTOVER_EXECUTED": "NO"}
    for fname, records in (("c4_e5_mismatches.csv", mismatches),
                           ("c4_e5_not_provable.json", notprovable)):
        path = output / fname
        if fname.endswith(".csv"):
            cols = ["cohort", "kind", "UID", "field", "frozen_value", "neon_value",
                    "git_blob", "category", "evidence_status"]
            with path.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=cols)
                w.writeheader()
                w.writerows(records)
        else:
            path.write_text(json.dumps(records, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    for name in ("c4_e5_exact_field_parity.json", "c4_e5_release_gate.json"):
        (output / name).write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    manifest = {p.name: sha256_file(p) for p in sorted(output.iterdir()) if p.is_file()}
    (output / "sha256_manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    return result

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--inputs", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--repo", default=".")
    p.add_argument("--synthetic-fixtures-only", action="store_true")
    args = p.parse_args()
    result = compare(args.inputs, args.out, args.repo, fixture=args.synthetic_fixtures_only)
    print(json.dumps({"verdict": result["verdict"], "issues": result["issues"],
                      "categories": result["observed_categories"]}))
    raise SystemExit(0 if result["verdict"].startswith("C4_E5_NONPARENT_") else 2)
