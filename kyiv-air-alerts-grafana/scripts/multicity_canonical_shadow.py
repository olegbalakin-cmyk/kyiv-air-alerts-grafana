#!/usr/bin/env python3
"""Fail-open scheduled production shadow for 23-city canonical AIR parents."""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from db_phase1_core import CANONICALIZATION_VERSION, canonical_json

FLAG_ENV = "MULTICITY_CANONICAL_DB_SHADOW"
DB_ENV = "MULTICITY_CANONICAL_DATABASE_URL"
BRANCH_ENV = "MULTICITY_CANONICAL_DB_BRANCH"
FAILURE_ENV = "MULTICITY_CANONICAL_DB_SHADOW_FAILURE_POLICY"
DIAGNOSTIC_ENV = "MULTICITY_CANONICAL_DB_SHADOW_DIAGNOSTIC"
PAYLOAD_ENV = "MULTICITY_CANONICAL_PAYLOAD_PATH"
INPUT_REPOSITORY_ENV = "MULTICITY_CANONICAL_INPUT_REPOSITORY"
INPUT_REF_ENV = "MULTICITY_CANONICAL_INPUT_REF"
INPUT_SHA_ENV = "MULTICITY_CANONICAL_INPUT_SHA"
DASHBOARD_ENV = "MULTICITY_CANONICAL_DASHBOARD_PATH"

_SECRET_RE = re.compile(
    r"(?i)(postgres(?:ql)?://[^\s]+|password\s*[=:]\s*[^\s,;]+|token\s*[=:]\s*[^\s,;]+)"
)


def _enabled() -> bool:
    return os.environ.get(FLAG_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def _diag_path() -> Path | None:
    raw = os.environ.get(DIAGNOSTIC_ENV, "").strip()
    return Path(raw) if raw else None


def _write_diag(obj: dict[str, Any]) -> None:
    path = _diag_path()
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sanitize(exc: BaseException) -> str:
    text = _SECRET_RE.sub("[REDACTED]", str(exc))
    return text[:500]


def _load_corpus() -> tuple[list[dict[str, Any]], list[str], str]:
    payload_raw = os.environ.get(PAYLOAD_ENV, "").strip()
    if not payload_raw:
        raise RuntimeError(f"{PAYLOAD_ENV} is required when shadow is enabled")
    dashboard_raw = os.environ.get(DASHBOARD_ENV, "").strip() or "data/dashboard_data.json"
    payload = json.loads(Path(payload_raw).read_text(encoding="utf-8"))
    dashboard = json.loads(Path(dashboard_raw).read_text(encoding="utf-8"))
    if payload.get("format") != "multicity-canonical-same-run-v1":
        raise RuntimeError("same-run canonical payload format mismatch")
    if payload.get("canonicalization_version") != CANONICALIZATION_VERSION:
        raise RuntimeError("same-run canonical payload canonicalization version mismatch")
    keys = list(dashboard.get("multicity_meta", {}).get("production_city_keys", []))
    if len(keys) != 23 or len(set(keys)) != 23:
        raise RuntimeError(f"production city boundary must be exactly 23 unique keys, got {len(keys)}")
    cities = payload.get("cities", {})
    if set(cities) != set(keys):
        missing = sorted(set(keys) - set(cities))
        extra = sorted(set(cities) - set(keys))
        raise RuntimeError(f"same-run canonical payload city mismatch: missing={missing}, extra={extra}")
    episodes: list[dict[str, Any]] = []
    for key in keys:
        block = cities[key]
        rows = list(block.get("episodes", []))
        if int(block.get("episode_count", -1)) != len(rows):
            raise RuntimeError(f"{key}: payload episode_count mismatch")
        episodes.extend(rows)
    serial = {
        "canonicalization_version": CANONICALIZATION_VERSION,
        "production_city_keys": keys,
        "episodes": episodes,
    }
    sha = hashlib.sha256(canonical_json(serial).encode("utf-8")).hexdigest()
    return episodes, keys, sha


def _provenance(*, city_count: int, episode_count: int, corpus_sha256: str) -> dict[str, Any]:
    run_id = os.environ.get("GITHUB_RUN_ID")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT")
    return {
        "run_kind": "multicity_canonical_shadow",
        "workflow_repository": os.environ.get("GITHUB_REPOSITORY"),
        "workflow_name": os.environ.get("GITHUB_WORKFLOW"),
        "workflow_ref": os.environ.get("GITHUB_REF"),
        "workflow_sha": os.environ.get("GITHUB_SHA"),
        "input_repository": os.environ.get(INPUT_REPOSITORY_ENV),
        "input_ref": os.environ.get(INPUT_REF_ENV),
        "input_sha": os.environ.get(INPUT_SHA_ENV),
        "github_run_id": int(run_id) if run_id else None,
        "github_run_attempt": int(attempt) if attempt else None,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "parameters": {
            "production_city_count": city_count,
            "canonical_episode_count": episode_count,
            "corpus_sha256": corpus_sha256,
            "source_provenance_coverage": "partial",
            "same_run_payload": True,
            "second_upstream_fetch": False,
        },
    }


def execute() -> dict[str, Any]:
    failure_policy = os.environ.get(FAILURE_ENV, "fail_open").strip() or "fail_open"
    base = {
        "db_branch": os.environ.get(BRANCH_ENV),
        "workflow_sha": os.environ.get("GITHUB_SHA"),
        "input_sha": os.environ.get(INPUT_SHA_ENV),
        "failure_policy": failure_policy,
        "production_output_mutation": False,
    }
    if not _enabled():
        diagnostic = {
            **base,
            "status": "disabled",
            "city_count": 0,
            "canonical_episode_count": 0,
            "corpus_sha256": None,
            "episodes_inserted": 0,
            "episodes_existing": 0,
            "episodes_updated": 0,
            "run_id": None,
            "writes": 0,
        }
        _write_diag(diagnostic)
        return diagnostic

    try:
        episodes, keys, corpus_sha = _load_corpus()
        db_url = os.environ.get(DB_ENV, "").strip()
        db_branch = os.environ.get(BRANCH_ENV, "").strip()
        if not db_url:
            raise RuntimeError(f"{DB_ENV} is required when shadow is enabled")
        if not db_branch:
            raise RuntimeError(f"{BRANCH_ENV} is required when shadow is enabled")

        # Imports stay inside the enabled path: flag OFF has no psycopg requirement.
        from multicity_canonical_postgres import persist_canonical_episodes

        try:
            import psycopg
            connection = psycopg.connect(db_url)
        except ImportError:
            import psycopg2
            connection = psycopg2.connect(db_url)

        try:
            result = persist_canonical_episodes(
                connection,
                episodes,
                provenance=_provenance(
                    city_count=len(keys),
                    episode_count=len(episodes),
                    corpus_sha256=corpus_sha,
                ),
                db_branch=db_branch,
            )
        finally:
            connection.close()

        diagnostic = {
            **base,
            "status": "succeeded",
            "persistence_status": result.get("status"),
            "city_count": len(keys),
            "canonical_episode_count": len(episodes),
            "corpus_sha256": corpus_sha,
            "episodes_inserted": result.get("episodes_inserted", 0),
            "episodes_existing": result.get("episodes_existing", 0),
            "episodes_updated": result.get("episodes_updated", 0),
            "run_id": result.get("run_id"),
            "writes": result.get("writes", 0),
        }
        _write_diag(diagnostic)
        return diagnostic
    except Exception as exc:
        diagnostic = {
            **base,
            "status": "failed",
            "city_count": 0,
            "canonical_episode_count": 0,
            "corpus_sha256": None,
            "episodes_inserted": 0,
            "episodes_existing": 0,
            "episodes_updated": 0,
            "run_id": None,
            "writes": 0,
            "error_type": type(exc).__name__,
            "sanitized_error_message": _sanitize(exc),
        }
        _write_diag(diagnostic)
        if failure_policy != "fail_open":
            raise
        return diagnostic


def main() -> int:
    result = execute()
    print(json.dumps({
        key: result.get(key)
        for key in (
            "status", "db_branch", "city_count", "canonical_episode_count",
            "corpus_sha256", "episodes_inserted", "episodes_existing",
            "episodes_updated", "writes", "run_id", "workflow_sha", "input_sha",
            "error_type",
        )
        if key in result
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
