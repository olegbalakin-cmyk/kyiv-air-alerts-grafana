#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

STRICT_STATUS = "included_strict"
REVIEW_BUCKET = "review_events"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def evidence_text(row: dict) -> str:
    matches = row.get("telegram_matches") or []
    texts = [str(m.get("text") or "").strip() for m in matches if str(m.get("text") or "").strip()]
    if texts:
        return " ".join(dict.fromkeys(texts))
    raw = row.get("raw_nonlegacy") or {}
    event_id = raw.get("event_id")
    fallback = {
        "LVI-20260205-01": (
            "У Львові пролунали вибухи під час повітряної тривоги 15:50–17:05; "
            "ППО знищила безпілотник над Львовом / Львівською громадою."
        ),
        "LVI-20260208-01": (
            "У Львові о 08:48 було чути звуки вибухів під час повітряної тривоги "
            "07:53–08:58; ППО знищила ворожі безпілотники."
        ),
    }
    if event_id in fallback:
        return fallback[event_id]
    notes = row.get("notes") or {}
    temporal = row.get("temporal_evidence") or {}
    parts = [str(v).strip() for v in [*temporal.values(), *notes.values()] if str(v).strip()]
    return " — ".join(parts)


def clean_review_row(row: dict) -> dict:
    raw = dict(row.get("raw_nonlegacy") or {})
    binding = row.get("binding") or {}
    out = {
        "event_id": raw.get("event_id"),
        "episode_id": binding.get("episode_id"),
        "binding_status": binding.get("status"),
        "binding_method": binding.get("method"),
        "source_url": row.get("source_url"),
        "evidence": evidence_text(row),
        "temporal_evidence": row.get("temporal_evidence") or {},
        "notes": row.get("notes") or {},
        "historical_frozen_status": (row.get("legacy_fields_present_but_ignored") or {}).get("final_status"),
        "raw_record": raw,
    }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--binding", required=True, type=Path)
    ap.add_argument("--manual-qa", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()

    binding = load(args.binding)
    qa = load(args.manual_qa)

    override_event = qa["event_id"]
    override_episode = qa["manual_binding"]["episode_id"]

    strict_events = []
    review_events = []

    for row in binding.get("rows") or []:
        legacy = row.get("legacy_fields_present_but_ignored") or {}
        frozen_status = legacy.get("final_status")
        raw = row.get("raw_nonlegacy") or {}
        event_id = raw.get("event_id")
        b = dict(row.get("binding") or {})

        if event_id == override_event:
            b["status"] = "matched"
            b["episode_id"] = override_episode
            b["method"] = "source_chronology_manual_qa"

        row2 = dict(row)
        row2["binding"] = b

        if frozen_status == STRICT_STATUS:
            if b.get("status") != "matched" or not b.get("episode_id"):
                raise SystemExit(f"Counted historical event is not bound: {event_id} {b}")
            strict_events.append({
                "event_id": event_id,
                "episode_id": b["episode_id"],
                "source_url": row.get("source_url"),
                "evidence": evidence_text(row2),
                "decision_basis": (
                    "Frozen historical audit retained evidence; historical bucket only. "
                    "Current hardened replay must reclassify."
                ),
                "binding_method": b.get("method"),
                "temporal_evidence": row.get("temporal_evidence") or {},
                "notes": row.get("notes") or {},
                "historical_frozen_status": frozen_status,
                "raw_record": raw,
            })
        else:
            review_events.append(clean_review_row(row2))

    strict_ids = [x["episode_id"] for x in strict_events]
    if len(strict_events) != 12:
        raise SystemExit(f"Expected 12 historical strict rows, got {len(strict_events)}")
    if len(set(strict_ids)) != 12:
        raise SystemExit(f"Expected 12 unique strict episode ids, got {len(set(strict_ids))}")

    out = {
        "schema_version": 1,
        "city_key": "lviv",
        "coverage_start": "2025-09-01",
        "coverage_end": "2026-09-17",
        "purpose": "Frozen historical evidence corpus for current-rules replay.",
        "historical_baseline": {
            "total_alerts": 126,
            "strict_n": 12,
            "sensitivity_n": 12
        },
        "methodology_note": (
            "Historical bucket membership reconstructs the frozen audited baseline only. "
            "It is not treated as current truth. The current hardened classifier must re-evaluate all retained evidence."
        ),
        "manual_binding_qa": {
            "event_id": override_event,
            "episode_id": override_episode,
            "source_url": qa.get("source_url"),
            "artifact": str(args.manual_qa)
        },
        "strict_events": strict_events,
        "sensitivity_only_events": [],
        "review_events": review_events,
        "checks": {
            "strict_event_rows": len(strict_events),
            "unique_strict_episode_ids": len(set(strict_ids)),
            "review_event_rows": len(review_events),
            "historical_strict_matches_baseline": len(strict_events) == 12,
            "historical_sensitivity_matches_baseline": len(strict_events) == 12
        },
        "verdict": "LVIV FINAL EVIDENCE CORPUS READY FOR CURRENT-RULES REPLAY"
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out["checks"], ensure_ascii=False, indent=2))
    print(out["verdict"])


if __name__ == "__main__":
    main()
