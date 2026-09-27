from datetime import datetime
import json
from pathlib import Path
import sys
import tempfile
import unittest

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import update_data as u


class Municipal404Session:
    def get(self, url, timeout=None):
        response = requests.Response()
        response.status_code = 404
        response.reason = "Not Found"
        response.url = url
        response._content = b""
        return response


class MunicipalFallbackRegressionTest(unittest.TestCase):
    def test_404_preserves_committed_history_and_builds_output(self):
        committed_rows = [
            {
                "start": "2026-09-23T10:00:00+03:00",
                "end": "2026-09-23T11:00:00+03:00",
                "source": "official_json",
            },
            {
                "start": "2026-09-24T12:00:00+03:00",
                "end": "2026-09-24T13:00:00+03:00",
                "source": "kyiv_digital_live",
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            fallback_path = Path(tmpdir) / "alerts_combined.json"
            fallback_path.write_text(
                json.dumps(committed_rows, ensure_ascii=False), encoding="utf-8"
            )

            historical, mode, warning = u.load_historical_base(
                Municipal404Session(), fallback_path
            )

        self.assertEqual(mode, "committed_alerts_combined_fallback")
        self.assertIn("404", warning or "")
        self.assertEqual(len(historical), len(committed_rows))
        self.assertEqual(
            [(a.start.isoformat(), a.end.isoformat(), a.source) for a in historical],
            [(row["start"], row["end"], row["source"]) for row in committed_rows],
        )

        live = [
            u.Alert(
                datetime(2026, 9, 24, 12, 0, tzinfo=u.TZ),
                datetime(2026, 9, 24, 13, 0, tzinfo=u.TZ),
                "kyiv_digital_live",
            ),
            u.Alert(
                datetime(2026, 9, 25, 14, 0, tzinfo=u.TZ),
                datetime(2026, 9, 25, 15, 0, tzinfo=u.TZ),
                "kyiv_digital_live",
            ),
        ]
        merged, added = u.merge_sources(historical, live)

        self.assertEqual(added, 1)
        self.assertEqual(len(merged), 3)
        self.assertEqual(
            [(a.start.isoformat(), a.end.isoformat(), a.source) for a in merged[:2]],
            [(row["start"], row["end"], row["source"]) for row in committed_rows],
        )

        output = u.build_outputs(
            merged,
            datetime(2026, 9, 27, 10, 0, tzinfo=u.TZ),
            {"historical_base_mode": mode},
        )
        self.assertEqual(output["meta"]["analysis_end"], "2026-09-26")
        self.assertEqual(output["daily28"][-1]["date"], "2026-09-26")
        self.assertEqual(len(output["daily28"]), 28)
        json.dumps(output)


if __name__ == "__main__":
    unittest.main()
