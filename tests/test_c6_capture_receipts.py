"""Offline replay of retained responses, collector hooks and C2/readback binding."""
import ast
import base64
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile

from bs4 import BeautifulSoup
from scripts import c6_history_freshness as h
from scripts import c2_shadow_bundle as c2
from tests import test_c6_history_freshness as fixtures

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / 'research/c6_freshness_receipts_2026_11_09/site-prod-integration.patch'
COLLECTORS = ROOT / 'tests/fixtures/c6_capture_collectors.zip'
capture = h.capture_contract()
UTC = timezone.utc
# Bytes are constructed test fixtures, never physical capture evidence.
KYIV = '<table><tr><td>01:00 07.11.26 Повітряна тривога</td></tr><tr><td>02:00 07.11.26 Відбій тривоги</td></tr></table>'.encode()
SEV = ('<div class="tgme_widget_message_wrap"><div class="tgme_widget_message" data-post="razvozhaev/1">'
       '<time datetime="2026-11-07T00:00:00Z"></time><div class="tgme_widget_message_text">Воздушная тревога!</div></div></div>'
       '<div class="tgme_widget_message_wrap"><div class="tgme_widget_message" data-post="razvozhaev/2">'
       '<time datetime="2026-11-07T01:00:00Z"></time><div class="tgme_widget_message_text">Отбой воздушной тревоги</div></div></div>').encode()
BRIDGE = json.dumps([{'regionId':'9','alarms':[{'alertType':'AIR','startDate':'2026-11-07T00:00:00Z',
                'endDate':'2026-11-07T01:00:00Z'}]}]).encode()


def parser_module(name, source, names, namespace):
    tree = ast.parse(source)
    tree.body = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]
    module = ModuleType(name)
    module.__dict__.update(namespace)
    exec(compile(tree, name, 'exec'), module.__dict__)
    return module


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.HistoryTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.env = {'MULTICITY_CANONICAL_PAYLOAD_PATH':str(self.f.root/'capture-payload.json'),
            'GITHUB_RUN_ID':'123','GITHUB_RUN_ATTEMPT':'1','GITHUB_SHA':'a'*40,'PHASE1_INPUT_SHA':'b'*40}
        self.path = Path(self.env['MULTICITY_CANONICAL_PAYLOAD_PATH'])
        self.path.write_text(json.dumps(self.f.payload))
        self.cp = self.f.root/'capture-checkpoints.json'
        with zipfile.ZipFile(COLLECTORS) as z:
            self.originals = {n:z.read(n).decode() for n in z.namelist()}
        from zoneinfo import ZoneInfo
        tz = ZoneInfo('Europe/Kyiv')
        kyiv = parser_module('update_data', self.originals['update_data.py'],
            {'parse_live_history','_kind_from_text','_parse_live_dt'},
            {'re':re,'datetime':datetime,'BeautifulSoup':BeautifulSoup,'UTC':UTC,
             'Alert':lambda s,e,source:SimpleNamespace(start=s,end=e,source=source),
             'LIVE_DT_RE':re.compile(r'(?P<hm>\d{2}:\d{2})\s+(?P<d>\d{2}\.\d{2}\.\d{2})(?!\d)'),
             'localize_naive':lambda dt:dt.replace(tzinfo=tz)})
        sev = parser_module('add_sevastopol_exact', self.originals['add_sevastopol_exact.py'],
            {'normalize','strict_kind','parse_page','msg_diag','pair_recent'},
            {'re':re,'datetime':datetime,'BeautifulSoup':BeautifulSoup,'UTC':UTC,'CHANNEL':'razvozhaev'})
        modules=patch.dict(sys.modules,{'update_data':kyiv,'add_sevastopol_exact':sev})
        modules.start();self.addCleanup(modules.stop)

    def row(self, city='kyiv', previous=True, continuity=True):
        source=h.INDEPENDENT.get(city,'ukrainealarm_region_history')
        identity=({'url':'https://kyiv.digital/storage/air-alert/stats.html'} if city=='kyiv' else
            {'url':'https://t.me/s/razvozhaev','channel':'razvozhaev'} if city=='sevastopol' else
            {'url':'https://api.ukrainealarm.com/api/v3/alerts/regionHistory','region_id':'9'})
        url=identity['url']+ ('?regionId=9' if 'region_id' in identity else '')
        raw=KYIV if city=='kyiv' else SEV if city=='sevastopol' else BRIDGE
        page={'url':url,'started_at':'2026-11-08T05:59:00Z','captured_at':self.f.checked,
            'body_sha256':hashlib.sha256(raw).hexdigest(),'body_base64':base64.b64encode(raw).decode()}
        fake={'pages':[page],'source_key':source}
        completed=capture.replay(fake)
        prev={'source_key':source,'source_identity':identity,'last_checked_at':'2026-11-08T02:00:00Z'} if previous else None
        return capture.record(city,source,identity,[page],completed,previous=prev,
            continuity=continuity,checkpoint_path=self.cp,env=self.env)

    def modern(self, missing=(), bootstrap=()):
        for city in self.f.keys:
            if city not in missing: self.row(city,previous=city not in bootstrap)
        self.f.payload=json.loads(self.path.read_text()); self.f.pack()
        self.f.proof.update(historical_source_receipts_sha256=h.fingerprint(self.f.payload['historical_source_receipts']),
            same_run_payload_sha256=h.digest(self.f.files['payload.json']),
            capture_run_identity={'github_run_id':123,'github_run_attempt':1,'workflow_sha':'a'*40,'input_sha':'b'*40})
        return self.f.evaluate()

    def verify(self,row):
        return capture.verify(row,city=row['city_key'],source_key=row['source_key'],
            run_identity=capture.identity(self.env),read_at=self.f.read_at)

    def test_21_bridge_and_independent_positive_replay(self):
        r=self.modern()
        self.assertEqual((r['full_receipt_cities'],r['fresh_cities']),(23,23))
        h.require_ready(r);self.assertFalse(r['publication_allowed'])

    def test_independent_missing_are_blocked_without_legacy_fallback(self):
        r=self.modern(missing=('kyiv','sevastopol'))
        self.assertEqual((r['full_receipt_cities'],r['fresh_cities']),(21,21))
        self.assertEqual(r['cities']['kyiv']['reasons'],['MISSING_INDEPENDENT_SOURCE_CAPTURE_CHECKPOINT'])

    def test_bootstrap_retains_capture_but_no_continuity(self):
        r=self.modern(bootstrap=('kyiv','sevastopol'))
        self.assertEqual(r['full_receipt_cities'],21)
        for city in h.INDEPENDENT:
            self.assertFalse(r['cities'][city]['full_receipt_verified'])
            self.assertIn('CAPTURE_HISTORY_CONTINUITY_NOT_PROVEN',r['cities'][city]['reasons'])

    def test_missing_bridge_capture_not_backfilled_from_dashboard(self):
        r=self.modern(missing=(self.f.keys[2],))
        self.assertEqual(r['fresh_cities'],22)

    def test_raw_bytes_normalized_pairs_identity_clock_and_checkpoint_tampering(self):
        original=self.row()
        for mutate in (
            lambda r:r['pages'][0].update(body_base64=base64.b64encode(b'changed').decode()),
            lambda r:r.update(completed_air=[]),
            lambda r:r.update(source_identity={'url':'https://wrong.example'}),
            lambda r:r.update(last_checked_at=self.f.read_at),
            lambda r:r.update(previous_checkpoint=None),
            lambda r:r.update(previous_checked_at=self.f.read_at),
            lambda r:r.update(source_payload_kind='event-date'),
            lambda r:r.update(oldest_fetched_completed_air_start=self.f.read_at)):
            row=copy.deepcopy(original);mutate(row)
            with self.assertRaises(ValueError):self.verify(row)

    def test_rehashed_forged_completed_history_rejected_by_existing_parser(self):
        row=self.row();row['completed_air'][0]['start']='2026-11-01T00:00:00Z'
        row['completed_air_sha256']=capture.fingerprint(row['completed_air'])
        with self.assertRaisesRegex(ValueError,'CAPTURE_REPLAY_MISMATCH'):self.verify(row)

    def test_run_attempt_workflow_and_input_binding(self):
        self.modern()
        original=copy.deepcopy(self.f.payload)
        for key,val in [('github_run_id',124),('github_run_attempt',2),('workflow_sha','c'*40),('input_sha','c'*40)]:
            self.f.payload=copy.deepcopy(original)
            self.f.payload['historical_source_receipts']['kyiv'][key]=val;self.f.pack()
            with self.assertRaisesRegex(ValueError,'CAPTURE_RUN_MISMATCH'):self.f.bind()

    def test_missing_readback_metadata_and_different_corpus_fail_closed(self):
        self.modern()
        original=copy.deepcopy(self.f.proof)
        for key in ('historical_source_receipts_sha256','same_run_payload_sha256','capture_run_identity','c2_corpus_sha256'):
            self.f.proof=copy.deepcopy(original);self.f.proof.pop(key)
            with self.assertRaises(ValueError):self.f.bind()

    def test_missing_receipts_or_contract_cannot_downgrade(self):
        self.modern(); original=copy.deepcopy(self.f.payload)
        for key in ('historical_source_receipts','history_capture_contract'):
            self.f.payload=copy.deepcopy(original);self.f.payload.pop(key);self.f.pack()
            with self.assertRaises(ValueError):self.f.bind()

    def test_36h_gate_uses_oldest_page_capture(self):
        self.modern(); binding=self.f.bind()
        self.assertEqual(self.f.evaluate(binding,h.utc(self.f.checked)+timedelta(hours=36))['fresh_cities'],23)
        self.assertEqual(self.f.evaluate(binding,h.utc(self.f.checked)+timedelta(hours=36,microseconds=1))['fresh_cities'],0)

    def test_failed_overlap_does_not_advance_prior_checkpoint(self):
        self.row(previous=False)
        old=self.cp.read_bytes()
        self.row(continuity=False)
        self.assertEqual(self.cp.read_bytes(),old)

    def test_capture_off_does_not_read_or_write_files(self):
        result=capture.record('kyiv','kyiv_digital',{},[],[],checkpoint_path=self.cp,env={})
        self.assertIsNone(result);self.assertFalse(self.cp.exists())

    def test_modern_orchestration_json_contract_and_explicit_missing_capture_block(self):
        self.modern();r=self.f.execute()
        self.assertEqual((r['status'],len(r['candidate_files'])),('PASS',6))
        self.assertFalse(r['publication_allowed'])
        report=json.loads((self.f.root/'output/source_gates.json').read_text())
        self.assertTrue(report['kyiv']['full_historical_receipt_verified'])
        retained=json.loads((self.f.root/'output/historical_source_receipts.json').read_text())
        self.assertEqual(retained,self.f.payload['historical_source_receipts'])

    def test_export_retains_exact_payload_source_bytes_and_summary(self):
        self.modern();site=self.f.root/'site';(site/'data').mkdir(parents=True)
        for name in c2.SITE_DATA:
            raw=self.f.files['site_data/'+name];(site/'data'/name).write_bytes(raw)
        for name in ('receipt.json','status.json','payload.json'):
            (self.f.root/name).write_bytes(self.f.files[name])
        r=c2.export_bundle(enabled='true',site=site,receipt_path=self.f.root/'receipt.json',
            status_path=self.f.root/'status.json',payload_path=self.f.root/'payload.json',output=self.f.root/'export',
            run_id=123,run_attempt=1,workflow_sha='a'*40,input_sha='b'*40,db_branch='br-test',
            writer_url='postgresql://ep-example.c-7.us-east-2.aws.neon.tech/neondb',verifier=lambda p:self.f.receipt)
        with zipfile.ZipFile(self.f.root/'export/c2-shadow-inputs.zip') as z:
            self.assertEqual(z.read('payload.json'),self.f.files['payload.json'])
            self.assertEqual(len(json.loads(z.read('manifest.json'))['historical_capture_receipts']['complete_cities']),23)
        self.assertEqual(r['status'],'EXPORTED')

    def test_collector_patch_applies_to_verified_production_blobs_and_compiles(self):
        expected={'update_data.py':'cebc2b455fb08ee16e03b9e4fcdb17aa2d9d6833',
            'apply_ukrainealarm_bridge.py':'8b95c4b508b9a473240889603f593e399cf8815d',
            'add_sevastopol_exact.py':'e4c091a677622eb28e504b0592a89e4d92d5fe02'}
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);scripts=root/'kyiv-air-alerts-grafana/scripts';scripts.mkdir(parents=True)
            for name,source in self.originals.items():
                raw=source.encode();got=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
                self.assertEqual(got,expected[name]);(scripts/name).write_bytes(raw)
            subprocess.run(['git','apply','--check',str(PATCH)],cwd=root,check=True,capture_output=True)
            subprocess.run(['git','apply',str(PATCH)],cwd=root,check=True,capture_output=True)
            for path in scripts.glob('*.py'):compile(path.read_text(),str(path),'exec')
            bridge=(scripts/'apply_ukrainealarm_bridge.py').read_text()
            module=parser_module('bridge_hook',bridge,{'history_rows'},
                {'UkraineAlarmClient':object,'datetime':datetime,'UTC':UTC,'HISTORY_URL':'https://api.ukrainealarm.com/api/v3/alerts/regionHistory',
                 'history_capture':capture,'parse_dt':lambda s:h.utc(s) if s else None})
            response=SimpleNamespace(content=BRIDGE,json=lambda:json.loads(BRIDGE))
            client=SimpleNamespace(get=Mock(return_value=response));pages=[]
            rows=module.history_rows(client,'9','test',capture=pages)
            self.assertEqual(len(rows),1);self.assertEqual(len(pages),1);client.get.assert_called_once()

    def patched_collectors(self):
        root=self.f.root/'patched'; scripts=root/'kyiv-air-alerts-grafana/scripts';scripts.mkdir(parents=True)
        for name,source in self.originals.items():(scripts/name).write_text(source)
        subprocess.run(['git','apply',str(PATCH)],cwd=root,check=True,capture_output=True)
        return {p.name:p.read_text() for p in scripts.glob('*.py')}

    def test_kyiv_collector_captures_existing_response_without_extra_http(self):
        source=self.patched_collectors()['update_data.py']
        response=SimpleNamespace(content=KYIV,text=KYIV.decode(),raise_for_status=Mock())
        session=SimpleNamespace(get=Mock(return_value=response))
        parser=sys.modules['update_data'];alerts,events=parser.parse_live_history(KYIV.decode())
        class StopAfterReceipt(Exception):pass
        module=parser_module('kyiv_hook',source,{'main'},dict(
            DATA_DIR=self.f.root/'data',http_session=lambda:session,
            load_historical_base=lambda _: (alerts,'municipal_open_data',None),
            LIVE_HISTORY_URL='https://kyiv.digital/storage/air-alert/stats.html',
            OFFICIAL_JSON_URL='fixture',datetime=datetime,UTC=UTC,TZ=UTC,
            parse_live_history=parser.parse_live_history,merge_sources=lambda a,b:(a,0),
            multicity_shadow_payload=SimpleNamespace(record_city_alerts=Mock()),
            history_capture=capture,build_outputs=Mock(side_effect=StopAfterReceipt)))
        with patch.dict('os.environ',self.env),patch.object(capture,'CHECKPOINTS',self.cp):
            with self.assertRaises(StopAfterReceipt):module.main()
        session.get.assert_called_once()
        row=json.loads(self.path.read_text())['historical_source_receipts']['kyiv']
        self.assertFalse(row['continuity_verified'])
        self.assertEqual(row['pages'][0]['body_sha256'],hashlib.sha256(KYIV).hexdigest())
        self.assertTrue(self.cp.exists())

    def test_sevastopol_collector_retains_pages_and_real_pairs_with_no_extra_http(self):
        source=self.patched_collectors()['add_sevastopol_exact.py']
        parser=sys.modules['add_sevastopol_exact']
        response=lambda raw:SimpleNamespace(content=raw,text=raw.decode(),raise_for_status=Mock())
        session=SimpleNamespace(headers={},get=Mock(side_effect=[response(SEV),response(b'')]))
        events=self.f.root/'events.json';events.write_text(json.dumps({'pairs':[],'meta':{}}))
        class StopAfterReceipt(Exception):pass
        module=parser_module('sev_hook',source,{'fetch_recent_messages','update_event_store','main'},dict(
            datetime=datetime,UTC=UTC,TZ=UTC,timedelta=timedelta,LOOKBACK_DAYS=21,
            requests=SimpleNamespace(Session=lambda:session),HEADERS={},SOURCE_URL='https://t.me/s/razvozhaev',
            CHANNEL='razvozhaev',CITY_KEY='sevastopol',parse_page=parser.parse_page,pair_recent=parser.pair_recent,
            history_capture=capture,time=SimpleNamespace(sleep=Mock()),EVENTS_FILE=events,json=json,
            apply_corrections=lambda current,anomalies:([],anomalies),
            multicity_shadow_payload=SimpleNamespace(record_city_alerts=Mock()),
            Alert=lambda **kwargs:SimpleNamespace(**kwargs),build_city_output=Mock(side_effect=StopAfterReceipt)))
        with patch.dict('os.environ',self.env),patch.object(capture,'CHECKPOINTS',self.cp):
            with self.assertRaises(StopAfterReceipt):module.main()
        self.assertEqual(session.get.call_count,2)
        row=json.loads(self.path.read_text())['historical_source_receipts']['sevastopol']
        self.assertEqual((len(row['pages']),len(row['completed_air'])),(2,1))
        self.assertFalse(row['continuity_verified'])
        self.assertNotIn('body_base64',events.read_text())

    def test_next_regular_cycle_can_use_independent_bootstrap_checkpoint(self):
        row=self.row(previous=False)
        pages=copy.deepcopy(row['pages'])
        pages[0].update(started_at='2026-11-08T06:59:00Z',captured_at=self.f.read_at)
        second=capture.record('kyiv',row['source_key'],row['source_identity'],pages,row['completed_air'],
            checkpoint_path=self.cp,env=self.env)
        self.assertTrue(self.verify(second))
        self.assertEqual(second['previous_checkpoint']['source_sha256'],row['source_sha256'])

    def test_modern_receipts_require_exact_frozen_bundle_before_generation(self):
        self.modern()
        with self.assertRaisesRegex(ValueError,'CAPTURE_RECEIPTS_REQUIRE_HASHED_SAME_RUN_BUNDLE'):
            self.f.execute(history_bundle=None,history_bundle_sha256=None)
        self.f.generate.assert_not_called()
        self.assertFalse((self.f.root/'output/candidate').exists())

    def test_only_exact_receipt_hook_variants_pass_existing_builder_gate(self):
        from scripts import neon_json_shadow_generator as generator
        patched=self.patched_collectors()
        for name,source in patched.items():
            path='scripts/'+name;old,new=generator.CAPTURE_HOOK_BLOBS[path]
            self.assertTrue(generator.accepted_builder_blob(path,self.originals[name].encode(),old))
            self.assertTrue(generator.accepted_builder_blob(path,source.encode(),old))
            self.assertFalse(generator.accepted_builder_blob(path,(source+'# drift\n').encode(),old))
            self.assertFalse(generator.accepted_builder_blob('scripts/other.py',source.encode(),old))

    def test_direct_cli_history_import_from_site_working_directory(self):
        from scripts import neon_json_shadow as shadow
        script=ROOT/'scripts/neon_json_shadow.py'
        code="import importlib.util; s=importlib.util.spec_from_file_location('shadow', " + repr(str(script)) + "); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); assert m.load_history().FRESH_AFTER_HOURS == 36"
        subprocess.run([sys.executable,'-I','-c',code],cwd=self.f.root,check=True,capture_output=True)
