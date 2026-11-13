"""Work P: same controlled HTTP ingestion path, synthetic in-memory responses only."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research.casualty_one_time_capture_2026_11_13 import run_capture as r
from research.casualty_one_time_capture_2026_11_13.test_workk import queue, synthetic_env, synthetic_launch
from research.casualty_controlled_capture_preflight_2026_11_13.test_preflight import FakeOpener, Response


def html_page(sentence, *, with_teaser=False):
    prefix = '<nav>Реклама: загинули 99 людей.</nav><aside>Інша подія: загинули 8.</aside>'
    teaser = '<article>Сторонній рекламний анонс</article>' if with_teaser else ''
    main = ('<main><div>' + 'Опис подій у місті та перебігу роботи служб. ' * 7 +
            'Російська ракета атакувала Запоріжжя. ' + sentence + '</div></main>')
    return ('<html><head><script>ignored()</script></head><body>' +
            prefix + teaser + main + '</body></html>').encode('utf-8')


class WorkP(unittest.TestCase):
    def test_01_real_loaded_modules_are_pinned_and_tamper_is_blocked(self):
        r.check_scope(queue())
        self.assertEqual(r.BLOBS['research/casualty_evidence_ingestion_2026_11_13/ingest.py'],
                         '86bc17b1112da1027fca4f0317534c322329b04f')
        self.assertEqual(r.BLOBS['kyiv-air-alerts-grafana/scripts/casualty_auto_review.py'],
                         '76518b35009615b5c29a4455bf0b9c3a3933cab7')
        for path in r.BLOBS:
            with self.subTest(path=path), patch.object(r, 'git', side_effect=lambda *args: '0'*40):
                with self.assertRaisesRegex(RuntimeError, 'PINNED_SOURCE_BLOB_DRIFT'):
                    r.check_scope(queue())

    def test_02_same_controlled_capture_path_mock_http200_through_evidence_json(self):
        plan, template = r.check_scope(queue())
        policy = r.validate_launch(synthetic_launch(), template, queue(), environ=synthetic_env())
        responses = [
            html_page('Загинули двоє людей.', with_teaser=True),
            html_page('Кількість загиблих зросла до трьох.'),
            html_page('Загинули троє людей.'),
        ]
        fake = FakeOpener([Response(200, body=data) for data in responses])
        real_capture_once = r.e._capture_once

        def injected_opener(url, approved, budget):
            return real_capture_once(url, approved, budget, opener=fake)

        with patch.object(r.e, '_capture_once', side_effect=injected_opener):
            with patch.object(r.e.time, 'sleep') as sleep:
                volatile, audit = r.e.controlled_capture(policy, queue(), enabled=True)
        self.assertEqual(len(fake.urls), 3)
        self.assertEqual(audit['requests_used'], 3)
        self.assertTrue(all(x['http_status'] == 200 for x in audit['targets']))
        self.assertEqual(audit['targets'][0]['content_scope'], 'main')
        self.assertEqual(sleep.call_count, 2)
        with tempfile.TemporaryDirectory() as tmp:
            r.retain_results(queue(), plan, volatile, audit, Path(tmp), authorization_id='OFFLINE_MOCK')
            result = json.loads((Path(tmp)/'minimal_capture_facts.json').read_text())
            summary = json.loads((Path(tmp)/'summary.json').read_text())
            preview = json.loads((Path(tmp)/'fact_preview_unverified.json').read_text())
            cards = result['facts']
            self.assertEqual([x['claim_deaths'] for x in cards], [2, 3, 3])
            # Two distinct source reports do not prove one corrected incident.
            # Preserve the observed 2 -> 3 totals, never sum them to 5.
            self.assertEqual(cards[1]['count_kind'], 'single_report_total')
            self.assertNotIn(5, [x['claim_deaths'] for x in cards])
            self.assertTrue(all(x['decision'] == 'NEEDS_REVIEW' for x in cards))
            self.assertTrue(all(x['excerpts'] for x in cards))
            self.assertTrue(all(len(x['text']) <= 170 for c in cards for x in c['excerpts']))
            self.assertIsNone(cards[2]['candidate_id'])
            self.assertEqual(result['official_incidents_automatically_matched'], 0)
            self.assertEqual(summary['automatic_death_credits'], 0)
            self.assertFalse(summary['publication_allowed'])
            self.assertFalse(preview['publication_allowed'])
            self.assertEqual(len(preview['source_decisions']), 3)
            self.assertTrue(all(x['document_sha256'] == hashlib.sha256(data).hexdigest()
                                for x, data in zip(cards, responses)))
            all_json = '\n'.join(x.read_text() for x in Path(tmp).glob('*.json'))
            for body in responses:
                self.assertNotIn(body.decode('utf-8'), all_json)
            for item in volatile['articles'] + volatile['official_articles']:
                self.assertNotIn(item['text'], all_json)
            manifest = json.loads((Path(tmp)/'manifest.json').read_text())
            self.assertEqual(len(manifest['files_sha256']), 4)
            for filename, digest in manifest['files_sha256'].items():
                self.assertEqual(hashlib.sha256((Path(tmp)/filename).read_bytes()).hexdigest(), digest)

    def test_03_unknown_count_unknown_date_and_privacy_marked(self):
        plan, _ = r.check_scope(queue())
        from research.casualty_one_time_capture_2026_11_13.test_workk import mock_inputs
        _, volatile, audit, _ = mock_inputs()
        volatile['articles'][0]['text'] = 'Після удару повідомляють про можливу загибель людей.'
        volatile['articles'][1]['text'] = 'Загинули двоє людей, повідомив свідок Петро Іваненко.'
        volatile['official_articles'][0]['text'] = 'Загинули троє людей.'
        with tempfile.TemporaryDirectory() as tmp:
            r.retain_results(queue(), plan, volatile, audit, Path(tmp), authorization_id='OFFLINE_MOCK')
            cards = json.loads((Path(tmp)/'minimal_capture_facts.json').read_text())['facts']
            self.assertIsNone(cards[0]['claim_deaths'])
            self.assertEqual(cards[0]['decision'], 'NEEDS_REVIEW')
            self.assertIn('PRIVACY_REVIEW_EXCERPT_WITHHELD', cards[1]['reasons'])
            self.assertIn('SHORT_EVIDENCE_PRIVACY_WITHHELD', cards[1]['reasons'])
            self.assertEqual(cards[1]['excerpts'], [])
            self.assertIsNone(cards[2]['attack_date_explicit'])
            self.assertEqual(cards[2]['decision'], 'NEEDS_REVIEW')
            self.assertIsNone(cards[2]['candidate_id'])

    def test_04_no_launch_in_ordinary_tree(self):
        self.assertFalse((r.HERE/'launch.json').exists())
        self.assertEqual(r.LIMITS['max_initial_urls'], 3)
        self.assertEqual(r.LIMITS['max_requests_total'], 6)
        self.assertEqual(r.LIMITS['min_delay_seconds'], 1)
        self.assertEqual(r.LIMITS['max_response_bytes'], 1000000)
        self.assertEqual(r.LIMITS['timeout_seconds'], 15)
        self.assertEqual(r.LIMITS['retries'], 0)
        self.assertEqual(r.LIMITS['authorization_max_hours'], 24)


if __name__ == '__main__':
    unittest.main()
