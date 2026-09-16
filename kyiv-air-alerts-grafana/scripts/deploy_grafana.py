#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_FILE = ROOT / "grafana" / "dashboard.json"
DEFAULT_TITLE = "Повітряні тривоги — міста України"
DATASOURCE_NAME = "Infinity"


def env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def api_url(base: str, path: str) -> str:
    return base.rstrip("/") + "/" + path.lstrip("/")


def request_json(
    session: requests.Session,
    method: str,
    url: str,
    *,
    expected: tuple[int, ...] = (200,),
    **kwargs: Any,
) -> Any:
    response = session.request(method, url, timeout=60, **kwargs)
    if response.status_code not in expected:
        body = response.text[:2000]
        raise RuntimeError(f"Grafana API {method} {url} -> {response.status_code}: {body}")
    if not response.content:
        return None
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError(f"Grafana API returned non-JSON for {method} {url}: {response.text[:1000]}") from exc


def replace_string(obj: Any, old: str, new: str) -> Any:
    if isinstance(obj, str):
        return obj.replace(old, new)
    if isinstance(obj, list):
        return [replace_string(x, old, new) for x in obj]
    if isinstance(obj, dict):
        return {k: replace_string(v, old, new) for k, v in obj.items()}
    return obj


def load_local_dashboard() -> dict:
    obj = json.loads(DASHBOARD_FILE.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise RuntimeError("grafana/dashboard.json must contain one dashboard object")
    return obj


def resolve_datasource_uid(session: requests.Session, base_url: str) -> str:
    name = env("GRAFANA_INFINITY_NAME") or DATASOURCE_NAME
    result = request_json(
        session,
        "GET",
        api_url(base_url, f"/api/datasources/name/{quote(name, safe='')}"),
    )
    uid = (result or {}).get("uid")
    if not uid:
        raise RuntimeError(f"Grafana datasource {name!r} has no uid")
    return str(uid)


def find_dashboard_uid(session: requests.Session, base_url: str, title: str) -> str:
    configured = env("GRAFANA_DASHBOARD_UID")
    if configured:
        return configured

    results = request_json(
        session,
        "GET",
        api_url(base_url, "/api/search"),
        params={"query": title, "type": "dash-db", "limit": 100},
    )
    exact = [item for item in (results or []) if item.get("title") == title and item.get("uid")]
    if len(exact) == 1:
        return str(exact[0]["uid"])
    if not exact:
        raise RuntimeError(
            f"Could not find existing Grafana dashboard with exact title {title!r}. "
            "Set GRAFANA_DASHBOARD_UID if the live title differs."
        )
    raise RuntimeError(
        f"Found {len(exact)} dashboards with exact title {title!r}; set GRAFANA_DASHBOARD_UID explicitly."
    )


def load_existing_dashboard(session: requests.Session, base_url: str, uid: str) -> dict:
    return request_json(
        session,
        "GET",
        api_url(base_url, f"/api/dashboards/uid/{quote(uid, safe='')}"),
    )


def prepare_dashboard(local: dict, existing: dict, dashboard_uid: str, datasource_uid: str) -> tuple[dict, str | None]:
    rendered = replace_string(local, "${DS_INFINITY}", datasource_uid)
    rendered.pop("__inputs", None)

    current = existing.get("dashboard") or {}
    meta = existing.get("meta") or {}

    rendered["uid"] = dashboard_uid
    rendered["id"] = current.get("id")
    rendered["version"] = current.get("version", 0)

    folder_uid = meta.get("folderUid") or None
    return rendered, folder_uid


def deploy_dashboard(
    session: requests.Session,
    base_url: str,
    dashboard: dict,
    folder_uid: str | None,
) -> dict:
    payload: dict[str, Any] = {
        "dashboard": dashboard,
        "overwrite": True,
        "message": "Automated deploy from GitHub Actions",
    }
    if folder_uid:
        payload["folderUid"] = folder_uid

    return request_json(
        session,
        "POST",
        api_url(base_url, "/api/dashboards/db"),
        expected=(200,),
        json=payload,
    )


def refresh_shared_dashboard(session: requests.Session, base_url: str, dashboard_uid: str) -> str:
    url = api_url(base_url, f"/api/dashboards/uid/{quote(dashboard_uid, safe='')}/public-dashboards/")
    response = session.get(url, timeout=60)
    if response.status_code == 404:
        return "none"
    if response.status_code != 200:
        raise RuntimeError(f"Grafana shared-dashboard lookup failed: {response.status_code}: {response.text[:2000]}")

    shared = response.json()
    public_uid = shared.get("uid")
    if not public_uid:
        return "none"

    payload = {
        "timeSelectionEnabled": bool(shared.get("timeSelectionEnabled", False)),
        "isEnabled": bool(shared.get("isEnabled", True)),
        "annotationsEnabled": bool(shared.get("annotationsEnabled", False)),
        "share": shared.get("share") or "public",
    }
    request_json(
        session,
        "PATCH",
        api_url(
            base_url,
            f"/api/dashboards/uid/{quote(dashboard_uid, safe='')}/public-dashboards/{quote(str(public_uid), safe='')}",
        ),
        expected=(200,),
        json=payload,
    )
    return str(public_uid)


def main() -> None:
    base_url = env("GRAFANA_URL")
    token = env("GRAFANA_TOKEN")

    if not base_url or not token:
        print("Grafana deploy skipped: GRAFANA_URL/GRAFANA_TOKEN are not configured")
        return

    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "kyiv-air-alerts-grafana-github-actions/1.0",
        }
    )

    local = load_local_dashboard()
    title = env("GRAFANA_DASHBOARD_TITLE") or local.get("title") or DEFAULT_TITLE
    datasource_uid = resolve_datasource_uid(session, base_url)
    dashboard_uid = find_dashboard_uid(session, base_url, str(title))
    existing = load_existing_dashboard(session, base_url, dashboard_uid)
    prepared, folder_uid = prepare_dashboard(local, existing, dashboard_uid, datasource_uid)

    result = deploy_dashboard(session, base_url, prepared, folder_uid)
    deployed_uid = result.get("uid") or dashboard_uid
    shared_uid = refresh_shared_dashboard(session, base_url, str(deployed_uid))

    saved = load_existing_dashboard(session, base_url, str(deployed_uid))
    saved_dashboard = saved.get("dashboard") or {}
    saved_from = (saved_dashboard.get("time") or {}).get("from")
    expected_from = (prepared.get("time") or {}).get("from")
    if saved_from != expected_from:
        raise RuntimeError(
            f"Grafana dashboard saved with unexpected time.from: {saved_from!r} != {expected_from!r}"
        )

    print(
        "Grafana deploy successful: "
        f"dashboard_uid={deployed_uid}, shared_dashboard_uid={shared_uid}, time.from={saved_from}"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
