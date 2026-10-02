#!/usr/bin/env python3
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from collections import Counter, OrderedDict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / 'research' / 'historical_23city_blind_sample_manifest_2026-10-02.json'
SEED = '20261002-23city-blind-v1'
FROZEN_CAMPAIGN_HEAD = '71cb6f6fbe856cc7b96759310fe9cc9c71cc0453'
FROZEN_STATUS_BLOB = '615b380b51c0da7aa052bad06222c12785090986'
OFFLINE_REPAIR_HEAD = '5d18ef85a66384f189ede5ca5654d750f60f088b'
REPAIRED_FIVECITY_SHA = '652bda9bc4037d263e7e1090455ff4df5387d1f4f1a73a8c5e160d7ce62132f5'
BASELINE_HEAD = 'fb563dc410fe6614263bdc8d4eb55025a987e950'
FORMALIZATION_ACCEPTANCE_HEAD = '31aa7a8f8f57ff090f24814ef3c62137eebebf16'

CITY_CONTRACTS = OrderedDict([
 ('cherkasy', (41,45,1436,'98bb8bd96ad4afd4c40a4c4757c9edb8b6d4772cbebc02db2ec11cab1625369c')),
 ('chernihiv',(46,50,1633,'f3924bcf11a33851e5639576e15efcb300dc5e1b2915dc003fec567b7d6e3403')),
 ('chernivtsi',(51,55,111,'e8b182435d43eceb5cb9b577ece4075d88c0975d0eef5c9251ac52a5064b6e2c')),
 ('dnipro',(56,60,2068,'91892fc80a2de04b9dce9e17a036df48a6f03da2a27114457e1954b792485d97')),
 ('ivano_frankivsk',(61,65,97,'21d0940462f2d6d2d3332f25b9bec6af5c2d365ca1d347a85dc6e10594890a5c')),
 ('kharkiv',(66,70,3250,'6e36efa07e7507ee4a34069542ad3d2bbcc8d2d24ba263f9551c1423894518e3')),
 ('kherson',(71,75,1410,'6486e359516a3e27864231ed008bcc822f23e86c88ed6e8ae3bb1b827097cb7f')),
 ('khmelnytskyi',(76,80,236,'f901140b86f688817c161fcd5570a5997ac112656da33b34a0a224378090d335')),
 ('kropyvnytskyi',(81,85,1122,'2115d79b7aa006434f5a31c4e40f5971d7021166ceaebf391be87916b2646f6a')),
 ('kyiv',(86,90,2045,'fc7c6a20e40a6ff31930da4201838e2d5f3ce2d8843f3b143105c1a5828628ab')),
 ('lutsk',(91,95,123,'0252b58e6da58063139836ac730551950ed435710dee5b726abbe3e962e98362')),
 ('lviv',(96,100,107,'348a3cbc16258f1f08e59c5c7f1d36d2eef0ab7b17250c82035a3aa233a5b96e')),
 ('mykolaiv',(101,105,1512,'d7d24f4f3673dce6e88bfa2d7fc1c68ad0eac233ec8197cd0fb5eff553540b62')),
 ('odesa',(106,110,1304,'820c994e5cabd0937b299b1b081636208a9c4eb7755d063418354482a4b83c45')),
 ('poltava',(111,115,1752,'65955f0848f1038b1172d8bd99caf7b05eb8d3a674dfc715bee009147d19adad')),
 ('rivne',(116,120,219,'e5a951266b06acdd73d06db217acc34d78481b7e1c869eaaf015d1a5ef1e53e8')),
 ('sevastopol',(121,125,527,'959f7737ed0d7f61ba2428047b113d84a2a53bf28f5ae3f880f0c3bc699a00a2')),
 ('sumy',(126,130,1715,'11017bcafcff4696780c5bfdadbdd2f524243c9d96eca9a4c85afac24c4dc4e4')),
 ('ternopil',(131,135,120,'d1836434086dd36ae375a62738a665387a79ea4834fa33dbdc5e106a414585ea')),
 ('uzhhorod',(136,140,91,'31a7e1e755fe3b142524ab108ccf620e5002d88559d08b11b764ee7e2ed57998')),
 ('vinnytsia',(141,145,355,'adab245d461cbcd5c03ad3ca4eac266d2a0c300d58e1ca017bed08b771ade910')),
 ('zaporizhzhia',(146,150,1632,'75095c3ab71def85e4bed4b2e4ef92ea364186f56e7324578d6c3d40d32011bc')),
 ('zhytomyr',(151,155,665,'e024869b4d5bb919b37000a58bad5fd419c4ec98271a4040a17f21118f52eb99')),
])

PRIOR = {
 'cherkasy':['b38a9ec3c677c27ca7c699df','dd3309d804e0e408d2574dc2','744dc40da0852b493391da48','c46a65867bfc8f5598aa9d79','39067ae1b3020336b065a41c','2a31f2e502448c3b60b8a519','547db273739626a788921a15'],
 'lviv':['f8ea1ceb7d4d3bbab70594a9','e6c11bdf24e2c18d773f1173','d226d5ad36223e4a5f625b6d'],
 'sevastopol':['c4d0a68613b9dda2405cb9d8','6069b17ec096cae0912ad9bd','0a01f6c533e8df9b125a0edc','3a736a09fa7bf09ed973ac63','b06bad03dbf8cc319b5bdd98','f45ebdd5bc2715289c464703'],
 'sumy':['53effeea680bcbbf58e326c4','846ff0a4252b01ba0bab560f','ae2718c10fcdc7079dbb220a','9e87e464ea93d32b31a09a3d','6d38867f9de5d8908b05d6d4','126de43f131806ee32cc40f2','035d1068a5fa897b177c73bd','af12444da27b16f9c8271218','4bb37482c689fc238aad2de9','0c8cdb07753d54e5b254a75d','f62c33859f5bc8059eab3e23','87746a13b03047f322902a64','abed0e1fbdad8fe82433c4e0','f19c06b0dbd60648f8c38962','ad29a2108ca5093e8020518e'],
 'zaporizhzhia':['55cf2f30f110ccbb4ed9ba60','94037a6ae891c1e54e799fc2','d63a0d93e9e1ff1b7e25d97c','ae1f9a678aae5d8bfa37b6b3','0132cbf753ac16a7b8d7d2e0','86098c23e322d3ea0012afd6','736690cd70c2bf8f9234cd40','194ab680fd50b7715adc2145','37b7efdaf39ad1b6cd81801b']
}
SUPERSEDED_SUMY={'ccb6b28dea38ec51006f2eac','5209406cdaec9406ecd9d213','e599097b2704aab8bd1edb91','584b4352978fab6d1cb0c505','c7e7097f754ba1b5bace6bfd'}

COMMITTED_FREEZES={
 'chernivtsi':('historical-blind-freeze-chernivtsi-proof-2026-10-02','research/historical_blind_freeze_chernivtsi_2026-10-02.json'),
 'dnipro':('historical-blind-freeze-dnipro-proof-2026-10-02','research/historical_blind_freeze_dnipro_2026-10-02.json'),
 'ivano_frankivsk':('historical-blind-freeze-ivano_frankivsk-proof-2026-10-02','research/historical_blind_freeze_ivano_frankivsk_2026-10-02.json'),
 'kharkiv':('historical-blind-freeze-kharkiv-proof-2026-10-02','research/historical_blind_freeze_kharkiv_2026-10-02.json'),
 'kyiv':('historical-blind-freeze-kyiv-proof-2026-10-02','research/historical_blind_freeze_kyiv_2026-10-02.json'),
 'mykolaiv':('historical-blind-freeze-mykolaiv-proof-2026-10-02','research/historical_blind_freeze_mykolaiv_2026-10-02.json'),
 'poltava':('historical-blind-freeze-poltava-proof-2026-10-02','research/historical_blind_freeze_poltava_2026-10-02.json'),
 'rivne':('historical-blind-freeze-rivne-proof-2026-10-02','research/historical_blind_freeze_rivne_2026-10-02.json'),
 'ternopil':('historical-blind-freeze-ternopil-proof-2026-10-02','research/historical_blind_freeze_ternopil_2026-10-02.json'),
 'uzhhorod':('historical-blind-freeze-uzhhorod-proof-2026-10-02','research/historical_blind_freeze_uzhhorod_2026-10-02.json'),
 'vinnytsia':('historical-blind-freeze-vinnytsia-proof-2026-10-02','research/historical_blind_freeze_vinnytsia_2026-10-02.json'),
 'zhytomyr':('historical-blind-freeze-zhytomyr-proof-2026-10-02','research/historical_blind_freeze_zhytomyr_2026-10-02.json'),
}
ACTION_FREEZES={
 'chernihiv':(36987242918,'historical-blind-freeze-chernihiv-2026-10-02'),
 'kherson':(36988080606,'historical-blind-freeze-kherson-2026-10-02'),
 'khmelnytskyi':(36987954879,'historical-blind-freeze-khmelnytskyi-2026-10-02'),
 'kropyvnytskyi':(36988078963,'historical-blind-freeze-kropyvnytskyi-2026-10-02'),
 'lutsk':(36988622287,'historical-blind-freeze-lutsk-2026-10-02'),
 'odesa':(36989283081,'historical-blind-freeze-odesa-2026-10-02'),
}
FREEZE_BRANCH_HEADS={
 'chernihiv':'7752da026415724a507636908b44ffba2cd715c4','chernivtsi':'7569df82f58673495569016587182389f485ceee','dnipro':'5ce973b8ca37b8eeec4936a34356331a8913c753','ivano_frankivsk':'9075593e4f5d91282d779de57c17720be44c0e59','kharkiv':'d6993fed19380cf63b525f0065039007190af969','kherson':'d116dcdde6bb220642620e513078323f518aebc5','khmelnytskyi':'42e77cc25c363c32bf72150fec9b86569e79557f','kropyvnytskyi':'e7df1f5440e84ab49413856d74b827412a574184','kyiv':'dac520ea5650a6e79eccc07b48210b448ee81610','lutsk':'483623207da9b948dc600ba947c7c37f9a712136','mykolaiv':'a55e258c5d6a4a892410d375e216d29b4d4a93a0','odesa':'870e41c6e4226acd75325bccc89fe87f0c659605','poltava':'49bce95c11af392f7815ebfaa0a46b9082864b59','rivne':'b3e23b6b3eb4f7dc8cce8221d1801a374b7cfffc','ternopil':'1c9d7b7b81e14d976ba588cf65cbf388db1ae2ee','uzhhorod':'abe3980bbcb69520fbb725cb1475f3272793dd81','vinnytsia':'b134480731f45f78089af9dd67a3bc09399739a2','zhytomyr':'0b970928833aa157e738e8084d583b0310a318df'
}

def git(*args, text=True):
    return subprocess.check_output(['git', *args], cwd=REPO, text=text)

def git_json(ref,path):
    return json.loads(git('show',f'{ref}:{path}'))

def compact(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(',',':')).encode('utf-8')

def sha(obj):
    return hashlib.sha256(compact(obj)).hexdigest()

def canonical_case(row, include_city_sha=False):
    keys=['case','city_key','episode_id','alert_start','alert_end','final_outcome','observation_count','rank']
    if include_city_sha: keys.append('city_sample_sha256')
    return OrderedDict((k,row[k]) for k in keys)

def load_action_artifact(city, run_id, name):
    dest=Path(tempfile.mkdtemp(prefix=f'freeze-{city}-'))
    env=os.environ.copy(); env['GH_TOKEN']=os.environ['GITHUB_TOKEN']
    subprocess.check_call(['gh','run','download',str(run_id),'-n',name,'-D',str(dest)],cwd=REPO,env=env)
    files=list(dest.rglob('*.json'))
    if len(files)!=1: raise SystemExit(f'{city}: expected one json in artifact, got {files}')
    return json.loads(files[0].read_text(encoding='utf-8'))

def build_early_five():
    for ref in (FROZEN_CAMPAIGN_HEAD, OFFLINE_REPAIR_HEAD):
        subprocess.check_call(['git','fetch','--no-tags','origin',ref],cwd=REPO)
    status_blob = git('rev-parse', f'{FROZEN_CAMPAIGN_HEAD}:research/historical_attack_event_backfill_status.json').strip()
    if status_blob != FROZEN_STATUS_BLOB:
        raise SystemExit(f'frozen status blob mismatch: {status_blob} != {FROZEN_STATUS_BLOB}')
    status=git_json(FROZEN_CAMPAIGN_HEAD,'research/historical_attack_event_backfill_status.json')
    scan=git_json(OFFLINE_REPAIR_HEAD,'research/historical_offline_repair_recovery_scan_2026-10-02.json')
    if scan['hashes']['repaired_target_state_sha256']!=REPAIRED_FIVECITY_SHA:
        raise SystemExit('repaired five-city target-state hash mismatch')
    changed={(x['city'],x['episode_id']):x['repaired_outcome'] for x in scan['targets']['changed_targets']}
    result={}; prov={}
    for city in ['cherkasy','lviv','sevastopol','sumy','zaporizhzhia']:
        lo,hi,before_expected,city_sha_expected=CITY_CONTRACTS[city]
        states=status['cities'][city]['episode_states']
        universe=[]
        for eid,s in states.items():
            state=changed.get((city,eid),s['state'])
            if state=='NO_CONFIRMED_EVENT':
                universe.append((eid,s))
        if len(universe)!=before_expected: raise SystemExit(f'{city}: before {len(universe)} != {before_expected}')
        listed=PRIOR[city]; uids={eid for eid,_ in universe}; intersect=[x for x in listed if x in uids]
        expected_intersect=14 if city=='sumy' else len(listed)
        if len(intersect)!=expected_intersect: raise SystemExit(f'{city}: exclusion intersection mismatch')
        eligible=[]
        excluded=set(listed)
        for eid,s in universe:
            if eid in excluded: continue
            rank=hashlib.sha256(f'{SEED}|{city}|{eid}'.encode()).hexdigest()
            eligible.append((rank,eid,s))
        eligible.sort(key=lambda x:(x[0],x[1]))
        selected=eligible[:5]
        rows=[]
        by_batch={}
        for off,(rank,eid,s) in enumerate(selected): by_batch.setdefault(s['batch'],[]).append((off,rank,eid,s))
        details={}
        for batch,items in by_batch.items():
            p=f'research/historical_attack_event_backfill/historical-attack-events-v2-2026-09-27/{city}/batch_{batch:06d}.json'
            batchj=git_json(FROZEN_CAMPAIGN_HEAD,p)
            idx={x['episode_id']:x for x in batchj['episode_results']}
            for off,rank,eid,s in items:
                ep=idx[eid]
                details[eid]=(ep['alert_start'],ep['alert_end'])
        for off,(rank,eid,s) in enumerate(selected):
            st,en=details[eid]
            rows.append(OrderedDict([
                ('case',lo+off),('city_key',city),('episode_id',eid),('alert_start',st),('alert_end',en),
                ('final_outcome','NO_CONFIRMED_EVENT'),('observation_count',s['observation_count']),('rank',rank)
            ]))
        got=sha([canonical_case(r) for r in rows])
        if got!=city_sha_expected: raise SystemExit(f'{city}: fingerprint {got} != {city_sha_expected}')
        result[city]=rows
        prov[city]={
          'source':'reconstructed_repaired_five_city_state','accepted_source_head':OFFLINE_REPAIR_HEAD,
          'source_campaign_head':FROZEN_CAMPAIGN_HEAD,'source_status_blob_sha':FROZEN_STATUS_BLOB,
          'case_range':[lo,hi],'eligible_before':len(universe),'prior_ids_listed':len(listed),'prior_ids_intersecting':len(intersect),
          'eligible_after':len(eligible),'accepted_city_sample_sha256':city_sha_expected,'recomputed_city_sample_sha256':got,'read_only_freeze':True
        }
    return result,prov

def main():
    current_head=git('rev-parse','HEAD').strip()
    expected_execution_head=os.environ.get('GITHUB_SHA')
    if expected_execution_head and current_head!=expected_execution_head:
        raise SystemExit(f'execution head drift: {current_head} != {expected_execution_head}')
    all_rows, provenance = build_early_five()
    for city,(branch,path) in COMMITTED_FREEZES.items():
        subprocess.check_call(['git','fetch','--no-tags','origin',f'refs/heads/{branch}:refs/remotes/origin/{branch}'],cwd=REPO)
        fetched_head=git('rev-parse',f'origin/{branch}').strip()
        if fetched_head!=FREEZE_BRANCH_HEADS[city]: raise SystemExit(f'{city}: proof branch head {fetched_head} != {FREEZE_BRANCH_HEADS[city]}')
        art=git_json(f'origin/{branch}',path)
        all_rows[city]=[canonical_case(x) for x in art['selected_cases']]
        lo,hi,before,expected=CITY_CONTRACTS[city]
        got=sha(all_rows[city])
        if got!=expected: raise SystemExit(f'{city}: fingerprint {got} != {expected}')
        provenance[city]={'source':'committed_city_freeze','proof_branch':branch,'proof_branch_head':FREEZE_BRANCH_HEADS[city],
            'artifact_path':path,'case_range':[lo,hi],'eligible_before':before,'prior_ids_listed':0,'prior_ids_intersecting':0,
            'eligible_after':art.get('eligible_count_after_exclusions',before),'accepted_city_sample_sha256':expected,'recomputed_city_sample_sha256':got}
    for city,(run_id,name) in ACTION_FREEZES.items():
        env=os.environ.copy(); env['GH_TOKEN']=os.environ['GITHUB_TOKEN']
        run=json.loads(subprocess.check_output(['gh','run','view',str(run_id),'--json','headSha,status,conclusion'],cwd=REPO,env=env,text=True))
        if run.get('status')!='completed' or run.get('conclusion')!='success': raise SystemExit(f'{city}: accepted action run not successful: {run}')
        if run.get('headSha')!=FREEZE_BRANCH_HEADS[city]: raise SystemExit(f'{city}: action run head {run.get("headSha")} != {FREEZE_BRANCH_HEADS[city]}')
        art=load_action_artifact(city,run_id,name)
        all_rows[city]=[canonical_case(x) for x in art['selected_cases']]
        lo,hi,before,expected=CITY_CONTRACTS[city]
        got=sha(all_rows[city])
        if got!=expected: raise SystemExit(f'{city}: fingerprint {got} != {expected}')
        provenance[city]={'source':'actions_city_freeze','proof_branch':f'historical-blind-freeze-{city}-proof-2026-10-02',
            'proof_branch_head':FREEZE_BRANCH_HEADS[city],'actions_run_id':run_id,'actions_artifact_name':name,
            'case_range':[lo,hi],'eligible_before':before,'prior_ids_listed':0,'prior_ids_intersecting':0,
            'eligible_after':art.get('eligible_count_after_exclusions',before),'accepted_city_sample_sha256':expected,'recomputed_city_sample_sha256':got}
    cases=[]
    for city,(lo,hi,before,expected) in CITY_CONTRACTS.items():
        rows=all_rows[city]
        if [r['case'] for r in rows]!=list(range(lo,hi+1)): raise SystemExit(f'{city}: case range mismatch')
        for row in rows:
            rr=canonical_case(row)
            rr['city_sample_sha256']=expected
            cases.append(rr)
    cases.sort(key=lambda r:r['case'])
    nums=[r['case'] for r in cases]; ids=[r['episode_id'] for r in cases]; pairs=[(r['city_key'],r['episode_id']) for r in cases]
    expected_nums=list(range(41,156))
    city_counts=Counter(r['city_key'] for r in cases)
    guards=OrderedDict([
      ('cities',len(city_counts)),('cases',len(cases)),('cases_per_city_exactly_5',all(city_counts[c]==5 for c in CITY_CONTRACTS)),
      ('case_min',min(nums)),('case_max',max(nums)),('missing_case_numbers',len(set(expected_nums)-set(nums))),
      ('duplicate_case_numbers',len(nums)-len(set(nums))),('duplicate_city_episode_pairs',len(pairs)-len(set(pairs))),
      ('duplicate_selected_episode_ids_globally',len(ids)-len(set(ids))),('unexpected_cities',len(set(city_counts)-set(CITY_CONTRACTS))),
      ('missing_cities',len(set(CITY_CONTRACTS)-set(city_counts))),('non_no_confirmed_event',sum(r['final_outcome']!='NO_CONFIRMED_EVENT' for r in cases)),
      ('city_fingerprint_checks_passed',sum(provenance[c]['recomputed_city_sample_sha256']==CITY_CONTRACTS[c][3] for c in CITY_CONTRACTS)),
      ('city_fingerprint_checks_total',23),('superseded_sumy_selections_present',sum(r['episode_id'] in SUPERSEDED_SUMY for r in cases if r['city_key']=='sumy'))
    ])
    required=[guards['cities']==23,guards['cases']==115,guards['cases_per_city_exactly_5'],guards['case_min']==41,guards['case_max']==155,
      guards['missing_case_numbers']==0,guards['duplicate_case_numbers']==0,guards['duplicate_city_episode_pairs']==0,
      guards['duplicate_selected_episode_ids_globally']==0,guards['unexpected_cities']==0,guards['missing_cities']==0,
      guards['non_no_confirmed_event']==0,guards['city_fingerprint_checks_passed']==23,guards['superseded_sumy_selections_present']==0]
    if not all(required): raise SystemExit('global invariant failure: '+json.dumps(guards))
    manifest_sha=sha([canonical_case(r,True) for r in cases])
    manifest=OrderedDict([
      ('schema_version','historical-23city-blind-sample-manifest-v1'),('verdict','23-CITY 115-CASE BLIND SAMPLE MANIFEST FROZEN'),
      ('seed',SEED),('case_range',[41,155]),('city_count',23),('case_count',115),
      ('foundations',OrderedDict([('frozen_campaign_head',FROZEN_CAMPAIGN_HEAD),('frozen_status_blob_sha',FROZEN_STATUS_BLOB),
        ('offline_repair_final_head',OFFLINE_REPAIR_HEAD),('repaired_five_city_target_state_sha256',REPAIRED_FIVECITY_SHA),
        ('common_23city_repaired_baseline',BASELINE_HEAD),('formalization_acceptance_head',FORMALIZATION_ACCEPTANCE_HEAD)])),
      ('cities',provenance),('cases',cases),('manifest_sha256',manifest_sha),('guards',guards),
      ('mutation_guards',OrderedDict([('RESEARCH PERFORMED','NO'),('PUBLIC WEB','NO'),('SOURCE DISCOVERY','NO'),('CLASSIFIER SEMANTICS CHANGED','NO'),
        ('HISTORICAL EVIDENCE MUTATIONS',0),('CANONICAL ALERT MUTATIONS',0),('DB/NEON','UNTOUCHED'),('INCORPORATION','NO'),('DEPLOY','NO'),('PRODUCTION STATE MUTATIONS',0)])),
      ('proof',OrderedDict([('branch','historical-23city-blind-sample-manifest-proof-2026-10-02'),('execution_head',os.environ.get('GITHUB_SHA','LOCAL')),
        ('construction','bounded checkout verifier; accepted compact freezes/actions artifacts plus repaired five-city deterministic reconstruction')]))
    ])
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(manifest,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    print(json.dumps({'verdict':manifest['verdict'],'cities':23,'cases':115,'case_range':[41,155],'guards':guards,'manifest_sha256':manifest_sha,'artifact_path':str(OUT.relative_to(REPO))},indent=2))

if __name__=='__main__': main()
