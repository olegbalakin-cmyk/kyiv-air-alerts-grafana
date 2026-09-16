#!/usr/bin/env python3
import json
from pathlib import Path

p = Path('kyiv-air-alerts-grafana/data/mykolaiv_mayor_channel_audit.json')
data = json.loads(p.read_text(encoding='utf-8'))
for idx, ctx in enumerate(data.get('anomaly_context', []), start=1):
    print(f"\n=== CASE {idx}: {ctx['previous_start']['id']} -> {ctx['next_start']['id']} ===")
    print('START:', ctx['previous_start']['at'], ctx['previous_start']['text'])
    for m in ctx.get('relevant_messages_between', []):
        print(f"{m['id']} | {m['at']} | classified={m['classified_as']} | {m['text']}")
    print('NEXT:', ctx['next_start']['at'], ctx['next_start']['text'])
