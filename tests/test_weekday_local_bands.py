"""Deterministic offline tests for exact Europe/Kyiv weekday time bands."""
import sys
import unittest
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "kyiv-air-alerts-grafana" / "scripts"))
from update_data import Alert
from build_time_of_day_heatmap import weekday_daypart_seconds

TZ = ZoneInfo("Europe/Kyiv")

def alert(y1,m1,d1,h1,n1,y2,m2,d2,h2,n2):
    return Alert(
        start=datetime(y1,m1,d1,h1,n1,tzinfo=TZ),
        end=datetime(y2,m2,d2,h2,n2,tzinfo=TZ),
        source="offline-test",
    )

class LocalBandsTests(unittest.TestCase):
    def test_cross_midnight_and_overlap_union(self):
        a=alert(2026,11,10,23,30,2026,11,11,0,30)
        r=weekday_daypart_seconds([a,a], date(2026,11,10),date(2026,11,11))
        self.assertEqual(r[date(2026,11,10)], [0,0,0,0,1800])
        self.assertEqual(r[date(2026,11,11)], [1800,0,0,0,0])

    def test_autumn_dst_25_hours(self):
        a=alert(2026,10,25,0,0,2026,10,26,0,0)
        r=weekday_daypart_seconds([a], date(2026,10,25),date(2026,10,25))
        self.assertEqual(r[date(2026,10,25)], [25200,10800,10800,21600,21600])
        self.assertEqual(sum(r[date(2026,10,25)]),90000)

    def test_spring_dst_23_hours(self):
        a=alert(2026,3,29,0,0,2026,3,30,0,0)
        r=weekday_daypart_seconds([a], date(2026,3,29),date(2026,3,29))
        self.assertEqual(r[date(2026,3,29)], [18000,10800,10800,21600,21600])
        self.assertEqual(sum(r[date(2026,3,29)]),82800)

    def test_0900_boundary_and_complement(self):
        a=alert(2026,11,17,8,30,2026,11,17,9,30)
        r=weekday_daypart_seconds([a], date(2026,11,17),date(2026,11,17))
        b=r[date(2026,11,17)]
        self.assertEqual(b,[0,1800,1800,0,0])
        self.assertEqual(b[2]+b[3],1800)
        self.assertEqual(b[0]+b[1]+b[4],1800)

if __name__ == "__main__":
    unittest.main()
