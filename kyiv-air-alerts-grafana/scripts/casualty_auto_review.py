"""Pure offline proposal preparation for the existing casualty reviewer.

Articles are evidence, never additive deaths. No discovery, REVIEW, PROMOTE,
network, candidate mutation or publication lives here. Unknown facts fail closed.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from review_casualty_candidates import REVISION_FIELDS, _validate_confirmation

FACTS = ('city_boundary', 'russian_air_attack', 'civilian')
ALLOWED_HOSTS = {'suspilne.media', 'armyinform.com.ua', 'lb.ua', 'npu.gov.ua',
                 'vechirniy.kyiv.ua', 'unian.ua', 'ua.korrespondent.net', 't.me'}
MONTHS = {'січня': 1, 'лютого': 2, 'березня': 3, 'квітня': 4, 'травня': 5,
          'червня': 6, 'липня': 7, 'серпня': 8, 'вересня': 9, 'жовтня': 10,
          'листопада': 11, 'грудня': 12}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def fingerprint(candidate):
    # A historical attestation cannot silently attach to an edited queue record.
    return digest({k: candidate.get(k) for k in
                   ('candidate_id', 'city_key', 'title', 'snippet', 'url', 'published_at')})


def canonical_url(url):
    p = urlsplit(str(url or ''))
    host = (p.hostname or '').lower().removeprefix('www.')
    # Google wrappers remain distinct; never pretend the wrapper is a primary source.
    path = p.path.removeprefix('/amp').removesuffix('/amp').rstrip('/')
    return urlunsplit(('https', host, path, '', '')) if host else ''


def incident_id(incident):
    # No death count, article URL, title, trigger or report date in the identity.
    keys = ('city_key', 'attack_date', 'place', 'attack_slot', 'attack_type')
    if not all(isinstance(incident.get(k), str) and incident[k].strip() for k in keys):
        raise ValueError('Incident requires city/date/place/attack_slot/attack_type')
    date.fromisoformat(incident['attack_date'])
    identity = {k: ' '.join(incident[k].casefold().split()) for k in keys}
    return 'casualty-event:' + digest(identity)[:24]


def article_key(candidate):
    # Publication duplicates only: same city, publisher, timestamp and title.
    # Identical titles on different days never merge. This is NOT an incident claim.
    return digest([candidate.get('city_key'), canonical_url(candidate.get('publisher_url')),
                   candidate.get('published_at'),
                   ' '.join(str(candidate.get('title', '')).casefold().split())])


def text_hints(candidate):
    text = (candidate.get('title', '') + ' ' + candidate.get('snippet', '')).casefold()
    reasons = []
    if re.search(r'військовослужбов|полеглого (?:воїна|захисника)|похова.{0,35}(?:воїна|військового)|загинув на фронті', text):
        reasons.append('MILITARY_OBITUARY_OR_MIXED_STATUS')
    if re.search(r'передміст|област|район|громад|селищ|на .{0,20}щині', text):
        reasons.append('CITY_VS_REGION_REQUIRES_EVIDENCE')
    if re.search(r'лікарні помер|згодом помер|пізніше помер', text):
        reasons.append('LATE_DEATH_REQUIRES_EVENT_TOTAL')
    dates = set(re.findall(r'20\d{2}-\d{2}-\d{2}', text))
    for day, month, year in re.findall(r'(\d{1,2})\s+(' + '|'.join(MONTHS) + r')(?:\s+(20\d{2}))?', text):
        # Year inference is a hint ONLY, never accepted attack-date evidence.
        try:
            dates.add(date(int(year or candidate.get('published_at', '')[:4]),
                           MONTHS[month], int(day)).isoformat())
        except (ValueError, TypeError):
            pass
    return {'possible_attack_dates': sorted(dates), 'text_flags': reasons}


def extract_cached_reports(queue, articles):
    """Narrow text rules for retained full-text articles, never RSS snippets.

    Only a single explicitly dated, timed, addressed city incident qualifies.
    Missing or mixed facts remain UNKNOWN. The underlying attribution must be
    stated in the article; publisher/domain counts are never independence proof.
    """
    by_id = {c['candidate_id']: c for c in queue}
    reports = []
    for article in articles:
        c = by_id[article['candidate_id']]
        text = article.get('text', '')
        low = text.casefold()
        days = set(re.findall(r'(?:атака сталася|удар стався)\s+(20\d{2}-\d{2}-\d{2})', low))
        times = set(re.findall(r'\bо (\d{2}:\d{2})\b', low))
        places = set(re.findall(r'(?:за адресою|на вулиці)\s+([^.;\n]{3,80})', low))
        if len(days) != 1 or len(times) != 1 or len(places) != 1:
            continue  # No incident identity, therefore no cross-article merge.
        day, time, place = next(iter(days)), next(iter(times)), next(iter(places))
        try:
            date.fromisoformat(day)
        except ValueError:
            continue
        if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', time):
            continue
        # Deliberately narrow language. No province-to-city or absence-of-military
        # inference, no title-based attack date and no injured/dead conflation.
        city_phrase = 'у межах міста ' + c.get('city', '').casefold()
        boundary = True if c.get('city') and city_phrase in low else None
        if 'передміст' in low or 'за межами міста' in low:
            boundary = None
        weapon = 'missile' if 'ракетний удар' in low else 'drone' if 'дронова атака' in low else 'unknown'
        aerial = True if ('російськ' in low and weapon != 'unknown') else None
        matches = re.findall(r'загинул[аои]?\s+(\d+)\s+цивільн\w*', low)
        count = int(matches[0]) if len(matches) == 1 else None
        civilian = True if count is not None else None
        if re.search(r'військовослужбов|серед загиблих.{0,30}військов|повторн|різних атак', low):
            civilian = None
        if re.search(r'не загину|не підтвердж|непідтвердж|спростув|ймовір|без загиблих|навчаль|умовн', low):
            count = None
            civilian = None
        origins = []
        for term, origin in [('дснс', 'dsns'), ('національна поліція', 'national-police'),
                             ('прокуратур', 'prosecutor'), ('міська військова адміністрація', 'city-mva')]:
            if term in low:
                origins.append(origin)
        # Unknown or multiple underlying sources cannot manufacture independence.
        origin = origins[0] if len(origins) == 1 else 'unknown-origin'
        facts = {'city_boundary': boundary, 'russian_air_attack': aerial,
                 'civilian': civilian, 'attack_date': True, 'incident_identity': True,
                 'death_count': count is not None}
        supports = [k for k,v in facts.items() if v is True] if len(origins) == 1 else []
        reports.append({'candidate_ids': [c['candidate_id']],
                        'candidate_fingerprints': {c['candidate_id']: fingerprint(c)},
                        'incident': {'city_key': c['city_key'], 'attack_date': day,
                                     'place': place, 'attack_slot': time, 'attack_type': weapon},
                        'facts': facts, 'count': {'kind': 'total' if count is not None else 'unknown', 'value': count},
                        'observed_at': article['observed_at'],
                        'sources': [{'url': article['url'], 'origin_id': origin,
                                     'basis': 'retained-text-sha256=' + hashlib.sha256(text.encode()).hexdigest(),
                                     'supports': supports}],
                        'provenance': {'kind': 'explicit_cached_text_rules_v1',
                                       'article_sha256': hashlib.sha256(text.encode()).hexdigest()}})
    return reports


def validate_reports(queue, reports):
    from casualty_review_operator import ALLOWED_CITY_KEYS
    if any(c.get('city_key') not in ALLOWED_CITY_KEYS for c in queue):
        raise ValueError('Unknown casualty city_key')
    by_id = {c['candidate_id']: c for c in queue}
    if len(by_id) != len(queue):
        raise ValueError('Duplicate candidate_id in input')
    for report in reports:
        incident_id(report['incident'])
        if not report.get('candidate_ids') or not report.get('provenance'):
            raise ValueError('Evidence needs candidate links and provenance')
        for cid in report['candidate_ids']:
            if cid not in by_id or by_id[cid]['city_key'] != report['incident']['city_key']:
                raise ValueError('Evidence candidate/city mismatch')
            if report.get('candidate_fingerprints', {}).get(cid) != fingerprint(by_id[cid]):
                raise ValueError('Stale evidence candidate fingerprint')
        if report['provenance'].get('kind') == 'existing_confirmed_disposition':
            from review_casualty_candidates import _validated_confirmed_disposition
            for cid in report['candidate_ids']:
                d = _validated_confirmed_disposition(by_id[cid])
                if (d['record_id'] != report['provenance'].get('record_id')
                        or d['attack_date'] != report['incident']['attack_date']
                        or canonical_url(d['source_url']) not in
                           {canonical_url(s['url']) for s in report.get('sources', [])}):
                    raise ValueError('Claimed existing human confirmation does not match queue')
        date.fromisoformat(report['observed_at'])
        count = report.get('count', {})
        if count.get('kind') not in {'total', 'increment', 'unknown'}:
            raise ValueError('Explicit count semantics required')
        value = count.get('value')
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError('Count must be a nonnegative integer')
        for source in report.get('sources', []):
            if not source.get('origin_id') or not source.get('basis'):
                raise ValueError('Source needs underlying origin and factual basis')
            p = urlsplit(source['url'])
            if p.scheme != 'https' or (p.hostname or '').removeprefix('www.') not in ALLOWED_HOSTS:
                raise ValueError('Unapproved evidence source host')


def group_events(queue, reports):
    validate_reports(queue, reports)
    report_groups = defaultdict(list)
    linked = defaultdict(set)
    for report in reports:
        eid = incident_id(report['incident'])
        report_groups[eid].append(report)
        for cid in report['candidate_ids']:
            linked[cid].add(eid)
    ambiguous = {cid for cid, ids in linked.items() if len(ids) > 1}
    groups = {}
    for eid, items in report_groups.items():
        groups[eid] = {'event_id': eid, 'incident': items[0]['incident'], 'reports': items,
                       'messages': [], 'group_basis': 'cached_incident_evidence'}
    # No transitive title-similarity or city/day merging. Unproved publications
    # are separate potential events; duplicate publications stay together.
    for c in sorted(queue, key=lambda x: x['candidate_id']):
        targets = linked.get(c['candidate_id'], set())
        if len(targets) == 1:
            key = next(iter(targets))
        else:
            key = 'unresolved-publication:' + article_key(c)[:24]
            groups.setdefault(key, {'event_id': key, 'incident': {'city_key': c['city_key']},
                                    'reports': [], 'messages': [],
                                    'group_basis': 'publication_only_not_proven_incident'})
        msg = {k: c.get(k) for k in ('candidate_id', 'city_key', 'title', 'snippet',
                                   'url', 'publisher', 'publisher_url', 'published_at', 'status')}
        msg['hints'] = text_hints(c)
        if c['candidate_id'] in ambiguous:
            msg['hints']['text_flags'].append('CONFLICTING_INCIDENT_LINKS')
        groups[key]['messages'].append(msg)
    # Remove empty evidence groups after ambiguous membership exclusion.
    return [g for _, g in sorted(groups.items()) if g['messages']]


def source_support(reports, fact):
    origins, links = set(), set()
    for r in reports:
        if r.get('facts', {}).get(fact) is not True:
            continue
        for s in r.get('sources', []):
            if fact in s.get('supports', []):
                origins.add(s['origin_id'])
                links.add(canonical_url(s['url']))
    # Narrow authoritative contract: direct police publication, explicit facts
    # retained in a pre-existing human-confirmed disposition. Not an RSS label.
    for r in reports:
        if r.get('facts', {}).get(fact) is True:
            for s in r.get('sources', []):
                if (s.get('contract') == 'existing-human-confirmed-police-v1'
                        and urlsplit(s['url']).hostname == 'npu.gov.ua'
                        and r.get('provenance', {}).get('kind') == 'existing_confirmed_disposition'
                        and fact in s.get('supports', [])):
                    return True
    # Different domains alone do not mean independent reports. Both an origin
    # family AND distinct underlying documents are needed.
    return len(origins) >= 2 and len(links) >= 2


def compare_ledger(event, total, revisions, baseline):
    """Return counted deaths and ambiguity reasons, using actual rows, not state flags."""
    eid, incident = event['event_id'], event['incident']
    city, day = incident['city_key'], incident['attack_date']
    reasons = []
    coverage = baseline.get(city)
    if not coverage:
        return 0, ['BASELINE_COVERAGE_UNKNOWN'], []
    date.fromisoformat(coverage['through'])
    # Monthly baselines cannot identify which individual deaths were already counted.
    if day <= coverage['through']:
        return 0, ['BASELINE_EVENT_ALLOCATION_UNKNOWN'], []
    candidates = {m['candidate_id'] for m in event['messages']}
    links = {canonical_url(s['url']) for r in event['reports'] for s in r.get('sources', [])}
    rows = []
    for row in revisions:
        tagged = re.search(r'(?:^|\s)event_id=([^\s;]+)', row.get('note', ''))
        same_tag = bool(tagged and tagged[1] == eid)
        same_candidate = bool(candidates & set(row.get('candidate_ids', '').split('|')))
        same_source = canonical_url(row.get('source_url')) in links
        if tagged and not same_tag:
            if same_candidate:
                reasons.append('LEDGER_IDENTITY_CONFLICT')
            continue  # A regional source may describe several different incidents.
        if same_tag or same_candidate or same_source:
            if row['city_key'] != city or row['attack_date'] != day:
                reasons.append('LEDGER_IDENTITY_CONFLICT')
            rows.append(row)
        elif row['city_key'] == city and row['attack_date'] == day and not tagged:
            # Never assume a differently named legacy row is a different attack.
            reasons.append('UNBOUND_SAME_DAY_LEDGER_RECORD')
    counted = 0
    for row in rows:
        if row['status'] != 'confirmed':
            reasons.append('NONCONFIRMED_EXISTING_LEDGER_RECORD')
        try:
            value = int(row['deaths_delta'])
            if value < 0:
                reasons.append('RETRACTION_REQUIRES_REVIEW')
            counted += value
        except (ValueError, TypeError):
            reasons.append('INVALID_LEDGER_COUNT')
    if counted > total:
        reasons.append('COUNT_BELOW_ALREADY_ACCOUNTED')
    return counted, reasons, [r['record_id'] for r in rows]


def prepare(queue, revisions, reports, baseline, previous_proposals=()):
    ids = [r['record_id'] for r in revisions]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate ledger record_id')
    events, proposals = group_events(queue, reports), []
    previous = {p['record_id']: p for p in previous_proposals}
    if len(previous) != len(previous_proposals):
        raise ValueError('Duplicate prior proposal ID')
    actual_by_id = {r['record_id']: r for r in revisions}
    for rid, row in previous.items():
        if rid in actual_by_id and any(str(row.get(k)) != str(actual_by_id[rid].get(k))
                                       for k in ('city_key', 'attack_date', 'deaths_delta', 'status')):
            raise ValueError('Applied revision conflicts with prior proposal')
    reserved_rows = [p for rid,p in previous.items() if rid not in actual_by_id]
    for event in events:
        reasons = []
        rs = event['reports']
        if not rs:
            reasons.append('NO_CACHED_FACT_EVIDENCE_TITLE_IS_NOT_PROOF')
        else:
            for fact in FACTS:
                vals = [r.get('facts', {}).get(fact) for r in rs]
                if any(v is False for v in vals):
                    reasons.append(fact.upper() + '_CONFLICT_OR_OUT_OF_SCOPE')
                elif not all(v is True for v in vals):
                    reasons.append(fact.upper() + '_UNKNOWN')
                elif not source_support(rs, fact):
                    reasons.append(fact.upper() + '_INSUFFICIENT_INDEPENDENT_ORIGINS')
            for fact in ('attack_date', 'incident_identity', 'death_count'):
                if not source_support(rs, fact):
                    reasons.append(fact.upper() + '_INSUFFICIENT_INDEPENDENT_ORIGINS')
        for m in event['messages']:
            reasons.extend(m['hints']['text_flags'])
            if m['status'] not in {'needs_review', 'confirmed'}:
                reasons.append('EXISTING_HUMAN_HOLD_OR_REJECTION')
        # Cached evidence can resolve regional wording and late-date ambiguity,
        # but never military-obituary or conflicting incident membership flags.
        if rs and all(r.get('facts', {}).get('city_boundary') is True for r in rs):
            reasons = [r for r in reasons if r != 'CITY_VS_REGION_REQUIRES_EVIDENCE']
        totals = {r['count']['value'] for r in rs if r['count']['kind'] == 'total'}
        if any(r['count']['kind'] != 'total' for r in rs):
            reasons.append('INCREMENT_WITHOUT_VERIFIED_EVENT_TOTAL')
        if len(totals) != 1 or None in totals:
            reasons.append('TOTAL_DEATHS_UNKNOWN_OR_CONFLICTING')
        else:
            total = next(iter(totals))
            event['confirmed_total_claim'] = total
            counted, ledger_reasons, matched = compare_ledger(event, total, revisions, baseline)
            effective, reserved_reasons, reserved_matches = compare_ledger(
                event, total, revisions + reserved_rows, baseline)
            event['already_accounted'] = counted
            event['reserved_in_previous_proposals'] = effective - counted
            event['matched_revision_ids'] = matched
            event['matched_reservation_ids'] = [r for r in reserved_matches if r not in matched]
            ledger_reasons += reserved_reasons
            reasons.extend(ledger_reasons)
            if not ledger_reasons:
                reasons = [r for r in reasons if r != 'LATE_DEATH_REQUIRES_EVENT_TOTAL']
            event['proposed_delta'] = max(0, total - effective)
            if event['proposed_delta'] and any(r['provenance'].get('kind') == 'existing_confirmed_disposition' for r in rs):
                reasons.append('EXISTING_CONFIRMATION_ALLOWED_FOR_NOOP_ONLY')
        event['reasons'] = sorted(set(reasons))
        event['category'] = 'NEEDS_REVIEW' if reasons else 'AUTO_READY'
        event['publication_allowed'] = False
        if reasons:
            if 'proposed_delta' in event:
                event['unverified_gap_not_a_proposal'] = event.pop('proposed_delta')
            continue
        delta = event['proposed_delta']
        event['action'] = ('PROPOSE' if delta else 'PROPOSAL_ALREADY_PREPARED'
                           if event['reserved_in_previous_proposals'] else 'ALREADY_ACCOUNTED')
        if not delta:
            continue
        eid, incident = event['event_id'], event['incident']
        rid = eid + ':total-' + str(event['confirmed_total_claim'])
        source = sorted((s for r in rs for s in r['sources']), key=lambda s: s['url'])[0]
        validated = _validate_confirmation(rid, incident['attack_date'], delta,
                                           source['origin_id'], source['url'])
        row = {**validated, 'city_key': incident['city_key'],
               'observed_at': max(r['observed_at'] for r in rs), 'status': 'confirmed',
               'note': f"SHADOW PROPOSAL ONLY; event_id={eid}; total={event['confirmed_total_claim']}; already_accounted={event['already_accounted']}; reserved={event['reserved_in_previous_proposals']}",
               'candidate_ids': '|'.join(sorted(m['candidate_id'] for m in event['messages']))}
        row['deaths_delta'] = str(row['deaths_delta'])
        event['proposal_record_id'] = rid
        if rid in previous:
            invariant = ('city_key', 'attack_date', 'deaths_delta', 'status')
            if any(str(previous[rid].get(k)) != str(row[k]) for k in invariant):
                raise ValueError('Prior proposal conflicts with current ledger calculation')
            event['action'] = 'PROPOSAL_ALREADY_PREPARED'
        else:
            proposals.append(row)
    publication_duplicates = sum(len(v) - 1 for v in _by_article(queue).values())
    summary = {'messages_processed': len(queue), 'potential_events': len(events),
               'auto_ready': sum(e['category'] == 'AUTO_READY' for e in events),
               'needs_review': sum(e['category'] == 'NEEDS_REVIEW' for e in events),
               'unique_proposals': len(proposals),
               'duplicate_publication_excess': publication_duplicates,
               'already_accounted_events': sum(e.get('action') == 'ALREADY_ACCOUNTED' for e in events),
               'prior_proposals_suppressed': sum(e.get('action') == 'PROPOSAL_ALREADY_PREPARED' for e in events),
               'reason_counts': dict(sorted(Counter(r for e in events for r in e['reasons']).items())),
               'publication_allowed': False,
               'scope': 'Retained queue only; not a discovery completeness/recall estimate'}
    return {'summary': summary, 'events': events, 'proposals': proposals}


def _by_article(queue):
    groups = defaultdict(list)
    for c in queue:
        groups[article_key(c)].append(c['candidate_id'])
    return groups


def run_offline(queue_path, revisions_path, evidence_path, baseline_path, output,
                previous_path=None):
    inputs = [Path(p).resolve() for p in (queue_path, revisions_path, evidence_path, baseline_path)]
    if previous_path:
        inputs.append(Path(previous_path).resolve())
    if not all(p.is_file() for p in inputs):
        raise ValueError('All input snapshots must exist; missing ledger is unsafe')
    output = Path(output).resolve()
    targets = [output / f for f in ('events.json', 'summary.json', 'proposals.csv', 'manifest.json')]
    data_dir = (Path(__file__).resolve().parents[1] / 'data').resolve()
    if (output == data_dir or data_dir in output.parents or output in {p.parent for p in inputs}
            or any(t.resolve() in inputs for t in targets)):
        raise ValueError('Output must not overwrite inputs or repository data')
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    from review_casualty_candidates import load_queue, load_revision_rows
    evidence = json.loads(Path(evidence_path).read_text())
    result = prepare(load_queue(Path(queue_path)), load_revision_rows(Path(revisions_path)),
                     evidence.get('reports', []) + extract_cached_reports(load_queue(Path(queue_path)), evidence.get('articles', [])),
                     json.loads(Path(baseline_path).read_text()),
                     load_revision_rows(Path(previous_path)) if previous_path else ())
    # Finish the full calculation before making any output visible.
    output.mkdir(parents=True, exist_ok=True)
    for name, value in [('events.json', result['events']), ('summary.json', result['summary'])]:
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    with (output / 'proposals.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=REVISION_FIELDS)
        writer.writeheader()
        writer.writerows(result['proposals'])
    after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    if hashes != after:
        raise RuntimeError('Input snapshot changed during calculation')
    manifest = {'input_sha256': hashes, 'inputs_unchanged': True,
                'output_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in targets if p.name != 'manifest.json'}}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return result['summary']
