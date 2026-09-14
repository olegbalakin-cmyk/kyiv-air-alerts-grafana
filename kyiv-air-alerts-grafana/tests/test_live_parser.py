from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import update_data as u


def test_live_parser_cross_midnight():
    html = """
    <table>
      <tr><td>00:12 10.09.26</td><td>🟢 Відбій тривоги</td><td>48 хвилин</td></tr>
      <tr><td>23:23 09.09.26</td><td>🔴 Повітряна тривога!</td><td></td></tr>
    </table>
    """
    alerts, events = u.parse_live_history(html)
    assert len(events) == 2
    assert len(alerts) == 1
    assert alerts[0].start.strftime("%Y-%m-%d %H:%M") == "2026-09-09 23:23"
    assert alerts[0].end.strftime("%Y-%m-%d %H:%M") == "2026-09-10 00:12"
    assert round(alerts[0].duration_seconds / 60) == 49


def test_overlap_is_not_double_counted():
    z = u.TZ
    alerts = [
        u.Alert(datetime(2026, 9, 1, 10, 0, tzinfo=z), datetime(2026, 9, 1, 12, 0, tzinfo=z), "x"),
        u.Alert(datetime(2026, 9, 1, 11, 0, tzinfo=z), datetime(2026, 9, 1, 13, 0, tzinfo=z), "y"),
    ]
    got = u.union_daily_seconds(alerts, datetime(2026, 9, 1).date(), datetime(2026, 9, 1).date())
    assert round(got[datetime(2026, 9, 1).date()] / 3600, 6) == 3.0
