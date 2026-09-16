#!/usr/bin/env python3
import json
from pathlib import Path

p = Path('kyiv-air-alerts-grafana/data/sevastopol_exact_city_audit.json')
data = json.loads(p.read_text(encoding='utf-8'))

print('FIRST_START', data.get('first_start'))
print('ANOMALIES', len(data.get('anomalies', [])))
for i, a in enumerate(data.get('anomalies', []), 1):
    print(f'ANOMALY {i}: {json.dumps(a, ensure_ascii=False)}')

pairs = data.get('pairs', [])
longs = sorted([x for x in pairs if x.get('duration_min', 0) > 360], key=lambda x: x['duration_min'], reverse=True)
print('LONG_GT_6H', len(longs))
for i, x in enumerate(longs[:50], 1):
    print(f'LONG {i}: {json.dumps(x, ensure_ascii=False)}')

# Print suspicious typed starts that are verbose instructions/explanations rather than activation messages.
for x in data.get('typed', []):
    if x.get('kind') == 'start' and len(x.get('text','')) > 150:
        print('VERBOSE_START', json.dumps(x, ensure_ascii=False))
