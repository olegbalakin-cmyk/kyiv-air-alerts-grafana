#!/usr/bin/env python3
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_time_of_day_heatmap import build_exploration_city
from update_data import Alert

TZ = ZoneInfo("Europe/Kyiv")

def stamp(d, h, m):
    return datetime(d.year, d.month, d.day, h, m, tzinfo=TZ)

def verify(d, spans, day, night):
    alerts = [Alert(start=stamp(d,*s), end=stamp(d,*e), source="test") for s,e in spans]
    city = build_exploration_city(alerts,d,d,label="test",source_type="city")
    assert len(city["monthly"]) == 1
    row = city["monthly"][0]
    minutes = row["time_day_night_minutes"]
    assert abs(minutes["day"] - day) < 0.02, (d,minutes)
    assert abs(minutes["evening_night"] - night) < 0.02, (d,minutes)
    assert abs(sum(minutes.values()) - row["alert_hours"]*60) < 0.05, (d,row)
    assert abs(sum(minutes.values()) - sum(row["time_band_minutes"].values())) < 0.06, (d,row)
    assert abs(sum(row["time_day_night_shares"].values()) - 100) < 0.005
    return row

winter = date(2026,1,15)
row = verify(winter, [((8,30),(9,30)),((17,30),(18,30)),((21,0),(22,30))],60,150)
assert row["time_band_minutes"]["06_12"] == 60.0, row
verify(date(2026,3,29), [((1,30),(9,30))],30,390)  # 1 lost hour at spring DST
verify(date(2026,10,25), [((2,30),(9,30))],30,450) # 1 repeated hour at autumn DST
empty = build_exploration_city([],winter,winter,label="empty",source_type="city")["monthly"][0]
assert empty["time_day_night_shares"] == {"day":0.0,"evening_night":0.0}
assert empty["time_day_night_minutes"] == {"day":0.0,"evening_night":0.0}
print("PASS: exact local 09-18/18-09 boundaries, DST spring/fall, zero days")
