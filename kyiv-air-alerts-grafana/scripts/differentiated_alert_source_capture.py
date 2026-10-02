#!/usr/bin/env python3
"""Fail-open same-run capture for accepted differentiated-alert current-state sources."""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

import requests

CAPTURE_ENV = "DIFFERENTIATED_ALERT_SOURCE_CAPTURE"
DIAGNOSTIC_ENV = "DIFFERENTIATED_ALERT_SOURCE_CAPTURE_DIAGNOSTIC"
KYIV_OUTPUT_ENV = "DIFFERENTIATED_ALERT_SHADOW_KYIV_JSON"
UA_OUTPUT_ENV = "DIFFERENTIATED_ALERT_SHADOW_UKRAINEALARM_JSON"
AIU_OUTPUT_ENV = "DIFFERENTIATED_ALERT_SHADOW_ALERTS_IN_UA_JSON"
UA_TOKEN_ENV = "UKRAINEALARM_API_TOKEN"

KYIV_URL = "https://kyiv.digital/open-api/air-alert/state"
UA_URL = "https://api.ukrainealarm.com/api/v3/alerts"
AIU_URL = "https://ubilling.net.ua/aerialalerts/?json=true&source=aiu&raw"
TRUE_VALUES = {"1", "true", "yes", "on"}

_SECRET_RE = re.compile(
    r"(?i)(authorization\s*[=:]\s*[^\s,;]+|token\s*[=:]\s*[^\s,;]+|"
    r"api[_-]?key\s*[=:]\s*[^\s,;]+|password\s*[=:]\s*[^\s,;]+|"
    r"postgres(?:ql)?://[^\s]+)"
)


def enabled(env: Mapping[str, str] | None = None) -> bool:
    env = os.environ if env is None else env
    return str(env.get(CAPTURE_ENV, "")).strip().lower() in TRUE_VALUES


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sanitize(value: object) -> str:
    return _SECRET_RE.sub("[REDACTED]", str(value))[:500]


def canonical_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def default_fetch(url: str, *, headers: Mapping[str, str], timeout: int = 30) -> tuple[int, Any]:
    response = requests.get(url, headers=dict(headers), timeout=timeout)
    response.raise_for_status()
    return response.status_code, response.json()


def _write_payload(path: str, payload: Any) -> dict[str, Any]:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    body = canonical_bytes(payload)
    target.write_bytes(body)
    return {
        "path": str(target),
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
    }


def capture_sources(
    *,
    env: Mapping[str, str] | None = None,
    fetch: Callable[..., tuple[int, Any]] | None = None,
    captured_at: str | None = None,
) -> dict[str, Any]:
    env = dict(os.environ if env is None else env)
    result: dict[str, Any] = {
        "capture_enabled": enabled(env),
        "status": "DISABLED",
        "captured_at": captured_at or utc_now(),
        "logical_acquisition_counts": {
            "kyiv_official": 0,
            "ukrainealarm": 0,
            "alerts_in_ua": 0,
        },
        "sources": {},
        "credentials_exposed": False,
        "production_output_mutation": False,
    }
    if not result["capture_enabled"]:
        return result

    fetch = default_fetch if fetch is None else fetch
    token = str(env.get(UA_TOKEN_ENV, "")).strip()
    specs = [
        (
            "kyiv_official",
            KYIV_URL,
            {"Accept": "application/json", "User-Agent": "kyiv-air-alerts-grafana/differentiated-capture"},
            KYIV_OUTPUT_ENV,
            False,
        ),
        (
            "ukrainealarm",
            UA_URL,
            {
                "Accept": "application/json",
                "Authorization": token,
                "User-Agent": "kyiv-air-alerts-grafana/differentiated-capture",
            },
            UA_OUTPUT_ENV,
            True,
        ),
        (
            "alerts_in_ua",
            AIU_URL,
            {"Accept": "application/json", "User-Agent": "kyiv-air-alerts-grafana/differentiated-capture"},
            AIU_OUTPUT_ENV,
            False,
        ),
    ]

    failures = 0
    for source, url, headers, output_env, needs_token in specs:
        sr: dict[str, Any] = {
            "source": source,
            "status": "NOT_ATTEMPTED",
            "url": url,
            "logical_acquisition_count": 0,
            "http_status": None,
            "bytes": None,
            "sha256": None,
        }
        result["sources"][source] = sr
        output_path = str(env.get(output_env, "")).strip()
        if not output_path:
            sr.update({"status": "FAILED", "error_type": "MissingOutputPath", "error": f"{output_env} is required"})
            failures += 1
            continue
        if needs_token and not token:
            sr.update({"status": "FAILED", "error_type": "MissingCredential", "error": f"{UA_TOKEN_ENV} is required"})
            failures += 1
            continue

        try:
            result["logical_acquisition_counts"][source] += 1
            sr["logical_acquisition_count"] = 1
            status, payload = fetch(url, headers=headers, timeout=30)
            meta = _write_payload(output_path, payload)
            sr.update({
                "status": "SUCCEEDED",
                "http_status": int(status),
                "bytes": meta["bytes"],
                "sha256": meta["sha256"],
                "stored_input_env": output_env,
                "transport_retries_attributable": "transport_client_specific",
            })
        except Exception as exc:
            sr.update({"status": "FAILED", "error_type": type(exc).__name__, "error": sanitize(exc)})
            failures += 1

    result["status"] = "SUCCEEDED" if failures == 0 else ("PARTIAL_FAILURE" if failures < len(specs) else "FAILED")
    return result


def write_diagnostic(path: str | None, result: Mapping[str, Any]) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    safe = json.loads(json.dumps(result))
    for source in safe.get("sources", {}).values():
        source.pop("path", None)
    target.write_text(json.dumps(safe, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    result = capture_sources()
    write_diagnostic(os.environ.get(DIAGNOSTIC_ENV), result)
    print(json.dumps({
        "status": result.get("status"),
        "logical_acquisition_counts": result.get("logical_acquisition_counts"),
        "sources": {
            k: {
                "status": v.get("status"),
                "http_status": v.get("http_status"),
                "bytes": v.get("bytes"),
                "sha256": v.get("sha256"),
                "error_type": v.get("error_type"),
            }
            for k, v in result.get("sources", {}).items()
        },
        "credentials_exposed": False,
    }, sort_keys=True))
    # Capture is auxiliary by contract: source failure is reported but does not fail normal publication.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
