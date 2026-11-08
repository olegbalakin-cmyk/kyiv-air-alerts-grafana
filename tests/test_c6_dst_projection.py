"""Only new historical correction and UTC regression checks; no live services."""
from __future__ import annotations

from contextlib import ExitStack
import copy
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

from scripts import c6_dst_projection as dst
from scripts import c6_dst_projection_offline as offline


class CorrectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = offline.retained()
        cls.lineage = json.loads(cls.data['projection_lineage.json'])
        proof = json.loads(cls.data['readback_proof.json'])
        cls.binding = {k: proof[k] for k in ('counts', 'table_sha256', 'c2_corpus_sha256')}
        cls.corrected, cls.receipt = dst.apply(cls.lineage, cls.binding)

    def setUp(self):
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(socket.socket, 'connect', side_effect=AssertionError('NO_NETWORK')))
        self.stack.enter_context(patch.object(socket, 'create_connection', side_effect=AssertionError('NO_NETWORK')))

    def test_exact_four_cases_and_integer_arithmetic(self):
        self.assertEqual(len(self.corrected) - len(self.lineage), 4)
        self.assertEqual(dst.duration(self.corrected) - dst.duration(self.lineage), -9059359958)
        self.assertEqual(len(self.receipt['replacement_intervals']), 7)
        self.assertEqual(len(self.receipt['excluded_physical_uids']), 3)
        for key, count, us in [('cherkasy', 1, 256663871), ('kharkiv', 1, -3311259182),
                               ('poltava', 1, -3042657209), ('zhytomyr', 1, -2962107438)]:
            old = [r for r in self.lineage if r['city_key'] == key]
            new = [r for r in self.corrected if r['city_key'] == key]
            self.assertEqual(len(new) - len(old), count)
            self.assertEqual(dst.duration(new) - dst.duration(old), us)

    def test_other_intervals_and_cherkasy_identity_are_exact(self):
        bad = set(self.receipt['excluded_physical_uids'])
        old = sorted([r for r in self.lineage if not set(r['physical_uids']) & bad], key=dst.token)
        new = sorted([r for r in self.corrected if 'correction' not in r], key=dst.token)
        self.assertEqual(old, new)
        uid = 'ff046d6c-fc7e-4cd2-9470-3e5433c3d582'
        self.assertEqual([r for r in old if uid in r['physical_uids']],
                         [r for r in new if uid in r['physical_uids']])

    def test_kyiv_2819_intervals_unchanged(self):
        old = sorted([r for r in self.lineage if r['city_key'] == 'kyiv'], key=dst.token)
        new = sorted([r for r in self.corrected if r['city_key'] == 'kyiv'], key=dst.token)
        self.assertEqual(len(old), 2819); self.assertEqual(old, new)

    def test_provenance_does_not_invent_physical_observations(self):
        for row in self.receipt['replacement_intervals']:
            self.assertEqual(row['physical_uids'], [])
            self.assertFalse(row['correction']['physical_neon_observation'])
            self.assertEqual(row['correction']['version'], dst.VERSION)
        self.assertEqual(self.receipt['physical_neon_observations_created'], 0)
        self.assertFalse(self.receipt['publication_allowed'])

    def test_deterministic_nonmutating_correction(self):
        before = copy.deepcopy(self.lineage)
        self.assertEqual(dst.apply(self.lineage, self.binding), (self.corrected, self.receipt))
        self.assertEqual(before, self.lineage)

    def test_fail_closed_on_each_projection_field_and_row_drift(self):
        for field, value in [('city_key', 'other'), ('start_utc', '2026-10-01T01:00:00Z'),
                             ('end_utc', None), ('physical_uids', []), ('selection', 'other'),
                             ('new_schema_column', True)]:
            with self.subTest(field=field):
                rows = copy.deepcopy(self.lineage); rows[0][field] = value
                with self.assertRaisesRegex(dst.Blocked, 'CORPUS_OR_SCHEMA_DRIFT'):
                    dst.apply(rows, self.binding)
        for rows in (self.lineage[:-1], self.lineage + [self.lineage[0]], self.corrected):
            with self.assertRaises(dst.Blocked): dst.apply(rows, self.binding)

    def test_fail_closed_on_every_bound_table_or_corpus_drift(self):
        for table in self.binding['table_sha256']:
            with self.subTest(table=table):
                binding = copy.deepcopy(self.binding); binding['table_sha256'][table] = '0' * 64
                with self.assertRaisesRegex(dst.Blocked, 'INPUT_CORPUS_OR_SCHEMA_DRIFT'):
                    dst.apply(self.lineage, binding)
        binding = copy.deepcopy(self.binding); binding['c2_corpus_sha256'] = 'changed'
        with self.assertRaises(dst.Blocked): dst.apply(self.lineage, binding)
        binding = copy.deepcopy(self.binding); binding['counts']['episodes'] += 1
        with self.assertRaises(dst.Blocked): dst.apply(self.lineage, binding)

    def test_fail_closed_on_missing_or_modified_evidence_and_unknown_version(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            for path in dst.EVIDENCE:
                target = root / path; target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((dst.ROOT / path).read_bytes())
            for path in dst.EVIDENCE:
                target = root / path; raw = target.read_bytes(); target.write_bytes(raw + b' ')
                with self.assertRaisesRegex(dst.Blocked, 'EVIDENCE_DRIFT'):
                    dst.apply(self.lineage, self.binding, root=root)
                target.unlink()
                with self.assertRaises(FileNotFoundError): dst.apply(self.lineage, self.binding, root=root)
                target.write_bytes(raw)
        with self.assertRaisesRegex(dst.Blocked, 'UNKNOWN_VERSION'):
            dst.apply(self.lineage, self.binding, version='v2')

    def test_offline_default_and_explicit_rollback_restore_all_six_bytes(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            offline.run(Path(os.environ['C6_TEST_SITE']), root / 'default')
            offline.run(Path(os.environ['C6_TEST_SITE']), root / 'rollback', correction=None)
            for name in offline.FILES:
                expected = self.data['candidate/' + name]
                self.assertEqual((root / 'default/candidate' / name).read_bytes(), expected)
                self.assertEqual((root / 'rollback/candidate' / name).read_bytes(), expected)


class UTCUnionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import sys
        sys.path.insert(0, str(Path(os.environ['C6_TEST_SITE']) / 'scripts'))
        spec = importlib.util.spec_from_file_location('dst_regression_bridge', dst.ROOT /
            'kyiv-air-alerts-grafana/scripts/apply_ukrainealarm_bridge.py')
        cls.bridge = importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.bridge)
        cls.Alert = cls.bridge.Alert
        cls.tz = ZoneInfo('Europe/Kyiv')

    def alert(self, start, end):
        return self.Alert(start=dst.utc(start).astimezone(self.tz),
                          end=dst.utc(end).astimezone(self.tz), source='original')

    def pairs(self, alerts):
        return [(a.start.astimezone(timezone.utc), a.end.astimezone(timezone.utc)) for a in alerts]

    def test_all_four_accepted_cases(self):
        readback, _, source = dst.evidence()
        for city in sorted(dst.AFFECTED):
            pairs = [(w['event']['start'], w['event']['end']) for w in source['witnesses']
                     if w['event']['city_key'] == city]
            if city == 'cherkasy':
                v = readback['protected_cherkasy']; pairs.append((v['start_utc'], v['end_utc']))
            inputs = [self.alert(*pair) for pair in reversed(pairs)]
            actual = self.bridge.union_alerts(inputs, 'merged')
            self.assertEqual(self.pairs(actual), sorted((dst.utc(a), dst.utc(b)) for a, b in pairs))
            self.assertTrue(all(a.source == 'merged' for a in actual))

    def test_fold_sort_uses_instants(self):
        alerts = [self.alert('2026-10-25T01:10:00Z', '2026-10-25T01:20:00Z'),
                  self.alert('2026-10-25T00:50:00Z', '2026-10-25T00:55:00Z')]
        self.assertEqual(self.pairs(self.bridge.union_alerts(alerts, 'm')),
                         self.pairs(list(reversed(alerts))))

    def test_end_extension_across_fold(self):
        alerts = [self.alert('2026-10-24T23:00:00Z', '2026-10-25T00:50:00Z'),
                  self.alert('2026-10-25T00:30:00Z', '2026-10-25T01:20:00Z')]
        result = self.bridge.union_alerts(alerts, 'm')
        self.assertEqual(self.pairs(result), [(dst.utc('2026-10-24T23:00:00Z'), dst.utc('2026-10-25T01:20:00Z'))])

    def test_touching_overlap_empty_and_timezone_representation_preserved(self):
        alerts = [self.alert('2026-10-24T20:00:00Z', '2026-10-24T21:00:00Z'),
                  self.alert('2026-10-24T21:00:00Z', '2026-10-24T22:00:00Z')]
        result = self.bridge.union_alerts(alerts, 'm')
        self.assertEqual(len(result), 1)
        self.assertIs(result[0].start.tzinfo, self.tz)
        self.assertEqual(self.bridge.union_alerts([], 'm'), [])


class RendererTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(); cls.addClassCleanup(cls.temp.cleanup)
        cls.output = Path(cls.temp.name) / 'corrected'
        cls.data = offline.retained()
        cls.result = offline.run(Path(os.environ['C6_TEST_SITE']), cls.output, correction=dst.VERSION)
        cls.old = {n: json.loads(cls.data['candidate/' + n]) for n in offline.FILES}
        cls.new = {n: json.loads((cls.output / 'candidate' / n).read_text()) for n in offline.FILES}

    def test_csv_and_frontend_json_shapes_unchanged(self):
        def shape(value):
            if isinstance(value, dict):
                return {k: shape(v) for k, v in value.items() if k != 'historical_dst_projection'}
            if isinstance(value, list):
                return sorted({json.dumps(shape(v), sort_keys=True) for v in value})
            return type(value).__name__
        for name in offline.FILES:
            self.assertEqual(shape(self.old[name]), shape(self.new[name]), name)
        self.assertEqual(self.new['historical-daily-kpi.json'], self.new['dashboard_data.json']['historical_daily_kpi'])
        self.assertFalse(self.result['publication_allowed'])

    def test_kyiv_casualties_and_auxiliary_bytes_preserved(self):
        for name in ('alerts_combined.json', 'kyiv_threat_mix.json', 'sevastopol_events.json'):
            self.assertEqual((self.output / 'candidate' / name).read_bytes(), self.data['candidate/' + name])
        self.assertEqual(len(self.new['alerts_combined.json']), 2819)
        for field in ('casualties', 'casualties_by_city'):
            self.assertEqual(self.old['dashboard_data.json'].get(field), self.new['dashboard_data.json'].get(field))

    def test_other_nineteen_cities_analytics_and_historical_index_preserved(self):
        old, new = self.old['dashboard_data.json'], self.new['dashboard_data.json']
        for key in set(old['cities']) - dst.AFFECTED:
            self.assertEqual(old['cities'][key], new['cities'][key], key)
            self.assertEqual(old['historical_daily_kpi']['cities'][key], new['historical_daily_kpi']['cities'][key], key)
            for section in ('all_cities_table', 'time_of_day_profile'):
                self.assertEqual(old[section]['cities'][key], new[section]['cities'][key], section + ':' + key)
            for section in ('all_cities_table_test', 'time_of_day_heatmap_test'):
                self.assertEqual(self.old['site_derived.json'][section]['cities'][key],
                                 self.new['site_derived.json'][section]['cities'][key], section + ':' + key)

    def test_only_october_25_daily_counts_change_in_four_cities(self):
        old, new = self.old['dashboard_data.json'], self.new['dashboard_data.json']
        for key in dst.AFFECTED:
            a, b = old['cities'][key]['daily28'], new['cities'][key]['daily28']
            self.assertEqual([r for r in a if r['date'] != '2026-10-25'],
                             [r for r in b if r['date'] != '2026-10-25'], key)
            row_a = next(r for r in a if r['date'] == '2026-10-25')
            row_b = next(r for r in b if r['date'] == '2026-10-25')
            self.assertEqual(row_b['alerts_started'] - row_a['alerts_started'], 1, key)
            ha, hb = old['historical_daily_kpi']['cities'][key], new['historical_daily_kpi']['cities'][key]
            self.assertEqual(ha['start'], hb['start']); self.assertEqual(ha['end'], hb['end'])
            changes = [(i, a, b) for i, (a, b) in enumerate(zip(ha['counts'], hb['counts'])) if a != b]
            self.assertEqual(len(changes), 1); self.assertEqual(changes[0][2] - changes[0][1], 1)
            self.assertEqual(ha['status'], hb['status'])


if __name__ == '__main__':
    unittest.main()
