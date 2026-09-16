#!/usr/bin/env python3
import json
import re
from collections import Counter
from pathlib import Path

p = Path('kyiv-air-alerts-grafana/data/sevastopol_exact_city_audit.json')
data = json.loads(p.read_text(encoding='utf-8'))
rows = data.get('typed', [])


def norm(s):
    s=s.lower().replace('ё','е').replace('\xa0',' ')
    s=re.sub(r'[⚡️❗‼️◻️]+',' ',s)
    return ' '.join(s.split())

forms=Counter()
recent=[]
for x in rows:
    if x.get('kind')!='end':
        continue
    s=norm(x.get('text',''))
    # bucket first 80 chars after stripping promo/emoji
    forms[s[:100]] += 1
    if x.get('at','') >= '2026-06-20':
        recent.append((x['id'],x['at'],s[:300]))

print('END_COUNT_RAW', sum(forms.values()))
print('UNIQUE_END_FORMS', len(forms))
for text,n in forms.most_common(50):
    print('FORM',n,'|',text)
print('RECENT_END_COUNT',len(recent))
for row in recent:
    print('RECENT_END',row[0],'|',row[1],'|',row[2])
