#!/usr/bin/env python3
"""Opt-in, fail-open differentiated-alert child-only sidecar for production updater integration."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

import proof_differentiated_alert_shadow_ingestion as shadow
import differentiated_alert_postgres as postgres

FEATURE_FLAG = "DIFFERENTIATED_ALERT_SHADOW"
DB_ENV = "DIFFERENTIATED_ALERT_SHADOW_DB"
BACKEND_ENV = "DIFFERENTIATED_ALERT_SHADOW_BACKEND"
DATABASE_URL_ENV = "DIFFERENTIATED_ALERT_SHADOW_DATABASE_URL"
DIAGNOSTIC_ENV = "DIFFERENTIATED_ALERT_SHADOW_DIAGNOSTIC"
KYIV_INPUT_ENV = "DIFFERENTIATED_ALERT_SHADOW_KYIV_JSON"
KYIV_INPUT_CLASS_ENV = "DIFFERENTIATED_ALERT_SHADOW_KYIV_INPUT_CLASS"
UA_INPUT_ENV = "DIFFERENTIATED_ALERT_SHADOW_UKRAINEALARM_JSON"
AIU_INPUT_ENV = "DIFFERENTIATED_ALERT_SHADOW_ALERTS_IN_UA_JSON"
INPUT_MODE_ENV = "DIFFERENTIATED_ALERT_SHADOW_INPUT_MODE"
STORED_ONLY_MODE = "stored_only"
KYIV_URL = "https://kyiv.digital/open-api/air-alert/state"
TRUE_VALUES = {"1", "true", "yes", "on"}


def enabled(env: Mapping[str, str] | None = None) -> bool:
    env = os.environ if env is None else env
    return str(env.get(FEATURE_FLAG, "")).strip().lower() in TRUE_VALUES


def _utc_iso(now: datetime | None = None) -> str:
    value = now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_file(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _episode_id(start: str, end: str) -> str:
    return "kyiv-air:" + hashlib.sha256(f"kyiv\0AIR\0{start}\0{end}".encode()).hexdigest()


def parent_episodes_from_updater(alerts: list[Any] | None) -> list[dict[str, Any]]:
    episodes: list[dict[str, Any]] = []
    for alert in alerts or []:
        start = alert.start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        end = alert.end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        episodes.append(
            {
                "episode_id": _episode_id(start, end),
                "city_key": "kyiv",
                "alert_type": "AIR",
                "start_at": start,
                "end_at": end,
            }
        )
    return episodes


def _safe_error(exc: BaseException) -> dict[str, str]:
    return {"error_type": type(exc).__name__, "error": str(exc)[:500]}


def _write_diagnostic(path: str | None, result: dict[str, Any]) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _source_result(input_class: str) -> dict[str, Any]:
    return {
        "input_class": input_class,
        "status": "NOT_ATTEMPTED",
        "inserted_snapshots": 0,
        "inserted_observations": 0,
        "binding": {"BOUND": 0, "AMBIGUOUS": 0, "UNBOUND": 0},
    }


class PostgresShadowStore:
    """Minimal child-only store wrapper around the accepted PostgreSQL adapter."""

    def __init__(self, database_url: str):
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("psycopg is required for differentiated postgres shadow backend") from exc
        self.connection = psycopg.connect(database_url)

    def persist(self, record: dict[str, Any]) -> dict[str, int]:
        stats = postgres.persist_record(self.connection, record)
        return {
            "inserted_snapshots": stats["inserted_snapshots"],
            "inserted_observations": stats["inserted_observations"],
        }

    def counts(self) -> dict[str, int]:
        cursor = self.connection.cursor()
        try:
            cursor.execute("SELECT count(*) FROM alert_state_snapshots")
            snapshots = cursor.fetchone()[0]
            cursor.execute("SELECT count(*) FROM alert_threat_observations")
            observations = cursor.fetchone()[0]
            return {"snapshots": snapshots, "observations": observations}
        finally:
            close = getattr(cursor, "close", None)
            if callable(close):
                close()

    def close(self) -> None:
        self.connection.close()


def _persist_one(store: Any, record: dict[str, Any], result: dict[str, Any]) -> None:
    persisted = store.persist(record)
    result["inserted_snapshots"] += persisted["inserted_snapshots"]
    result["inserted_observations"] += persisted["inserted_observations"]
    binding = record["snapshot"]["binding_state"]
    result["binding"][binding] += 1
    result["status"] = "SUCCEEDED"


def _input_mode(env: Mapping[str, str]) -> str:
    return str(env.get(INPUT_MODE_ENV, "legacy") or "legacy").strip().lower()


def _stored_input_preflight(env: Mapping[str, str]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    paths = {
        "kyiv": env.get(KYIV_INPUT_ENV),
        "ukrainealarm": env.get(UA_INPUT_ENV),
        "alerts_in_ua": env.get(AIU_INPUT_ENV),
    }
    loaded: dict[str, Any] = {}
    for source, path in paths.items():
        if not path:
            return None, {
                "source": source,
                "error_type": "MissingStoredInput",
                "error": f"stored_only requires declared stored input for {source}",
            }
        try:
            loaded[source] = _json_file(path)
        except FileNotFoundError as exc:
            return None, {"source": source, "error_type": type(exc).__name__, "error": str(exc)[:500]}
        except (OSError, json.JSONDecodeError) as exc:
            return None, {"source": source, "error_type": type(exc).__name__, "error": str(exc)[:500]}
    return loaded, None


def run_shadow(
    alerts: list[Any] | None,
    *,
    env: Mapping[str, str] | None = None,
    fetch_json: Callable[[str, int], Any] | None = None,
    store_factory: Callable[[str], Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    env = dict(os.environ if env is None else env)
    result: dict[str, Any] = {
        "attempted": False,
        "feature_flag": FEATURE_FLAG,
        "status": "DISABLED",
        "sources": {},
        "inserted_snapshots": 0,
        "inserted_observations": 0,
        "binding": {"BOUND": 0, "AMBIGUOUS": 0, "UNBOUND": 0},
        "store_counts": None,
        "production_output_mutation": False,
    }
    if not enabled(env):
        return result

    result["attempted"] = True
    observed_at = _utc_iso(now)
    backend = str(env.get(BACKEND_ENV, "sqlite") or "sqlite").strip().lower()
    result["backend"] = backend
    if backend not in {"sqlite", "postgres"}:
        result.update({"status": "FAILED", **_safe_error(RuntimeError(f"unsupported {BACKEND_ENV}={backend!r}"))})
        _write_diagnostic(env.get(DIAGNOSTIC_ENV), result)
        return result

    target_env = DATABASE_URL_ENV if backend == "postgres" else DB_ENV
    store_target = env.get(target_env)
    if not store_target:
        result.update({"status": "FAILED", **_safe_error(RuntimeError(f"{target_env} is required when {FEATURE_FLAG}=1 and backend={backend}"))})
        _write_diagnostic(env.get(DIAGNOSTIC_ENV), result)
        return result

    input_mode = _input_mode(env)
    result["input_mode"] = input_mode
    stored_inputs = None
    if input_mode == STORED_ONLY_MODE:
        stored_inputs, stored_error = _stored_input_preflight(env)
        if stored_error is not None:
            result.update({
                "status": "FAILED",
                "stored_input_error": stored_error,
                "sidecar_network_requests": 0,
            })
            _write_diagnostic(env.get(DIAGNOSTIC_ENV), result)
            return result

    fetch_json = shadow.fetch_json if fetch_json is None else fetch_json
    if store_factory is None:
        store_factory = PostgresShadowStore if backend == "postgres" else shadow.ShadowStore
    parents = parent_episodes_from_updater(alerts)

    try:
        store = store_factory(store_target)
    except Exception as exc:
        result.update({"status": "FAILED", **_safe_error(exc)})
        _write_diagnostic(env.get(DIAGNOSTIC_ENV), result)
        return result

    source_failures = 0
    source_successes = 0
    try:
        kyiv_path = env.get(KYIV_INPUT_ENV)
        kyiv_class = env.get(KYIV_INPUT_CLASS_ENV, "STORED_RAW" if kyiv_path else "LIVE_RAW")
        if kyiv_class not in {"LIVE_RAW", "STORED_RAW", "FIXTURE"}:
            kyiv_class = "FIXTURE"
        kr = _source_result(kyiv_class)
        result["sources"]["kyiv"] = kr
        try:
            if input_mode == STORED_ONLY_MODE:
                payload = stored_inputs["kyiv"]
            else:
                payload = _json_file(kyiv_path) if kyiv_path else fetch_json(KYIV_URL, 10)
            record = shadow.canonicalize_kyiv(
                payload,
                observed_at=observed_at,
                target_city_key="kyiv",
                raw_object_path="$LIVE_RAW" if kyiv_class == "LIVE_RAW" else "$FROZEN_RAW",
            )
            record = shadow.bind(record, parents)
            _persist_one(store, record, kr)
            source_successes += 1
        except Exception as exc:
            kr.update({"status": "FAILED", **_safe_error(exc)})
            source_failures += 1

        ua_path = env.get(UA_INPUT_ENV)
        ur = _source_result("STORED_RAW" if ua_path else "SKIPPED_NO_CREDENTIAL")
        result["sources"]["ukrainealarm"] = ur
        if ua_path:
            try:
                payload = stored_inputs["ukrainealarm"] if input_mode == STORED_ONLY_MODE else _json_file(ua_path)
                region_id = str(payload.get("regionId") or "147")
                record = shadow.canonicalize_ukrainealarm(
                    payload,
                    observed_at=observed_at,
                    target_city_key="zaporizhzhia",
                    region_id=region_id,
                    raw_object_path="$STORED_RAW",
                )
                record = shadow.bind(record, parents)
                _persist_one(store, record, ur)
                source_successes += 1
            except Exception as exc:
                ur.update({"status": "FAILED", **_safe_error(exc)})
                source_failures += 1
        else:
            ur["status"] = "SKIPPED"

        aiu_path = env.get(AIU_INPUT_ENV)
        ar = _source_result("STORED_RAW" if aiu_path else "SKIPPED_NO_CREDENTIAL")
        result["sources"]["alerts_in_ua"] = ar
        if aiu_path:
            try:
                payload = stored_inputs["alerts_in_ua"] if input_mode == STORED_ONLY_MODE else _json_file(aiu_path)
                record = shadow.canonicalize_alerts_in_ua(
                    payload,
                    observed_at=observed_at,
                    target_city_key="donetsk",
                    raw_object_path="$STORED_RAW",
                )
                record = shadow.bind(record, parents)
                _persist_one(store, record, ar)
                source_successes += 1
            except Exception as exc:
                ar.update({"status": "FAILED", **_safe_error(exc)})
                source_failures += 1
        else:
            ar["status"] = "SKIPPED"

        counts = store.counts()
        result["store_counts"] = counts
        result["sidecar_network_requests"] = 0 if input_mode == STORED_ONLY_MODE else (1 if not kyiv_path else 0)
        for sr in result["sources"].values():
            result["inserted_snapshots"] += sr["inserted_snapshots"]
            result["inserted_observations"] += sr["inserted_observations"]
            for key in result["binding"]:
                result["binding"][key] += sr["binding"][key]
        if source_failures:
            result["status"] = "PARTIAL_FAILURE" if source_successes else "FAILED"
        else:
            result["status"] = "SUCCEEDED"
    finally:
        store.close()

    _write_diagnostic(env.get(DIAGNOSTIC_ENV), result)
    return result


def run_from_updater(alerts: list[Any] | None, *, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Fail-open production seam. Never raises into the authoritative updater."""
    try:
        result = run_shadow(alerts, env=env)
    except Exception as exc:
        result = {
            "attempted": True,
            "feature_flag": FEATURE_FLAG,
            "status": "FAILED",
            "sources": {},
            "inserted_snapshots": 0,
            "inserted_observations": 0,
            "binding": {"BOUND": 0, "AMBIGUOUS": 0, "UNBOUND": 0},
            "store_counts": None,
            "production_output_mutation": False,
            **_safe_error(exc),
        }
    if result.get("status") == "DISABLED":
        return result
    safe = {
        "attempted": result.get("attempted"),
        "status": result.get("status"),
        "sources": {
            name: {
                "input_class": value.get("input_class"),
                "status": value.get("status"),
                "inserted_snapshots": value.get("inserted_snapshots"),
                "inserted_observations": value.get("inserted_observations"),
                "error_type": value.get("error_type"),
            }
            for name, value in result.get("sources", {}).items()
        },
        "inserted_snapshots": result.get("inserted_snapshots"),
        "inserted_observations": result.get("inserted_observations"),
        "error_type": result.get("error_type"),
    }
    print("DIFFERENTIATED_ALERT_SHADOW " + json.dumps(safe, ensure_ascii=False, sort_keys=True), file=sys.stderr)
    return result
