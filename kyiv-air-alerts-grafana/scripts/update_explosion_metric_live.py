#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
BASELINE_FILE = DATA_DIR / "explosion_audited_baseline.json"
SEED_FILE = DATA_DIR / "explosion_daily_alert_seed.json"
STATE_FILE = DATA_DIR / "explosion_candidate_monitor_state.json"
QUEUE_FILE = DATA_DIR / "explosion_review_queue.json"
LAST_RUN_FILE = DATA_DIR / "explosion_candidate_monitor_last_run.json"
OUTPUT_FILE = DATA_DIR / "explosions_test.json"
DASHBOARD_FILE = DATA_DIR / "dashboard_data.json"

KYIV_TZ = ZoneInfo("Europe/Kyiv")
UTC = timezone.utc
ROLLING_DAYS = 90
APPROVED_STRICT = "approved_strict"
APPROVED_SENSITIVITY = "approved_sensitivity"


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def atomic_json(path: Path, obj) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def pct(n: int, d: int) -> float | None:
    return round(n / d * 100, 2) if d else None


def episode_index(state: dict) -> dict[str, dict]:
    out = {}
    for cstate in (state.get("cities") or {}).values():
        for ep in cstate.get("episodes", []):
            eid = str(ep.get("episode_id") or "")
            if eid:
                out[eid] = ep
    return out


def approval_sets(queue: list[dict], city_key: str, ep_index: dict[str, dict], latest_complete: date):
    strict_ids: set[str] = set()
    sensitivity_ids: set[str] = set()
    review_errors = []
    for item in queue:
        if not isinstance(item, dict) or item.get("city_key") != city_key:
            continue
        status = item.get("status")
        if status not in {APPROVED_STRICT, APPROVED_SENSITIVITY}:
            continue
        eid = str(item.get("matched_episode_id") or "")
        ep = ep_index.get(eid)
        if not eid or not ep:
            review_errors.append({"candidate_id": item.get("candidate_id"), "error": "approved_without_resolvable_matched_episode_id"})
            continue
        start = parse_dt(ep.get("alert_start"))
        if not start:
            review_errors.append({"candidate_id": item.get("candidate_id"), "error": "matched_episode_missing_start"})
            continue
        start_day = start.astimezone(KYIV_TZ).date()
        if start_day > latest_complete:
            continue
        sensitivity_ids.add(eid)
        if status == APPROVED_STRICT:
            strict_ids.add(eid)
    return strict_ids, sensitivity_ids, review_errors


def self_test() -> None:
    assert pct(1, 3) == 33.33
    assert list(daterange(date(2026, 9, 17), date(2026, 9, 18))) == [date(2026, 9, 17), date(2026, 9, 18)]
    print("Self-test OK: percentages and date windows")


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild the live test explosion metric from the frozen baseline, new alert episodes, and manually approved review items.")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return

    baseline = load_json(BASELINE_FILE, {})
    seed = load_json(SEED_FILE, {})
    state = load_json(STATE_FILE, {"cities": {}})
    queue = load_json(QUEUE_FILE, [])
    last_run = load_json(LAST_RUN_FILE, {})
    if not isinstance(queue, list):
        queue = []

    cities = baseline.get("cities") or {}
    seed_cities = seed.get("cities") or {}
    if set(cities) != set(seed_cities):
        raise RuntimeError(f"Seed/baseline city mismatch: {sorted(cities)} vs {sorted(seed_cities)}")

    now_local = datetime.now(KYIV_TZ)
    latest_complete = now_local.date() - timedelta(days=1)
    ep_index = episode_index(state)
    out = {
        "meta": {
            "schema_version": 2,
            "snapshot_date": now_local.date().isoformat(),
            "updated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "metric": "strict confirmed public reports of explosions matched to production alert episodes",
            "rolling_window_days": ROLLING_DAYS,
            "rolling_rule": "sum(strict matched alert episodes) / sum(all tracked alert episodes) over 90 completed calendar days; full windows only",
            "test_only": True,
            "production_data_pipeline_changed": False,
            "automation": {
                "denominator": "automatic_after_completed_alert_episode",
                "candidate_discovery": "automatic_alert_triggered_telegram_and_google_news",
                "strict_promotion": "auto_only_if_unambiguous_otherwise_manual_review",
                "auto_strict_rule": "exact city + air context + explicit during-alert wording + immediate candidate published inside unique alert window (+30m grace)",
                "followups": ["immediate", "24h", "72h", "7d"],
                "last_monitor_run_at": last_run.get("started_at"),
            },
            "city_count": len(cities),
        },
        "cities": {},
    }
    all_review_errors = []

    for city_key, base in cities.items():
        base_end = date.fromisoformat(base["coverage_end"])
        cstate = (state.get("cities") or {}).get(city_key) or {}
        last_success = parse_dt(cstate.get("last_successful_poll_at"))
        safe_complete = (last_success.astimezone(KYIV_TZ).date() - timedelta(days=1)) if last_success else base_end
        effective_end = max(base_end, min(latest_complete, safe_complete))
        daily = {date.fromisoformat(k): int(v) for k, v in (seed_cities[city_key].get("daily_alerts") or {}).items()}
        for d in daterange(base_end + timedelta(days=1), effective_end):
            daily.setdefault(d, 0)

        seen_episode_ids = set()
        new_episode_days = Counter()
        for ep in (state.get("cities", {}).get(city_key, {}).get("episodes") or []):
            eid = str(ep.get("episode_id") or "")
            if not eid or eid in seen_episode_ids:
                continue
            seen_episode_ids.add(eid)
            start = parse_dt(ep.get("alert_start"))
            if not start:
                continue
            d = start.astimezone(KYIV_TZ).date()
            if base_end < d <= effective_end:
                new_episode_days[d] += 1
        for d, n in new_episode_days.items():
            daily[d] = n

        strict_ids, sensitivity_ids, review_errors = approval_sets(queue, city_key, ep_index, effective_end)
        all_review_errors.extend({"city_key": city_key, **e} for e in review_errors)

        strict_daily = Counter({date.fromisoformat(k): int(v) for k, v in (base.get("strict_daily") or {}).items()})
        for eid in strict_ids:
            start = parse_dt(ep_index[eid].get("alert_start"))
            if start:
                strict_daily[start.astimezone(KYIV_TZ).date()] += 1

        new_alerts = sum(n for d, n in daily.items() if base_end < d <= effective_end)
        total_alerts = int(base["total_alerts"]) + new_alerts
        strict_n = int(base["strict_n"]) + len(strict_ids)
        sensitivity_n = int(base["sensitivity_n"]) + len(sensitivity_ids)

        rolling = list(base.get("rolling90") or [])
        for end_day in daterange(base_end + timedelta(days=1), effective_end):
            start_day = end_day - timedelta(days=ROLLING_DAYS - 1)
            missing = [d for d in daterange(start_day, end_day) if d not in daily]
            if missing:
                raise RuntimeError(f"{city_key}: missing daily denominator for rolling window {start_day}..{end_day}; first missing {missing[0]}")
            alerts_n = sum(daily[d] for d in daterange(start_day, end_day))
            strict_window = sum(strict_daily.get(d, 0) for d in daterange(start_day, end_day))
            rolling.append({
                "date": end_day.isoformat(),
                "strict_n": strict_window,
                "alerts_n": alerts_n,
                "pct": pct(strict_window, alerts_n),
            })

        pending = sum(1 for item in queue if isinstance(item, dict) and item.get("city_key") == city_key and item.get("status") == "needs_review")
        out["cities"][city_key] = {
            "label": base["label"],
            "coverage_start": base["coverage_start"],
            "coverage_end": effective_end.isoformat(),
            "baseline_coverage_end": base["coverage_end"],
            "total_alerts": total_alerts,
            "strict_n": strict_n,
            "strict_pct": pct(strict_n, total_alerts),
            "sensitivity_n": sensitivity_n,
            "sensitivity_pct": pct(sensitivity_n, total_alerts),
            "strict_daily": {d.isoformat(): strict_daily[d] for d in sorted(strict_daily)},
            "rolling90": rolling,
            "automation": {
                "new_alert_episodes_since_baseline": new_alerts,
                "approved_strict_episodes_since_baseline": len(strict_ids),
                "approved_sensitivity_episodes_since_baseline": len(sensitivity_ids),
                "pending_review_candidates": pending,
                "last_successful_poll_at": cstate.get("last_successful_poll_at"),
            },
        }

    out["meta"]["review_errors"] = all_review_errors
    out["meta"]["review_queue_size"] = len(queue)
    atomic_json(OUTPUT_FILE, out)

    dashboard = load_json(DASHBOARD_FILE, {})
    if not isinstance(dashboard, dict) or not dashboard:
        raise RuntimeError("dashboard_data.json is missing or invalid")
    dashboard["explosion_metric_test"] = out
    atomic_json(DASHBOARD_FILE, dashboard)

    print(json.dumps({
        "ok": not all_review_errors,
        "coverage_end": latest_complete.isoformat(),
        "city_count": len(out["cities"]),
        "review_queue_size": len(queue),
        "review_errors": all_review_errors,
        "totals": {k: {"alerts": v["total_alerts"], "strict": v["strict_n"], "pct": v["strict_pct"]} for k, v in out["cities"].items()},
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
