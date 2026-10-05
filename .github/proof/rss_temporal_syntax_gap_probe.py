#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "kyiv-air-alerts-grafana"
sys.path.insert(0, str(APP / "scripts"))
import monitor_explosion_candidates as mon

SOURCE_SHA = "5ebd77a7a1066fa4a2dabe62c98ee5c6b30d60c817282d560e8908f482ff8ef8"
TARGETS = {
    "f958519cfda65d5cd8eb81e5": ("kropyvnytskyi", "2026-09-24T10:37:00"),
    "ecf26b3980c9dcac8234f689": ("kyiv", "2026-10-03T22:30:00"),
    "383e064c794bece60e20d4ca": ("sumy", "2026-09-27T15:00:00"),
    "5b93c789ce785522030a51f4": ("sumy", "2026-10-04T08:00:00"),
    "ccc799cf4b6706daac05f35e": ("sumy", "2026-10-04T08:00:00"),
    "130a62ecc060e529737c7326": ("sumy", "2026-10-04T14:00:00"),
    "7b99452890d6b851455983af": ("sumy", "2026-10-04T14:00:00"),
}

def main() -> None:
    source = Path(sys.argv[1])
    out = Path(sys.argv[2])
    raw = source.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SOURCE_SHA
    doc = json.loads(raw)
    ledger = doc["candidate_level_durability_ledger"]
    assert len(ledger) == 228
    rows = {row["candidate_id"]: row for row in ledger}
    assert set(TARGETS) <= set(rows)

    state = json.loads((APP / "data" / "explosion_candidate_monitor_state.json").read_text(encoding="utf-8"))
    kyiv_tz = ZoneInfo("Europe/Kyiv")
    result = []
    for cid, (city, local_iso) in TARGETS.items():
        row = rows[cid]
        local_dt = datetime.fromisoformat(local_iso).replace(tzinfo=kyiv_tz)
        utc_dt = local_dt.astimezone(mon.UTC)
        episodes = mon.tracked_episodes_for_city(state, city)
        active = mon.exact_active_episodes_at(utc_dt, episodes)
        support = mon.logical_episode_support(active)
        nearby = []
        for ep in episodes:
            start = mon.parse_dt(ep.get("alert_start"))
            end = mon.parse_dt(ep.get("alert_end"))
            if start and end and abs((utc_dt - start).total_seconds()) <= 7200 or start and end and abs((utc_dt - end).total_seconds()) <= 7200:
                nearby.append(ep)
        result.append({
            "candidate_id": cid,
            "city": city,
            "cluster_local_time": local_iso,
            "cluster_utc_time": mon.iso(utc_dt),
            "active_episodes": active,
            "active_logical_support": support,
            "nearby_episodes": nearby,
            "publication_timestamp": row.get("publication_timestamp"),
            "counterfactual": row.get("counterfactual"),
            "audit_contexts": row.get("audit_contexts"),
            "article_metadata": row.get("article_metadata"),
            "official_classification_before": row.get("official_classification_before"),
        })

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
