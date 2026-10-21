#!/usr/bin/env python3
"""Isolated pure producer regression. Do not run update_data.main()."""
import json
import sys
from pathlib import Path
from datetime import datetime, date
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from update_data import Alert, TZ, build_outputs, round3, union_daily_seconds
from apply_site_rolling_7d import add_partial_month, period_summary

def t(day, hour, minute=0, month=9):
    return datetime(2026, month, day, hour, minute, tzinfo=TZ)

events=[
    Alert(t(10,12),t(10,13),"fixture"),
    Alert(t(10,12,30),t(10,13,30),"fixture"),
    Alert(t(30,23),t(1,1,month=10),"fixture"),
    Alert(t(9,8,month=11),t(9,9,15,month=11),"fixture")
]
out=build_outputs(events,datetime(2026,12,3,tzinfo=TZ),{"city":"fixture"})
months={r["month"]:r for r in out["monthly"]}
assert months["2026-09"]["total_alert_duration_seconds"]==9000
assert months["2026-10"]["total_alert_duration_seconds"]==3600
assert months["2026-11"]["total_alert_duration_seconds"]==4500
assert months["2026-09"]["avg_daily_alert_hours"]==round3(9000/30/3600)
assert months["2026-10"]["avg_daily_alert_hours"]==round3(3600/31/3600)
assert months["2026-09"]["alerts_started"]==3
assert months["2026-10"]["alerts_started"]==0
assert json.loads(json.dumps(out))["monthly"][0]["total_alert_duration_seconds"]==9000
city={"monthly":[]}
add_partial_month(city,events,date(2026,9,9),date(2026,11,12))
current=city["monthly"][0]
assert current["month"]=="2026-11" and current["is_partial_period"] is True
assert current["total_alert_duration_seconds"]==4500
assert period_summary(events,date(2026,11,1),date(2026,11,12))["alert_seconds"]==4500
# Midnight and daylight-saving cuts must be exactly as the existing union function.
dst=[Alert(datetime(2026,10,25,2,15,tzinfo=ZoneInfo("Europe/Kyiv")),
           datetime(2026,10,25,4,15,tzinfo=ZoneInfo("Europe/Kyiv")),"fixture")]
seconds=union_daily_seconds(dst,date(2026,10,25),date(2026,10,25))[date(2026,10,25)]
assert build_outputs(dst,datetime(2026,12,3,tzinfo=TZ),{"city":"fixture"})["monthly"][0]["total_alert_duration_seconds"]==seconds
print("PASS offline producer: unrounded monthly and partial seconds; overlapping intervals; midnight; Kyiv DST; legacy averages")
