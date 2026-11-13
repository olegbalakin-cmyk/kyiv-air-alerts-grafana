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
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from review_casualty_candidates import REVISION_FIELDS, _validate_confirmation

FACTS = ('city_boundary', 'russian_air_attack', 'civilian')
ALLOWED_HOSTS = {'suspilne.media', 'armyinform.com.ua', 'lb.ua', 'npu.gov.ua',
                 'vechirniy.kyiv.ua', 'unian.ua', 'ua.korrespondent.net', 't.me',
                 'zprz.city', 'zp.npu.gov.ua', 'ukrinform.ua', 'mig.com.ua',
                 'interfax.com.ua', '1news.zp.ua', 'zabor.zp.ua'}
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


COUNT_WORDS = {'один': 1, 'одна': 1, 'дві': 2, 'двоє': 2,
               'три': 3, 'троє': 3, 'чотири': 4, 'четверо': 4,
               'двох': 2, 'трьох': 3}
COUNT_TOKEN = r'(?:\d+|один|одна|дві|двоє|три|троє|чотири|четверо|двох|трьох)'
COUNT_NOUN = r'(?:люд\w*|цивільн\w*|мирн\w*|військовослужбов\w*)'
CITY_FORMS = {
    'zaporizhzhia': r'\bзапоріжж(?:я|і|ю|ям)\b',
    'dnipro': r'\bдніпр(?:о|і|а|у|ом)\b',
    'odesa': r'\bодес(?:а|і|у|ою)\b',
}


def _number(token):
    return int(token) if token.isdigit() else COUNT_WORDS.get(token)


def _cumulative_total_update(low):
    """Select an explicit official *cumulative* correction, not a maximum.

    Text is not assumed chronological (live articles often show newest first).
    Only a single incident scope, one attack window/weapon, explicit revision
    language for every differing claim and an attributable official final count
    may unlock the otherwise conflicting totals. Ambiguity remains a hold.
    """
    if re.search(r'\b(?:інш\w*|окрем\w*|повторн\w*|друг\w*)\s+'
                 r'(?:атак\w*|удар\w*|обстріл\w*)', low):
        return None
    if re.search(r'\b(?:ще|додатково)\s+\d+\s+'
                 r'(?:люд\w*|загибл\w*).{0,35}(?:загинул|помер|загибл)', low):
        return None
    slots = {name for name, pattern in (
        ('morning', r'\b(?:вранці|ранков\w*)\b'),
        ('evening', r'\b(?:увечері|ввечері|вечірн\w*)\b'),
        ('night', r'\b(?:вночі|нічн\w*)\b'),
        ('afternoon', r'\b(?:вдень|денн\w* удар)\b'))
        if re.search(pattern, low)}
    if len(slots) > 1:
        return None
    # Different weapons in competing fatality claims cannot be treated as
    # revisions of one attack merely because city/day matches.
    weapons = sum(bool(re.search(p, low)) for p in
                  (r'ракет\w*', r'дрон|бпла|безпілотн', r'\bкаб\w*|авіабомб'))
    if weapons > 1:
        return None
    patterns = (rf'\bзагинул[аои]?\s+({COUNT_TOKEN})\s+{COUNT_NOUN}',
                rf'\b({COUNT_TOKEN})\s+{COUNT_NOUN}\s+загинул[аои]?\b',
                rf'\b({COUNT_TOKEN})\s+загиблих\b',
                rf'\bдо\s+({COUNT_TOKEN})\s+люд\w*\s+зросл\w*\s+кількіст\w*\s+загиблих\b',
                rf'\bкількіст\w*\s+загиблих\s+(?:зросл\w*|збільшил\w*)\s+до\s+({COUNT_TOKEN})\b')
    claims = []
    for sentence in re.split(r'(?<=[.!?])\s+|\n+', low):
        if not sentence.strip():
            continue
        values = {_number(m[1]) for pattern in patterns
                  for m in re.finditer(pattern, sentence)}
        values.discard(None)
        if not values:
            continue
        if len(values) != 1:
            return None  # Multiple incompatible numbers in one statement.
        origin, origin_name = _origin_attribution(sentence)
        # A directly attributable DSNS correction may use "уточнили"
        # rather than the verbs used by ordinary source attribution.
        if origin == 'unattributed' and re.search(r'\bдснс\b', sentence) \
                and re.search(r'уточнил\w*', sentence):
            origin, origin_name = 'dsns', 'ДСНС'
        update = bool(re.search(
            r'уточнен|уточнил|за останніми даними|станом на|'
            r'зросл\w*.{0,45}кількіст|до\s+\d+\s+люд\w*\s+зросл|'
            r'збільшил|зменшил|пізніше|згодом|раніше|спочатку|первинно|'
            r'виправлен|скоригован|остаточн', sentence))
        claims.append({'value': next(iter(values)), 'origin_id': origin,
                       'origin_name': origin_name, 'update': update,
                       'earlier': bool(re.search(r'\bраніше\b|\bспочатку\b|'
                                                 r'\bпервинно\b|до уточнення', sentence)),
                       'later': bool(re.search(r'\bпізніше\b|\bзгодом\b|'
                                               r'\bостаточн\w*|після уточнення', sentence)),
                       'sentence_sha256': hashlib.sha256(sentence.encode()).hexdigest()})
    totals = {claim['value'] for claim in claims}
    if len(totals) < 2:
        return None
    officials = [c for c in claims if c['origin_id'] in
                 {'dsns', 'prosecutor', 'national-police', 'city-mva'}
                 and c['update'] and not c['earlier']]
    later = {c['value'] for c in officials if c['later']}
    choices = later if later else {c['value'] for c in officials}
    if len(choices) != 1:
        return None
    selected = next(iter(choices))
    # Unexplained totals may be independent groups, not earlier estimates.
    if any(not any(other['update'] for other in claims
                       if other['value'] == c['value'])
           for c in claims if c['value'] != selected):
        return None
    chosen = next(c for c in officials if c['value'] == selected)
    return {'value': selected, 'reported_totals': sorted(totals),
            'basis': 'unique_attributed_official_cumulative_update',
            'origin_id': chosen['origin_id'], 'origin_name': chosen['origin_name'],
            'official_sentence_sha256': chosen['sentence_sha256']}


def _fatal_total(low):
    """Only a definite event total, not injuries, guesses, or a second strike."""
    nums = []
    patterns = (rf'\bзагинул[аои]?\s+({COUNT_TOKEN})\s+{COUNT_NOUN}',
                rf'\b({COUNT_TOKEN})\s+{COUNT_NOUN}\s+загинул[аои]?\b')
    for pattern in patterns:
        nums.extend(_number(m[1]) for m in re.finditer(pattern, low))
    # An explicitly cumulative formulation, never an increment to add.
    nums.extend(_number(m[1]) for m in re.finditer(
        rf'\bкількіст\w*\s+загиблих\s+(?:зросл\w*|збільшил\w*)\s+до\s+({COUNT_TOKEN})\b', low))
    if re.search(r'не загинул|без загиблих|не підтвердж|непідтвердж|спростув|'
                 r'ймовірн|попередн\w* даними|можлив\w* загиб', low):
        return None
    # Also detect prior "18 загиблих" claims, without accepting that wording
    # alone as a new standalone automatic fatality total.
    all_values = {n for n in nums if n is not None}
    all_values.update(_number(m[1]) for m in
                      re.finditer(rf'\b({COUNT_TOKEN})\s+загиблих\b', low))
    all_values.update(_number(m[1]) for m in re.finditer(
        rf'\bдо\s+({COUNT_TOKEN})\s+люд\w*\s+зросл\w*\s+кількіст\w*\s+загиблих\b', low))
    all_values.discard(None)
    if len(all_values) == 1 and nums:
        return next(iter(all_values))
    if len(all_values) > 1:
        update = _cumulative_total_update(low)
        return update['value'] if update else None
    return None

def _date_signals(low, published_at):
    """Distinguish attack date from news date; never treat a mourning date as attack."""
    year = str(published_at or '')[:4]
    years = [int(year)] if re.fullmatch(r'20\d{2}', year) else []
    mentioned = []
    attack = []
    pattern = r'\b(\d{1,2})\s+(' + '|'.join(MONTHS) + r')\b'
    for match in re.finditer(pattern, low):
        if not years:
            continue
        try:
            day = date(years[0], MONTHS[match[2]], int(match[1])).isoformat()
        except ValueError:
            continue
        mentioned.append(day)
        context = low[max(0, match.start()-36):match.end()+100]
        if re.search(r'атакув|(?:удар|атака)\s+ставс|(?:завдал|здійснил).{0,25}удар', context):
            attack.append(day)
    for match in re.finditer(r'\b20\d{2}-\d{2}-\d{2}\b', low):
        try:
            day = date.fromisoformat(match[0]).isoformat()
        except ValueError:
            continue
        mentioned.append(day)
        context = low[max(0, match.start()-45):match.end()+65]
        if re.search(r'атакув|(?:удар|атака)\s+ставс', context):
            attack.append(day)
    return (next(iter(set(attack))) if len(set(attack)) == 1 else None,
            next(iter(set(mentioned))) if len(set(mentioned)) == 1 else None)


def _attack_slot(low):
    time_matches = []
    for m in re.finditer(r'\b(?:о|близько)\s+([01]\d|2[0-3]):([0-5]\d)\b', low):
        nearby = low[max(0, m.start()-35):m.end()+45]
        # A later repeat is NOT the time of casualties reported earlier.
        if not re.search(r'повторн|знову|ще раз', nearby):
            time_matches.append(m[1] + ':' + m[2])
    if len(set(time_matches)) == 1:
        return time_matches[0]
    if len(set(time_matches)) > 1:
        return None
    for slot, pattern in (('morning', r'\b(?:вранці|ранков\w*)\b'),
                          ('night', r'\b(?:вночі|нічн\w*)\b'),
                          ('evening', r'\b(?:ввечері|увечері|вечірн\w*)\b'),
                          ('afternoon', r'\b(?:вдень|денн\w* удар)\b')):
        if re.search(pattern, low):
            return slot
    return None


def _incident_scopes(low):
    """Keep facts from separately introduced strikes out of each other's event.

    This is deliberately a small, conservative narrative boundary, not NLP.
    When multiple sections report death totals, none is auto-parsed.
    """
    boundary = (r'(?=(?:^|(?<=[.!?])|(?<=\n))[ \t]*'
                r'(?:раніше|також|окремо|напередодні|до цього|перед тим|того ж дня)\b'
                r'[^\n.!?]{0,160}\b(?:атакув\w*|удар\w*|вдарил\w*|обстрілял\w*|влуч\w*)\b)')
    return [part.strip() for part in re.split(boundary, low) if part.strip()]


def _civilian_status(low, total):
    # A direct assertion about deceased servicemembers overrides the presumption.
    # Keep victim wording adjacent: wounded soldiers and military officials are
    # not evidence that those who died were soldiers.
    person = r'(?:військовослужбов\w*|військов(?:ий|і|их|ими)|бійц\w*|боєць|солдат\w*)'
    died = r'(?:загинул[аои]?|загинув|померл[аои]?|помер)'
    military_deaths = bool(re.search(
        rf'\b(?:усі\s+)?загибл(?:і|их)\s*(?:(?:[-–—:]\s*(?:це\s+)?(?:усі\s+)?)|(?:це|були|є)\s+)(?!не\s+){person}\b'
        rf'|\bсеред\s+загиблих\s+(?:(?:є|були|також)\s+)?(?!не\s+){person}\b'
        rf'|\b{died}\s+(?:{COUNT_TOKEN}\s+)?{person}\b'
        rf'|\b{COUNT_TOKEN}\s+{person}\s+{died}\b'
        rf'|\b{person}\s+{died}\b'
        rf'|\bзагибл(?:і|их)\s*[-–—:]\s*цивільн\w*\s*(?:,|і|й|та)\s*{person}\b', low))
    military_risk = bool(re.search(
        r'змішан\w* втрат|(?:військов\w*|армійськ\w*)\s+(?:об.єкт|частин|технік)'
        r'|склад[іу]?\s+(?:боєприпас|військов)', low))
    if military_deaths or military_risk:
        return 'civilian_ambiguous'
    if total is None:
        return None
    if re.search(r'(?:загинул\w*.{0,45}(?:цивільн|мирн\w* жител)'
                 r'|(?:цивільн\w*|мирн\w* жител).{0,45}загинул)', low):
        return 'civilian_explicit'
    # Presume civilians only when no military deceased or risk marker applies.
    return 'civilian_presumed'


def _origin_attribution(low):
    """A media domain is not an independent primary origin."""
    if re.search(r'дснс', low) and re.search(r'повідомил|повідомля|за даними|зазначил', low):
        return 'dsns', 'ДСНС'
    if re.search(r'прокуратур', low) and re.search(r'за даними|повідомил|повідомля|заявил', low):
        return 'prosecutor', 'Прокуратура'
    if re.search(r'національн\w* поліці|поліці[яїі]', low) and re.search(r'повідомил|за даними', low):
        return 'national-police', 'Національна поліція'
    # Direct reporter attribution: "повідомив очільник Одеської міської
    # військової адміністрації". Keep the verb and named office in one
    # contiguous phrase; a separate mention of a police/prosecutor or MVA
    # elsewhere in an article is not evidence of an official statement.
    if re.search(r'\bповідомив\s+очільник\s+(?:[а-яіїєґ-]+\s+){0,2}міськ\w*\s+військов\w*\s+адміністраці', low):
        return 'city-mva', 'Міська військова адміністрація'
    if re.search(r'начальник\w* мва|міськ\w* військов\w* адміністраці', low) and re.search(r'написав|повідомил|за даними', low):
        return 'city-mva', 'Міська військова адміністрація'
    return 'unattributed', None


def extract_cached_reports(queue, articles, *, diagnostics=None):
    """Extract evidence from retained article text, not synthetic fact labels.

    A unique city/date plus attack window or location anchors an incident.
    An undated corroboration can join only ONE dated anchor with compatible
    city, same-day reporting, time/place, and casualty total. The join is
    preserved as an inference, NOT presented as a date assertion in its source.
    """
    by_id = {c['candidate_id']: c for c in queue}
    parsed = []
    trace = []
    stage = {'articles_seen': len(articles), 'source_text_present': 0,
             'unique_fatal_scope': 0, 'city_boundary_supported': 0,
             'explicit_attack_date': 0, 'weapon_and_origin_supported': 0,
             'dated_incident_anchors': 0, 'unique_incident_match': 0,
             'structured_reports': 0}
    def hold(article, reason, at):
        trace.append({'candidate_id': article.get('candidate_id'),
                      'source_url': article.get('url'), 'stage': at,
                      'reason': reason, 'status': 'NEEDS_REVIEW'})
    for article in articles:
        c = by_id[article['candidate_id']]
        full_text = str(article.get('text') or '').casefold()
        if not full_text.strip():
            hold(article, 'SOURCE_TEXT_NOT_RETAINED', 'source_text')
            continue
        stage['source_text_present'] += 1
        # A whole article is not one incident: earlier/other attacks must
        # never donate their place, weapon, time, city or official origin.
        scopes = _incident_scopes(full_text)
        fatal_scopes = [part for part in scopes if _fatal_total(part) is not None]
        if len(fatal_scopes) != 1:
            if len(fatal_scopes) > 1:
                reason = 'MULTIPLE_POSSIBLE_INCIDENTS'
            elif re.search(r'\b(?:ще|додатково)\s+\d+\s+люд', full_text):
                reason = 'COUNT_IS_NOT_CUMULATIVE'
            elif re.search(r'помер\w*.{0,45}лікарн|лікарн.{0,45}помер\w*', full_text):
                reason = 'LATE_DEATH_OFFICIAL_CONFIRMATION_MISSING'
            elif re.search(r'загиб|загин|помер', full_text):
                reason = 'NO_PARSEABLE_FATAL_TOTAL'
            else:
                reason = 'NO_FATAL_CLAIM'
            hold(article, reason, 'fatal_scope')
            continue  # A number in a title is never enough.
        stage['unique_fatal_scope'] += 1
        low = fatal_scopes[0]
        city_pattern = CITY_FORMS.get(c['city_key'], rf'\b{re.escape(c.get("city", "").casefold())}\b')
        city_present = bool(re.search(city_pattern, low))
        outside = bool(re.search(r'передміст|за межами міста|на околиці (?:області|громади)|'
                                 r'у (?:селі|селищі)|в (?:селі|селищі)', low))
        boundary = True if city_present and not outside else None
        total = _fatal_total(low)
        day, mentioned_day = _date_signals(low, c.get('published_at'))
        slot = _attack_slot(low)
        weapon = ('missile' if re.search(r'ракет', low) else
                  'drone' if re.search(r'безпілотник|безпілотн|дрон|бпла|бпіл', low)
                  else 'guided-bomb' if re.search(r'\bкаб\w*|керован\w*\s+авіабомб', low)
                  else 'unknown')
        russian = bool(re.search(r'\bрф\b|російськ|ворог', low))
        air = True if russian and weapon != 'unknown' else None
        place = None
        match = re.search(r'(?:за адресою|на вулиці)\s+([^.;\n]{3,65})', low)
        if match:
            place = ' '.join(match[1].split())
        elif re.search(r'житлов\w* будин', low):
            place = 'residential-buildings'
        elif re.search(r'склад\w* (?:харч|продукт)', low):
            place = 'food-warehouse'
        elif re.search(r'інфраструктурн\w* об.єкт', low):
            place = 'infrastructure-object'
        resolution = _cumulative_total_update(low)
        origin_id, origin_name = ((resolution['origin_id'], resolution['origin_name'])
                                  if resolution else _origin_attribution(low))
        parsed.append({'c': c, 'article': article, 'low': low,
                       'day': day, 'mentioned_day': mentioned_day,
                       'slot': slot, 'weapon': weapon, 'place': place,
                       'boundary': boundary, 'russian': russian, 'air': air,
                       'total': total, 'status': _civilian_status(low, total),
                       'count_resolution': resolution,
                       'origin_id': origin_id, 'origin_name': origin_name})
    stage['city_boundary_supported'] = sum(p['boundary'] is True for p in parsed)
    stage['explicit_attack_date'] = sum(bool(p['day']) for p in parsed)
    stage['weapon_and_origin_supported'] = sum(p['air'] is True for p in parsed)
    anchors = [p for p in parsed if p['day'] and (p['slot'] or p['place'])
               and p['weapon'] != 'unknown' and p['boundary'] is True
               and p['total'] is not None and p['air'] is True]
    stage['dated_incident_anchors'] = len(anchors)
    reports = []
    for p in parsed:
        if p['total'] is None:
            hold(p['article'], 'NO_PARSEABLE_FATAL_TOTAL', 'fatal_count')
            continue
        matches = []
        for a in anchors:
            if p['c']['city_key'] != a['c']['city_key'] or p['total'] != a['total']:
                continue
            if p['day'] and p['day'] != a['day']:
                continue
            if not p['day'] and (p['mentioned_day'] != a['day']
                                 or str(p['c'].get('published_at', ''))[:10] != a['day']):
                continue
            if p['slot'] and a['slot'] and p['slot'] != a['slot']:
                continue
            if p['weapon'] != 'unknown' and p['weapon'] != a['weapon']:
                continue
            if p['place'] and a['place'] and p['place'] != a['place']:
                continue
            matches.append(a)
        identities = {}
        for a in matches:
            key = (a['day'], a['slot'] or 'unknown', a['place'] or 'unlocated', a['weapon'])
            identities[key] = a
        # Multiple compatible concrete events are ambiguous, not permission to merge.
        if len(identities) != 1:
            reason = ('CITY_BOUNDARY_UNCERTAIN' if p['boundary'] is not True
                      else 'ATTACK_DATE_MISSING' if not p['day']
                      else 'ATTACK_IDENTITY_AMBIGUOUS' if not (p['slot'] or p['place'])
                      else 'WEAPON_ORIGIN_UNCONFIRMED' if p['air'] is not True
                      else 'MULTIPLE_POSSIBLE_INCIDENTS' if len(identities) > 1
                      else 'ATTACK_IDENTITY_AMBIGUOUS')
            hold(p['article'], reason, 'incident_match')
            continue
        a = next(iter(identities.values()))
        # Do not attach a second, ambiguous city/day article by total alone.
        if p is not a and not (p['slot'] or p['place']):
            hold(p['article'], 'ATTACK_IDENTITY_AMBIGUOUS', 'corroboration')
            continue
        if p['boundary'] is not True or not p['russian']:
            hold(p['article'], 'CITY_BOUNDARY_UNCERTAIN' if p['boundary'] is not True
                 else 'WEAPON_ORIGIN_UNCONFIRMED', 'city_origin')
            continue
        state = p['status']
        aerial = p['air'] is True or (p['weapon'] == 'unknown' and a['air'] is True
                                     and p['slot'] == a['slot'])
        if not aerial:
            hold(p['article'], 'WEAPON_ORIGIN_UNCONFIRMED', 'attack_origin')
            continue
        stage['unique_incident_match'] += 1
        incident = {'city_key': p['c']['city_key'], 'attack_date': a['day'],
                    'place': a['place'] or 'unlocated',
                    'attack_slot': a['slot'] or 'unknown',
                    'attack_type': a['weapon']}
        facts = {'city_boundary': p['boundary'], 'russian_air_attack': True,
                 'civilian': True if state in ('civilian_explicit', 'civilian_presumed')
                 else None,
                 'attack_date': True, 'incident_identity': True, 'death_count': True}
        sha = hashlib.sha256(str(p['article']['text']).encode()).hexdigest()
        supports = list(facts)
        source = {'url': p['article']['url'], 'origin_id': p['origin_id'],
                  'origin_name': p['origin_name'],
                  'basis': 'retained-text-sha256=' + sha,
                  'supports': [k for k, v in facts.items() if v is True]}
        if p['origin_name']:
            source['contract'] = 'attributed-competent-official-v1'
        reports.append({
            'candidate_ids': [p['c']['candidate_id']],
            'candidate_fingerprints': {p['c']['candidate_id']: fingerprint(p['c'])},
            'incident': incident, 'facts': facts, 'civilian_status': state,
            'civilian_status_basis': ('explicit article wording' if state == 'civilian_explicit'
                                      else 'no identified military-victim/object marker in retained excerpt'
                                      if state == 'civilian_presumed' else 'military/uncertain status marker'),
            'count': {'kind': 'total', 'value': p['total']},
            'observed_at': p['article']['observed_at'],
            'sources': [source],
            'provenance': {
                'kind': 'parsed_retained_article_v2', 'article_sha256': sha,
                'date_basis': 'explicit_attack_date' if p['day'] else
                              'unique_same_day_report_corroborated_by_dated_article',
                'attack_date_in_article': p['day'],
                'matched_dated_article_sha256': (None if p is a else
                    hashlib.sha256(str(a['article']['text']).encode()).hexdigest()),
                'attack_slot_in_article': p['slot'],
                'attack_type_in_article': p['weapon'],
                'origin_attribution': p['origin_name'],
                **({'cumulative_update': p['count_resolution']}
                   if p['count_resolution'] else {}),
                'later_attack_mentioned': bool(re.search(r'повторно.{0,35}атакув|'
                                                          r'повторно\s+атакував', p['low']))}
        })
    stage['structured_reports'] = len(reports)
    if diagnostics is not None:
        for report in reports:
            trace.append({'candidate_id': report['candidate_ids'][0],
                          'source_url': report['sources'][0]['url'],
                          'stage': 'structured_report',
                          'reason': 'REPORT_EXTRACTED_NOT_AUTOMATICALLY_CONFIRMED',
                          'status': 'EXTRACTED_NOT_PUBLISHED',
                          'official_attribution': bool(report['sources'][0].get('contract'))})
        diagnostics.update({'parser_version': 'casualty-auto-review-workj-v1',
                            'stage_counts': stage,
                            'source_decisions': trace,
                            'reason_counts': dict(sorted(Counter(
                                d['reason'] for d in trace).items()))})
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
        if report.get('civilian_status') not in (None, 'civilian_explicit',
                                                 'civilian_presumed', 'civilian_ambiguous'):
            raise ValueError('Unknown civilian status evidence state')
        if report.get('civilian_status') == 'civilian_ambiguous' and report.get('facts', {}).get('civilian') is True:
            raise ValueError('Ambiguous civilian evidence cannot claim clear status')
        observed = str(report['observed_at'])
        if len(observed) > 10:
            datetime.fromisoformat(observed.replace('Z', '+00:00'))
        else:
            date.fromisoformat(observed)
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
    # A previously human-confirmed police disposition remains no-op only.
    for r in reports:
        if r.get('facts', {}).get(fact) is True:
            for s in r.get('sources', []):
                if (s.get('contract') == 'existing-human-confirmed-police-v1'
                        and urlsplit(s['url']).hostname == 'npu.gov.ua'
                        and r.get('provenance', {}).get('kind') == 'existing_confirmed_disposition'
                        and fact in s.get('supports', [])):
                    return True
    # Owner-approved SHADOW rule: one explicitly attributed competent official
    # fatality account suffices for count credibility. Other event details may
    # come from retained, traceable corroboration of the SAME uniquely anchored
    # incident; they need not each have two independent official confirmations.
    official_fatality = any(
        r.get('provenance', {}).get('kind') == 'parsed_retained_article_v2'
        and r.get('facts', {}).get('death_count') is True
        and any(s.get('contract') == 'attributed-competent-official-v1'
                and s.get('origin_id') in {'dsns', 'prosecutor', 'national-police', 'city-mva'}
                and 'death_count' in s.get('supports', [])
                for s in r.get('sources', []))
        for r in reports)
    if official_fatality and any(
            r.get('facts', {}).get(fact) is True
            and any(fact in s.get('supports', []) for s in r.get('sources', []))
            for r in reports):
        return True
    # Independent media requires distinct underlying origins AND documents.
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
            states = {r.get('civilian_status') for r in rs if r.get('civilian_status')}
            if 'civilian_ambiguous' in states:
                reasons.append('CIVILIAN_AMBIGUOUS')
            event['civilian_status'] = ('civilian_ambiguous' if 'civilian_ambiguous' in states
                                        else 'civilian_explicit' if 'civilian_explicit' in states
                                        else 'civilian_presumed' if 'civilian_presumed' in states
                                        else 'legacy_not_recorded')
            for fact in FACTS:
                vals = [r.get('facts', {}).get(fact) for r in rs]
                if any(v is False for v in vals):
                    reasons.append(fact.upper() + '_CONFLICT_OR_OUT_OF_SCOPE')
                elif not any(v is True for v in vals):
                    reasons.append(fact.upper() + '_UNKNOWN')
                elif not source_support(rs, fact):
                    reasons.append(fact.upper() + '_INSUFFICIENT_EVIDENCE')
            for fact in ('attack_date', 'incident_identity', 'death_count'):
                if not any(r.get('facts', {}).get(fact) is True for r in rs):
                    reasons.append(fact.upper() + '_UNKNOWN')
                elif not source_support(rs, fact):
                    reasons.append(fact.upper() + '_INSUFFICIENT_EVIDENCE')
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
        source = sorted((s for r in rs for s in r['sources']),
                        key=lambda s: (s.get('contract') != 'attributed-competent-official-v1', s['url']))[0]
        validated = _validate_confirmation(rid, incident['attack_date'], delta,
                                           (source.get('origin_name') or source['origin_id']), source['url'])
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
