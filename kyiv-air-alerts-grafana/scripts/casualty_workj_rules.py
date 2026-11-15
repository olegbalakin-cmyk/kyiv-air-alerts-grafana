"""Pinned Work J PR #121 count/date/incident-scope helpers (OFFLINE, unchanged).

Source: casualty_auto_review.py, blob 19d0ed3911b62b7abc02700bd9f9a431e1d442e0.
Only the standalone imports and month constants are extracted alongside the
original helper definitions. This is Work J code reuse, not a new parser.
No source HTTP, reviewer, incident matching, PROMOTE or production writes.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date

MONTHS = {'січня': 1, 'лютого': 2, 'березня': 3, 'квітня': 4, 'травня': 5,
          'червня': 6, 'липня': 7, 'серпня': 8, 'вересня': 9, 'жовтня': 10,
          'листопада': 11, 'грудня': 12}


COUNT_WORDS = {'один': 1, 'одна': 1, 'дві': 2, 'двоє': 2,
               'три': 3, 'троє': 3, 'чотири': 4, 'четверо': 4,
               'двох': 2, 'трьох': 3, 'п\'ять': 5, 'п\'яти': 5, 'п\'ятеро': 5}
COUNT_TOKEN = r'(?:\d+|один|одна|дві|двоє|три|троє|чотири|четверо|двох|трьох|п'ять|п'яти|п'ятеро)'
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
    """Only a definite event total, not injuries, guesses, or an increment."""
    # Without a separately established cumulative event total, "two MORE"
    # cannot safely become the incident's full casualty count.
    if re.search(r'\b(?:ще|додатково)\s+(?:загинул\w*\s+)?'
                 rf'{COUNT_TOKEN}\s+{COUNT_NOUN}\s+загинул\w*'
                 rf'|\bзагинул\w*\s+(?:ще|додатково)\s+{COUNT_TOKEN}\b', low):
        return None
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
