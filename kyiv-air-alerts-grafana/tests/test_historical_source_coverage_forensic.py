import importlib.util
import sys
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("forensic", HERE / "audit_historical_source_coverage.py")
M = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = M
SPEC.loader.exec_module(M)


def sh(cwd, *args):
    p = subprocess.run(list(args), cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode:
        raise RuntimeError(p.stderr)
    return p.stdout.strip()


class ClassificationTests(unittest.TestCase):
    def test_complete_status_plus_narrow_is_not_complete(self):
        self.assertEqual(M.classify_slice('status="complete"; narrow exact-city search', True, 'complete'), 'PARTIAL')

    def test_inaccessible_input_is_blocked(self):
        txt = 'upstream historical episode rows could not be re-enumerated through the connector because the source blob exceeds its size limit'
        self.assertEqual(M.classify_slice(txt, True, 'complete'), 'BLOCKED')

    def test_source_not_covered_miss_prevents_complete_city(self):
        self.assertEqual(M.classify_city_search(['PROVEN_COMPLETE'], True, False, True), 'PARTIAL')

    def test_dimensions_remain_separate(self):
        parents = [
            {'frozen_denominator': '5', 'city_frozen_denominator': '10'},
            {'frozen_denominator': '5', 'city_frozen_denominator': '10'},
        ]
        final = {'frozen_denominator': 10, 'qa': {'denominators_verified': True, 'parts_sum_to_full_denominator': True}}
        replay = {'expected_alert_episodes': 10, 'reconstructed_alert_episodes': 10}
        self.assertEqual(M.canonical_coverage(parents, final, replay), 'PROVEN_COMPLETE')
        self.assertEqual(M.classify_city_search(['PARTIAL', 'PARTIAL'], False, False, True), 'PARTIAL')

    def test_retrieval_failure_never_becomes_negative_complete(self):
        self.assertNotEqual(M.classify_slice('source input inaccessible', True, 'complete'), 'PROVEN_COMPLETE')


class HistoryLookupTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.repo = Path(self.td.name)
        sh(self.repo, 'git', 'init', '-q')
        sh(self.repo, 'git', 'config', 'user.email', 'qa@example.test')
        sh(self.repo, 'git', 'config', 'user.name', 'QA')

    def tearDown(self):
        self.td.cleanup()

    def test_deleted_historical_blob_is_discoverable(self):
        p = self.repo / 'research' / 'kherson_old_blind_qa.json'
        p.parent.mkdir(parents=True)
        p.write_text('{"city":"kherson","decision":"CONFIRMED_FALSE_NEGATIVE","failure_stage":"SOURCE_NOT_COVERED"}\n')
        sh(self.repo, 'git', 'add', '.')
        sh(self.repo, 'git', 'commit', '-qm', 'add old qa')
        p.unlink()
        sh(self.repo, 'git', 'add', '-u')
        sh(self.repo, 'git', 'commit', '-qm', 'delete old qa')
        head = sh(self.repo, 'git', 'rev-parse', 'HEAD')
        rf = M.RepoForensics(self.repo, head)
        rows = rf.historical_blobs('kherson')
        self.assertTrue(any('CONFIRMED_FALSE_NEGATIVE' in text for _, _, text in rows))

    def test_slice_city_discovery(self):
        path = self.repo / M.SLICE_CSV
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            'task_id,city_key,city_label,part,parts_total,episode_start_date_from,episode_start_date_to,frozen_denominator,city_frozen_denominator,status\n'
            'kherson-P1,kherson,Херсон,1,1,2026-01-01,2026-01-31,10,10,complete\n'
            'kyiv-P1,kyiv,Київ,1,1,2026-01-01,2026-01-31,20,20,complete\n', encoding='utf-8')
        for rel, content in [(M.SUBSLICE_CSV, 'task_id,parent_task_id,city_key\n'), (M.REPAIR_CSV, 'task_id,parent_task_id,city_key\n')]:
            f = self.repo / rel; f.parent.mkdir(parents=True, exist_ok=True); f.write_text(content)
        sh(self.repo, 'git', 'add', '.')
        sh(self.repo, 'git', 'commit', '-qm', 'tables')
        head = sh(self.repo, 'git', 'rev-parse', 'HEAD')
        rf = M.RepoForensics(self.repo, head)
        parents, _, _ = M.load_slice_tables(rf, 'kherson')
        self.assertEqual([x['task_id'] for x in parents], ['kherson-P1'])


class CalibrationAndAggregationTests(unittest.TestCase):
    def kherson(self):
        return {
            'city': 'kherson', 'input_head': 'abc', 'canonical_episodes': 1412,
            'original_strict': 9, 'current_strict': 2,
            'canonical_coverage': 'PROVEN_COMPLETE', 'search_coverage': 'PARTIAL',
            'result_retention': 'NOT_PROVEN', 'strict_adjudication': 'PROVEN_COMPLETE',
            'blind_qa_confirmed_misses': 1, 'source_not_covered_misses': 1,
            'reaudit_needed': True, 'recommended_scope': 'bounded',
            'slices': [
                {'part':'P1','search_coverage':'PARTIAL'},
                {'part':'P2','search_coverage':'BLOCKED'},
                {'part':'P3','search_coverage':'PARTIAL'},
            ]
        }

    def test_kherson_fixture_passes(self):
        ok, errors = M.kherson_calibration(self.kherson())
        self.assertTrue(ok, errors)

    def test_kherson_wrong_slice_fails(self):
        x = self.kherson(); x['slices'][1]['search_coverage'] = 'PARTIAL'
        ok, errors = M.kherson_calibration(x)
        self.assertFalse(ok)
        self.assertTrue(any('P2' in e for e in errors))

    def test_aggregation_orders_six_cities(self):
        with tempfile.TemporaryDirectory() as td:
            inp = Path(td) / 'in'; out = Path(td) / 'out'; inp.mkdir()
            for c in M.TARGET_CITIES:
                r = self.kherson().copy()
                r['city'] = c
                if c != 'kherson':
                    r['canonical_episodes'] = 100
                    r['original_strict'] = 5
                    r['current_strict'] = 5
                    r['canonical_coverage'] = 'PROVEN_COMPLETE'
                    r['search_coverage'] = 'PARTIAL'
                    r['result_retention'] = 'NOT_PROVEN'
                    r['strict_adjudication'] = 'PROVEN_COMPLETE'
                    r['slices'] = [{'part':'P1','search_coverage':'PARTIAL'}]
                (inp / f'{c}.json').write_text(json.dumps(r))
                (inp / f'{c}.md').write_text(c)
            summary, ok = M.aggregate(inp, out, 'abc', 'CLEAN')
            self.assertTrue(ok)
            self.assertEqual([r['city'] for r in summary['cities']], M.TARGET_CITIES)
            self.assertTrue((out / 'summary.csv').exists())
            self.assertTrue((out / 'manifest.json').exists())


if __name__ == '__main__':
    unittest.main()
