#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "dashboard_data.json"
DASHBOARD = ROOT / "grafana" / "dashboard.json"
QA_FILE = ROOT / "data" / "dashboard_qa.json"

UPSTREAM_REPO = "Vadimkin/ukrainian-air-raid-sirens-dataset"
UPSTREAM_PATH = "datasets/official_data_uk.csv"
UPSTREAM_COMMITS_API = f"https://api.github.com/repos/{UPSTREAM_REPO}/commits"
WARN_AFTER_HOURS = 48.0
UTC = timezone.utc


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def source_freshness(data: dict) -> dict:
    now = datetime.now(UTC)

    # Event freshness comes from the exact CSV snapshot already consumed in this run.
    latest_event = None
    for city in data.get("cities", {}).values():
        meta = city.get("meta", {})
        if meta.get("source_type") != "raion_proxy":
            continue
        candidate = parse_iso(meta.get("latest_proxy_record_end"))
        if candidate and (latest_event is None or candidate > latest_event):
            latest_event = candidate

    result = {
        "checked_at": now.isoformat(),
        "warning_threshold_hours": WARN_AFTER_HOURS,
        "latest_proxy_event_end": latest_event.isoformat() if latest_event else None,
        "latest_proxy_event_lag_hours": round((now - latest_event).total_seconds() / 3600, 2) if latest_event else None,
        "upstream_file_commit_at": None,
        "upstream_file_commit_lag_hours": None,
        "status": "unknown",
        "warning": False,
        "check_error": None,
    }

    try:
        response = requests.get(
            UPSTREAM_COMMITS_API,
            params={"path": UPSTREAM_PATH, "per_page": 1},
            headers={"User-Agent": "kyiv-air-alerts-grafana/1.0 (+public dashboard updater)"},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload:
            raise RuntimeError("GitHub commits API returned no commits for upstream CSV")
        commit_date = payload[0].get("commit", {}).get("committer", {}).get("date")
        commit_at = parse_iso(commit_date)
        if commit_at is None:
            raise RuntimeError("Could not parse upstream CSV commit timestamp")
        lag = (now - commit_at).total_seconds() / 3600
        result["upstream_file_commit_at"] = commit_at.isoformat()
        result["upstream_file_commit_lag_hours"] = round(lag, 2)
        result["status"] = "stale" if lag > WARN_AFTER_HOURS else "fresh"
        result["warning"] = lag > WARN_AFTER_HOURS
    except Exception as exc:  # QA must not break production solely because GitHub API is unavailable.
        result["check_error"] = f"{type(exc).__name__}: {exc}"
        # Conservative fallback: an event gap >72h is enough to flag uncertainty,
        # but is not described as proof that the source file itself is stale.
        event_lag = result.get("latest_proxy_event_lag_hours")
        if event_lag is not None and event_lag > 72:
            result["status"] = "unknown_event_gap"
            result["warning"] = True
    return result


def source_groups(data: dict) -> tuple[list[str], list[str], dict[str, str]]:
    meta = data.get("multicity_meta", {})
    keys = list(meta.get("production_city_keys", []))
    cities_meta = meta.get("cities", {})
    labels = {}
    exact = []
    proxy = []
    for key in keys:
        item = cities_meta.get(key, {})
        label = item.get("label") or data.get("cities", {}).get(key, {}).get("meta", {}).get("city_label") or key
        labels[key] = label
        source_type = item.get("source_type") or data.get("cities", {}).get(key, {}).get("meta", {}).get("source_type")
        if source_type == "raion_proxy":
            proxy.append(key)
        elif source_type == "exact_city":
            exact.append(key)
    return exact, proxy, labels


def add_series_style_overrides(panel: dict, exact_labels: list[str], proxy_labels: list[str]) -> None:
    field_config = panel.setdefault("fieldConfig", {})
    overrides = field_config.setdefault("overrides", [])

    # Exact-city: visually dominant solid lines.
    for label in exact_labels:
        overrides.append({
            "matcher": {"id": "byName", "options": label},
            "properties": [
                {"id": "custom.lineWidth", "value": 3},
                {"id": "custom.lineStyle", "value": {"fill": "solid"}},
            ],
        })

    # Raion proxy: thin dashed lines. Labels already contain the raion in parentheses.
    for label in proxy_labels:
        overrides.append({
            "matcher": {"id": "byName", "options": label},
            "properties": [
                {"id": "custom.lineWidth", "value": 1},
                {"id": "custom.lineStyle", "value": {"fill": "dash", "dash": [8, 6]}},
            ],
        })


def freshness_markdown(fresh: dict) -> str:
    commit_at = fresh.get("upstream_file_commit_at")
    commit_lag = fresh.get("upstream_file_commit_lag_hours")
    event_at = fresh.get("latest_proxy_event_end")
    event_lag = fresh.get("latest_proxy_event_lag_hours")

    if fresh.get("status") == "stale":
        return (
            "⚠️ **Районні дані можуть бути неповними біля правого краю графіків.** "
            f"Файл upstream востаннє оновлено **{commit_at[:10] if commit_at else 'невідомо'}** "
            f"(≈ {commit_lag:.0f} год тому). Останній завершений proxy-event у завантаженому CSV: "
            f"**{event_at[:10] if event_at else 'невідомо'}**. Не інтерпретуйте нулі після цієї дати "
            "як гарантовану відсутність тривог."
        )

    if fresh.get("status") == "unknown_event_gap":
        return (
            "⚠️ **Не вдалося надійно перевірити freshness upstream-файлу.** "
            f"Останній завершений proxy-event у завантажених даних був ≈ {event_lag:.0f} год тому. "
            "Кінцеві нулі слід трактувати обережно."
        )

    if fresh.get("check_error"):
        return "ℹ️ Не вдалося перевірити timestamp останнього commit upstream-файлу під час цього оновлення."

    return (
        f"Upstream районних даних свіжий: останній commit файлу — {commit_at[:10] if commit_at else 'невідомо'}."
    )


def insert_warning_panel(obj: dict, fresh: dict) -> None:
    if not fresh.get("warning"):
        return

    warning_id = 99001
    panels = obj.setdefault("panels", [])
    if any(p.get("id") == warning_id for p in panels):
        return

    # Reserve two rows at the very top for a warning visible before any city section.
    for panel in panels:
        grid = panel.get("gridPos")
        if isinstance(grid, dict) and isinstance(grid.get("y"), int):
            grid["y"] += 2

    panels.insert(0, {
        "id": warning_id,
        "type": "text",
        "title": "Стан джерела районних даних",
        "gridPos": {"h": 2, "w": 24, "x": 0, "y": 0},
        "options": {"mode": "markdown", "content": freshness_markdown(fresh)},
        "transparent": False,
    })


def patch_methodology(obj: dict, fresh: dict, exact_labels: list[str], proxy_labels: list[str]) -> None:
    methodology = next(
        (
            p for p in obj.get("panels", [])
            if p.get("type") == "text" and "методолог" in str(p.get("title", "")).lower()
        ),
        None,
    )
    if methodology is None:
        return
    content = methodology.setdefault("options", {}).get("content", "")
    qa_note = (
        "\n\n**Як читати порівняння.** Товсті суцільні лінії — **exact-city**; "
        "тонкі пунктирні — **районні proxy**. Районний proxy може завищувати тривалість для самого міста, "
        "тому ці ряди не слід трактувати як повністю еквівалентні географії. "
        f"Exact-city зараз: {', '.join(exact_labels)}."
        "\n\n**Freshness upstream.** " + freshness_markdown(fresh)
    )
    if "**Як читати порівняння.**" not in content:
        methodology["options"]["content"] = content + qa_note


def patch_comparison_rows(obj: dict, exact_labels: list[str], proxy_labels: list[str]) -> int:
    patched = 0
    legend_note = (
        "Товсті суцільні лінії = exact-city; тонкі пунктирні = районні proxy. "
        "Назва кожного proxy містить район у дужках. Географії не є повністю еквівалентними."
    )
    for panel in obj.get("panels", []):
        if panel.get("type") != "row":
            continue
        title = str(panel.get("title", ""))
        if not title.startswith("Порівняння міст") and not title.startswith("Порівняння рядів"):
            continue
        panel["title"] = title.replace("Порівняння міст", "Порівняння рядів")
        for child in panel.get("panels", []):
            if child.get("type") != "timeseries":
                continue
            add_series_style_overrides(child, exact_labels, proxy_labels)
            description = str(child.get("description", "")).strip()
            if legend_note not in description:
                child["description"] = (description + " " + legend_note).strip()
            patched += 1
    return patched


def validate(data: dict, obj: dict, exact: list[str], proxy: list[str], labels: dict[str, str]) -> dict:
    errors = []
    warnings = []
    keys = list(data.get("multicity_meta", {}).get("production_city_keys", []))

    if "mykolaiv" not in keys:
        errors.append("Mykolaiv missing from production_city_keys")
    if data.get("cities", {}).get("mykolaiv", {}).get("meta", {}).get("source_type") != "raion_proxy":
        errors.append("Mykolaiv is not marked raion_proxy")
    if data.get("cities", {}).get("sevastopol", {}).get("meta", {}).get("source_type") != "exact_city":
        errors.append("Sevastopol is not marked exact_city")

    for key in proxy:
        label = labels[key]
        if "район" not in label.lower() or "(" not in label:
            errors.append(f"Proxy label is not explicit: {key} -> {label}")

    if len(exact) < 4:
        errors.append(f"Expected at least 4 exact-city rows, found {len(exact)}")
    if len(proxy) < 19:
        errors.append(f"Expected at least 19 proxy rows, found {len(proxy)}")

    rendered = json.dumps(obj, ensure_ascii=False)
    for token in ("${city}", "${comparison_period}", "${duration_unit}"):
        if token in rendered:
            errors.append(f"Unsupported template token remains: {token}")

    if not any(str(p.get("title", "")).startswith("Порівняння рядів") for p in obj.get("panels", [])):
        errors.append("Comparison rows were not renamed")

    return {
        "production_rows": len(keys),
        "exact_city_rows": len(exact),
        "raion_proxy_rows": len(proxy),
        "errors": errors,
        "warnings": warnings,
        "ok": not errors,
    }


def main() -> None:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    obj = json.loads(DASHBOARD.read_text(encoding="utf-8"))

    exact, proxy, labels = source_groups(data)
    exact_labels = [labels[k] for k in exact]
    proxy_labels = [labels[k] for k in proxy]
    freshness = source_freshness(data)
    data.setdefault("multicity_meta", {})["upstream_freshness"] = freshness

    patched_comparison_panels = patch_comparison_rows(obj, exact_labels, proxy_labels)
    insert_warning_panel(obj, freshness)
    patch_methodology(obj, freshness, exact_labels, proxy_labels)

    qa = validate(data, obj, exact, proxy, labels)
    qa.update({
        "generated_at": datetime.now(UTC).isoformat(),
        "patched_comparison_panels": patched_comparison_panels,
        "exact_city_labels": exact_labels,
        "raion_proxy_labels": proxy_labels,
        "upstream_freshness": freshness,
    })

    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DASHBOARD.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    QA_FILE.write_text(json.dumps(qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(qa, ensure_ascii=False, indent=2))
    if not qa["ok"]:
        raise RuntimeError("Dashboard QA failed: " + "; ".join(qa["errors"]))


if __name__ == "__main__":
    main()
