#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PREVIEW_INPUT = DATA / "explosion_preview_input.json"
BASELINE_FILE = DATA / "explosion_audited_baseline.json"
SEED_FILE = DATA / "explosion_daily_alert_seed.json"
DEFAULT_CITY_DIR = DATA / "grafana" / "cities"
ROLLING_DAYS = 90
SEED_DAYS = 120


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, obj: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def add_days(value: str, days: int) -> str:
    d = date.fromisoformat(value) + timedelta(days=days)
    return d.isoformat()


def reconstruct_daily(city_feed: dict, coverage_start: str, coverage_end: str, alerts_total: int) -> dict[str, int]:
    weekly = {
        str(row["week_end"]): int(row.get("alerts_started") or 0)
        for row in city_feed.get("weekly") or []
        if row.get("week_end")
    }
    daily = {
        str(row["date"]): int(row.get("alerts_started") or 0)
        for row in city_feed.get("daily28") or []
        if row.get("date")
    }
    ends = sorted(weekly)
    if len(ends) < 2 or not daily:
        raise RuntimeError("city feed lacks weekly/daily28 anchors")

    changed = True
    while changed:
        changed = False
        for i in range(len(ends) - 1, 0, -1):
            t = ends[i]
            prev = ends[i - 1]
            if date.fromisoformat(prev) + timedelta(days=1) != date.fromisoformat(t):
                continue
            prev7 = add_days(t, -7)
            if t in daily and prev7 not in daily:
                value = weekly[prev] - weekly[t] + daily[t]
                if value < 0 or int(value) != value:
                    raise RuntimeError(f"invalid reconstructed daily count {prev7}={value}")
                daily[prev7] = int(value)
                changed = True

    start = date.fromisoformat(coverage_start)
    end = date.fromisoformat(coverage_end)
    if end < start:
        raise RuntimeError("coverage_end before coverage_start")

    after_start = 0
    d = start + timedelta(days=1)
    while d <= end:
        key = d.isoformat()
        if key not in daily:
            raise RuntimeError(f"missing reconstructed denominator day {key}")
        after_start += daily[key]
        d += timedelta(days=1)

    residual = int(alerts_total) - after_start
    if residual < 0:
        raise RuntimeError(
            f"coverage_start residual negative: total={alerts_total}, after_start={after_start}"
        )
    daily[coverage_start] = residual

    check = 0
    d = start
    while d <= end:
        key = d.isoformat()
        if key not in daily:
            raise RuntimeError(f"missing denominator day {key}")
        check += int(daily[key])
        d += timedelta(days=1)
    if check != int(alerts_total):
        raise RuntimeError(f"denominator mismatch: reconstructed={check}, expected={alerts_total}")
    return daily


def strict_daily_from_input(city: dict) -> dict[str, int]:
    dates = [str(x) for x in city.get("strict_episode_start_dates") or []]
    strict = int(city.get("strict") or 0)
    if strict == 0 and not dates:
        return {}
    if len(dates) != strict:
        raise RuntimeError(
            f"strict episode dates missing/incomplete: strict={strict}, dated episodes={len(dates)}"
        )
    for value in dates:
        date.fromisoformat(value)
    return dict(sorted(Counter(dates).items()))


def build_rolling(
    daily_alerts: dict[str, int],
    strict_daily: dict[str, int],
    coverage_start: str,
    coverage_end: str,
) -> list[dict]:
    start = date.fromisoformat(coverage_start) + timedelta(days=ROLLING_DAYS - 1)
    end = date.fromisoformat(coverage_end)
    out = []
    d = start
    while d <= end:
        window = [(d - timedelta(days=i)).isoformat() for i in range(ROLLING_DAYS)]
        if not all(day in daily_alerts for day in window):
            raise RuntimeError(f"rolling denominator incomplete at {d.isoformat()}")
        alerts_n = sum(int(daily_alerts[day]) for day in window)
        strict_n = sum(int(strict_daily.get(day, 0)) for day in window)
        out.append(
            {
                "date": d.isoformat(),
                "strict_n": strict_n,
                "alerts_n": alerts_n,
                "pct": round(strict_n / alerts_n * 100, 2) if alerts_n else None,
            }
        )
        d += timedelta(days=1)
    return out


def seed_slice(daily_alerts: dict[str, int], coverage_start: str, coverage_end: str) -> dict[str, int]:
    start = max(
        date.fromisoformat(coverage_start),
        date.fromisoformat(coverage_end) - timedelta(days=SEED_DAYS - 1),
    )
    end = date.fromisoformat(coverage_end)
    out = {}
    d = start
    while d <= end:
        key = d.isoformat()
        if key not in daily_alerts:
            raise RuntimeError(f"seed missing day {key}")
        out[key] = int(daily_alerts[key])
        d += timedelta(days=1)
    return out


def baseline_city_from_preview(city: dict, daily_alerts: dict[str, int]) -> dict:
    coverage_start = str(city["coverage_start"])
    coverage_end = str(city["coverage_end"])
    strict_daily = strict_daily_from_input(city)
    strict = int(city.get("strict") or 0)
    total = int(city.get("alerts_total") or 0)
    sensitivity = int(city.get("sensitivity") or strict)

    return {
        "label": str(city.get("label") or ""),
        "coverage_start": coverage_start,
        "coverage_end": coverage_end,
        "total_alerts": total,
        "strict_n": strict,
        "strict_pct": round(strict / total * 100, 2) if total else 0,
        "sensitivity_n": sensitivity,
        "sensitivity_pct": round(sensitivity / total * 100, 2) if total else 0,
        "strict_daily": strict_daily,
        "rolling90": build_rolling(daily_alerts, strict_daily, coverage_start, coverage_end),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--city-data-dir", type=Path, default=DEFAULT_CITY_DIR)
    parser.add_argument("--dashboard-data", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        assert add_days("2026-09-17", 1) == "2026-09-18"
        assert strict_daily_from_input({"strict": 2, "strict_episode_start_dates": ["2026-09-01", "2026-09-01"]}) == {"2026-09-01": 2}
        print("Self-test OK")
        return

    preview = load_json(PREVIEW_INPUT)
    baseline = load_json(BASELINE_FILE)
    seed = load_json(SEED_FILE)
    dashboard = load_json(args.dashboard_data) if args.dashboard_data else {}

    def get_city_feed(city_key: str) -> dict:
        dashboard_cities = dashboard.get("cities") if isinstance(dashboard, dict) else {}
        if isinstance(dashboard_cities, dict):
            row = dashboard_cities.get(city_key) or dashboard_cities.get(city_key.replace("_", "-"))
            if isinstance(row, dict) and row.get("weekly") and row.get("daily28"):
                return row
        feed_path = args.city_data_dir / f"{city_key}.json"
        if feed_path.exists():
            return load_json(feed_path)
        raise RuntimeError(
            f"{city_key}: no production city feed in dashboard_data or {feed_path}"
        )

    preview_cities = preview.get("cities") or {}
    baseline_cities = baseline.setdefault("cities", {})
    seed_cities = seed.setdefault("cities", {})

    added = []
    seeded = []
    skipped = []

    for key, city in preview_cities.items():
        if key not in baseline_cities:
            strict = int(city.get("strict") or 0)
            dated = city.get("strict_episode_start_dates") or []
            if strict and len(dated) != strict:
                skipped.append(
                    {
                        "city_key": key,
                        "reason": "missing_strict_episode_start_dates",
                        "strict": strict,
                        "dated": len(dated),
                    }
                )
                continue

            try:
                feed = get_city_feed(key)
            except RuntimeError as exc:
                skipped.append({"city_key": key, "reason": str(exc)})
                continue
            daily = reconstruct_daily(
                feed,
                str(city["coverage_start"]),
                str(city["coverage_end"]),
                int(city["alerts_total"]),
            )
            baseline_cities[key] = baseline_city_from_preview(city, daily)
            added.append(key)

        if key not in seed_cities and key in baseline_cities:
            base = baseline_cities[key]
            daily = reconstruct_daily(
                get_city_feed(key),
                str(base["coverage_start"]),
                str(base["coverage_end"]),
                int(base["total_alerts"]),
            )
            sliced = seed_slice(daily, str(base["coverage_start"]), str(base["coverage_end"]))
            seed_cities[key] = {
                "label": base.get("label") or key,
                "coverage_start": base["coverage_start"],
                "baseline_total_alerts": int(base["total_alerts"]),
                "daily_alerts": sliced,
                "seed_total_alerts": sum(sliced.values()),
            }
            seeded.append(key)

    baseline.setdefault("meta", {})
    baseline["meta"].update(
        {
            "canonical_audited_baseline": True,
            "auto_expand_from": PREVIEW_INPUT.name,
            "city_count": len(baseline_cities),
        }
    )
    seed["schema_version"] = 1
    seed["generated_from"] = "audited explosion baseline + production city rolling/daily series"
    seed["days"] = SEED_DAYS
    seed["city_count"] = len(seed_cities)

    atomic_json(BASELINE_FILE, baseline)
    atomic_json(SEED_FILE, seed)

    report = {
        "baseline_city_count": len(baseline_cities),
        "seed_city_count": len(seed_cities),
        "added_baseline_cities": added,
        "added_seed_cities": seeded,
        "skipped": skipped,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if skipped:
        raise RuntimeError(
            "One or more audited cities could not be auto-onboarded; "
            "complete their dated strict episodes / city feed first."
        )


if __name__ == "__main__":
    main()
