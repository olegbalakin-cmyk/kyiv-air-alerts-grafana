#!/usr/bin/env python3
"""Read-only, reproducible rolling-origin Holt-damped vs EWMA backtest.

Pinned site-prod Git JSON inputs. Targets: daily alerts_started and union alert
hours/day; complete calendar weeks/months only. No model sees future test rows.
"""
import argparse
import calendar
import hashlib
import itertools
import json
import math
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ALPHA_EWMA = 0.3
GRID = list(itertools.product((0.2, 0.4, 0.6), (0.1, 0.2, 0.4), (0.8, 0.9, 0.98)))
MIN = {"daily": 21, "weekly": 8, "monthly": 6}
METRICS = ("alerts", "hours")
PERIODS = ("daily", "weekly", "monthly")


def ewma(values, alpha=ALPHA_EWMA):
    result = values[0]
    for y in values[1:]:
        result = alpha * y + (1.0 - alpha) * result
    return [result, result]


def holt(values, alpha, beta, phi):
    # Damped additive trend. Explicit initialization, no external statistics.
    level = values[0]
    n0 = min(7, len(values) - 1)
    trend = (values[n0] - values[0]) / n0 if n0 else 0.0
    for y in values[1:]:
        previous = level
        level = alpha * y + (1 - alpha) * (previous + phi * trend)
        trend = beta * (level - previous) + (1 - beta) * phi * trend
    return [level + phi * trend, level + (phi + phi * phi) * trend]


def bounded(value, metric):
    # Hours per calendar day physically cannot exceed 24; count cannot be negative.
    return max(0.0, min(24.0, value)) if metric == "hours" else max(0.0, value)


def daily_series(root, city):
    h = root["historical_daily_kpi"]["cities"][city]
    start = date.fromisoformat(h["start"][:10])
    counts = h["counts"]
    seconds = h["daily_total_alert_duration_seconds"]
    assert len(counts) == len(seconds) and len(counts) >= 28, city
    dates = [start + timedelta(days=i) for i in range(len(counts))]
    if h["end"][:10] != dates[-1].isoformat():
        raise AssertionError((city, "daily calendar alignment", h["start"], h["end"], dates[-1]))
    rows = []
    for day, n, seconds_value in zip(dates, counts, seconds):
        if not isinstance(n, (int, float)) or not isinstance(seconds_value, (int, float)):
            raise AssertionError((city, day, "missing numeric metric"))
        if not math.isfinite(n) or n < 0 or not math.isfinite(seconds_value) or seconds_value < 0:
            raise AssertionError((city, day, "invalid numeric metric"))
        rows.append({"key": day.isoformat(), "alerts": float(n), "hours": float(seconds_value) / 3600.0})
    return rows


def weekly_series(daily):
    groups = defaultdict(list)
    for r in daily:
        day = date.fromisoformat(r["key"])
        start = day - timedelta(days=day.weekday())
        groups[start.isoformat()].append(r)
    out = []
    for key, rows in sorted(groups.items()):
        if len(rows) != 7:
            continue
        if [r["key"] for r in rows] != [(date.fromisoformat(key) + timedelta(days=i)).isoformat() for i in range(7)]:
            continue
        out.append({"key": key, "alerts": sum(r["alerts"] for r in rows) / 7,
                    "hours": sum(r["hours"] for r in rows) / 7})
    return out


def monthly_series(root, city):
    verified = set(root["historical_daily_kpi"]["cities"][city]["verified_metric_months"])
    out = []
    for r in root["cities"][city]["monthly"]:
        month = r.get("month")
        if not month or r.get("is_partial_period") or month not in verified:
            continue
        out.append({"key": month, "alerts": float(r["alerts_per_day"]), "hours": float(r["avg_daily_alert_hours"])})
    assert len({r["key"] for r in out}) == len(out), city
    return sorted(out, key=lambda r:r["key"])


def boundaries(n, period):
    # Tuning on 60%-80%; strict final holdout on last 20%.
    valid_begin = max(MIN[period], int(0.6*n))
    test_begin = max(valid_begin+2, int(0.8*n))
    if n-test_begin < 3:
        return None
    return valid_begin, test_begin


def origins(n, period, split):
    b = boundaries(n, period)
    if not b:
        return []
    v, t = b
    return range(v, min(t, n-2)) if split == "val" else range(t, n-2)


def scores(data, period, metric, split, model, params=None):
    by_city = {}
    for city, rows in data.items():
        values = [r[metric] for r in rows[period]]
        if not values:
            continue
        errors = {1: [], 2: []}
        for origin in origins(len(values), period, split):
            history = values[:origin]
            p = ewma(history) if model == "EWMA" else holt(history, *params)
            for h in (1,2):
                pred = bounded(p[h-1], metric)
                err = abs(pred - values[origin+h-1])
                errors[h].append(err)
        if errors[1] and errors[2]:
            by_city[city] = {h:sum(errors[h])/len(errors[h]) for h in (1,2)}
    # Same weight per city prevents long Kyiv history from dominating.
    avg = {h:sum(row[h] for row in by_city.values())/len(by_city) for h in (1,2)} if by_city else {}
    return {"mae":avg, "by_city":by_city, "n_cities":len(by_city),
            "n_origins":sum(len(origins(len(rows[period]),period,split)) for rows in data.values())}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--dashboard",required=True)
    p.add_argument("--output",required=True)
    args=p.parse_args()
    raw=Path(args.dashboard).read_bytes()
    root=json.loads(raw)
    cities=root["multicity_meta"]["production_city_keys"]
    assert len(cities)==23, len(cities)
    data={}
    for city in cities:
        daily=daily_series(root,city)
        data[city]={"daily":daily,"weekly":weekly_series(daily),"monthly":monthly_series(root,city)}
    comparisons=[]
    for period in PERIODS:
        for metric in METRICS:
            baseline_val=scores(data,period,metric,"val","EWMA")
            baseline_test=scores(data,period,metric,"test","EWMA")
            ranked=[]
            for params in GRID:
                s=scores(data,period,metric,"val","HOLT",params)
                if s["n_cities"] != baseline_val["n_cities"] or not s["n_cities"]:
                    continue
                ranked.append((sum(s["mae"].values()),params,s))
            if not ranked:
                comparisons.append({"period":period,"metric":metric,"status":"INSUFFICIENT_VALIDATION","ewma_test":baseline_test})
                continue
            _,params,best_validation=min(ranked,key=lambda x:x[0])
            test=scores(data,period,metric,"test","HOLT",params)
            hresults={}
            for h in (1,2):
                reference=baseline_test["mae"].get(h)
                candidate=test["mae"].get(h)
                hresults[str(h)] = {
                    "ewma_mae":round(reference,6) if reference is not None else None,
                    "holt_mae":round(candidate,6) if candidate is not None else None,
                    "holt_vs_ewma_pct":round(100*(candidate/reference-1),2) if reference else None,
                    "holt_city_wins":sum(test["by_city"][city][h] < baseline_test["by_city"][city][h] for city in test["by_city"]),
                    "holt_city_losses":sum(test["by_city"][city][h] > baseline_test["by_city"][city][h] for city in test["by_city"])
                }
            comparisons.append({"period":period,"metric":metric,"status":"COMPARED",
                                "validation_cities":baseline_val["n_cities"],
                                "test_cities":test["n_cities"],
                                "test_origins":test["n_origins"],
                                "params":{"alpha":params[0],"beta":params[1],"phi":params[2]},
                                "validation_ewma_mae":baseline_val["mae"],
                                "validation_holt_mae":best_validation["mae"],
                                "horizons":hresults})
    result={"schema":"forecast-holt-damped-research-v1",
            "source_sha256":hashlib.sha256(raw).hexdigest(),
            "city_count":len(cities),
            "series_lengths":{k:{p:len(data[k][p]) for p in PERIODS} for k in cities},
            "notes":["Read-only site-prod snapshot; exact full local calendar months verified by source.",
                     "Daily counts and union alert seconds from historical_daily_kpi, weeks grouped Mon-Sun, monthly from published complete rows.",
                     "Equal city weighting, chronological per-city 60%-80% parameter validation, final 20% untouched testing.",
                     "All values on per-day scales. Positive percentage means Holt is worse.",
                     "Two-step forecasts use the same origin; no actual +1 observation is revealed to +2.",
                     "No assumption that a smooth trend predicts future attacks."],
            "grid_size":len(GRID),"comparisons":comparisons}
    Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("RESULT_SHA",result["source_sha256"],"CITY_COUNT",result["city_count"],"GRID",result["grid_size"])
    for row in comparisons:
        if row["status"]=="COMPARED":
            print("RESULT",row["period"],row["metric"],"city_count",row["test_cities"],
                  "n_origins",row["test_origins"],"params",row["params"],
                  "h1",row["horizons"]["1"],"h2",row["horizons"]["2"])
        else:
            print("RESULT",row["period"],row["metric"],row["status"])
    assert all(x["status"]=="COMPARED" and x["test_cities"]==23 for x in comparisons), "Not enough verified observations for complete 23-city backtest"

if __name__=="__main__":
    main()
