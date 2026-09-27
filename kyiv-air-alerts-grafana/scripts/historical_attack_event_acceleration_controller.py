#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

CAMPAIGN_ID = "historical-attack-events-v2-2026-09-27"
CAMPAIGN_BRANCH = "historical-attack-event-backfill-2026-09-27"
METHODOLOGY_VERSION = "historical-attack-event-air-defense-action-v2"
CHECKPOINT_SCHEMA = 2
FROZEN_TOTAL = 6863
BATCH_SIZE = 50
STATE_SCHEMA = 1
STAGE1_PROMOTION_RUNS = 8
SYSTEMIC_RETRY_MIN = 20
SYSTEMIC_RETRY_RATIO = 0.50

PHASE_CONTROL = "CONTROL"
PHASE_2X = "ACCELERATED_2X"
PHASE_4X = "ACCELERATED_4X"
PHASE_FALLBACK = "SAFETY_FALLBACK"
PHASE_COMPLETE = "COMPLETE"
PHASES = {PHASE_CONTROL, PHASE_2X, PHASE_4X, PHASE_FALLBACK, PHASE_COMPLETE}

STATE_REL = Path("research/historical_attack_event_backfill_acceleration_state.json")
STATUS_REL = Path("research/historical_attack_event_backfill_status.json")
LAUNCH_REL = Path("research/historical_attack_event_backfill_campaign_launch_2026-09-27.json")
BATCH_ROOT_REL = Path("research/historical_attack_event_backfill") / CAMPAIGN_ID
WORKER_REL = Path("kyiv-air-alerts-grafana/scripts/run_historical_attack_event_backfill_batch.py")

VERSION_FILES = {
    "classifier_sha": Path("kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py"),
    "source_adapter_sha": Path("kyiv-air-alerts-grafana/scripts/historical_attack_event_sources.py"),
    "orchestrator_sha": WORKER_REL,
    "discovery_sha": Path("kyiv-air-alerts-grafana/scripts/discover_historical_attack_events.py"),
    "sevastopol_pilot_sha": Path("kyiv-air-alerts-grafana/scripts/run_historical_attack_event_source_adapter_pilot.py"),
    "source_registry_sha": Path("research/historical_attack_event_source_registry.json"),
}

TERMINAL_STATES = {
    "STRICT_EVENT_POSITIVE",
    "SENSITIVITY_EVENT_POSITIVE",
    "NO_CONFIRMED_EVENT",
    "NEEDS_REVIEW",
    "SOURCE_ADAPTER_REQUIRED",
}


class GuardFailure(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def run_cmd(args: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if check and proc.returncode:
        raise GuardFailure(f"COMMAND_FAILED:{' '.join(args)}:{proc.stderr.strip() or proc.stdout.strip()}")
    return proc


def git(root: Path, *args: str, check: bool = True) -> str:
    return run_cmd(["git", *args], root, check=check).stdout.strip()


def blob(root: Path, rel: Path) -> str:
    path = root / rel
    if not path.exists():
        raise GuardFailure(f"REQUIRED_FILE_MISSING:{rel.as_posix()}")
    return git(root, "hash-object", rel.as_posix())


def current_head(root: Path) -> str:
    return git(root, "rev-parse", "HEAD")


def remote_head(root: Path) -> str:
    git(root, "fetch", "origin", CAMPAIGN_BRANCH)
    return git(root, "rev-parse", f"origin/{CAMPAIGN_BRANCH}")


def phase_batch_limit(phase: str) -> int:
    return {
        PHASE_CONTROL: 1,
        PHASE_2X: 2,
        PHASE_4X: 4,
        PHASE_FALLBACK: 1,
        PHASE_COMPLETE: 0,
    }[phase]


def campaign_progress(status: dict) -> tuple[int, int, int]:
    p = status.get("progress") or {}
    return int(p.get("processed") or 0), int(p.get("total") or 0), int(p.get("terminal") or 0)


def new_state(status: dict, timestamp: str) -> dict:
    processed, total, _ = campaign_progress(status)
    return {
        "schema_version": STATE_SCHEMA,
        "campaign_id": CAMPAIGN_ID,
        "campaign_version": copy.deepcopy(status.get("campaign_version") or {}),
        "frozen_total_episodes": total,
        "phase": PHASE_CONTROL,
        "clean_scheduled_runs": 0,
        "failed_or_guarded_runs": 0,
        "last_scheduler_run_id": None,
        "last_progress_before": processed,
        "last_progress_after": processed,
        "last_success_at": None,
        "stage1_started_at": None,
        "stage2_started_at": None,
        "fallback_reason": None,
        "updated_at": timestamp,
    }


def validate_status_contract(root: Path, status: dict, launch: dict) -> None:
    if int(status.get("schema_version") or 0) != CHECKPOINT_SCHEMA:
        raise GuardFailure("CHECKPOINT_SCHEMA_MISMATCH")
    if status.get("campaign_id") != CAMPAIGN_ID:
        raise GuardFailure("CAMPAIGN_ID_MISMATCH")
    versions = status.get("campaign_version") or {}
    if versions.get("methodology_version") != METHODOLOGY_VERSION:
        raise GuardFailure("METHODOLOGY_VERSION_MISMATCH")
    processed, total, terminal = campaign_progress(status)
    if total != FROZEN_TOTAL or int(status.get("frozen_total_episodes") or 0) != FROZEN_TOTAL:
        raise GuardFailure("FROZEN_TOTAL_MISMATCH")
    if not (0 <= terminal <= processed <= total):
        raise GuardFailure("CHECKPOINT_PROGRESS_INVALID")
    for key, rel in VERSION_FILES.items():
        expected = versions.get(key)
        if not expected or blob(root, rel) != expected:
            raise GuardFailure(f"CAMPAIGN_VERSION_FILE_MISMATCH:{key}")
    if versions.get("normalization_version") != "historical-attack-event-observation-v2":
        raise GuardFailure("NORMALIZATION_VERSION_MISMATCH")
    frozen_cities = list(status.get("frozen_cities") or [])
    launch_universe = launch.get("frozen_city_universe") or {}
    if set(frozen_cities) != set(launch_universe):
        raise GuardFailure("FROZEN_CITY_UNIVERSE_DRIFT")
    counted = 0
    for city in frozen_cities:
        row = (status.get("cities") or {}).get(city) or {}
        launch_row = launch_universe.get(city) or {}
        ids = list(row.get("frozen_episode_ids") or [])
        source_blobs = list(row.get("frozen_episode_source_blobs") or [])
        if ids != list(launch_row.get("ordered_episode_ids") or []):
            raise GuardFailure(f"FROZEN_EPISODE_IDS_DRIFT:{city}")
        if source_blobs != list(launch_row.get("source_blobs") or []):
            raise GuardFailure(f"FROZEN_SOURCE_BLOBS_DRIFT:{city}")
        if int(row.get("frozen_episode_count") or 0) != int(launch_row.get("total_episodes") or 0):
            raise GuardFailure(f"FROZEN_EPISODE_COUNT_DRIFT:{city}")
        if len(ids) != len(set(ids)):
            raise GuardFailure(f"FROZEN_EPISODE_DUPLICATE_IDS:{city}")
        counted += len(ids)
    if counted != FROZEN_TOTAL:
        raise GuardFailure("FROZEN_UNIVERSE_TOTAL_DRIFT")


def validate_state_contract(state: dict, status: dict) -> None:
    if int(state.get("schema_version") or 0) != STATE_SCHEMA:
        raise GuardFailure("ACCELERATION_STATE_SCHEMA_MISMATCH")
    if state.get("campaign_id") != CAMPAIGN_ID:
        raise GuardFailure("ACCELERATION_STATE_CAMPAIGN_MISMATCH")
    if state.get("phase") not in PHASES:
        raise GuardFailure("ACCELERATION_STATE_PHASE_INVALID")
    if int(state.get("frozen_total_episodes") or 0) != FROZEN_TOTAL:
        raise GuardFailure("ACCELERATION_STATE_UNIVERSE_MISMATCH")
    if (state.get("campaign_version") or {}) != (status.get("campaign_version") or {}):
        raise GuardFailure("ACCELERATION_STATE_VERSION_MISMATCH")

