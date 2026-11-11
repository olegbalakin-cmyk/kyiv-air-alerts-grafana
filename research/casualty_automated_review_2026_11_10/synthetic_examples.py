#!/usr/bin/env python3
"""Inspect positive lineage without mislabelling fixtures as real confirmations."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'kyiv-air-alerts-grafana/scripts'))
from casualty_auto_review import extract_cached_reports, prepare

HERE=Path(__file__).resolve().parent
cs=[{'candidate_id':'SYNTHETIC-'+key,'city_key':'dnipro','city':'Дніпро',
     'status':'needs_review','title':'SYNTHETIC OFFLINE CONTROL',
     'snippet':'','url':'https://'+host+'/SYNTHETIC-NOT-A-REAL-ARTICLE',
     'publisher_url':'https://'+host,'published_at':'2026-11-03T10:00:00Z'}
    for key,host in [('A','suspilne.media'),('B','npu.gov.ua')]]

def articles(n):
    text=f'У межах міста Дніпро російський ракетний удар стався 2026-11-03 о 08:00. За адресою Тестова, 1. Загинули {n} цивільних.'
    return [{'candidate_id':c['candidate_id'],'url':c['url'],'text':text+' Повідомляє '+origin+'.',
             'observed_at':'2026-11-03'} for c,origin in zip(cs,['ДСНС','Національна поліція'])]

base={'dnipro':{'through':'2026-09-18'}}
first=prepare(cs,[],extract_cached_reports(cs,articles(2)),base)
# Independent in-memory ledger overlay only. No reviewer or promoter invocation.
second=prepare(cs,first['proposals'],extract_cached_reports(cs,articles(3)),base)
again=prepare(cs,first['proposals']+second['proposals'],extract_cached_reports(cs,articles(3)),base)
assert first['proposals'][0]['deaths_delta']=='2'
assert second['proposals'][0]['deaths_delta']=='1'
assert again['proposals']==[]
out={'scope':'SYNTHETIC ONLY. These are not real news, deaths or proposed publication.',
     'retained_text_inputs':articles(2), 'initial':first,'update_2_to_3':second,'repeat':again}
(HERE/'results/synthetic_positive_lineage.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print('SYNTHETIC: +2, then +1, then +0')
