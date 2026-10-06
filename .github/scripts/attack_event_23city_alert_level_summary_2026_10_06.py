import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

SOURCE_COMMIT = "efefa399e69eadd3d7fc8393ac1553cfde35f138"
SOURCE_PATH = "research/attack_event_23city_persistence_snapshot_v2_2026-10-04.json"
EXPECTED_BLOB = "8a2f6bd33f879be9db978da59c12c34e61f6f843"
OUTPUT_FILE = "attack_event_23city_alert_level_summary_2026-10-06.json"
EXPECTED_TOTAL = 26405
EXPECTED = {
    "STRICT_EVENT_POSITIVE": 1017,
    "SENSITIVITY_EVENT_POSITIVE": 63,
    "NO_CONFIRMED_EVENT": 23530,
    "NEEDS_REVIEW": 1795,
}
ALLOWED = set(EXPECTED)

def git(*args):
    return subprocess.check_output(["git", *args], text=True).strip()

def blocked(blob, gate, details=None):
    out = {
        "verdict": "23-CITY ALERT-LEVEL SUMMARY = BLOCKED",
        "frozen_source": {
            "path": SOURCE_PATH,
            "commit": SOURCE_COMMIT,
            "expected_blob": EXPECTED_BLOB,
            "actual_blob": blob,
            "blob_verified": blob == EXPECTED_BLOB,
        },
        "validation": {
            "first_failing_gate": gate,
            "details": details,
        },
        "global_totals": None,
        "per_city_summary": None,
        "kyiv_summary": None,
        "kyiv_monthly_summary": None,
        "run": {"github_run_id": os.getenv("GITHUB_RUN_ID"), "workflow_commit": os.getenv("GITHUB_SHA")},
        "mutation_confirmation": {
            "classifier_mutations": 0, "parser_mutations": 0, "source_mutations": 0,
            "alert_state_mutations": 0, "persistence_mutations": 0,
            "neon_db_queries": 0, "neon_db_writes": 0, "deployments": 0,
        },
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return 1

def find_exact_key(obj, key, max_depth=6):
    def walk(x, depth):
        if depth > max_depth:
            return None
        if isinstance(x, dict):
            if key in x:
                return x[key]
            for v in x.values():
                if isinstance(v, (dict, list)):
                    got = walk(v, depth + 1)
                    if got is not None:
                        return got
        elif isinstance(x, list) and len(x) <= 50:
            for v in x:
                if isinstance(v, (dict, list)):
                    got = walk(v, depth + 1)
                    if got is not None:
                        return got
        return None
    return walk(obj, 0)

def find_by_keys(obj, keys, max_depth=6):
    for key in keys:
        got = find_exact_key(obj, key, max_depth=max_depth)
        if got is not None:
            return got
    return None

def find_verdict(obj):
    v = find_by_keys(obj, [
        "verdict", "classification_verdict", "final_verdict",
        "classification", "event_classification", "classification_status"
    ])
    if isinstance(v, str) and v in ALLOWED:
        return v
    found = []
    def walk(x, depth=0):
        if depth > 6:
            return
        if isinstance(x, str) and x in ALLOWED:
            found.append(x)
        elif isinstance(x, dict):
            for vv in x.values():
                walk(vv, depth + 1)
        elif isinstance(x, list) and len(x) <= 50:
            for vv in x:
                walk(vv, depth + 1)
    walk(obj)
    uniq = list(dict.fromkeys(found))
    return uniq[0] if len(uniq) == 1 else None

def parse_dt(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return datetime.fromtimestamp(v, tz=timezone.utc)
    s = str(v).strip()
    if not s:
        return None
    if re.fullmatch(r"\d{10}(?:\.\d+)?", s):
        return datetime.fromtimestamp(float(s), tz=timezone.utc)
    if re.fullmatch(r"\d{13}", s):
        return datetime.fromtimestamp(int(s) / 1000, tz=timezone.utc)
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

START_KEYS = [
    "alert_start", "alert_start_at", "alert_started_at", "alert_start_time",
    "alert_episode_start", "alert_episode_start_at", "episode_start",
    "started_at", "start_at", "start_time", "start"
]
END_KEYS = [
    "alert_end", "alert_end_at", "alert_ended_at", "alert_end_time",
    "alert_episode_end", "alert_episode_end_at", "episode_end",
    "ended_at", "end_at", "end_time", "end"
]

def find_time(rec, keys):
    alert_obj = find_by_keys(rec, ["alert_episode", "alert"])
    if isinstance(alert_obj, dict):
        v = find_by_keys(alert_obj, keys, max_depth=4)
        if v is not None:
            return v
    return find_by_keys(rec, keys, max_depth=6)

def month_from_raw(v, dt):
    if isinstance(v, str):
        m = re.match(r"^(\d{4})-(\d{2})", v.strip())
        if m:
            return f"{m.group(1)}-{m.group(2)}"
    return dt.strftime("%Y-%m") if dt else None

def date_from_raw(v, dt):
    if isinstance(v, str):
        m = re.match(r"^(\d{4}-\d{2}-\d{2})", v.strip())
        if m:
            return m.group(1)
    return dt.strftime("%Y-%m-%d") if dt else None

actual_blob = git("rev-parse", f"{SOURCE_COMMIT}:{SOURCE_PATH}")
if actual_blob != EXPECTED_BLOB:
    sys.exit(blocked(actual_blob, "source_blob_exact", {"expected": EXPECTED_BLOB, "actual": actual_blob}))

raw = subprocess.check_output(["git", "show", f"{SOURCE_COMMIT}:{SOURCE_PATH}"])
root = json.loads(raw)

candidates = []
def sample_score(rec):
    if not isinstance(rec, dict):
        return -1
    return (2 if isinstance(find_exact_key(rec, "city_key"), str) else 0) + (3 if find_verdict(rec) in ALLOWED else 0)

def scan(node, path="$", depth=0):
    if depth > 5:
        return
    if isinstance(node, list):
        if len(node) == EXPECTED_TOTAL:
            s = node[:3] + node[-3:]
            if s and all(isinstance(x, dict) for x in s):
                candidates.append((sum(sample_score(x) for x in s), path, node))
        return
    if isinstance(node, dict):
        if len(node) == EXPECTED_TOTAL:
            vals = list(node.values())
            s = vals[:3] + vals[-3:]
            if s and all(isinstance(x, dict) for x in s):
                candidates.append((sum(sample_score(x) for x in s), path, vals))
        for k, v in node.items():
            if isinstance(v, (dict, list)):
                scan(v, f"{path}.{k}", depth + 1)

scan(root)
if not candidates:
    sys.exit(blocked(actual_blob, "classifications_count", {"reason": "26,405-record collection not found"}))
candidates.sort(key=lambda x: x[0], reverse=True)
score, collection_path, records = candidates[0]
if score <= 0:
    sys.exit(blocked(actual_blob, "mechanical_field_parse", {"reason": "classification collection fields not identifiable"}))

global_counts = Counter()
city = defaultdict(lambda: {
    "total_classifications": 0,
    "STRICT_EVENT_POSITIVE": 0,
    "SENSITIVITY_EVENT_POSITIVE": 0,
    "NO_CONFIRMED_EVENT": 0,
    "NEEDS_REVIEW": 0,
    "_earliest": None, "_earliest_raw": None, "_latest": None, "_latest_raw": None,
})
parsed = []
errors = []

for i, rec in enumerate(records):
    city_key = find_exact_key(rec, "city_key")
    verdict = find_verdict(rec)
    start_raw = find_time(rec, START_KEYS)
    end_raw = find_time(rec, END_KEYS)
    start_dt = parse_dt(start_raw)
    end_dt = parse_dt(end_raw)
    if not isinstance(city_key, str) or not city_key:
        errors.append(f"{i}:city_key")
        continue
    if verdict not in ALLOWED:
        errors.append(f"{i}:verdict")
        continue
    if start_dt is None:
        errors.append(f"{i}:start")
        continue
    if end_dt is None:
        errors.append(f"{i}:end")
        continue
    parsed.append((city_key, verdict, start_raw, start_dt, end_raw, end_dt))
    global_counts[verdict] += 1
    c = city[city_key]
    c["total_classifications"] += 1
    c[verdict] += 1
    if c["_earliest"] is None or start_dt < c["_earliest"]:
        c["_earliest"], c["_earliest_raw"] = start_dt, start_raw
    if c["_latest"] is None or end_dt > c["_latest"]:
        c["_latest"], c["_latest_raw"] = end_dt, end_raw

per_city = {}
for k in sorted(city):
    c = city[k]
    per_city[k] = {
        "total_classifications": c["total_classifications"],
        "STRICT_EVENT_POSITIVE": c["STRICT_EVENT_POSITIVE"],
        "SENSITIVITY_EVENT_POSITIVE": c["SENSITIVITY_EVENT_POSITIVE"],
        "confirmed_positives": c["STRICT_EVENT_POSITIVE"] + c["SENSITIVITY_EVENT_POSITIVE"],
        "NO_CONFIRMED_EVENT": c["NO_CONFIRMED_EVENT"],
        "NEEDS_REVIEW": c["NEEDS_REVIEW"],
        "earliest_alert_start": c["_earliest_raw"],
        "latest_alert_end": c["_latest_raw"],
    }

validation = {
    "source_blob_exact": {"passed": actual_blob == EXPECTED_BLOB, "expected": EXPECTED_BLOB, "actual": actual_blob},
    "classifications_count": {"passed": len(records) == EXPECTED_TOTAL, "expected": EXPECTED_TOTAL, "actual": len(records)},
    "aggregate_verdict_distribution": {
        "passed": all(global_counts[k] == v for k, v in EXPECTED.items()),
        "expected": EXPECTED,
        "actual": {k: global_counts[k] for k in EXPECTED},
    },
    "sum_city_totals": {
        "passed": sum(v["total_classifications"] for v in per_city.values()) == EXPECTED_TOTAL,
        "expected": EXPECTED_TOTAL,
        "actual": sum(v["total_classifications"] for v in per_city.values()),
    },
    "sum_city_confirmed_positives": {
        "passed": sum(v["confirmed_positives"] for v in per_city.values()) == 1080,
        "expected": 1080,
        "actual": sum(v["confirmed_positives"] for v in per_city.values()),
    },
    "mechanical_field_parse": {
        "passed": not errors and len(parsed) == EXPECTED_TOTAL,
        "parsed_rows": len(parsed),
        "errors_count": len(errors),
        "errors_sample": errors[:20],
        "classification_collection_path": collection_path,
    },
}
gate_order = ["source_blob_exact", "classifications_count", "aggregate_verdict_distribution", "sum_city_totals", "sum_city_confirmed_positives", "mechanical_field_parse"]
first_fail = next((g for g in gate_order if not validation[g]["passed"]), None)
validation["first_failing_gate"] = first_fail

keys = sorted(per_city)
kyiv_candidates = [k for k in keys if k.lower() == "kyiv"]
if not kyiv_candidates:
    kyiv_candidates = [k for k in keys if k.lower() in {"kyiv_city", "kyiv-city", "kiev"}]
if not kyiv_candidates:
    kyiv_candidates = [k for k in keys if "kyiv" in k.lower() and "oblast" not in k.lower() and "region" not in k.lower()]
if len(kyiv_candidates) != 1:
    first_fail = first_fail or "mechanical_field_parse"
    validation["first_failing_gate"] = first_fail
    validation["kyiv_identification"] = {"passed": False, "candidates": kyiv_candidates}
    kyiv_key = None
else:
    kyiv_key = kyiv_candidates[0]
    validation["kyiv_identification"] = {"passed": True, "city_key": kyiv_key}

monthly = defaultdict(lambda: Counter())
last_pos = None
last_pos_raw = None
if kyiv_key:
    for city_key, verdict, start_raw, start_dt, end_raw, end_dt in parsed:
        if city_key != kyiv_key:
            continue
        month = month_from_raw(start_raw, start_dt)
        monthly[month]["total_alert_episodes"] += 1
        monthly[month][verdict] += 1
        if verdict in {"STRICT_EVENT_POSITIVE", "SENSITIVITY_EVENT_POSITIVE"} and (last_pos is None or start_dt > last_pos):
            last_pos, last_pos_raw = start_dt, start_raw

monthly_out = []
for month in sorted(monthly):
    m = monthly[month]
    monthly_out.append({
        "month": month,
        "total_alert_episodes": m["total_alert_episodes"],
        "STRICT_EVENT_POSITIVE": m["STRICT_EVENT_POSITIVE"],
        "SENSITIVITY_EVENT_POSITIVE": m["SENSITIVITY_EVENT_POSITIVE"],
        "confirmed_positives": m["STRICT_EVENT_POSITIVE"] + m["SENSITIVITY_EVENT_POSITIVE"],
        "NO_CONFIRMED_EVENT": m["NO_CONFIRMED_EVENT"],
        "NEEDS_REVIEW": m["NEEDS_REVIEW"],
    })

kyiv_summary = None
if kyiv_key:
    k = per_city[kyiv_key]
    kyiv_summary = {
        "city_key": kyiv_key,
        "total_alert_episodes": k["total_classifications"],
        "confirmed_positives": k["confirmed_positives"],
        "STRICT_EVENT_POSITIVE": k["STRICT_EVENT_POSITIVE"],
        "SENSITIVITY_EVENT_POSITIVE": k["SENSITIVITY_EVENT_POSITIVE"],
        "earliest_alert_start": k["earliest_alert_start"],
        "latest_alert_end": k["latest_alert_end"],
        "last_confirmed_positive_alert_date": date_from_raw(last_pos_raw, last_pos) if last_pos else None,
        "last_confirmed_positive_month": month_from_raw(last_pos_raw, last_pos) if last_pos else None,
    }

complete = first_fail is None
out = {
    "verdict": "23-CITY ALERT-LEVEL SUMMARY = COMPLETE" if complete else "23-CITY ALERT-LEVEL SUMMARY = BLOCKED",
    "frozen_source": {
        "path": SOURCE_PATH, "commit": SOURCE_COMMIT, "expected_blob": EXPECTED_BLOB,
        "actual_blob": actual_blob, "blob_verified": actual_blob == EXPECTED_BLOB,
    },
    "validation": validation,
    "global_totals": {
        "total_classifications": len(records),
        "STRICT_EVENT_POSITIVE": global_counts["STRICT_EVENT_POSITIVE"],
        "SENSITIVITY_EVENT_POSITIVE": global_counts["SENSITIVITY_EVENT_POSITIVE"],
        "confirmed_positives": global_counts["STRICT_EVENT_POSITIVE"] + global_counts["SENSITIVITY_EVENT_POSITIVE"],
        "NO_CONFIRMED_EVENT": global_counts["NO_CONFIRMED_EVENT"],
        "NEEDS_REVIEW": global_counts["NEEDS_REVIEW"],
    },
    "per_city_summary": per_city,
    "kyiv_summary": kyiv_summary,
    "kyiv_monthly_summary": monthly_out,
    "run": {"github_run_id": os.getenv("GITHUB_RUN_ID"), "workflow_commit": os.getenv("GITHUB_SHA")},
    "mutation_confirmation": {
        "classifier_mutations": 0, "parser_mutations": 0, "source_mutations": 0,
        "alert_state_mutations": 0, "persistence_mutations": 0,
        "neon_db_queries": 0, "neon_db_writes": 0, "deployments": 0,
    },
}
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2, default=str)
    f.write("\n")
sys.exit(0 if complete else 1)
