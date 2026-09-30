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
from urllib.parse import urlsplit

import proof_differentiated_alert_shadow_ingestion as shadow

FEATURE_FLAG = "DIFFERENTIATED_ALERT_SHADOW"
DB_ENV = "DIFFERENTIATED_ALERT_SHADOW_DB"  # legacy SQLite proof compatibility
DATABASE_URL_ENV = "DIFFERENTIATED_ALERT_SHADOW_DATABASE_URL"
DB_SCHEMA_ENV = "DIFFERENTIATED_ALERT_SHADOW_SCHEMA"
DB_BRANCH_ENV = "DIFFERENTIATED_ALERT_SHADOW_DB_BRANCH"
DIAGNOSTIC_ENV = "DIFFERENTIATED_ALERT_SHADOW_DIAGNOSTIC"
INPUT_SHA_ENV = "DIFFERENTIATED_ALERT_SHADOW_INPUT_SHA"
OBSERVED_AT_ENV = "DIFFERENTIATED_ALERT_SHADOW_OBSERVED_AT"
KYIV_INPUT_ENV = "DIFFERENTIATED_ALERT_SHADOW_KYIV_JSON"
KYIV_INPUT_CLASS_ENV = "DIFFERENTIATED_ALERT_SHADOW_KYIV_INPUT_CLASS"
UA_INPUT_ENV = "DIFFERENTIATED_ALERT_SHADOW_UKRAINEALARM_JSON"
AIU_INPUT_ENV = "DIFFERENTIATED_ALERT_SHADOW_ALERTS_IN_UA_JSON"
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


def _observed_at(env: Mapping[str, str], now: datetime | None) -> str:
    forced = str(env.get(OBSERVED_AT_ENV) or "").strip()
    if forced:
        value = forced[:-1] + "+00:00" if forced.endswith("Z") else forced
        return _utc_iso(datetime.fromisoformat(value))
    return _utc_iso(now)


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


def _sanitize_text(text: str, env: Mapping[str, str]) -> str:
    out = text
    for key in (DATABASE_URL_ENV, "PHASE1_PROD_SHADOW_DATABASE_URL", "PHASE1_DATABASE_URL", "UKRAINEALARM_API_TOKEN"):
        value = str(env.get(key) or "").strip()
        if value:
            out = out.replace(value, "[REDACTED]")
            if "DATABASE_URL" in key:
                try:
                    password = urlsplit(value).password
                except ValueError:
                    password = None
                if password:
                    out = out.replace(password, "[REDACTED]")
    return out


def _write_diagnostic(path: str | None, result: dict[str, Any], env: Mapping[str, str]) -> None:
    if not path:
        return
    raw = _sanitize_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", env)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(raw, encoding="utf-8")


def _source_result(input_class: str, status: str = "NOT_ATTEMPTED") -> dict[str, Any]:
    return {
        "input_class": input_class,
        "status": status,
        "inserted_snapshots": 0,
        "existing_snapshots": 0,
        "inserted_observations": 0,
        "existing_observations": 0,
        "binding": {"BOUND": 0, "AMBIGUOUS": 0, "UNBOUND": 0},
    }


def _persist_one(store: Any, record: dict[str, Any], result: dict[str, Any]) -> None:
    persisted = store.persist(record)
    for key in ("inserted_snapshots", "existing_snapshots", "inserted_observations", "existing_observations"):
        result[key] += int(persisted.get(key, 0))
    result["binding"][record["snapshot"]["binding_state"]] += 1
    result["status"] = "SUCCEEDED"


def _open_store(env: Mapping[str, str], store_factory: Callable[[str], Any] | None):
    if store_factory is not None:
        target = str(env.get(DB_ENV) or env.get(DATABASE_URL_ENV) or "")
        if not target:
            raise RuntimeError(f"{DB_ENV} or {DATABASE_URL_ENV} is required when {FEATURE_FLAG}=1")
        return store_factory(target)
    database_url = str(env.get(DATABASE_URL_ENV) or "").strip()
    if database_url:
        from differentiated_alert_postgres import PostgresShadowStore
        return PostgresShadowStore(database_url, str(env.get(DB_SCHEMA_ENV) or "differentiated_alert_shadow"))
    legacy = str(env.get(DB_ENV) or "").strip()
    if legacy:
        return shadow.ShadowStore(legacy)
    raise RuntimeError(f"{DATABASE_URL_ENV} is required for production; {DB_ENV} is accepted only for proof compatibility")


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
        "existing_snapshots": 0,
        "inserted_observations": 0,
        "existing_observations": 0,
        "binding": {"BOUND": 0, "AMBIGUOUS": 0, "UNBOUND": 0},
        "store_counts": None,
        "production_output_mutation": False,
        "db_branch": str(env.get(DB_BRANCH_ENV) or "").strip() or None,
        "input_sha": str(env.get(INPUT_SHA_ENV) or "").strip() or None,
        "exact_retry": False,
    }
    if not enabled(env):
        return result

    result["attempted"] = True
    observed_at = _observed_at(env, now)
    fetch_json = shadow.fetch_json if fetch_json is None else fetch_json
    parents = parent_episodes_from_updater(alerts)

    try:
        store = _open_store(env, store_factory)
    except Exception as exc:
        result.update({"status": "FAILED", **_safe_error(exc)})
        _write_diagnostic(env.get(DIAGNOSTIC_ENV), result, env)
        return result

    source_failures = 0
    source_successes = 0
    try:
        kyiv_path = env.get(KYIV_INPUT_ENV)
        kyiv_class = env.get(KYIV_INPUT_CLASS_ENV, "STORED_RAW" if kyiv_path else "LIVE_RAW")
        if kyiv_class not in {"LIVE_RAW", "CURRENT_RUN_RAW", "STORED_RAW", "FIXTURE"}:
            kyiv_class = "FIXTURE"
        kr = _source_result(kyiv_class)
        result["sources"]["kyiv"] = kr
        try:
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
                payload = _json_file(ua_path)
                region_id = str(payload.get("regionId") or "147")
                target_city_key = str(payload.get("targetCityKey") or "zaporizhzhia")
                record = shadow.canonicalize_ukrainealarm(
                    payload,
                    observed_at=observed_at,
                    target_city_key=target_city_key,
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
            ur["status"] = "SKIPPED_NO_LIVE_RAW_SOURCE"

        aiu_path = env.get(AIU_INPUT_ENV)
        ar = _source_result("STORED_RAW" if aiu_path else "SKIPPED_NO_CREDENTIAL")
        result["sources"]["alerts_in_ua"] = ar
        if aiu_path:
            try:
                payload = _json_file(aiu_path)
                record = shadow.canonicalize_alerts_in_ua(
                    payload,
                    observed_at=observed_at,
                    target_city_key=str(payload.get("targetCityKey") or "donetsk"),
                    raw_object_path="$STORED_RAW",
                )
                record = shadow.bind(record, parents)
                _persist_one(store, record, ar)
                source_successes += 1
            except Exception as exc:
                ar.update({"status": "FAILED", **_safe_error(exc)})
                source_failures += 1
        else:
            ar["status"] = "SKIPPED_NO_LIVE_RAW_SOURCE"

        result["store_counts"] = store.counts()
        for sr in result["sources"].values():
            for key in ("inserted_snapshots", "existing_snapshots", "inserted_observations", "existing_observations"):
                result[key] += int(sr.get(key, 0))
            for key in result["binding"]:
                result["binding"][key] += int(sr["binding"][key])
        if source_failures:
            result["status"] = "PARTIAL_FAILURE" if source_successes else "FAILED"
        else:
            result["status"] = "SUCCEEDED" if source_successes else "FAILED"
        result["exact_retry"] = bool(
            source_successes
            and result["inserted_snapshots"] == 0
            and result["inserted_observations"] == 0
            and result["existing_snapshots"] > 0
        )
    finally:
        store.close()

    _write_diagnostic(env.get(DIAGNOSTIC_ENV), result, env)
    return result


def run_from_updater(alerts: list[Any] | None, *, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Fail-open production seam. Never raises into the authoritative updater."""
    effective_env = dict(os.environ if env is None else env)
    try:
        result = run_shadow(alerts, env=effective_env)
    except Exception as exc:
        result = {
            "attempted": True,
            "feature_flag": FEATURE_FLAG,
            "status": "FAILED",
            "sources": {},
            "inserted_snapshots": 0,
            "existing_snapshots": 0,
            "inserted_observations": 0,
            "existing_observations": 0,
            "binding": {"BOUND": 0, "AMBIGUOUS": 0, "UNBOUND": 0},
            "store_counts": None,
            "production_output_mutation": False,
            "db_branch": str(effective_env.get(DB_BRANCH_ENV) or "").strip() or None,
            "input_sha": str(effective_env.get(INPUT_SHA_ENV) or "").strip() or None,
            "exact_retry": False,
            **_safe_error(exc),
        }
        _write_diagnostic(effective_env.get(DIAGNOSTIC_ENV), result, effective_env)
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
                "existing_snapshots": value.get("existing_snapshots"),
                "inserted_observations": value.get("inserted_observations"),
                "existing_observations": value.get("existing_observations"),
                "binding": value.get("binding"),
                "error_type": value.get("error_type"),
            }
            for name, value in result.get("sources", {}).items()
        },
        "inserted_snapshots": result.get("inserted_snapshots"),
        "existing_snapshots": result.get("existing_snapshots"),
        "inserted_observations": result.get("inserted_observations"),
        "existing_observations": result.get("existing_observations"),
        "binding": result.get("binding"),
        "db_branch": result.get("db_branch"),
        "input_sha": result.get("input_sha"),
        "exact_retry": result.get("exact_retry"),
        "error_type": result.get("error_type"),
    }
    print("DIFFERENTIATED_ALERT_SHADOW " + json.dumps(safe, ensure_ascii=False, sort_keys=True), file=sys.stderr)
    return result
