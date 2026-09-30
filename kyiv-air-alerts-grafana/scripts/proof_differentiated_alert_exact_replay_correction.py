#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
CHECKOUT = ROOT.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import update_data
from differentiated_alert_shadow_runtime import run_shadow

RESULT = CHECKOUT / "research" / "differentiated_alert_exact_replay_correction_runtime.json"
FIX = ROOT / "tests" / "fixtures" / "differentiated_alert_shadow"
PARENT_CORPUS = ROOT / "data" / "alerts_combined.json"
FROZEN_NOW = datetime(2026, 9, 29, 9, 13, 47, tzinfo=timezone.utc)


def exact_replay_gate(
    result: Mapping[str, Any],
    before_counts: Mapping[str, int] | None,
) -> bool:
    counts = result.get("store_counts")
    return bool(
        result.get("attempted") is True
        and result.get("status") == "SUCCEEDED"
        and result.get("inserted_snapshots") == 0
        and result.get("inserted_observations") == 0
        and isinstance(counts, Mapping)
        and before_counts is not None
        and dict(counts) == dict(before_counts)
    )


def runtime_env(db_path: Path, diagnostic_path: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "DIFFERENTIATED_ALERT_SHADOW": "1",
            "DIFFERENTIATED_ALERT_SHADOW_DB": str(db_path),
            "DIFFERENTIATED_ALERT_SHADOW_KYIV_JSON": str(
                FIX / "kyiv_live_raw_2026-09-29_111347.json"
            ),
            "DIFFERENTIATED_ALERT_SHADOW_KYIV_INPUT_CLASS": "LIVE_RAW",
            "DIFFERENTIATED_ALERT_SHADOW_UKRAINEALARM_JSON": str(
                FIX / "ukrainealarm_overlap_stored_raw_2026-09-14.json"
            ),
            "DIFFERENTIATED_ALERT_SHADOW_ALERTS_IN_UA_JSON": str(
                FIX / "alerts_in_ua_stored_raw_2026-09-16.json"
            ),
            "DIFFERENTIATED_ALERT_SHADOW_DIAGNOSTIC": str(diagnostic_path),
        }
    )
    return env


def load_parent_alerts():
    payload = json.loads(PARENT_CORPUS.read_text(encoding="utf-8"))
    return update_data.parse_committed_alerts(payload)


def fresh_process_replay(db_path: Path, diagnostic_path: Path) -> dict[str, Any]:
    env = runtime_env(db_path, diagnostic_path)
    env["EXACT_REPLAY_CHILD"] = "1"
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--child", str(db_path), str(diagnostic_path)],
        cwd=str(ROOT),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"fresh-process replay failed rc={proc.returncode}: {proc.stdout[-4000:]}")
    return json.loads(proc.stdout.strip().splitlines()[-1])


def child_main(db_path: Path, diagnostic_path: Path) -> int:
    alerts = load_parent_alerts()
    result = run_shadow(
        alerts,
        env=runtime_env(db_path, diagnostic_path),
        now=FROZEN_NOW,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def main() -> int:
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        return child_main(Path(sys.argv[2]), Path(sys.argv[3]))

    work = Path(tempfile.mkdtemp(prefix="diff-exact-replay-correction-"))
    db_path = work / "child.sqlite"
    first_diag = work / "first.json"
    second_diag = work / "second.json"
    third_diag = work / "third.json"
    alerts = load_parent_alerts()

    first = run_shadow(
        alerts,
        env=runtime_env(db_path, first_diag),
        now=FROZEN_NOW,
    )
    before_counts = first.get("store_counts")
    first_ok = bool(
        first.get("attempted") is True
        and first.get("status") == "SUCCEEDED"
        and int(first.get("inserted_snapshots") or 0) > 0
        and int(first.get("inserted_observations") or 0) > 0
        and isinstance(before_counts, Mapping)
    )

    second = run_shadow(
        alerts,
        env=runtime_env(db_path, second_diag),
        now=FROZEN_NOW,
    )
    second_ok = exact_replay_gate(second, before_counts)

    third = fresh_process_replay(db_path, third_diag)
    third_ok = exact_replay_gate(third, before_counts)

    disabled_false_positive = {
        "attempted": False,
        "status": "DISABLED",
        "inserted_snapshots": 0,
        "inserted_observations": 0,
        "store_counts": None,
    }
    disabled_rejected = not exact_replay_gate(disabled_false_positive, before_counts)

    result = {
        "status": "PASS" if all([first_ok, second_ok, third_ok, disabled_rejected]) else "FAIL",
        "proof_scope": "focused_exact_replay_correction_only",
        "production_writes": 0,
        "external_network_required": False,
        "frozen_parent_corpus": str(PARENT_CORPUS.relative_to(ROOT)),
        "frozen_now": FROZEN_NOW.isoformat().replace("+00:00", "Z"),
        "first_run": first,
        "counts_before_exact_replay": before_counts,
        "second_run": second,
        "second_run_gate_pass": second_ok,
        "fresh_process_third_run": third,
        "fresh_process_gate_pass": third_ok,
        "final_store_counts_equal": (
            isinstance(second.get("store_counts"), Mapping)
            and isinstance(third.get("store_counts"), Mapping)
            and dict(second["store_counts"]) == dict(before_counts or {})
            and dict(third["store_counts"]) == dict(before_counts or {})
        ),
        "disabled_zero_zero_rejected": disabled_rejected,
    }
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": result["status"],
        "first_inserts": {
            "snapshots": first.get("inserted_snapshots"),
            "observations": first.get("inserted_observations"),
        },
        "second": {
            "attempted": second.get("attempted"),
            "status": second.get("status"),
            "inserted_snapshots": second.get("inserted_snapshots"),
            "inserted_observations": second.get("inserted_observations"),
            "store_counts": second.get("store_counts"),
        },
        "disabled_zero_zero_rejected": disabled_rejected,
    }, ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
