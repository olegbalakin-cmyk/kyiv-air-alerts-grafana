#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from urllib.parse import quote

import requests

import deploy_grafana as dg

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_FILE = ROOT / "grafana" / "dashboard.json"
PUBLIC_UID = "ukraine-air-alerts-public"
PUBLIC_TITLE = "Повітряні тривоги — міста України — публічна версія"


REPLACEMENTS = [
    ("${city:text}", "Київ"),
    ("${city}", "kyiv"),
    ("${duration_unit:text}", "Хвилини"),
    ("${duration_unit}", "minutes"),
    ("${comparison_period:text}", "Місяці"),
    ("${comparison_period}", "monthly"),
    ("${compare_city_a:text}", "Київ"),
    ("${compare_city_a}", "kyiv"),
    ("${compare_city_b:text}", "Харків"),
    ("${compare_city_b}", "kharkiv"),
    ("${compare_city_c:text}", "Запоріжжя"),
    ("${compare_city_c}", "zaporizhzhia"),
]


def replace_static(obj):
    if isinstance(obj, str):
        for old, new in REPLACEMENTS:
            obj = obj.replace(old, new)
        return obj
    if isinstance(obj, list):
        return [replace_static(x) for x in obj]
    if isinstance(obj, dict):
        return {k: replace_static(v) for k, v in obj.items()}
    return obj


def all_targets(panels):
    for panel in panels or []:
        for target in panel.get("targets", []):
            yield panel, target
        yield from all_targets(panel.get("panels", []))


def build_public_dashboard(source: dict, datasource_uid: str) -> dict:
    obj = replace_static(copy.deepcopy(source))
    obj.pop("__inputs", None)
    obj["uid"] = PUBLIC_UID
    obj["id"] = None
    obj["version"] = 0
    obj["title"] = PUBLIC_TITLE
    obj["templating"] = {"list": []}

    obj = dg.replace_string(obj, "${DS_INFINITY}", datasource_uid)

    # The public dashboard must not depend on template variables anywhere.
    raw = json.dumps(obj, ensure_ascii=False)
    unresolved = sorted({
        token for token in (
            "${city}", "${city:text}", "${duration_unit}", "${duration_unit:text}",
            "${comparison_period}", "${comparison_period:text}",
            "${compare_city_a}", "${compare_city_a:text}",
            "${compare_city_b}", "${compare_city_b:text}",
            "${compare_city_c}", "${compare_city_c:text}",
        )
        if token in raw
    })
    if unresolved:
        raise RuntimeError(f"Unresolved public-dashboard variables: {unresolved}")

    # Assert all Infinity queries are backend queries and all URLs are fixed.
    targets = list(all_targets(obj.get("panels", [])))
    if not targets:
        raise RuntimeError("No Infinity targets found")
    for panel, target in targets:
        if target.get("type") != "json" or target.get("source") != "url":
            continue
        if target.get("parser") != "backend":
            raise RuntimeError(
                f"Panel {panel.get('id')} is not using Infinity backend parser: {target.get('parser')!r}"
            )
        if "${" in str(target.get("url") or "") or "${" in str(target.get("root_selector") or ""):
            raise RuntimeError(f"Panel {panel.get('id')} still has a variable-dependent query")

    return obj


def get_or_create_public_share(session: requests.Session, base_url: str) -> dict:
    url = dg.api_url(
        base_url,
        f"/api/dashboards/uid/{quote(PUBLIC_UID, safe='')}/public-dashboards/",
    )
    response = session.get(url, timeout=60)
    if response.status_code == 200:
        shared = response.json()
        public_uid = shared.get("uid")
        if public_uid:
            patch_url = dg.api_url(
                base_url,
                f"/api/dashboards/uid/{quote(PUBLIC_UID, safe='')}/public-dashboards/{quote(str(public_uid), safe='')}",
            )
            patched = dg.request_json(
                session,
                "PATCH",
                patch_url,
                expected=(200,),
                json={
                    "timeSelectionEnabled": True,
                    "isEnabled": True,
                    "annotationsEnabled": False,
                    "share": "public",
                },
            )
            return patched
    elif response.status_code != 404:
        raise RuntimeError(
            f"Grafana shared-dashboard lookup failed: {response.status_code}: {response.text[:2000]}"
        )

    created = dg.request_json(
        session,
        "POST",
        url,
        expected=(200,),
        json={
            "timeSelectionEnabled": True,
            "isEnabled": True,
            "annotationsEnabled": False,
            "share": "public",
        },
    )
    public_uid = created.get("uid")
    if public_uid:
        patch_url = dg.api_url(
            base_url,
            f"/api/dashboards/uid/{quote(PUBLIC_UID, safe='')}/public-dashboards/{quote(str(public_uid), safe='')}",
        )
        return dg.request_json(
            session,
            "PATCH",
            patch_url,
            expected=(200,),
            json={
                "timeSelectionEnabled": True,
                "isEnabled": True,
                "annotationsEnabled": False,
                "share": "public",
            },
        )
    return created


def main() -> None:
    base_url = dg.env("GRAFANA_URL")
    token = dg.env("GRAFANA_TOKEN")
    if not base_url or not token:
        raise RuntimeError("GRAFANA_URL/GRAFANA_TOKEN are required")

    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "ukraine-air-alerts-public-dashboard/1.0",
        }
    )

    source = json.loads(DASHBOARD_FILE.read_text(encoding="utf-8"))

    interactive_uid = dg.find_dashboard_uid(
        session,
        base_url,
        dg.env("GRAFANA_DASHBOARD_TITLE") or source.get("title") or dg.DEFAULT_TITLE,
    )
    existing = dg.load_existing_dashboard(session, base_url, interactive_uid)
    datasource_uid = dg.resolve_datasource_uid(session, base_url, existing)
    folder_uid = (existing.get("meta") or {}).get("folderUid") or None

    public_dashboard = build_public_dashboard(source, datasource_uid)
    result = dg.deploy_dashboard(session, base_url, public_dashboard, folder_uid)
    deployed_uid = result.get("uid") or PUBLIC_UID
    if deployed_uid != PUBLIC_UID:
        raise RuntimeError(f"Unexpected public dashboard uid: {deployed_uid}")

    shared = get_or_create_public_share(session, base_url)
    access_token = shared.get("accessToken")
    if not access_token:
        raise RuntimeError(f"Shared dashboard has no accessToken: {shared}")

    public_url = f"{base_url.rstrip('/')}/public-dashboards/{access_token}"

    # Public page itself must be reachable without authentication.
    check = requests.get(public_url, timeout=60)
    if check.status_code != 200:
        raise RuntimeError(f"Public dashboard URL returned {check.status_code}: {check.text[:500]}")

    status = {
        "ok": True,
        "interactive_dashboard_uid": interactive_uid,
        "public_dashboard_uid": PUBLIC_UID,
        "shared_dashboard_uid": shared.get("uid"),
        "public_url": public_url,
        "fixed_city": "kyiv",
        "fixed_duration_unit": "minutes",
        "fixed_comparison": ["kyiv", "kharkiv", "zaporizhzhia"],
        "template_variables": 0,
    }
    print(json.dumps(status, ensure_ascii=False))


if __name__ == "__main__":
    main()
