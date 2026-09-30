#!/usr/bin/env python3
"""Proof-only differentiated-alert normalizer. No production imports or writes."""
from __future__ import annotations
import copy, hashlib, json
from datetime import datetime, timezone

SNAPSHOT_V='differentiated-snapshot-v1'; OBS_V='differentiated-threat-observation-v1'; COMP_V='differentiated-component-signature-v1'
END_SOURCE='SOURCE_EXPLICIT'; END_SNAPSHOT='SNAPSHOT_INFERRED'; END_EPISODE='EPISODE_CLOSE_INFERRED'; END_UNKNOWN='UNKNOWN'

def cj(x): return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def h(*x): return hashlib.sha256('\0'.join('' if v is None else str(v) for v in x).encode()).hexdigest()
def payload_hash(x): return hashlib.sha256(cj(x).encode()).hexdigest()
def ts(x):
    if not x:return None
    x=x[:-1]+'+00:00' if x.endswith('Z') else x
    d=datetime.fromisoformat(x); return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
def severity(x):
    x='' if x is None else str(x).strip().lower(); return x if x in {'yellow','red'} else 'unknown'
def geo(x):
    x='' if x is None else str(x).strip().lower()
    return {'city':'CITY','hromada':'HROMADA','community':'HROMADA','raion':'RAION','district':'RAION','oblast':'OBLAST','state':'OBLAST'}.get(x,'OTHER')
def ua_type(x): return {'дронова загроза':'drone','ракетна загроза':'missile_unspecified'}.get(('' if x is None else str(x).strip().lower()),'unknown')
def aiu_type(x):
    return {'drones':'drone','ballistic_missiles':'missile_ballistic','cruise_missiles':'missile_cruise','unspecified_missiles':'missile_unspecified','tactic_aircraft_activity':'tactical_aircraft_activity','strategic_aircraft_activity':'strategic_aircraft_activity','mig31k_departure':'mig31k_departure','guided_aerial_bombs':'guided_aerial_bomb','air_defense':'air_defense','unknown':'unknown'}.get(('' if x is None else str(x).strip().lower()),'unknown')
def kyiv_type(x): return {'drone':'drone','missile':'missile_unspecified','ballistic':'missile_ballistic','missile-drone':'missile_drone_combined','massive-drone':'massive_drone','mig':'mig'}.get(('' if x is None else str(x).strip().lower()),'unknown')

def finalize(snapshot, raw, threats):
    s=copy.deepcopy(snapshot); s['raw_payload_hash']=payload_hash(raw); s['snapshot_key_version']=SNAPSHOT_V
    locator=cj([s.get('source_alert_id'),s['source_geography']['scope'],s['source_geography']['id_raw'],s['alert_type']])
    s['snapshot_key']=h(SNAPSHOT_V,s['source'],locator,s['observed_at'],s.get('source_state_at'),s['raw_payload_hash'])
    s.setdefault('episode_id',None); s.setdefault('binding_state','UNBOUND')
    rows=[]; seen={}
    for r in sorted((copy.deepcopy(x) for x in threats),key=cj):
        fp=cj({k:r.get(k) for k in ['source_threat_id','component_signature','level_raw','cause_raw','reason_raw','source_message_raw','source_started_at','source_ended_at']})
        n=seen.get(fp,0);seen[fp]=n+1;r['duplicate_ordinal']=n;r['snapshot_key']=s['snapshot_key'];r['observation_key_version']=OBS_V;r['observation_key']=h(OBS_V,s['snapshot_key'],fp,n);rows.append(r)
    return {'snapshot':s,'threat_observations':rows}

def ua(payload,*,observed_at,target_city_key,region_id,region_type='raion',raw_object_path=None):
    matches=[x for x in payload.get('activeAlerts',[]) if str(x.get('regionId'))==str(region_id) and str(x.get('type','')).upper()=='AIR']
    if len(matches)>1: raise ValueError('multiple AIR objects')
    a=matches[0] if matches else None; rt=(a or {}).get('regionType') or region_type
    s={'source':'ukrainealarm','source_alert_identity':'EPISODE_BOUND','source_alert_id':None,'target_city_key':target_city_key,'alert_type':'AIR','source_geography':{'scope':geo(rt),'type_raw':rt,'id_raw':str(region_id)},'observed_at':observed_at,'source_state_at':None if a is None else a.get('lastUpdate'),'source_active':a is not None,'source_alert_level_raw':None,'source_state_raw':None,'raw_object_path':raw_object_path}
    rows=[]
    for x in [] if a is None else a.get('activeAlertLevels',[]):
        reason=x.get('reason');start=x.get('createdAt')
        rows.append({'source_threat_id':None,'component_signature':h(COMP_V,'ukrainealarm',region_id,'AIR',reason,start),'component_identity_basis':'DETERMINISTIC_INFERRED','level_raw':x.get('alertLevel'),'cause_raw':None,'reason_raw':reason,'source_message_raw':None,'source_started_at':start,'source_ended_at':None,'severity_normalized':severity(x.get('alertLevel')),'threat_type_normalized':ua_type(reason)})
    return finalize(s,payload,rows)

def aiu(alert,*,observed_at,target_city_key,raw_object_path=None):
    uid=alert.get('location_uid'); typ=alert.get('location_type'); ast=alert.get('started_at')
    s={'source':'alerts_in_ua','source_alert_identity':'NOT_PROVEN','source_alert_id':alert.get('id'),'target_city_key':target_city_key,'alert_type':str(alert.get('alert_type','AIR')).upper(),'source_geography':{'scope':geo(typ),'type_raw':typ,'id_raw':uid},'observed_at':observed_at,'source_state_at':alert.get('updated_at'),'source_alert_started_at':ast,'source_alert_ended_at':alert.get('finished_at'),'source_active':alert.get('finished_at') is None,'source_alert_level_raw':alert.get('alert_level'),'source_state_raw':None,'raw_object_path':raw_object_path}
    rows=[]
    for x in alert.get('threats',[]) or []:
        raw=x.get('threat_type'); start=x.get('started_at')
        rows.append({'source_threat_id':None,'component_signature':h(COMP_V,'alerts_in_ua',uid,s['alert_type'],ast,raw,start),'component_identity_basis':'DETERMINISTIC_INFERRED','level_raw':x.get('level'),'cause_raw':raw,'reason_raw':None,'source_message_raw':x.get('source_message'),'source_started_at':start,'source_ended_at':None,'severity_normalized':severity(x.get('level')),'threat_type_normalized':aiu_type(raw)})
    return finalize(s,alert,rows)

def kyiv(payload,*,observed_at,target_city_key='kyiv',raw_object_path=None):
    c=payload.get('current',payload); causes=c.get('causes') or []; state=c.get('state')
    active=state not in (0,'0',False,'clear','inactive',None)
    s={'source':'kyiv_official','source_alert_identity':'EPISODE_BOUND','source_alert_id':None,'target_city_key':target_city_key,'alert_type':'AIR','source_geography':{'scope':'CITY','type_raw':'city','id_raw':'kyiv'},'observed_at':observed_at,'source_state_at':c.get('created_at'),'source_active':active,'source_alert_level_raw':None,'source_state_raw':state,'source_last_cause_raw':c.get('last_cause'),'raw_object_path':raw_object_path}
    rows=[{'source_threat_id':None,'component_signature':None,'component_identity_basis':'SNAPSHOT_ONLY','level_raw':None,'cause_raw':x,'reason_raw':None,'source_message_raw':None,'source_started_at':None,'source_ended_at':None,'severity_normalized':'unknown','threat_type_normalized':kyiv_type(x)} for x in causes]
    return finalize(s,payload,rows)

def bind(rec,episodes):
    out=copy.deepcopy(rec);s=out['snapshot'];point=ts(s.get('source_state_at')) or ts(s.get('observed_at'));hits=[]
    for e in episodes:
        if e.get('city_key')!=s.get('target_city_key') or str(e.get('alert_type','AIR')).upper()!='AIR': continue
        a=ts(e.get('start_at') or e.get('alert_start'));b=ts(e.get('end_at') or e.get('alert_end'))
        if a and point and point>=a and (b is None or point<=b):hits.append(e)
    if len(hits)==1:s['binding_state']='BOUND';s['episode_id']=hits[0].get('episode_id') or hits[0].get('legacy_episode_id')
    elif len(hits)>1:s['binding_state']='AMBIGUOUS';s['episode_id']=None
    else:s['binding_state']='UNBOUND';s['episode_id']=None
    return out

def effective(rec):
    known=[x['severity_normalized'] for x in rec['threat_observations'] if x.get('severity_normalized') in {'yellow','red'}]
    if known:return {'effective_severity':'red' if 'red' in known else 'yellow','basis':'COMPONENT_MAX'}
    x=severity(rec['snapshot'].get('source_alert_level_raw'));return {'effective_severity':x,'basis':'SOURCE_ALERT_LEVEL' if x!='unknown' else 'UNKNOWN'}

def comp_key(s,r):
    if r.get('component_signature'):return 'signature:'+r['component_signature'],r.get('component_identity_basis')
    return 'adjacent:'+h(s['source'],s.get('episode_id'),r.get('cause_raw'),r.get('reason_raw'),r.get('threat_type_normalized')),'ADJACENT_SNAPSHOT_INFERRED'
def intervals(records,episode_end_at=None):
    records=sorted(records,key=lambda r:ts(r['snapshot']['observed_at']));open_={};done=[];prev=None
    for rec in records:
        s=rec['snapshot'];now=s['observed_at'];cur={comp_key(s,r)[0]:(r,comp_key(s,r)[1]) for r in rec['threat_observations']}
        for k in [k for k in open_ if k not in cur]:
            x=open_.pop(k);x.update(first_seen_inactive_at=now,end_lower_bound=x['last_seen_active_at'],end_upper_bound=now,source_ended_at=None,derived_end_at=None,end_basis=END_EPISODE if s.get('source_active') is False else END_SNAPSHOT);done.append(x)
        for k,(r,basis) in cur.items():
            if k not in open_:
                st=r.get('source_started_at');open_[k]={'derived_component_key':k,'identity_basis':basis,'source':s['source'],'episode_id':s.get('episode_id'),'cause_raw':r.get('cause_raw'),'reason_raw':r.get('reason_raw'),'threat_type_normalized':r.get('threat_type_normalized'),'source_started_at':st,'start_basis':'SOURCE_EXPLICIT' if st else 'SNAPSHOT_INFERRED','start_lower_bound':st or prev,'start_upper_bound':st or now,'first_seen_active_at':now,'last_seen_active_at':now,'source_ended_at':None,'derived_end_at':None,'end_basis':END_UNKNOWN}
            else:open_[k]['last_seen_active_at']=now
            if r.get('source_ended_at'):
                x=open_.pop(k);end=r['source_ended_at'];x.update(first_seen_inactive_at=end,end_lower_bound=end,end_upper_bound=end,source_ended_at=end,derived_end_at=end,end_basis=END_SOURCE);done.append(x)
        prev=now
    if episode_end_at:
        for k in list(open_):
            x=open_.pop(k);x.update(first_seen_inactive_at=episode_end_at,end_lower_bound=x['last_seen_active_at'],end_upper_bound=episode_end_at,source_ended_at=None,derived_end_at=None,end_basis=END_EPISODE);done.append(x)
    return done+list(open_.values())

def entities():
    return {'alert_episode':'EXISTING_PARENT_UNCHANGED','alert_state_snapshot':'PERSIST','alert_threat_observation':'PERSIST','threat_component':'DERIVED_ONLY','effective_severity':'DERIVED_ONLY','component_interval':'DERIVED_ONLY'}
