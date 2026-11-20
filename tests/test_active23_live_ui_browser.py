#!/usr/bin/env python3
"""Immutable Netlify branch preview proof for the production C6 source-state UI.

Runs ONLY against the explicitly unpublished Netlify draft alias, never prod.
This is deliberately a real Chromium check, not a JSON/model-only assertion.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = os.getenv(
    'ACTIVE23_PREVIEW_URL',
    'https://active23-live-ui-20261120--ukraine-air-alerts.netlify.app',
).rstrip('/')
EXPECTED = '2026-11-20'
OUT = Path(os.getenv('ACTIVE23_BROWSER_PROOF', '_browser_proof'))
OUT.mkdir(parents=True, exist_ok=True)

EXTRACT = r'''() => {
  const el = document.getElementById('cityIntensityChart');
  const chart = window.Chart?.getChart(el);
  if (!chart) return null;
  const labels = chart.data.labels || [];
  const x = chart.scales.x;
  const ticks = (x?.ticks || []).map(t => String(t.label || ''));
  const meta = chart.getDatasetMeta(0);
  const last = meta.data?.[meta.data.length - 1];
  const bar = last ? {x:last.x, y:last.y, base:last.base, width:last.width,
    visible:Number.isFinite(last.x) && Number.isFinite(last.y) && last.x >= 0 &&
      last.x <= chart.width && Number.isFinite(last.width) && last.width > 0} : null;
  const overlay = chart.options?.plugins?.active23FinalBar?.overlay;
  const cityKey=document.getElementById('citySelect')?.value;
  const raw=state.data.cities[cityKey]?.daily28?.at(-1);
  const sourceStart=state.active23Snapshot?.cities?.[cityKey]?.start_at;
  const startDay=sourceStart ? new Intl.DateTimeFormat('en-GB',{
    timeZone:'Europe/Kyiv',year:'numeric',month:'2-digit',day:'2-digit'
  }).formatToParts(new Date(sourceStart)) : [];
  const part=(type)=>startDay.find(x=>x.type===type)?.value;
  const startedHere=sourceStart &&
    part('year')+'-'+part('month')+'-'+part('day')==='2026-11-20' ? 1:0;
  const countLineLast=chart.data.datasets?.[1]?.data?.at(-1);
  const dailyCountChart=window.Chart?.getChart(document.getElementById('daily28AlertsDurationChart'));
  const dailyCountBar=dailyCountChart?.data?.datasets?.find(d=>
    d.type==='bar'&&d.label?.includes('Тривог, що почалися'))?.data?.at(-1);
  const dailyCountSum=dailyCountChart?.data?.datasets?.filter(d=>
    d.type==='bar'&&d.yAxisID==='yAlerts').reduce((sum,d)=>
      sum+(Number(d.data?.at(-1))||0),0);

  const delta = chart.options?.plugins?.periodForecastDeltaHatch;
  return {
    city:document.getElementById('citySelect')?.value,
    period:document.getElementById('cityPeriod')?.value,
    rangeTo:document.getElementById('cityDateTo')?.value,
    rangeMax:document.getElementById('cityDateTo')?.max,
    labelsLength:labels.length,
    first:String(labels[0] || ''),
    last:String(labels[labels.length - 1] || ''),
    ticks,
    datasetLast:chart.data.datasets?.[0]?.data?.at(-1),
    startedHere,baseCount:raw?.alerts_started,
    countLineLast,dailyCountBar,dailyCountSum,
    bar,
    overlayIndex:overlay?.index ?? null,
    overlayOpen:overlay?.provisionalHours ?? 0,
    deltaIndex:delta?.index ?? null,
    showTrend:document.getElementById('showTrend')?.checked,
    language:document.documentElement.lang,
    chartWidth:chart.width
  };
}'''


def read(page):
    return page.evaluate(EXTRACT)


def assert_visible_day(page, name, *, expect_open=True):
    state = read(page)
    assert state, f'{name}: no Chart.js chart'
    assert state['period'] == 'daily28', f'{name}: incorrect period: {state}'
    if state['last'] != EXPECTED:
        diagnostic = page.evaluate(r'''async () => {
          const key='kyiv';
          const source=state.data.cities[key];
          const snapshot=state.active23Snapshot;
          const data=await fetch('site-derived.json?v=diagnostic-'+Date.now(),{cache:'no-store'});
          let derived=null,err=null;
          try{derived=await data.json()}catch(e){err=String(e)}
          const e=derived?.explorations?.daily28_current;
          const before=source?.daily28?.at(-1);
          let manual=null;
          try{manual=window.Active23ChartOverlay?.ensureSnapshotDay(
            state.data.cities,snapshot,snapshot?.cities?.kyiv?.date,e)}
          catch(x){manual='ERROR: '+String(x)}
          return {sourceDay:snapshot?.cities?.kyiv?.date,
            hasSnapshot:!!snapshot,derivedHttp:data.status,derivedParse:err,
            hasExplorationsCities:!!derived?.explorations?.cities,
            derivedDay:e?.meta?.current_day,derivedMeta:e?.meta,
            derivedKyiv:e?.cities?.kyiv,
            priorLast:before,afterLast:source?.daily28?.at(-1),
            browserToday:kyivCalendarToday(), manual,
            sourceCount:Object.keys(state.data.cities).length
          };
        }''')
        print('ACTIVE23_BROWSER_DATE_DIAGNOSTIC', json.dumps(
            diagnostic, ensure_ascii=False, default=str)[:9000], flush=True)
    assert state['last'] == EXPECTED, f'{name}: Chart.js last data LABEL is not {EXPECTED}: {state}'
    assert state['labelsLength'] == 28, f'{name}: 28-day window shifted: {state}'
    assert state['rangeTo'] == EXPECTED, f'{name}: date filter hides current day: {state}'
    assert state['rangeMax'] == EXPECTED, f'{name}: upper limit stale: {state}'
    assert any(EXPECTED in t for t in state['ticks']), (
        f'{name}: actual Chart.js canvas axis tick omits {EXPECTED}: {state}')
    assert state['bar'] and state['bar']['visible'], f'{name}: last canvas bar missing: {state}'
    expected_count = int(state['baseCount']) + int(state['startedHere'])
    assert state['countLineLast'] == expected_count, (
        f'{name}: green alert-start line missed/duplicated unfinished start: {state}')
    assert state['countLineLast'] >= 0, f'{name}: negative starts: {state}'
    assert state['dailyCountSum'] == expected_count, (
        f'{name}: daily alerts bar missed/duplicated source start: {state}')

    if expect_open:
        assert state['overlayIndex'] == 27, f'{name}: unclosed cap not on 20 Nov: {state}'
        assert state['overlayOpen'] > 0, f'{name}: no source-verified provisional cap: {state}'
        assert state['deltaIndex'] == -1, f'{name}: conflicting trend hatch: {state}'
    else:
        assert not state['overlayOpen'], f'{name}: unverified Sevastopol open cap: {state}'
    return state


def open_page(browser, lang, size):
    context = browser.new_context(
        viewport=size, locale='en-GB' if lang == 'en' else 'uk-UA',
        timezone_id='Europe/Kyiv', device_scale_factor=1,
    )
    page = context.new_page()
    # Only this immutable archived-source preview uses a pinned browser clock.
    # Production itself always reads the real wall clock and expires after 8h.
    page.clock.install(time=datetime(2026, 11, 20, 7, 30,
                                     tzinfo=timezone(timedelta(hours=2))))
    problems = []
    page.on('pageerror', lambda error: problems.append(str(error)))
    prefix = '/en/' if lang == 'en' else '/'
    response = page.goto(
        f'{URL}{prefix}?city=kyiv&period=daily28&active23_browser_proof=1',
        wait_until='domcontentloaded', timeout=90000,
    )
    assert response and response.ok, f'{lang}: preview returned {response.status if response else "no response"}'
    page.wait_for_function(
        '() => !!(window.Chart && window.Chart.getChart(document.getElementById("cityIntensityChart")))',
        timeout=90000,
    )
    if page.locator('#tourSkip').is_visible():
        page.locator('#tourSkip').click()
    assert not problems, f'{lang}: browser JavaScript error: {problems}'
    return context, page


def snap(page, name):
    chart = page.locator('#cityIntensityChart')
    chart.scroll_into_view_if_needed()
    chart.screenshot(path=str(OUT / (name + '.png')))


def main():
    results = {'url': URL, 'expected_day': EXPECTED, 'cases': []}
    try:
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True, args=['--no-sandbox'])
            for lang, viewport, slug in [
                ('uk', {'width': 1366, 'height': 900}, 'ua-desktop'),
                ('en', {'width': 390, 'height': 844}, 'en-mobile'),
            ]:
                context, page = open_page(browser, lang, viewport)
                state = assert_visible_day(page, slug)
                results['cases'].append({'name': slug, **state})
                snap(page, slug)
                # Real click triggers the same render path the owner uses.
                page.locator('#showTrend').check()
                trend = assert_visible_day(page, slug + '-trend')
                assert trend['showTrend'], f'{slug}: trend toggle not active'
                results['cases'].append({'name': slug + '-trend', **trend})
                snap(page, slug + '-trend')
                page.locator('#showTrend').uncheck()
                assert_visible_day(page, slug + '-no-trend')
                if lang == 'uk':
                    # Every city uses the same exact C2 capture and chart path.
                    options = page.locator('#citySelect option').evaluate_all(
                        '(nodes) => nodes.map(n => n.value).filter(Boolean)')
                    assert len(options) == 23, f'expected 23 city options; got {options}'
                    for key in options:
                        page.select_option('#citySelect', value=key)
                        row = assert_visible_day(page, 'city-' + key,
                            expect_open=(key != 'sevastopol'))
                        results['cases'].append({'name': 'city-' + key, **row})
                context.close()
            browser.close()
    finally:
        (OUT / 'chart-axis-proof.json').write_text(
            json.dumps(results, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )
    print('ACTIVE23_LIVE_UI_CHROMIUM_23_CITY_PASS',
          len(results['cases']), 'cases; 23 cities; UA desktop, EN mobile; trend on/off')


if __name__ == '__main__':
    main()
