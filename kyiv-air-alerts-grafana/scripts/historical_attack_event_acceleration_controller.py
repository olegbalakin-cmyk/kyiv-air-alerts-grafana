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



def verify_protected(root: Path, launch: dict) -> dict[str, str]:
    expected = launch.get("protected_file_hashes") or {}
    if not expected:
        raise GuardFailure("PROTECTED_HASH_BASELINE_MISSING")
    current: dict[str, str] = {}
    for path, expected_sha in expected.items():
        rel = Path(path)
        actual = blob(root, rel)
        current[path] = actual
        if actual != expected_sha:
            raise GuardFailure(f"PROTECTED_FILE_MUTATION:{path}")
    return current


def launch_blob(root: Path) -> str:
    return blob(root, LAUNCH_REL)


def episode_snapshot(status: dict) -> dict[str, tuple[str, str]]:
    version = json.dumps(status.get("campaign_version") or {}, sort_keys=True, separators=(",", ":"))
    out: dict[str, tuple[str, str]] = {}
    for city, city_state in (status.get("cities") or {}).items():
        for episode_id, row in (city_state.get("episode_states") or {}).items():
            out[f"{city}:{episode_id}"] = (str((row or {}).get("state") or ""), version)
    return out


def validate_episode_progress(before: dict[str, tuple[str, str]], after: dict[str, tuple[str, str]]) -> None:
    for key, (old_state, old_version) in before.items():
        if old_state in TERMINAL_STATES:
            current = after.get(key)
            if current is None:
                raise GuardFailure(f"TERMINAL_EPISODE_STATE_LOST:{key}")
            if current[1] == old_version and current[0] != old_state:
                raise GuardFailure(f"TERMINAL_EPISODE_RERUN_OR_REGRESSION:{key}:{old_state}->{current[0]}")


def collect_observation_ids(root: Path) -> set[str]:
    seen: set[str] = set()
    batch_root = root / BATCH_ROOT_REL
    if not batch_root.exists():
        return seen
    for path in sorted(batch_root.glob("*/batch_*.json")):
        doc = load_json(path)
        local: set[str] = set()
        for row in doc.get("observations") or []:
            oid = str((row or {}).get("observation_id") or "")
            if not oid:
                continue
            if oid in local or oid in seen:
                raise GuardFailure(f"DUPLICATE_OBSERVATION_ID:{oid}:{path.relative_to(root).as_posix()}")
            local.add(oid)
        seen.update(local)
    return seen


def validate_new_batch_observations(batch_path: Path, seen: set[str]) -> set[str]:
    doc = load_json(batch_path)
    local: set[str] = set()
    for row in doc.get("observations") or []:
        oid = str((row or {}).get("observation_id") or "")
        if not oid:
            continue
        if oid in local or oid in seen:
            raise GuardFailure(f"DUPLICATE_OBSERVATION_ID:{oid}:{batch_path.name}")
        local.add(oid)
    return local


def run_worker(root: Path) -> dict:
    proc = run_cmd([
        sys.executable,
        str(root / WORKER_REL),
        "--campaign-id", CAMPAIGN_ID,
        "--city-key", "auto",
        "--batch-size", str(BATCH_SIZE),
        "--output-dir", str(root / "research/historical_attack_event_backfill"),
        "--resume",
    ], root / "kyiv-air-alerts-grafana", check=False)
    text = proc.stdout.strip()
    if proc.returncode:
        raise GuardFailure(f"WORKER_FAILED:{proc.returncode}:{proc.stderr.strip() or text}")
    start = text.find("{")
    if start < 0:
        raise GuardFailure("WORKER_OUTPUT_NOT_JSON")
    try:
        payload = json.loads(text[start:])
    except json.JSONDecodeError as exc:
        raise GuardFailure(f"WORKER_OUTPUT_NOT_JSON:{exc}") from exc
    if payload.get("ok") is not True:
        raise GuardFailure(f"WORKER_NOT_OK:{payload.get('reason')}")
    return payload


def changed_paths(root: Path) -> set[str]:
    rows = [x for x in git(root, "status", "--porcelain", "--untracked-files=all").splitlines() if x.strip()]
    out: set[str] = set()
    for row in rows:
        path = row[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        out.add(path)
    return out


def ensure_expected_dirty_paths(root: Path, batch_rel: Path | None, *, metadata_only: bool = False) -> None:
    changed = changed_paths(root)
    allowed = {STATUS_REL.as_posix()}
    if batch_rel is not None:
        allowed.add(batch_rel.as_posix())
    if metadata_only:
        allowed = {STATUS_REL.as_posix()}
    unexpected = sorted(changed - allowed)
    if unexpected:
        raise GuardFailure("UNEXPECTED_WORKTREE_MUTATION:" + ",".join(unexpected))


def rollback_worker(root: Path) -> None:
    git(root, "reset", "--hard", "HEAD", check=False)
    git(root, "clean", "-fd", "research/historical_attack_event_backfill", check=False)


def remote_head(root: Path) -> str:
    git(root, "fetch", "origin", CAMPAIGN_BRANCH)
    return git(root, "rev-parse", f"origin/{CAMPAIGN_BRANCH}")


def assert_remote_unchanged(root: Path, expected_head: str) -> None:
    actual = remote_head(root)
    if actual != expected_head:
        raise GuardFailure(f"STALE_WRITER_CONFLICT:{expected_head}!={actual}")


def commit_and_push(root: Path, paths: list[Path], message: str, expected_head: str) -> str:
    assert_remote_unchanged(root, expected_head)
    git(root, "config", "user.name", "github-actions[bot]")
    git(root, "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    git(root, "add", "--", *[p.as_posix() for p in paths])
    if not git(root, "diff", "--cached", "--name-only"):
        return expected_head
    git(root, "commit", "-m", message)
    new_head = git(root, "rev-parse", "HEAD")
    git(root, "push", "origin", f"HEAD:{CAMPAIGN_BRANCH}")
    visible = remote_head(root)
    if visible != new_head:
        raise GuardFailure(f"PUSHED_CHECKPOINT_NOT_VISIBLE:{new_head}!={visible}")
    return new_head


def systemic_source_failure(payload: dict) -> bool:
    new_work = int(payload.get("new_work") or 0)
    retryable = int(payload.get("retryable") or 0)
    return (
        new_work > 0
        and retryable >= SYSTEMIC_RETRY_MIN
        and retryable / new_work >= SYSTEMIC_RETRY_RATIO
    )


def transition_state(
    state: dict,
    *,
    scheduled: bool,
    clean: bool,
    did_work: bool,
    complete: bool,
    run_id: str | None,
    progress_before: int,
    progress_after: int,
    timestamp: str,
    reason: str | None = None,
) -> dict:
    out = copy.deepcopy(state)
    phase = out["phase"]
    if complete:
        out["phase"] = PHASE_COMPLETE
        out["clean_scheduled_runs"] = 0
        out["fallback_reason"] = None
        out["last_progress_before"] = progress_before
        out["last_progress_after"] = progress_after
        out["last_success_at"] = timestamp
        out["updated_at"] = timestamp
        if scheduled:
            out["last_scheduler_run_id"] = run_id
        return out
    if not clean:
        out["clean_scheduled_runs"] = 0
        out["failed_or_guarded_runs"] = int(out.get("failed_or_guarded_runs") or 0) + 1
        out["fallback_reason"] = reason or "UNSPECIFIED_GUARD_FAILURE"
        if phase in {PHASE_2X, PHASE_4X}:
            out["phase"] = PHASE_FALLBACK
        out["last_progress_before"] = progress_before
        out["last_progress_after"] = progress_after
        out["updated_at"] = timestamp
        if scheduled:
            out["last_scheduler_run_id"] = run_id
        return out
    if not scheduled or not did_work:
        return out
    if phase == PHASE_CONTROL:
        out["phase"] = PHASE_2X
        out["clean_scheduled_runs"] = 0
        out["stage1_started_at"] = out.get("stage1_started_at") or timestamp
        out["fallback_reason"] = None
    elif phase == PHASE_2X:
        streak = int(out.get("clean_scheduled_runs") or 0) + 1
        if streak >= STAGE1_PROMOTION_RUNS:
            out["phase"] = PHASE_4X
            out["clean_scheduled_runs"] = 0
            out["stage2_started_at"] = out.get("stage2_started_at") or timestamp
        else:
            out["clean_scheduled_runs"] = streak
        out["fallback_reason"] = None
    elif phase == PHASE_FALLBACK:
        out["phase"] = PHASE_2X
        out["clean_scheduled_runs"] = 0
        out["stage1_started_at"] = timestamp
        out["fallback_reason"] = None
    elif phase == PHASE_4X:
        out["clean_scheduled_runs"] = int(out.get("clean_scheduled_runs") or 0) + 1
        out["fallback_reason"] = None
    out["last_scheduler_run_id"] = run_id
    out["last_progress_before"] = progress_before
    out["last_progress_after"] = progress_after
    out["last_success_at"] = timestamp
    out["updated_at"] = timestamp
    return out


def persist_state(root: Path, old_state: dict, new_state_doc: dict, expected_head: str, message: str) -> str:
    if old_state == new_state_doc:
        return expected_head
    dump_json(root / STATE_REL, new_state_doc)
    return commit_and_push(root, [STATE_REL], message, expected_head)


def persist_guard_after_refresh(
    root: Path,
    event_name: str,
    run_id: str | None,
    reason: str,
) -> tuple[dict, str]:
    git(root, "fetch", "origin", CAMPAIGN_BRANCH)
    git(root, "reset", "--hard", f"origin/{CAMPAIGN_BRANCH}")
    head = git(root, "rev-parse", "HEAD")
    status = load_json(root / STATUS_REL)
    launch = load_json(root / LAUNCH_REL)
    validate_status_contract(root, status, launch)
    state = load_json(root / STATE_REL)
    validate_state_contract(state, status)
    before, _, _ = campaign_progress(status)
    updated = transition_state(
        state,
        scheduled=event_name == "schedule",
        clean=False,
        did_work=False,
        complete=False,
        run_id=run_id,
        progress_before=before,
        progress_after=before,
        timestamp=now_iso(),
        reason=reason,
    )
    head = persist_state(
        root,
        state,
        updated,
        head,
        "Record historical backfill acceleration safety fallback",
    )
    return updated, head


def summary(
    before: dict,
    after: dict,
    processed_before: int,
    processed_after: int,
    batches_attempted: int,
    batches_committed: int,
    new_episodes: int,
    clean: bool,
    fallback_reason: str | None,
    complete: bool,
    *,
    head: str | None = None,
) -> dict:
    return {
        "campaign_id": CAMPAIGN_ID,
        "phase_before": before.get("phase"),
        "phase_after": after.get("phase"),
        "processed_before": processed_before,
        "processed_after": processed_after,
        "batches_attempted": batches_attempted,
        "batches_committed": batches_committed,
        "new_episodes_processed": new_episodes,
        "clean_run": "YES" if clean else "NO",
        "clean_run_streak": int(after.get("clean_scheduled_runs") or 0),
        "fallback_reason": fallback_reason,
        "campaign_complete": "YES" if complete else "NO",
        "campaign_head": head,
    }


def run_controller(root: Path, event_name: str, run_id: str | None) -> dict:
    root = root.resolve()
    status = load_json(root / STATUS_REL)
    launch = load_json(root / LAUNCH_REL)
    validate_status_contract(root, status, launch)
    verify_protected(root, launch)
    initial_launch_blob = launch_blob(root)
    state = load_json(root / STATE_REL) if (root / STATE_REL).exists() else new_state(status, now_iso())
    validate_state_contract(state, status)
    phase_before = state["phase"]
    processed_before, total, terminal_before = campaign_progress(status)
    if state["phase"] == PHASE_COMPLETE:
        if processed_before != total or terminal_before != total:
            raise GuardFailure("COMPLETE_STATE_WITH_INCOMPLETE_CAMPAIGN")
        return summary(
            state, state, processed_before, processed_before,
            0, 0, 0, True, None, True, head=git(root, "rev-parse", "HEAD")
        )
    if processed_before == total and terminal_before == total:
        updated = transition_state(
            state, scheduled=event_name == "schedule", clean=True, did_work=False, complete=True,
            run_id=run_id, progress_before=processed_before, progress_after=processed_before,
            timestamp=now_iso(),
        )
        head = persist_state(
            root, state, updated, git(root, "rev-parse", "HEAD"),
            "Mark historical backfill acceleration complete"
        )
        return summary(
            state, updated, processed_before, processed_before,
            0, 0, 0, True, None, True, head=head
        )

    seen_observations = collect_observation_ids(root)
    max_batches = phase_batch_limit(phase_before)
    batches_attempted = 0
    batches_committed = 0
    new_episodes = 0
    metadata_transitions = 0
    expected_head = git(root, "rev-parse", "HEAD")
    guard_reason: str | None = None

    try:
        while batches_committed < max_batches:
            status_before_doc = load_json(root / STATUS_REL)
            launch_before_doc = load_json(root / LAUNCH_REL)
            validate_status_contract(root, status_before_doc, launch_before_doc)
            verify_protected(root, launch_before_doc)
            if launch_blob(root) != initial_launch_blob:
                raise GuardFailure("LAUNCH_ARTIFACT_MUTATED")
            episode_before = episode_snapshot(status_before_doc)
            progress0, _, _ = campaign_progress(status_before_doc)
            batches_attempted += 1
            payload = run_worker(root)

            status_after_doc = load_json(root / STATUS_REL)
            launch_after_doc = load_json(root / LAUNCH_REL)
            validate_status_contract(root, status_after_doc, launch_after_doc)
            verify_protected(root, launch_after_doc)
            if launch_blob(root) != initial_launch_blob:
                raise GuardFailure("LAUNCH_ARTIFACT_MUTATED")
            episode_after = episode_snapshot(status_after_doc)
            validate_episode_progress(episode_before, episode_after)
            progress1, _, _ = campaign_progress(status_after_doc)
            if progress1 < progress0:
                raise GuardFailure(f"CHECKPOINT_PROGRESS_REGRESSION:{progress0}->{progress1}")

            new_work = int(payload.get("new_work") or 0)
            if new_work == 0:
                dirty_status = git(root, "status", "--porcelain", "--", STATUS_REL.as_posix())
                if dirty_status:
                    ensure_expected_dirty_paths(root, None, metadata_only=True)
                    expected_head = commit_and_push(
                        root, [STATUS_REL],
                        "Advance historical attack-event campaign state",
                        expected_head,
                    )
                    metadata_transitions += 1
                    if metadata_transitions > 8:
                        raise GuardFailure("EXCESSIVE_METADATA_ONLY_TRANSITIONS")
                    continue
                break

            batch_path_str = str(payload.get("batch_path") or "")
            if not batch_path_str:
                raise GuardFailure("WORKER_BATCH_PATH_MISSING")
            batch_rel = Path(batch_path_str)
            if batch_rel.is_absolute():
                try:
                    batch_rel = batch_rel.relative_to(root)
                except ValueError as exc:
                    raise GuardFailure("WORKER_BATCH_PATH_OUTSIDE_CHECKOUT") from exc
            batch_path = root / batch_rel
            if not batch_path.exists():
                raise GuardFailure("WORKER_BATCH_FILE_MISSING")
            ensure_expected_dirty_paths(root, batch_rel)
            new_ids = validate_new_batch_observations(batch_path, seen_observations)
            source_guard = systemic_source_failure(payload)
            expected_head = commit_and_push(
                root, [STATUS_REL, batch_rel],
                "Checkpoint historical attack-event backfill",
                expected_head,
            )
            seen_observations.update(new_ids)
            batches_committed += 1
            new_episodes += max(0, progress1 - progress0)
            if source_guard:
                guard_reason = (
                    f"SYSTEMIC_SOURCE_FAILURE:retryable={int(payload.get('retryable') or 0)}/"
                    f"new_work={new_work}"
                )
                break
    except GuardFailure as exc:
        guard_reason = str(exc)
        rollback_worker(root)

    status_final = load_json(root / STATUS_REL)
    processed_after, total_after, terminal_after = campaign_progress(status_final)
    complete = processed_after == total_after and terminal_after == total_after
    scheduled = event_name == "schedule"
    did_work = batches_committed > 0
    clean = guard_reason is None and did_work
    if not did_work and not complete and guard_reason is None:
        guard_reason = "NO_ELIGIBLE_WORK_BEFORE_COMPLETION"
        clean = False

    if guard_reason and "STALE_WRITER_CONFLICT" in guard_reason:
        updated, expected_head = persist_guard_after_refresh(root, event_name, run_id, guard_reason)
        status_final = load_json(root / STATUS_REL)
        processed_after, total_after, terminal_after = campaign_progress(status_final)
        complete = processed_after == total_after and terminal_after == total_after
    else:
        refreshed_state = load_json(root / STATE_REL)
        validate_state_contract(refreshed_state, status_final)
        updated = transition_state(
            refreshed_state,
            scheduled=scheduled,
            clean=clean,
            did_work=did_work,
            complete=complete,
            run_id=run_id,
            progress_before=processed_before,
            progress_after=processed_after,
            timestamp=now_iso(),
            reason=guard_reason,
        )
        expected_head = persist_state(
            root, refreshed_state, updated, expected_head,
            "Update historical backfill acceleration state"
        )

    launch_final = load_json(root / LAUNCH_REL)
    validate_status_contract(root, status_final, launch_final)
    verify_protected(root, launch_final)
    if launch_blob(root) != initial_launch_blob:
        raise GuardFailure("LAUNCH_ARTIFACT_MUTATED_AFTER_RUN")
    result = summary(
        state, updated, processed_before, processed_after,
        batches_attempted, batches_committed, new_episodes,
        guard_reason is None, guard_reason, complete, head=expected_head
    )
    if guard_reason:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        raise GuardFailure(guard_reason)
    return result


def inspect_current(root: Path) -> dict:
    root = root.resolve()
    status = load_json(root / STATUS_REL)
    launch = load_json(root / LAUNCH_REL)
    state = load_json(root / STATE_REL)
    validate_status_contract(root, status, launch)
    validate_state_contract(state, status)
    protected = verify_protected(root, launch)
    collect_observation_ids(root)
    processed, total, terminal = campaign_progress(status)
    return {
        "ok": True,
        "campaign_id": CAMPAIGN_ID,
        "phase": state["phase"],
        "max_batches_per_run": phase_batch_limit(state["phase"]),
        "batch_size": BATCH_SIZE,
        "processed": processed,
        "terminal": terminal,
        "total": total,
        "protected_file_count": len(protected),
        "frozen_universe_unchanged": True,
    }


def self_test() -> dict:
    timestamp = "2026-09-27T00:00:00Z"
    status = {
        "campaign_version": {"methodology_version": METHODOLOGY_VERSION},
        "progress": {"processed": 50, "total": FROZEN_TOTAL, "terminal": 50},
    }
    base = new_state(status, timestamp)
    assert phase_batch_limit(PHASE_CONTROL) == 1
    assert phase_batch_limit(PHASE_2X) == 2
    assert phase_batch_limit(PHASE_4X) == 4
    assert phase_batch_limit(PHASE_FALLBACK) == 1

    manual = transition_state(
        base, scheduled=False, clean=True, did_work=True, complete=False, run_id="m",
        progress_before=50, progress_after=100, timestamp=timestamp,
    )
    assert manual == base

    stage1 = transition_state(
        base, scheduled=True, clean=True, did_work=True, complete=False, run_id="1",
        progress_before=50, progress_after=100, timestamp=timestamp,
    )
    assert stage1["phase"] == PHASE_2X and stage1["clean_scheduled_runs"] == 0

    cur = stage1
    for i in range(7):
        cur = transition_state(
            cur, scheduled=True, clean=True, did_work=True, complete=False, run_id=str(i + 2),
            progress_before=100 + i, progress_after=101 + i, timestamp=timestamp,
        )
        assert cur["phase"] == PHASE_2X
        assert cur["clean_scheduled_runs"] == i + 1
    cur = transition_state(
        cur, scheduled=True, clean=True, did_work=True, complete=False, run_id="9",
        progress_before=107, progress_after=108, timestamp=timestamp,
    )
    assert cur["phase"] == PHASE_4X and cur["clean_scheduled_runs"] == 0

    stage1_failure = transition_state(
        stage1, scheduled=True, clean=False, did_work=True, complete=False, run_id="f1",
        progress_before=100, progress_after=150, timestamp=timestamp, reason="SYNTHETIC_GUARD",
    )
    assert stage1_failure["phase"] == PHASE_FALLBACK
    assert stage1_failure["clean_scheduled_runs"] == 0

    stage2_failure = transition_state(
        cur, scheduled=True, clean=False, did_work=True, complete=False, run_id="f2",
        progress_before=108, progress_after=158, timestamp=timestamp, reason="SYNTHETIC_GUARD",
    )
    assert stage2_failure["phase"] == PHASE_FALLBACK

    recovered = transition_state(
        stage1_failure, scheduled=True, clean=True, did_work=True, complete=False, run_id="r1",
        progress_before=150, progress_after=200, timestamp=timestamp,
    )
    assert recovered["phase"] == PHASE_2X
    assert recovered["clean_scheduled_runs"] == 0

    idle = transition_state(
        recovered, scheduled=True, clean=True, did_work=False, complete=False, run_id="idle",
        progress_before=200, progress_after=200, timestamp=timestamp,
    )
    assert idle == recovered

    complete = transition_state(
        recovered, scheduled=True, clean=True, did_work=True, complete=True, run_id="done",
        progress_before=6813, progress_after=6863, timestamp=timestamp,
    )
    assert complete["phase"] == PHASE_COMPLETE
    complete_idle = transition_state(
        complete, scheduled=True, clean=True, did_work=False, complete=True, run_id="done2",
        progress_before=6863, progress_after=6863, timestamp=timestamp,
    )
    assert complete_idle["phase"] == PHASE_COMPLETE

    assert systemic_source_failure({"new_work": 50, "retryable": 25})
    assert not systemic_source_failure({"new_work": 50, "retryable": 5})

    return {
        "ok": True,
        "batch_size": BATCH_SIZE,
        "phase_batch_limits": {
            PHASE_CONTROL: 1,
            PHASE_2X: 2,
            PHASE_4X: 4,
            PHASE_FALLBACK: 1,
        },
        "control_resume_gate": "PASS",
        "manual_does_not_promote": "PASS",
        "stage1_eight_run_promotion": "PASS",
        "stage1_failure_fallback": "PASS",
        "stage2_failure_fallback": "PASS",
        "fallback_recovery_to_stage1_only": "PASS",
        "idempotence_no_work": "PASS",
        "completion_idempotence": "PASS",
        "synthetic_guard_injection": "PASS",
        "systemic_source_failure_guard": "PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("self-test")
    inspect_p = sub.add_parser("inspect")
    inspect_p.add_argument("--checkout-root", type=Path, required=True)
    run_p = sub.add_parser("run")
    run_p.add_argument("--checkout-root", type=Path, required=True)
    run_p.add_argument("--event-name", required=True)
    run_p.add_argument("--run-id")
    args = parser.parse_args()
    try:
        if args.command == "self-test":
            print(json.dumps(self_test(), ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        if args.command == "inspect":
            print(json.dumps(inspect_current(args.checkout_root), ensure_ascii=False, sort_keys=True))
            return 0
        result = run_controller(args.checkout_root, args.event_name, args.run_id)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except GuardFailure as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
