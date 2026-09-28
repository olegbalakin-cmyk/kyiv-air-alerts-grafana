#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PRODUCTION_BASE_SHA = "82494701ae8b49b9780eb42d535e0990fd889151"
ACCEPTED_PHASE1_REFERENCE_SHA = "73b841c0d3adfeff078bbf427efaecc5db985973"
EXPECTED_PERSISTENCE_BLOB = "06f3098df63d7aaf2348c366b6a351901926cb53"
EXPECTED_DDL_BLOB = "3b8af7940b23aae03a4f6b434d90d97dde10bfc0"
EXPECTED_PRESENT = "b3df9090f7264ddbd726e113"
KNOWN_BAD_ABSENT = "7dd411c2a2587efc740a1a66"


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def run_json(code: str, *args: str, cwd: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, "-c", code, *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"subprocess failed rc={proc.returncode}; stdout={proc.stdout!r}; stderr={proc.stderr!r}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"subprocess did not emit JSON; stdout={proc.stdout!r} stderr={proc.stderr!r}"
        ) from exc


CANONICAL_SNAPSHOT_CODE = r"""
import json
import sys
from pathlib import Path

repo_root = Path(sys.argv[1]).resolve()
app_root = repo_root / "kyiv-air-alerts-grafana"
sys.path.insert(0, str(app_root / "scripts"))
from db_phase1_lviv_import import build_lviv_persistence_payload

payload = build_lviv_persistence_payload(
    app_root / "tests" / "fixtures" / "db_phase1"
)
payload["episodes"] = sorted(payload["episodes"], key=lambda x: x["legacy_episode_id"])
payload["source_observations"] = sorted(
    payload["source_observations"],
    key=lambda x: (x["source_key"], x["source_record_key_version"], x["source_record_key"]),
)
print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
"""


PRODUCT_SNAPSHOT_CODE = r"""
import json
import sys
from datetime import datetime
from pathlib import Path

repo_root = Path(sys.argv[1]).resolve()
raw_rows_path = Path(sys.argv[2]).resolve()
app_root = repo_root / "kyiv-air-alerts-grafana"
sys.path.insert(0, str(app_root / "scripts"))

import expand_multicity_production as base
import apply_ukrainealarm_bridge as bridge

rows = json.loads(raw_rows_path.read_text(encoding="utf-8"))["rows"]

if hasattr(base, "proxy_alerts_and_lviv_observations_from_rows"):
    base.PROXY_CONFIG = {"lviv": base.PROXY_CONFIG["lviv"]}
    base.PROXY_KEYS = ["lviv"]
    base.CITY_LABELS = {"lviv": "Львів"}
    proxy = base.proxy_alerts_and_lviv_observations_from_rows(rows)[0]["lviv"]
else:
    import csv
    import io
    fieldnames = sorted({key for row in rows for key in row})
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    payload = buf.getvalue().encode("utf-8-sig")

    class Response:
        content = payload
        def raise_for_status(self):
            return None

    class Session:
        def get(self, *args, **kwargs):
            return Response()

    base.http_session = lambda: Session()
    base.PROXY_CONFIG = {"lviv": base.PROXY_CONFIG["lviv"]}
    base.PROXY_KEYS = ["lviv"]
    base.CITY_LABELS = {"lviv": "Львів"}
    proxy = base.fetch_proxy_alerts()["lviv"]

static, _ = bridge.load_static_bridge()
store = bridge.load_store()
status = store.get("regions", {}).get("lviv", {})
continuous = bool(status.get("continuous"))
api_alerts = bridge.api_store_alerts(store, "lviv") if continuous else []
combined = bridge.union_alerts(
    [*proxy, *static["lviv"], *api_alerts],
    "historical_proxy_plus_alertsinua_plus_ukrainealarm",
)

data = json.loads((app_root / "data" / "dashboard_data.json").read_text(encoding="utf-8"))
meta = dict(data.get("cities", {}).get("lviv", {}).get("meta", {}))
meta.update(
    {
        "proxy_completed_alert_episodes": len(combined),
        "latest_proxy_record_start": max(a.start for a in combined).isoformat(),
        "latest_proxy_record_end": max(a.end for a in combined).isoformat(),
        "data_source_kind": "raion proxy history + Alerts.in.ua seam + official UkraineAlarm API",
        "static_bridge_events": len(static["lviv"]),
        "ukrainealarm_bridge_events": len(api_alerts),
        "ukrainealarm_bridge_continuous": continuous,
        "ukrainealarm_api_region_id": status.get("region_id"),
    }
)
fixed_now = datetime(2026, 9, 28, 12, 0, 0, tzinfo=base.TZ)
out = base.build_outputs(combined, fixed_now, meta)
base.enrich_weekly(out, combined)
base.trim_to_complete_coverage(
    out,
    base.date.fromisoformat(base.PROXY_CONFIG["lviv"]["coverage_start"]),
)
snapshot = {
    "combined": [
        {"start": a.start.isoformat(), "end": a.end.isoformat(), "source": a.source}
        for a in combined
    ],
    "dashboard_city": out,
}
print(json.dumps(snapshot, ensure_ascii=False, sort_keys=True))
"""


def indexed(rows: list[dict], field: str) -> dict[str, dict]:
    return {str(row[field]): row for row in rows}


def compare_payloads(accepted: dict, current: dict) -> dict:
    ae = indexed(accepted["episodes"], "legacy_episode_id")
    ce = indexed(current["episodes"], "legacy_episode_id")
    asrc = indexed(accepted["source_observations"], "source_record_key")
    csrc = indexed(current["source_observations"], "source_record_key")
    common_e = sorted(set(ae) & set(ce))
    common_s = sorted(set(asrc) & set(csrc))
    return {
        "missing_episode_ids": sorted(set(ae) - set(ce)),
        "unexpected_episode_ids": sorted(set(ce) - set(ae)),
        "episode_mismatches": [
            {"episode_id": key, "accepted": ae[key], "refactored": ce[key]}
            for key in common_e
            if ae[key] != ce[key]
        ],
        "missing_source_record_keys": sorted(set(asrc) - set(csrc)),
        "unexpected_source_record_keys": sorted(set(csrc) - set(asrc)),
        "source_observation_mismatches": [
            {"source_record_key": key, "accepted": asrc[key], "refactored": csrc[key]}
            for key in common_s
            if asrc[key] != csrc[key]
        ],
        "binding_mismatches": [
            {
                "source_record_key": key,
                "accepted_episode_id": asrc[key]["episode_legacy_id"],
                "refactored_episode_id": csrc[key]["episode_legacy_id"],
            }
            for key in common_s
            if asrc[key]["episode_legacy_id"] != csrc[key]["episode_legacy_id"]
        ],
        "checkpoint_mismatches": (
            []
            if accepted["checkpoint_candidate"] == current["checkpoint_candidate"]
            else [{
                "accepted": accepted["checkpoint_candidate"],
                "refactored": current["checkpoint_candidate"],
            }]
        ),
    }


def boundary_snapshot(payload: dict) -> dict:
    def observation(row: dict) -> dict:
        copied = dict(row)
        interval = copied.pop("effective_interval")
        copied["effective_interval"] = {
            "start": interval.start.isoformat(),
            "end": interval.end.isoformat(),
        }
        return copied

    return {
        "episodes": sorted(
            [
                {
                    "legacy_episode_id": row["legacy_episode_id"],
                    "start": row["start"],
                    "end": row["end"],
                }
                for row in payload["episodes"]
            ],
            key=lambda x: x["legacy_episode_id"],
        ),
        "source_observations": sorted(
            [observation(row) for row in payload["source_observations"]],
            key=lambda x: (x["source_key"], x["source_record_key"]),
        ),
        "source_record_keys": payload["source_record_keys"],
        "checkpoint_candidate": payload.get("checkpoint_candidate"),
        "boundary_errors": payload["boundary_errors"],
        "canonicalization_version": payload["canonicalization_version"],
        "assembly_profile": payload["assembly_profile"],
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--accepted-worktree", type=Path, required=True)
    p.add_argument("--production-worktree", type=Path, required=True)
    p.add_argument("--current-worktree", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()

    accepted = run_json(
        CANONICAL_SNAPSHOT_CODE,
        str(args.accepted_worktree),
        cwd=args.accepted_worktree,
    )
    current = run_json(
        CANONICAL_SNAPSHOT_CODE,
        str(args.current_worktree),
        cwd=args.current_worktree,
    )
    diagnostics = compare_payloads(accepted, current)

    accepted_app = args.accepted_worktree / "kyiv-air-alerts-grafana"
    production_app = args.production_worktree / "kyiv-air-alerts-grafana"
    current_app = args.current_worktree / "kyiv-air-alerts-grafana"

    sys.path.insert(0, str(current_app / "scripts"))
    import db_phase1_lviv_canonical as canonical
    import db_phase1_lviv_proof as proof

    fixtures = current_app / "tests" / "fixtures" / "db_phase1"
    built = proof.build_lviv(fixtures)
    vad = [
        {k: v for k, v in row.items() if k != "episode_id"}
        for row in built["observations"]
        if row["source_key"] == "vadimkin_official_data_uk"
    ]
    ua = [
        {k: v for k, v in row.items() if k != "episode_id"}
        for row in built["observations"]
        if row["source_key"] == "ukrainealarm_region_history"
    ]
    checkpoint_state = built["checkpoint_state"]

    normal = canonical.canonicalize_lviv(vad, ua, checkpoint_state=checkpoint_state)
    reversed_input = canonical.canonicalize_lviv(
        list(reversed(vad)),
        list(reversed(ua)),
        checkpoint_state=checkpoint_state,
    )
    repeated = canonical.canonicalize_lviv(vad, ua, checkpoint_state=checkpoint_state)
    duplicated = canonical.canonicalize_lviv(
        vad + [dict(row) for row in vad],
        ua + [dict(row) for row in ua],
        checkpoint_state=checkpoint_state,
    )
    normal_snapshot = boundary_snapshot(normal)
    determinism_checks = {
        "normal_vs_reversed": normal_snapshot == boundary_snapshot(reversed_input),
        "repeated_invocation": normal_snapshot == boundary_snapshot(repeated),
        "duplicate_observation_idempotence": normal_snapshot == boundary_snapshot(duplicated),
    }

    raw_rows = current_app / "tests" / "fixtures" / "db_phase1" / "lviv" / "vadimkin_rows.json"
    product_baseline = run_json(
        PRODUCT_SNAPSHOT_CODE,
        str(args.production_worktree),
        str(raw_rows),
        cwd=args.production_worktree,
    )
    product_refactored = run_json(
        PRODUCT_SNAPSHOT_CODE,
        str(args.current_worktree),
        str(raw_rows),
        cwd=args.current_worktree,
    )
    baseline_hash = hashlib.sha256(canonical_json(product_baseline).encode()).hexdigest()
    refactored_hash = hashlib.sha256(canonical_json(product_refactored).encode()).hexdigest()
    product_parity = "PASS" if product_baseline == product_refactored else "FAIL"

    accepted_split = Counter(x["source_key"] for x in accepted["source_observations"])
    current_split = Counter(x["source_key"] for x in current["source_observations"])
    current_ids = {x["legacy_episode_id"] for x in current["episodes"]}

    persistence_before = git_blob_sha(accepted_app / "scripts" / "db_phase1_persistence.py")
    persistence_after = git_blob_sha(current_app / "scripts" / "db_phase1_persistence.py")
    ddl_before = git_blob_sha(accepted_app / "db" / "migrations" / "001_phase1_core.sql")
    ddl_after = git_blob_sha(current_app / "db" / "migrations" / "001_phase1_core.sql")

    explosion_guard = {}
    for name in ("app.js", "index.html"):
        source = (current_app / "pages-preview" / name).read_text(encoding="utf-8")
        explosion_guard[name] = {
            "explosion": source.lower().count("explosion"),
            "вибух": source.casefold().count("вибух"),
        }

    accepted_inputs = {
        "vadimkin_rows": sha256_file(accepted_app / "tests" / "fixtures" / "db_phase1" / "lviv" / "vadimkin_rows.json"),
        "ukrainealarm_bridge": sha256_file(accepted_app / "tests" / "fixtures" / "db_phase1" / "lviv" / "ukrainealarm_bridge.json"),
        "oracle": sha256_file(accepted_app / "tests" / "fixtures" / "db_phase1" / "lviv" / "oracle.json"),
    }
    product_inputs = {
        "vadimkin_rows": sha256_file(raw_rows),
        "ukrainealarm_bridge_store": sha256_file(production_app / "data" / "ukrainealarm_bridge.json"),
        "alerts_in_ua_bridge_primary": sha256_file(production_app / "data" / "alerts_in_ua_bridge_2026-09-07_16.csv.gz.b64"),
        "alerts_in_ua_bridge_additional": sha256_file(production_app / "data" / "alerts_in_ua_bridge_additional_2026-09-07_16.csv.gz.b64"),
    }

    mismatch_keys = (
        "missing_episode_ids",
        "unexpected_episode_ids",
        "episode_mismatches",
        "missing_source_record_keys",
        "unexpected_source_record_keys",
        "source_observation_mismatches",
        "binding_mismatches",
        "checkpoint_mismatches",
    )
    exact_parity = all(diagnostics[key] == [] for key in mismatch_keys)
    regression_checks = {
        "expected_present": EXPECTED_PRESENT in current_ids,
        "known_bad_absent": KNOWN_BAD_ABSENT not in current_ids,
    }
    blobs_ok = (
        persistence_before == EXPECTED_PERSISTENCE_BLOB
        and persistence_after == EXPECTED_PERSISTENCE_BLOB
        and ddl_before == EXPECTED_DDL_BLOB
        and ddl_after == EXPECTED_DDL_BLOB
    )
    explosion_ok = all(
        value == 0
        for counts in explosion_guard.values()
        for value in counts.values()
    )
    success = (
        exact_parity
        and len(accepted["episodes"]) == 126
        and len(current["episodes"]) == 126
        and len(accepted["source_observations"]) == 140
        and len(current["source_observations"]) == 140
        and accepted_split == current_split
        and accepted_split["vadimkin_official_data_uk"] == 120
        and accepted_split["ukrainealarm_region_history"] == 20
        and all(regression_checks.values())
        and all(determinism_checks.values())
        and product_parity == "PASS"
        and blobs_ok
        and explosion_ok
    )

    artifact = {
        "schema_version": "db-phase1-shared-canonical-payload-boundary-proof-v1",
        "production_base_sha": PRODUCTION_BASE_SHA,
        "accepted_phase1_reference_sha": ACCEPTED_PHASE1_REFERENCE_SHA,
        "shared_canonical_module": "scripts/db_phase1_lviv_canonical.py",
        "shared_canonical_entrypoint": "canonicalize_lviv",
        "accepted_input_hashes": accepted_inputs,
        "production_parity_input_hashes": product_inputs,
        "accepted_episode_count": len(accepted["episodes"]),
        "refactored_episode_count": len(current["episodes"]),
        "episode_identity_match": (
            not diagnostics["missing_episode_ids"]
            and not diagnostics["unexpected_episode_ids"]
            and not diagnostics["episode_mismatches"]
        ),
        "accepted_source_observation_count": len(accepted["source_observations"]),
        "refactored_source_observation_count": len(current["source_observations"]),
        "source_record_key_match": (
            not diagnostics["missing_source_record_keys"]
            and not diagnostics["unexpected_source_record_keys"]
            and not diagnostics["source_observation_mismatches"]
        ),
        "source_split": {
            "accepted": dict(sorted(accepted_split.items())),
            "refactored": dict(sorted(current_split.items())),
        },
        "binding_match": not diagnostics["binding_mismatches"],
        "checkpoint_candidate_match": not diagnostics["checkpoint_mismatches"],
        "regression_checks": regression_checks,
        "determinism_checks": determinism_checks,
        "product_baseline_hash": baseline_hash,
        "product_refactored_hash": refactored_hash,
        "product_output_parity": product_parity,
        "persistence_blob_before": persistence_before,
        "persistence_blob_after": persistence_after,
        "ddl_blob_before": ddl_before,
        "ddl_blob_after": ddl_after,
        "explosion_guard": explosion_guard,
        **diagnostics,
        "db_access_performed": False,
        "neon_branch_created": False,
        "production_files_published": False,
        "credentials_exposed": False,
        "verdict": (
            "PHASE-1 SHARED CANONICAL PAYLOAD BOUNDARY PROVEN"
            if success
            else "PHASE-1 SHARED CANONICAL PAYLOAD BOUNDARY BLOCKED"
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(artifact, ensure_ascii=False, sort_keys=True))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
