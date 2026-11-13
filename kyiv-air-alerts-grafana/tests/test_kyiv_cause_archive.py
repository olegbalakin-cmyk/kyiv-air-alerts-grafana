"""Offline QA for immutable Kyiv cause-history preview reconstruction.
No HTTP is performed. Does not alter canonical production data.
"""
import json
from datetime import date, timedelta
from pathlib import Path

root = Path("kyiv-air-alerts-grafana")
generator = (root / "scripts/build_kyiv_threat_mix.py").read_text(encoding="utf-8")
payload = json.loads((root / "pages-preview/kyiv_threat_mix_preview.json").read_text(encoding="utf-8"))
meta = payload["meta"]
rows = payload["rows"]
assert "visible_start = first_day" in generator, "generator should not clip history"
assert "last_visible - timedelta(days=27)" not in generator
assert "source_http_performed" in meta and meta["source_http_performed"] is False
assert meta["preview_archival_proof"] is True
assert meta["visible_start"] == "2026-09-10"
assert meta["visible_end"] == "2026-11-12"
assert meta["visible_day_count"] == len(rows) == 64
assert meta["archive_provenance"]["overlap_conflicts"] == 0
assert meta["archive_provenance"]["calendar_date_gaps"] == 0
assert len(meta["archive_provenance"]["snapshots"]) == 3
assert [row["date"] for row in rows] == [
    (date(2026, 9, 10) + timedelta(days=offset)).isoformat()
    for offset in range(64)
]
for row in rows:
    assert abs(sum(row["minutes"].values()) - row["total_minutes"]) < 0.02, row["date"]
    assert abs(sum(row["shares"].values()) - (100 if row["total_minutes"] > 0 else 0)) < 0.02, row["date"]
print("PASS: 64 consecutive archived days (2026-09-10..2026-11-12), all-time retention, 0 overlap conflicts, no source HTTP")
