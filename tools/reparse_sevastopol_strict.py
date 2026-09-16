#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

SRC = Path('kyiv-air-alerts-grafana/data/sevastopol_exact_city_audit.json')
OUT = Path('kyiv-air-alerts-grafana/data/sevastopol_strict_audit.json')


def norm(text: str) -> str:
    s = text.lower().replace('ё', 'е').replace('\xa0', ' ')
    s = re.sub(r'[⚡️❗‼️◻️]+', ' ', s)
    return ' '.join(s.split())


def strict_kind(text: str) -> str | None:
    s = norm(text)

    # Formal all-clear. Narrative mentions like "как только дали отбой" are excluded.
    if re.match(r'^отбой\s+воздушн(?:ой|ая)\s+тревог', s):
        return 'end'

    # Formal activation patterns used in the channel. Allow promo text after the
    # signal, but the alert formula itself must be at the beginning of the post.
    if re.match(r'^внимание\s+всем[!,. ]+воздушная\s+тревога(?:\s+и\s+морская\s+опасность)?[!,. ]*', s):
        return 'start'
    if re.match(r'^воздушная\s+тревога[!,. ]*$', s):
        return 'start'
    if re.match(r'^воздушная\s+тревога[!,. ]+', s) and len(s) < 120:
        return 'start'

    # Some operational posts prepend a short attack-status sentence, then emit
    # the formal alert formula. Keep only when the exact formula appears near the
    # beginning, not in quoted/explanatory prose.
    pos = s.find('внимание всем! воздушная тревога')
    if 0 <= pos <= 250 and any(token in s[:pos] for token in ('отражают атаку', 'работает пво', 'сбито')):
        return 'start'
    return None


def main() -> None:
    raw = json.loads(SRC.read_text(encoding='utf-8'))
    candidates = raw.get('typed', [])
    selected = []
    rejected = []
    for row in candidates:
        kind = strict_kind(row.get('text', ''))
        item = {**row, 'strict_kind': kind}
        if kind:
            selected.append(item)
        else:
            rejected.append(item)

    selected.sort(key=lambda x: (x['at'], x['id']))
    active = None
    pairs = []
    anomalies = []
    duplicate_starts = 0

    for row in selected:
        k = row['strict_kind']
        dt = datetime.fromisoformat(row['at'])
        if k == 'start':
            if active is not None:
                prev_dt = datetime.fromisoformat(active['at'])
                gap_min = (dt - prev_dt).total_seconds() / 60
                if gap_min <= 5:
                    duplicate_starts += 1
                    continue
                # Do not invent the missing all-clear: mark previous activation
                # incomplete and restart state from the newly observed signal.
                anomalies.append({
                    'type': 'missing_end_before_new_start',
                    'start_id': active['id'],
                    'next_start_id': row['id'],
                    'gap_min': round(gap_min, 2),
                    'start_at': active['at'],
                    'next_start_at': row['at'],
                })
            active = row
            continue

        if active is None:
            anomalies.append({'type': 'orphan_end', 'end_id': row['id'], 'end_at': row['at']})
            continue
        start_dt = datetime.fromisoformat(active['at'])
        duration = (dt - start_dt).total_seconds() / 60
        if duration <= 0:
            anomalies.append({'type': 'nonpositive', 'start_id': active['id'], 'end_id': row['id']})
        else:
            pairs.append({
                'start': active['at'], 'end': row['at'],
                'duration_min': round(duration, 3),
                'start_id': active['id'], 'end_id': row['id'],
                'start_url': active['url'], 'end_url': row['url'],
            })
        active = None

    if active is not None:
        anomalies.append({'type': 'open_start', 'start_id': active['id'], 'start_at': active['at']})

    by_year = {}
    by_month = {}
    for p in pairs:
        for key, bucket in ((p['start'][:4], by_year), (p['start'][:7], by_month)):
            r = bucket.setdefault(key, {'events': 0, 'hours': 0.0})
            r['events'] += 1
            r['hours'] += p['duration_min'] / 60
    for bucket in (by_year, by_month):
        for r in bucket.values():
            r['hours'] = round(r['hours'], 3)

    starts = [x for x in selected if x['strict_kind'] == 'start']
    ends = [x for x in selected if x['strict_kind'] == 'end']
    long_pairs = [p for p in pairs if p['duration_min'] > 12 * 60]
    out = {
        'source_audit_generated_at': raw.get('generated_at'),
        'source': raw.get('source'),
        'provenance': raw.get('provenance'),
        'coverage_start_external': '2023-09-25',
        'candidate_messages': len(candidates),
        'strict_messages': len(selected),
        'strict_starts': len(starts),
        'strict_ends': len(ends),
        'duplicate_starts_within_5m': duplicate_starts,
        'paired_complete_events': len(pairs),
        'anomaly_count': len(anomalies),
        'long_pair_count_gt_12h': len(long_pairs),
        'first_start': starts[0] if starts else None,
        'last_start': starts[-1] if starts else None,
        'by_year': by_year,
        'by_month': by_month,
        'anomalies': anomalies,
        'long_pairs_gt_12h': long_pairs,
        'pairs': pairs,
        'rejected_candidate_examples': rejected[:30],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: out[k] for k in (
        'candidate_messages','strict_messages','strict_starts','strict_ends',
        'duplicate_starts_within_5m','paired_complete_events','anomaly_count',
        'long_pair_count_gt_12h','first_start','last_start','by_year'
    )}, ensure_ascii=False, indent=2))
    if anomalies:
        print('ANOMALIES')
        for a in anomalies:
            print(json.dumps(a, ensure_ascii=False))
    if long_pairs:
        print('LONG_PAIRS')
        for p in long_pairs:
            print(json.dumps(p, ensure_ascii=False))

if __name__ == '__main__':
    main()
