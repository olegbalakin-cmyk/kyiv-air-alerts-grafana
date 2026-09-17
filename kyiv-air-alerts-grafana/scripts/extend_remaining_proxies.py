#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import expand_multicity_production as base
from update_data import TZ, build_outputs

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "dashboard_data.json"
DASHBOARD = ROOT / "grafana" / "dashboard.json"

# These rows were initially held back because the rollout date was not documented
# externally. They are now enabled as explicitly-labelled raion proxies after:
# 1) a stable source-observed raion start, and
# 2) a verified Alerts.in.ua -> official UkraineAlarm API handoff in Sep 2026.
ADDITIONAL_PROXIES: dict[str, dict] = {
    "kherson": {
        "label": "Херсон",
        "oblast": "Херсонська область",
        "raion": "Херсонський район",
        "coverage_start": "2025-08-30",
        "coverage_basis": "source_observed_cross_source_validated",
    },
    "mykolaiv": {
        "label": "Миколаїв",
        "oblast": "Миколаївська область",
        "raion": "Миколаївський район",
        "coverage_start": "2025-11-05",
        "coverage_basis": "source_observed_cross_source_validated",
    },
    "lutsk": {
        "label": "Луцьк",
        "oblast": "Волинська область",
        "raion": "Луцький район",
        "coverage_start": "2025-11-06",
        "coverage_basis": "source_observed_cross_source_validated",
    },
    "uzhhorod": {
        "label": "Ужгород",
        "oblast": "Закарпатська область",
        "raion": "Ужгородський район",
        "coverage_start": "2025-11-06",
        "coverage_basis": "source_observed_cross_source_validated",
    },
    "ivano_frankivsk": {
        "label": "Івано-Франківськ",
        "oblast": "Івано-Франківська область",
        "raion": "Івано-Франківський район",
        "coverage_start": "2025-11-06",
        "coverage_basis": "source_observed_cross_source_validated",
    },
    "ternopil": {
        "label": "Тернопіль",
        "oblast": "Тернопільська область",
        "raion": "Тернопільський район",
        "coverage_start": "2025-11-06",
        "coverage_basis": "source_observed_cross_source_validated",
    },
    "chernivtsi": {
        "label": "Чернівці",
        "oblast": "Чернівецька область",
        "raion": "Чернівецький район",
        "coverage_start": "2025-11-06",
        "coverage_basis": "source_observed_cross_source_validated",
    },
}


def explicit_proxy_label(city: str, raion: str) -> str:
    return f"{city} ({raion})"


def configure_all_proxies() -> dict[str, dict]:
    cfg = {k: dict(v) for k, v in base.PROXY_CONFIG.items()}
    cfg.update({k: dict(v) for k, v in ADDITIONAL_PROXIES.items()})
    base.PROXY_CONFIG = cfg
    base.PROXY_KEYS = list(cfg)
    base.CITY_LABELS = {
        "kyiv": "Київ",
        "kharkiv": "Харків",
        "zaporizhzhia": "Запоріжжя",
        **{k: v["label"] for k, v in cfg.items()},
    }
    return cfg


def generic_comparison(cities: dict, keys: list[str], period: str) -> list[dict]:
    by_city = {key: {row["time"]: row for row in cities[key].get(period, [])} for key in keys}
    if not keys:
        return []
    shared = set(by_city[keys[0]])
    for key in keys[1:]:
        shared &= set(by_city[key])
    out = []
    for timestamp in sorted(shared):
        row = {"time": timestamp}
        for key in keys:
            src = by_city[key][timestamp]
            row[f"{key}_alerts_per_day"] = src.get("alerts_per_day")
            row[f"{key}_avg_daily_alert_hours"] = src.get("avg_daily_alert_hours")
            row[f"{key}_avg_alert_duration_min"] = src.get("avg_alert_duration_min")
        out.append(row)
    return out


def methodology_content(data: dict, all_proxy_cfg: dict[str, dict]) -> str:
    official = []
    observed = []
    for key, cfg in all_proxy_cfg.items():
        line = f"- **{cfg['label']}** -> `{cfg['raion']}`; coverage з {cfg['coverage_start']}."
        if cfg.get("coverage_basis") == "source_observed_cross_source_validated":
            observed.append(line)
        else:
            official.append(line)

    return (
        "**Географія та джерела.** Київ використовує міські відкриті дані та Kyiv Digital fallback. "
        "Харків і Запоріжжя мають exact-city ряди. Решта показаних обласних центрів, окрім Севастополя, "
        "позначені як **районні proxy**: використовується однойменний район, а не exact-city ряд.  \n\n"
        "**Proxy з документованою датою районного rollout:**  \n"
        + "\n".join(official)
        + "  \n\n"
        "**Додаткові proxy з source-observed стартом.** Для цих міст дата початку взята з появи стабільного "
        "районного ряду в historical source. Їхній перехід через розрив upstream окремо перевірено по конкретних "
        "подіях `Alerts.in.ua -> UkraineAlarm API` (допуск cross-source timestamp до 15 секунд):  \n"
        + "\n".join(observed)
        + "  \n\n"
        "**Донецьк і Луганськ** поки не показуються: для них потрібна окрема методологія, і область не підміняється містом.  \n\n"
        "**Агрегація.** Для proxy перекривні районні та explicit `oblast` інтервали historical source зливаються "
        "в єдині alert episodes. Перший неповний місяць і тиждень після coverage-start виключаються. "
        "Тривоги через північ розподіляються між календарними добами в Europe/Kyiv. Поточний календарний день "
        "не входить до завершених денних агрегатів. Порівняння міст використовує лише спільні повні періоди.  \n\n"
        "Пропозиції надсилати @olbalakin в телеграм"
    )


def main() -> None:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    cities = data.setdefault("cities", {})
    mm = data.setdefault("multicity_meta", {})

    all_proxy_cfg = configure_all_proxies()
    proxy_alerts = base.fetch_proxy_alerts()
    now_local = datetime.now(TZ)

    for key, cfg in ADDITIONAL_PROXIES.items():
        alerts = proxy_alerts[key]
        coverage_day = date.fromisoformat(cfg["coverage_start"])
        meta = {
            "city": key,
            "city_label": cfg["label"],
            "source_type": "raion_proxy",
            "proxy_raion": cfg["raion"],
            "oblast": cfg["oblast"],
            "coverage_start": cfg["coverage_start"],
            "coverage_start_basis": cfg["coverage_basis"],
            "city_source_url": base.CITY_SOURCE_URL,
            "proxy_completed_alert_episodes": len(alerts),
            "first_proxy_record": min(a.start for a in alerts).isoformat(),
            "latest_proxy_record_start": max(a.start for a in alerts).isoformat(),
            "latest_proxy_record_end": max(a.end for a in alerts).isoformat(),
            "data_source_kind": (
                "eponymous raion proxy union explicit oblast; source-observed start, "
                "cross-source handoff validated"
            ),
        }
        output = build_outputs(alerts, now_local, meta)
        base.enrich_weekly(output, alerts)
        base.trim_to_complete_coverage(output, coverage_day)
        cities[key] = output

    keys = list(mm.get("production_city_keys", []))
    for key in ADDITIONAL_PROXIES:
        if key not in keys:
            keys.append(key)
    mm["production_city_keys"] = keys
    mm.setdefault("cities", {})
    for key in ADDITIONAL_PROXIES:
        meta = cities[key]["meta"]
        mm["cities"][key] = {
            "label": meta["city_label"],
            "source_type": meta["source_type"],
            "coverage_start": meta["coverage_start"],
            "coverage_start_basis": meta["coverage_start_basis"],
            "first_complete_month": meta.get("first_complete_month"),
            "first_complete_week_start": meta.get("first_complete_week_start"),
            "proxy_raion": meta["proxy_raion"],
        }

    mm["deferred"] = {
        "donetsk": "requires separate methodology",
        "luhansk": "requires separate methodology",
    }
    mm["proxy_cross_source_match_tolerance_seconds"] = 15

    data["comparison"] = {
        "monthly": generic_comparison(cities, keys, "monthly"),
        "weekly": generic_comparison(cities, keys, "weekly"),
    }
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    obj = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    panel = next((p for p in obj.get("panels", []) if p.get("id") == 30), None)
    if panel:
        panel["title"] = "Джерела та методологія"
        panel.setdefault("options", {})["mode"] = "markdown"
        panel["options"]["content"] = methodology_content(data, all_proxy_cfg)
    DASHBOARD.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("Enabled additional proxy rows:", ", ".join(ADDITIONAL_PROXIES))
    print("Production rows before Sevastopol:", len(keys))
    print("Monthly shared comparison starts:", data["comparison"]["monthly"][0]["time"] if data["comparison"]["monthly"] else None)
    print("Weekly shared comparison starts:", data["comparison"]["weekly"][0]["time"] if data["comparison"]["weekly"] else None)


if __name__ == "__main__":
    main()
