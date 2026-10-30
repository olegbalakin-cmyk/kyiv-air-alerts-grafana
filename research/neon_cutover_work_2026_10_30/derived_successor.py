"""Pure research-only derivation of site_derived.json consumer fields.

Successor of the accepted 22-city derived wrapper. Reuses pinned production
functions for all 23 cities with explicit alert inputs and a single cutoff.
Never calls a network-fetching producer main().
"""
from __future__ import annotations

import copy
from datetime import date, datetime, time, timedelta
from pathlib import Path

from contract import CITY_KEYS, COVERAGE, KYIV, PROXY, UTC, aware


def create_derived(candidate: dict, reference_derived: dict, alerts: dict,
                   now: datetime, site_root: Path, mods: dict) -> dict:
    """Create every city section from explicit research alert inputs.

    Generates time-of-day, common table, explorations and current-day partial
    through production's existing pure Python functions.
    """
    heat = mods['build_time_of_day_heatmap']
    keys = candidate['multicity_meta']['production_city_keys']
    city_keys = keys
    if len(keys) != 23 or set(keys) != {*CITY_KEYS, 'kyiv'}:
        raise ValueError('Unexpected 23-city consumer selector')
    if set(alerts) != set(keys):
        raise ValueError('Missing explicit alert input for a city')
    alerts = dict(alerts)
    # The deployed derived producer calls load_kyiv(), which unions touching
    # intervals. Retain its existing presentation rule; never rebind parents.
    alerts['kyiv'] = heat.union_alerts(alerts['kyiv'], 'neon_kyiv_derived_union')
    result = copy.deepcopy(reference_derived)
    dashboard = copy.deepcopy(candidate)
    coverage = {}
    ends = {}
    for key in keys:
        meta = candidate['cities'][key]['meta']
        coverage[key] = date.fromisoformat(str(meta.get('coverage_start') or meta.get('first_city_level_date'))[:10])
        ends[key] = date.fromisoformat(meta['analysis_end'])
    for key in city_keys:
        start, end = coverage[key], ends[key]
        heat_rows = {period: heat.period_heatmap(alerts[key], start, end, days)
                     for period, days in heat.PERIODS.items()}
        result['time_of_day_heatmap_test']['cities'][key] = {
            'coverage_start': start.isoformat(),
            'analysis_end': end.isoformat(),
            'source_type': candidate['multicity_meta']['cities'][key]['source_type'],
            'periods': heat_rows,
        }
        table_meta = reference_derived['all_cities_table_test']['meta']
        table_start = date.fromisoformat(table_meta['common_start'])
        table_end = date.fromisoformat(table_meta['common_end'])
        table_periods = {}
        for name,length in (('7d',7),('30d',30),('90d',90),('year',365),('common',None)):
            lower = table_start if length is None else max(table_start, table_end - timedelta(days=length-1))
            table_periods[name] = heat.period_summary(alerts[key], lower, table_end)
        result['all_cities_table_test']['cities'][key] = {'periods': table_periods}
    # Every city uses the same explicit inputs and cutoff.
    explorations = heat.build_exploration_payload(dashboard, keys, alerts, coverage, ends, now)
    current_day = now.astimezone(KYIV).date().isoformat()
    daily28_current = {}
    for key in city_keys:
        city = copy.deepcopy(candidate['cities'][key])
        heat.enrich_daily28_active_durations(city, alerts[key])
        heat.append_current_day_daily28(city, alerts[key], now.astimezone(KYIV))
        last = city.get('daily28', [])[-1] if city.get('daily28') else None
        if last and last.get('date') == current_day and last.get('is_partial_period') is True:
            daily28_current[key] = last
    explorations['daily28_current'] = {
        'meta': {
            'timezone': 'Europe/Kyiv',
            'current_day': current_day,
            'current_day_is_partial': True,
            'kpi_period_unchanged': True,
            'city_count': len(daily28_current),
        },
        'cities': daily28_current,
    }
    result['explorations'] = explorations
    result.setdefault('meta',{})['source'] = 'research-only; not the production updater'
    return result


def diff_derived(reference: dict, candidate: dict) -> dict:
    items=[]
    for section in ('time_of_day_heatmap_test','all_cities_table_test','explorations'):
        for key in city_keys:
            old = reference.get(section, {}).get('cities',{}).get(key)
            new = candidate.get(section, {}).get('cities',{}).get(key)
            if old != new:
                items.append({'section':section,'city_key':key,
                              'known_dst_related':key in ('kharkiv','zhytomyr','poltava','cherkasy')})
    for key in city_keys:
        old = reference.get('explorations',{}).get('daily28_current',{}).get('cities',{}).get(key)
        new = candidate.get('explorations',{}).get('daily28_current',{}).get('cities',{}).get(key)
        if old != new:
            items.append({'section':'explorations.daily28_current','city_key':key,
                          'known_dst_related':key in ('kharkiv','zhytomyr','poltava','cherkasy')})
    return {'total_diff_sections':len(items),'differences':items,
            'verdict':'SHAPE_MATH_MATCH_ONLY' if not items else 'PARTIAL_DISCREPANCIES',
            'production_reader_switch':False}
