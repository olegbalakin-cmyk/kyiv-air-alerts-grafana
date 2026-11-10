"""Meaningful safety cases: real controls plus adversarial offline fixtures."""
import copy
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from casualty_auto_review import (FACTS, article_key, extract_cached_reports, fingerprint,
                                  incident_id, prepare, run_offline)
from review_casualty_candidates import REVISION_FIELDS

BASE = {'dnipro': {'through': '2026-09-18'}}


def candidate(cid='one', title='Удар у Дніпрі', **kw):
    return dict(candidate_id=cid, city_key='dnipro', city='Дніпро', status='needs_review',
                title=title, snippet='', url='https://suspilne.media/dnipro/'+cid,
                publisher_url='https://suspilne.media', published_at='2026-11-03T10:00:00Z', **kw)


def report(cs, total=2, **kw):
    facts = dict.fromkeys([*FACTS, 'attack_date', 'incident_identity', 'death_count'], True)
    r = {'candidate_ids': [c['candidate_id'] for c in cs],
         'candidate_fingerprints': {c['candidate_id']: fingerprint(c) for c in cs},
         'incident': {'city_key': 'dnipro', 'attack_date': '2026-11-03',
                      'place': 'street-1', 'attack_slot': '08:00', 'attack_type': 'missile'},
         'facts': facts, 'count': {'kind': 'total', 'value': total},
         'observed_at': '2026-11-03',
         'sources': [{'url': 'https://suspilne.media/dnipro/test', 'origin_id': 'dsns',
                      'basis': 'SYNTHETIC explicit civilian-city-missile-total evidence', 'supports': list(facts)},
                     {'url': 'https://npu.gov.ua/news/test', 'origin_id': 'police',
                      'basis': 'SYNTHETIC separate primary confirmation', 'supports': list(facts)}],
         'provenance': {'kind': 'SYNTHETIC_TEST_ONLY'}}
    r.update(kw)
    return r


class ProposalTests(unittest.TestCase):
    def test_ready_and_format(self):
        c = candidate(); out = prepare([c], [], [report([c])], BASE)
        self.assertEqual(out['summary']['auto_ready'], 1)
        self.assertEqual(out['proposals'][0]['deaths_delta'], '2')
        self.assertEqual(set(out['proposals'][0]), set(REVISION_FIELDS))
        self.assertFalse(out['summary']['publication_allowed'])

    def test_titles_never_proof(self):
        c = candidate(title='Російська ракета вбила 3 цивільних у Дніпрі 3 листопада')
        out = prepare([c], [], [], BASE)
        self.assertEqual(out['proposals'], [])
        self.assertEqual(out['summary']['needs_review'], 1)

    def test_syndicated_domains_one_origin(self):
        c=candidate(); r=report([c]); r['sources'][1]['origin_id']='dsns'
        self.assertEqual(prepare([c],[],[r],BASE)['summary']['auto_ready'],0)

    def test_same_document_cannot_be_two_origins(self):
        c=candidate(); r=report([c]); r['sources'][1]['url']=r['sources'][0]['url']
        self.assertEqual(prepare([c],[],[r],BASE)['summary']['auto_ready'],0)

    def test_duplicate_messages_one_total(self):
        cs=[candidate('a'),candidate('b')]; r=report(cs)
        out=prepare(cs,[],[r],BASE)
        self.assertEqual(len(out['events']),1)
        self.assertEqual(out['summary']['duplicate_publication_excess'],1)
        self.assertEqual(out['proposals'][0]['deaths_delta'],'2')
        self.assertEqual(len(out['events'][0]['messages']),2)

    def test_same_title_different_days(self):
        a,b=candidate('a'),candidate('b'); b['published_at']='2026-11-04T10:00:00Z'
        self.assertNotEqual(article_key(a), article_key(b))
        self.assertEqual(len(prepare([a,b],[],[],BASE)['events']),2)

    def test_two_attacks_same_day(self):
        a,b=candidate('a'),candidate('b'); r1,r2=report([a]),report([b])
        r2['incident']['attack_slot']='21:00'
        out=prepare([a,b],[],[r1,r2],BASE)
        self.assertEqual(len(out['events']),2)
        self.assertEqual(len(out['proposals']),2)
        self.assertNotEqual(out['proposals'][0]['record_id'],out['proposals'][1]['record_id'])

    def test_two_to_three_is_plus_one(self):
        c=candidate(); first=prepare([c],[],[report([c])],BASE)['proposals']
        out=prepare([c],first,[report([c],3)],BASE)
        self.assertEqual(out['proposals'][0]['deaths_delta'],'1')
        replay=prepare([c],first+out['proposals'],[report([c],3)],BASE)
        self.assertEqual(replay['proposals'],[])
        self.assertEqual(replay['events'][0]['action'],'ALREADY_ACCOUNTED')

    def test_repeated_proposal_suppressed(self):
        c=candidate(); r=report([c]); first=prepare([c],[],[r],BASE)
        again=prepare([c],[],[r],BASE,first['proposals'])
        self.assertEqual(again['proposals'],[])
        self.assertEqual(again['summary']['prior_proposals_suppressed'],1)

    def test_pending_two_then_three_reserves_only_one_more(self):
        c=candidate(); pending=prepare([c],[],[report([c],2)],BASE)['proposals']
        out=prepare([c],[],[report([c],3)],BASE,pending)
        self.assertEqual(out['proposals'][0]['deaths_delta'],'1')
        again=prepare([c],[],[report([c],3)],BASE,pending+out['proposals'])
        self.assertFalse(again['proposals'])
        # When a reserved row is applied it must not be subtracted twice.
        applied=prepare([c],pending,[report([c],3)],BASE,pending)
        self.assertEqual(applied['proposals'][0]['deaths_delta'],'1')

    def test_forged_existing_human_confirmation_refused(self):
        c=candidate(); r=report([c]); r['provenance']={'kind':'existing_confirmed_disposition','record_id':'fake'}
        with self.assertRaises(ValueError): prepare([c],[],[r],BASE)

    def test_permutation_stable(self):
        cs=[candidate('a'),candidate('b')]; r=report(cs)
        self.assertEqual(prepare(cs,[],[r],BASE),prepare(cs[::-1],[],[r],BASE))

    def test_downward_retraction_held(self):
        c=candidate(); rows=prepare([c],[],[report([c],3)],BASE)['proposals']
        out=prepare([c],rows,[report([c],2)],BASE)
        self.assertIn('COUNT_BELOW_ALREADY_ACCOUNTED',out['events'][0]['reasons'])
        self.assertFalse(out['proposals'])

    def test_ambiguous_legacy_same_day(self):
        c=candidate(); row=prepare([c],[],[report([c])],BASE)['proposals'][0]
        row.update(record_id='legacy-other',note='',candidate_ids='someone',source_url='https://npu.gov.ua/other')
        out=prepare([c],[row],[report([c],3)],BASE)
        self.assertIn('UNBOUND_SAME_DAY_LEDGER_RECORD',out['events'][0]['reasons'])

    def test_same_regional_url_different_tag_not_subtracted(self):
        c=candidate(); r=report([c]); row=prepare([c],[],[r],BASE)['proposals'][0]
        row['note']='event_id=some-other-incident'; row['candidate_ids']='unrelated'
        out=prepare([c],[row],[r],BASE)
        self.assertEqual(out['proposals'][0]['deaths_delta'],'2')

    def test_baseline_covered_month_held(self):
        c=candidate(); out=prepare([c],[],[report([c])],{'dnipro':{'through':'2026-11-30'}})
        self.assertIn('BASELINE_EVENT_ALLOCATION_UNKNOWN',out['events'][0]['reasons'])

    def test_missing_baseline_held(self):
        c=candidate(); self.assertFalse(prepare([c],[],[report([c])],{})['proposals'])

    def test_military_obituary_held_even_with_bad_annotation(self):
        c=candidate(title='У Дніпрі поховали військового, який загинув на фронті')
        out=prepare([c],[],[report([c])],BASE)
        self.assertIn('MILITARY_OBITUARY_OR_MIXED_STATUS',out['events'][0]['reasons'])

    def test_unknown_civilian_and_boundary(self):
        c=candidate(); r=report([c]); r['facts'].update(civilian=None,city_boundary=None)
        e=prepare([c],[],[r],BASE)['events'][0]
        self.assertIn('CIVILIAN_UNKNOWN',e['reasons']); self.assertIn('CITY_BOUNDARY_UNKNOWN',e['reasons'])

    def test_late_increment_not_new_total(self):
        c=candidate(); r=report([c],1); r['count']['kind']='increment'
        e=prepare([c],[],[r],BASE)['events'][0]
        self.assertIn('INCREMENT_WITHOUT_VERIFIED_EVENT_TOTAL',e['reasons'])

    def test_conflicting_counts_held(self):
        a,b=candidate('a'),candidate('b'); r1,r2=report([a],2),report([b],3)
        e=prepare([a,b],[],[r1,r2],BASE)['events'][0]
        self.assertIn('TOTAL_DEATHS_UNKNOWN_OR_CONFLICTING',e['reasons'])

    def test_stale_evidence_rejected(self):
        c=candidate(); r=report([c]); c['title']='edited'
        with self.assertRaisesRegex(ValueError,'Stale'): prepare([c],[],[r],BASE)

    def test_conflicting_incident_links_no_auto(self):
        c=candidate(); a,b=report([c]),report([c]); b['incident']['attack_slot']='21:00'
        out=prepare([c],[],[a,b],BASE)
        self.assertEqual(out['summary']['auto_ready'],0)
        self.assertIn('CONFLICTING_INCIDENT_LINKS',out['events'][0]['reasons'])

    def test_retained_text_rules_no_fact_labels(self):
        a,b=candidate('a'),candidate('b')
        text='У межах міста Дніпро російський ракетний удар стався 2026-11-03 о 08:00. За адресою Тестова, 1. Загинули 2 цивільних.'
        articles=[{'candidate_id':a['candidate_id'],'url':'https://suspilne.media/test',
                   'text':text+' Повідомляє ДСНС.', 'observed_at':'2026-11-03'},
                  {'candidate_id':b['candidate_id'],'url':'https://npu.gov.ua/test',
                   'text':text+' Повідомляє Національна поліція.', 'observed_at':'2026-11-03'}]
        reports=extract_cached_reports([a,b],articles)
        out=prepare([a,b],[],reports,BASE)
        self.assertEqual(len(out['proposals']),1)
        self.assertEqual(out['proposals'][0]['deaths_delta'],'2')
        articles[1]['text']=articles[0]['text']
        # One attributed DSNS report now suffices for shadow; duplicated text
        # must still contribute only one total, never two independent origins.
        dupe=prepare([a,b],[],extract_cached_reports([a,b],articles),BASE)
        self.assertEqual(len(dupe['proposals']),1)
        self.assertEqual(dupe['proposals'][0]['deaths_delta'],'2')

    def test_raw_text_injuries_not_deaths(self):
        c=candidate(); article={'candidate_id':'one','url':'https://suspilne.media/test','observed_at':'2026-11-03',
          'text':'У межах міста Дніпро російський ракетний удар стався 2026-11-03 о 08:00. За адресою Тестова, 1. Поранені 3 цивільних. ДСНС.'}
        rs=extract_cached_reports([c],[article])
        self.assertFalse(prepare([c],[],rs,BASE)['proposals'])

    def test_negated_and_uncertain_death_reports(self):
        c=candidate()
        for sentence in ['Не загинули 2 цивільних.', 'Ймовірно загинули 2 цивільних.',
                         'Загинули 2 цивільних — інформацію не підтверджено.']:
            a={'candidate_id':'one','url':'https://suspilne.media/test','observed_at':'2026-11-03',
               'text':'У межах міста Дніпро російський ракетний удар стався 2026-11-03 о 08:00. За адресою Тестова, 1. ДСНС. '+sentence}
            rs=extract_cached_reports([c],[a])
            self.assertTrue(not rs or rs[0]['count']['value'] is None,sentence)
            self.assertFalse(prepare([c],[],rs,BASE)['proposals'])

    def test_unknown_city_rejected(self):
        c=candidate(); c['city_key']='province'
        with self.assertRaisesRegex(ValueError,'city_key'): prepare([c],[],[],BASE)

    def test_output_and_inputs_unchanged(self):
        c=candidate(); r=report([c])
        with tempfile.TemporaryDirectory() as td:
            p=Path(td); q=p/'queue.json'; rev=p/'revisions.csv'; ev=p/'evidence.json'; base=p/'base.json'
            q.write_text(json.dumps([c])); rev.write_text(','.join(REVISION_FIELDS)+'\n')
            ev.write_text(json.dumps({'reports':[r]})); base.write_text(json.dumps(BASE))
            before={x:x.read_bytes() for x in [q,rev,ev,base]}
            self.assertEqual(run_offline(q,rev,ev,base,p/'out')['unique_proposals'],1)
            for x,data in before.items(): self.assertEqual(x.read_bytes(),data)
            with self.assertRaises(ValueError): run_offline(q,rev,ev,base,p)

    def test_practical_presumed_civilian_with_one_official_source(self):
        c = candidate()
        text = ('Вранці 3 листопада РФ атакувала Дніпро ракетами. '
                'У Дніпрі загинули двоє людей. Про це повідомили в ДСНС.')
        article = {'candidate_id': c['candidate_id'], 'url': c['url'],
                   'text': text, 'observed_at': '2026-11-03'}
        r = extract_cached_reports([c], [article])
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]['civilian_status'], 'civilian_presumed')
        out = prepare([c], [], r, BASE)
        self.assertEqual([p['deaths_delta'] for p in out['proposals']], ['2'])

    def test_explicit_military_victims_are_held(self):
        c = candidate()
        text = ('Вранці 3 листопада РФ атакувала Дніпро ракетами. '
                'У Дніпрі загинули двоє людей. Серед загиблих військовослужбовці. '
                'Про це повідомили в ДСНС.')
        r = extract_cached_reports([c], [{'candidate_id': c['candidate_id'],
                  'url': c['url'], 'text': text, 'observed_at': '2026-11-03'}])
        self.assertTrue(r)
        self.assertEqual(r[0]['civilian_status'], 'civilian_ambiguous')
        self.assertIn('CIVILIAN_AMBIGUOUS', prepare([c], [], r, BASE)['events'][0]['reasons'])

    def test_military_object_unknown_victims_are_held_not_excluded(self):
        c = candidate()
        text = ('Вранці 3 листопада РФ атакувала Дніпро ракетами. '
                'На військовий об’єкт припав удар. У Дніпрі загинули двоє людей. '
                'За даними ДСНС, це сталося вранці.')
        r = extract_cached_reports([c], [{'candidate_id': c['candidate_id'],
                  'url': c['url'], 'text': text, 'observed_at': '2026-11-03'}])
        self.assertTrue(r)
        self.assertEqual(r[0]['civilian_status'], 'civilian_ambiguous')
        out = prepare([c], [], r, BASE)
        self.assertFalse(out['proposals'])
        self.assertEqual(out['events'][0]['category'], 'NEEDS_REVIEW')

    def test_late_death_without_event_total_not_assumed_additive(self):
        c = candidate()
        text = ('Вранці 3 листопада РФ атакувала Дніпро ракетами. '
                'У лікарні згодом помер один чоловік. Про це повідомили в ДСНС.')
        r = extract_cached_reports([c], [{'candidate_id': c['candidate_id'],
                  'url': c['url'], 'text': text, 'observed_at': '2026-11-05'}])
        self.assertFalse(prepare([c], [], r, BASE)['proposals'])

    def test_outside_city_with_dead_not_auto_ready(self):
        c = candidate()
        text = ('Вранці 3 листопада РФ атакувала передмістя Дніпра ракетами. '
                'За межами міста загинули двоє людей. Про це повідомили в ДСНС.')
        r = extract_cached_reports([c], [{'candidate_id': c['candidate_id'],
                  'url': c['url'], 'text': text, 'observed_at': '2026-11-03'}])
        self.assertFalse(prepare([c], [], r, BASE)['proposals'])

    def test_two_same_day_officially_reported_strikes_stay_distinct(self):
        cs = [candidate('early'), candidate('late')]
        articles = [
            {'candidate_id': 'early', 'url': cs[0]['url'], 'observed_at':'2026-11-03',
             'text': ('Вранці 3 листопада РФ атакувала Дніпро ракетами. '
                      'У Дніпрі загинули двоє людей. Про це повідомили в ДСНС.')},
            {'candidate_id': 'late', 'url': cs[1]['url'], 'observed_at':'2026-11-03',
             'text': ('Увечері 3 листопада РФ атакувала Дніпро ракетами. '
                      'У Дніпрі загинули троє людей. Про це повідомили в ДСНС.')},
        ]
        rs = extract_cached_reports(cs, articles)
        out = prepare(cs, [], rs, BASE)
        self.assertEqual(len(out['proposals']), 2)
        self.assertEqual(sorted(int(p['deaths_delta']) for p in out['proposals']), [2, 3])

    def test_real_controls_and_existing_noop(self):
        root=Path(__file__).resolve().parents[2]
        evidence=json.loads((root/'research/casualty_automated_review_2026_11_10/cached_evidence.json').read_text())
        # Assert the persisted full-queue proof, not synthetic expected totals.
        events=json.loads((root/'research/casualty_automated_review_2026_11_10/results/events.json').read_text())
        by={r['case_id']:e for e in events for r in e['reports']}
        for key in ['DN-1103','OD-1109','KY-LATE','ZP-1103','DN-1108']:
            self.assertEqual(by[key]['category'],'NEEDS_REVIEW',key)
        self.assertIn('CITY_BOUNDARY_UNKNOWN',by['DN-1108']['reasons'])
        self.assertIn('CIVILIAN_UNKNOWN',by['ZP-1103']['reasons'])
        self.assertIn('INCREMENT_WITHOUT_VERIFIED_EVENT_TOTAL',by['KY-LATE']['reasons'])
        self.assertEqual(by['EXISTING-SUMY']['action'],'ALREADY_ACCOUNTED')
        self.assertEqual(by['EXISTING-SUMY']['proposed_delta'],0)
