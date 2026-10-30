#!/usr/bin/env python3
"""Physical browser consumer QA of an offline two-source preview, without DB access."""
import argparse
import csv
import functools
import hashlib
import http.server
import json
import shutil
import threading
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright
from build_preview import write_source


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--preview', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--chrome')
    args = ap.parse_args()
    root, out = args.preview.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((root / 'preview-manifest.json').read_text())
    payloads = {s: json.loads((root / 'data' / s / 'dashboard_data.json').read_text()) for s in ('neon', 'legacy')}
    all_files_before = {str(p.relative_to(root)): sha(p) for p in root.rglob('*') if p.is_file()}
    write_source(root, 'neon')
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(root)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}/'
    report = {'scope': 'RUNNER_LOCAL_FROZEN_BROWSER_PREVIEW', 'started_at': datetime.now(timezone.utc).isoformat(),
              'cutoff': manifest['cutoff_utc'], 'continuous_freshness_proven': False,
              'production_cutover_allowed': False, 'candidate_commit': manifest['candidate_commit'],
              'site_reference': manifest['site_reference'], 'city_results': [], 'csv': [],
              'page_errors': [], 'requests': [], 'response_hashes': [], 'error_cases': [],
              'rollback': {}, 'external_requests': [], 'netlify_deploy': 'NOT_EXECUTED_NO_AUTHENTICATED_UPLOAD_CAPABILITY'}
    network = []
    try:
        with sync_playwright() as pw:
            chrome = args.chrome or shutil.which('google-chrome') or shutil.which('chromium')
            browser = pw.chromium.launch(executable_path=chrome, headless=True, args=['--no-sandbox'])
            report['browser_version'] = browser.version
            context = browser.new_context(viewport={'width': 1440, 'height': 1080}, accept_downloads=True)
            context.add_init_script("""
                localStorage.setItem('air-alerts-intro-tour-v5','done');
                window.__qaResponses = [];
                window.__qaPending = 0;
                const qaFetch = window.fetch.bind(window);
                window.fetch = async (...args) => {
                    const response = await qaFetch(...args);
                    const clone = response.clone();
                    window.__qaPending++;
                    clone.arrayBuffer().then(bytes => crypto.subtle.digest('SHA-256', bytes))
                      .then(hash => window.__qaResponses.push({url:response.url,status:response.status,
                        sha256:[...new Uint8Array(hash)].map(x=>x.toString(16).padStart(2,'0')).join('')}))
                      .finally(()=>window.__qaPending--);
                    return response;
                };
            """)
            def route(request_route):
                if not request_route.request.url.startswith(base):
                    report['external_requests'].append(request_route.request.url)
                    request_route.abort()
                else:
                    request_route.continue_()
            context.route('**/*', route)
            page = context.new_page()
            page.on('pageerror', lambda e: report['page_errors'].append(str(e)))
            page.on('request', lambda r: report['requests'].append(r.url))
            def response_received(response):
                path = urlparse(response.url).path.lstrip('/')
                network.append({'url': response.url, 'status': response.status})
            page.on('response', response_received)

            def collect_response_hashes():
                page.wait_for_function('(window.__qaPending || 0) === 0')
                for response in page.evaluate('window.__qaResponses || []'):
                    path = urlparse(response['url']).path.lstrip('/')
                    if path.startswith('data/') and response['status'] == 200:
                        assert response['sha256'] == sha(root / path), path
                        report['response_hashes'].append({'path': path, 'sha256': response['sha256'], 'exact_package_match': True, 'digest_location': 'browser_crypto_subtle_over_actual_response_clone'})

            def load(url=base):
                page.goto(url, wait_until='networkidle')
                page.wait_for_function('state.charts.cityIntensityChart && state.explorations && state.historicalDaily', timeout=45000)
                if page.locator('#tourSkip').is_visible():
                    page.locator('#tourSkip').click()
                assert page.locator('#citySelect option').count() == 23
                collect_response_hashes()

            def select_city(key):
                page.locator('#citySelect').select_option(key)
                assert page.locator('#citySelect').input_value() == key

            def dates(prefix, start, end):
                for field, value in [('From', start), ('To', end)]:
                    el = page.locator('#' + prefix + 'Date' + field)
                    el.fill(value)
                    el.press('Tab')

            def snapshot(chart_id):
                return page.evaluate('id => {const c=state.charts[id]; return c ? {labels:c.data.labels, datasets:c.data.datasets.map((d,i)=>({label:d.label,data:d.data,hidden:!c.isDatasetVisible(i),axis:d.yAxisID,rows:d._exportRows})),width:c.width,height:c.height} : null}', chart_id)

            def valid_chart(chart_id, allow_empty=False):
                c = snapshot(chart_id)
                assert c is not None and c['width'] > 0 and c['height'] > 0, chart_id
                if not allow_empty:
                    assert len(c['labels']) > 0 and len(c['datasets']) > 0, chart_id
                for d in c['datasets']:
                    assert len(d['data']) == len(c['labels']), chart_id
                    assert all(v is None or isinstance(v, (int, float, dict)) for v in d['data']), chart_id
                return c

            def csv_download(chart_id, tag):
                c = valid_chart(chart_id)
                with page.expect_download(timeout=15000) as event:
                    page.locator(f'[data-csv-chart="{chart_id}"] button.csv-export-button:not(.chart-image-button):not(.chart-embed-button)').click()
                download = event.value
                target = out / 'csv' / (tag + '__' + download.suggested_filename)
                target.parent.mkdir(exist_ok=True)
                download.save_as(target)
                rows = list(csv.reader(target.read_text(encoding='utf-8-sig').splitlines()))
                assert len(rows) == len(c['labels']) + 1, tag
                assert [r[0] for r in rows[1:]] == [str(x) for x in c['labels']], tag
                assert all(len(r) == len(rows[0]) for r in rows), tag
                # Every visible series numeric value must survive the actual file download.
                cursor = 1
                for dataset in c['datasets']:
                    if dataset['hidden']:
                        continue
                    for i, value in enumerate(dataset['data']):
                        if isinstance(value, dict):
                            value = value.get('y', value.get('x'))
                        if value is None:
                            assert rows[i + 1][cursor] == '', tag
                        else:
                            assert abs(float(rows[i + 1][cursor]) - value) < 1e-8, (tag, i)
                    suffix = rows[0][cursor]
                    cursor += 2 if any(suffix.endswith('[' + x + ']') for x in ['hours', 'minutes', 'relative_peak_pct']) or (cursor + 1 < len(rows[0]) and any(rows[0][cursor+1].endswith('[' + x + ']') for x in ['days', 'minutes'])) else 1
                report['csv'].append({'tag': tag, 'file': str(target.relative_to(out)), 'rows': len(rows)-1,
                                      'columns': len(rows[0]), 'numeric_values_match_chart': True, 'sha256': sha(target)})

            def verify_monthly(key, source):
                page.locator('#cityPeriod').select_option('monthly')
                dates('city', '', '')
                c = valid_chart('cityIntensityChart')
                by_month = {r['month']: r for r in payloads[source]['cities'][key]['monthly']}
                for d, field in [(c['datasets'][0], 'avg_daily_alert_hours'), (c['datasets'][1], 'alerts_per_day')]:
                    assert len(d['rows']) == len(c['labels'])
                    for row, val in zip(d['rows'], d['data']):
                        assert abs(val - by_month[row['month']][field]) < 1e-8, (key, source, row['month'], field)
                return c

            def verify_history(key, source):
                dates('city', '2026-09-01', '2026-09-30')
                kpi = page.evaluate('state.lastCityKpi')
                history = payloads[source]['historical_daily_kpi']['cities'][key]
                start = datetime.fromisoformat(history['start']).date()
                a = (datetime(2026, 9, 1).date() - start).days
                b = (datetime(2026, 9, 30).date() - start).days + 1
                expected = sum(history['counts'][a:b])
                assert kpi['complete'] and kpi['alerts'] == expected, (key, kpi, expected)
                assert abs(kpi['hours'] - sum(history['daily_total_alert_duration_seconds'][a:b])/3600) < 1e-7, key
                return {'range': '2026-09-01/2026-09-30', 'alerts': expected, 'hours': kpi['hours'], 'independent_daily_index_match': True}

            load()
            assert page.evaluate('PREVIEW_CONFIG.source') == 'neon'
            assert 'DST SIMULATION' in page.locator('#researchNotice').inner_text()
            keys = page.locator('#citySelect option').evaluate_all('els=>els.map(e=>e.value)')
            types = payloads['neon']['multicity_meta']['cities']
            periods = page.locator('#cityPeriod option').evaluate_all('els=>els.map(e=>e.value)')
            core = ['cityIntensityChart', 'cityDurationChart', 'timeOfDayChart', 'heavyDaysChart', 'extremesChart', 'daypartChart']
            compare = ['compareAlertsChart', 'compareHoursChart', 'compareDurationChart', 'compareCumulativeHoursChart', 'compareTimeOfDayChart']
            for key in keys:
                select_city(key)
                chart = verify_monthly(key, 'neon')
                source_type = types[key]['source_type']
                assert page.locator('#cityMeta .badge.' + ('proxy' if source_type == 'raion_proxy' else 'exact')).count() == 1
                csv_download('cityIntensityChart', 'neon-' + key + '-monthly')
                history = verify_history(key, 'neon')
                dates('city', '', '')
                views = {}
                for period in periods:
                    page.locator('#cityPeriod').select_option(period)
                    dates('city', '', '')
                    views[period] = {cid: len(valid_chart(cid)['labels']) for cid in core}
                page.locator('#compareA').select_option('kyiv')
                page.locator('#compareB').select_option(key if key != 'kyiv' else 'kharkiv')
                page.locator('#compareC').select_option('')
                page.locator('#comparePeriod').select_option('monthly')
                dates('compare', '', '')
                comparisons = {cid: len(valid_chart(cid)['labels']) for cid in compare}
                result = {'city': key, 'source_type': source_type, 'monthly_points': len(chart['labels']),
                          'monthly_matches_candidate': True, 'periods': views, 'history': history, 'comparisons': comparisons}
                report['city_results'].append(result)
                if key in ['kyiv', 'kharkiv', 'poltava', 'zhytomyr', 'cherkasy', 'sevastopol']:
                    page.locator('#cityPeriod').select_option('monthly')
                    page.screenshot(path=str(out / (key + '-candidate.png')), full_page=False)
                print(json.dumps({'city': key, 'verdict': 'PASS'}), flush=True)
            assert sum(r['source_type'] == 'exact_city' for r in report['city_results']) == 4
            assert sum(r['source_type'] == 'raion_proxy' for r in report['city_results']) == 19

            select_city('kyiv')
            page.locator('#cityPeriod').select_option('monthly')
            dates('city', '', '')
            # Download all currently offered charts, including auxiliary tracks;
            # contents are checked as rendered, not presented as Neon-generated auxiliaries.
            for cid in page.evaluate('Object.keys(CSV_CHART_CONFIG)'):
                if page.locator(f'[data-csv-chart="{cid}"] button.csv-export-button:not(.chart-image-button):not(.chart-embed-button)').is_visible() and snapshot(cid) and snapshot(cid)['labels']:
                    csv_download(cid, 'neon-chart-' + cid)
            for section in ['timeOfDaySection', 'alertBurdenSection', 'comparisonSection', 'allCitiesSection']:
                page.locator('#' + section).screenshot(path=str(out / (section + '-candidate.png')))
            for period in ('daily28', 'weekly', 'rolling30', 'rolling90', 'rolling180', 'calendarWeekly'):
                page.locator('#cityPeriod').select_option(period)
                dates('city', '', '')
                csv_download('cityIntensityChart', 'neon-kyiv-' + period)
            # Legend visibility must affect CSV columns as promised by the UI.
            page.evaluate("state.charts.cityIntensityChart.setDatasetVisibility(1,false);state.charts.cityIntensityChart.update('none')")
            csv_download('cityIntensityChart', 'neon-visible-series-only')
            page.evaluate("state.charts.cityIntensityChart.setDatasetVisibility(1,true);state.charts.cityIntensityChart.update('none')")
            report['comparison_periods'] = {}
            for period in page.locator('#comparePeriod option').evaluate_all('els=>els.map(e=>e.value)'):
                page.locator('#comparePeriod').select_option(period)
                dates('compare', '', '')
                results = {}
                for cid in compare:
                    chart = valid_chart(cid, allow_empty=cid == 'compareCumulativeHoursChart')
                    results[cid] = len(chart['labels'])
                    if cid == 'compareCumulativeHoursChart' and not chart['labels']:
                        note = page.locator('#compareCumulativeNote').inner_text().lower()
                        assert 'немає' in note or 'no shared' in note, (period, note)
                        results['cumulative_empty_note'] = note
                report['comparison_periods'][period] = results
            for value in page.locator('#allCitiesRange option').evaluate_all('els=>els.map(e=>e.value)'):
                if value == 'custom':
                    continue
                page.locator('#allCitiesRange').select_option(value)
                assert page.locator('#allCitiesTable tr').count() == 23
            # Natural empty-state contract: two dates within a partial month
            # provide no completed shared month for cumulative comparison.
            page.locator('#comparePeriod').select_option('monthly')
            dates('compare', '2026-10-01', '2026-10-02')
            empty = snapshot('compareCumulativeHoursChart')
            assert not empty['labels']
            assert 'немає' in page.locator('#compareCumulativeNote').inner_text().lower() or 'no shared' in page.locator('#compareCumulativeNote').inner_text().lower()
            report['empty_state'] = {'shared_complete_months': 0, 'explicit_note': page.locator('#compareCumulativeNote').inner_text()}
            page.locator('#comparisonSection').screenshot(path=str(out / 'empty-comparison.png'))
            # A city without a casualty series must hide the previous city's chart.
            unavailable = next((k for k in keys if not payloads['neon'].get('casualties_by_city', {}).get(k, {}).get('monthly') and k != 'kyiv'), None)
            if unavailable:
                select_city(unavailable)
                assert not page.locator('#casualtySection').is_visible()
                report['auxiliary_empty_state'] = {'city': unavailable, 'casualty_section_hidden': True}

            # Real HTTP fault injection at the loopback server's browser boundary.
            for name, status, body, fatal in [('dashboard_data.json', 503, 'unavailable', True),
                                              ('dashboard_data.json', 200, '{', True),
                                              ('site_derived.json', 503, 'unavailable', False),
                                              ('kyiv_threat_mix.json', 503, 'unavailable', False)]:
                pattern = '**/data/neon/' + name + '*'
                page.route(pattern, lambda r, status=status, body=body: r.fulfill(status=status, body=body, content_type='application/json'))
                page.goto(base, wait_until='networkidle')
                if fatal:
                    assert page.locator('#freshnessBanner').is_visible()
                    assert 'завантажити' in page.locator('#freshnessBanner').inner_text() or 'load' in page.locator('#freshnessBanner').inner_text()
                else:
                    page.wait_for_function('state.charts.cityIntensityChart')
                    assert 'Preview data load error' in page.locator('#previewLoadStatus').inner_text()
                report['error_cases'].append({'file': name, 'status': status, 'invalid_json': body == '{', 'visible_error': True, 'remote_fallback': False})
                page.screenshot(path=str(out / ('error-' + name + '-' + str(status) + '.png')))
                page.unroute(pattern)
            load()
            # Exercise visible source control both directions before the config-only rollback.
            page.locator('#previewSource').select_option('legacy')
            page.wait_for_function('window.PREVIEW_CONFIG.source === "legacy" && state.charts.cityIntensityChart')
            page.locator('#previewSource').select_option('neon')
            page.wait_for_function('window.PREVIEW_CONFIG.source === "neon" && state.charts.cityIntensityChart')
            load(base)  # Remove preview_source override for source-only config rehearsal.
            candidate_marker = next(r for r in payloads['neon']['cities']['kharkiv']['monthly'] if r['month'] == '2026-10')
            frontend_before = {n: sha(root / n) for n in ['app.js', 'index.html', 'preview-bootstrap.js']}
            config_before = sha(root / 'preview-config.js')
            write_source(root, 'legacy')
            config_after = sha(root / 'preview-config.js')
            load(base)
            assert page.evaluate('PREVIEW_CONFIG.source') == 'legacy'
            legacy_results = []
            for key in keys:
                select_city(key)
                verify_monthly(key, 'legacy')
                history = verify_history(key, 'legacy')
                legacy_results.append({'city': key, 'monthly_and_history': 'PASS', 'history': history})
            select_city('kharkiv')
            verify_monthly('kharkiv', 'legacy')
            csv_download('cityIntensityChart', 'legacy-rollback-kharkiv')
            page.screenshot(path=str(out / 'legacy-rollback-browser.png'))
            legacy_marker = next(r for r in payloads['legacy']['cities']['kharkiv']['monthly'] if r['month'] == '2026-10')
            assert candidate_marker != legacy_marker, 'Rollback witness must differ between sources'
            assert frontend_before == {n: sha(root / n) for n in frontend_before}
            all_files_after = {str(p.relative_to(root)): sha(p) for p in root.rglob('*') if p.is_file()}
            changed = [p for p in all_files_before if all_files_before[p] != all_files_after[p]]
            assert changed == ['preview-config.js'], changed
            # Successful data responses must match exact packaged bytes, including
            # all auxiliary/fallback URLs; fault-injected responses are classified.
            seen = {r['path'] for r in report['response_hashes']}
            for source in ('neon', 'legacy'):
                for name in ['dashboard_data.json', 'site_derived.json', 'kyiv_threat_mix.json', 'historical-daily-kpi.json']:
                    # Legacy may accept its timestamp-aligned embedded index and
                    # legitimately omit the separate fallback request.
                    if name == 'historical-daily-kpi.json' and source == 'legacy':
                        continue
                    assert f'data/{source}/{name}' in seen, (source, name)
            report['response_hashes'] = list({r['path']: r for r in report['response_hashes']}.values())
            report['rollback'] = {'verdict': 'PASS_SOURCE_ONLY_FROZEN_ROLLBACK', 'changed_files': changed,
                                  'config_before_sha256': config_before, 'config_after_sha256': config_after,
                                  'frontend_unchanged': True, 'data_files_unchanged': True, 'legacy_cities': legacy_results,
                                  'kharkiv_october_candidate': candidate_marker, 'kharkiv_october_legacy': legacy_marker,
                                  'legacy_data_response_hashes_match_pinned_git': True, 'production_mutations': 0}
            assert not report['external_requests'] and not report['page_errors'], (report['external_requests'], report['page_errors'])
            report['verdict'] = 'PASS_BOUNDED_BROWSER_AND_SOURCE_ROLLBACK'
            browser.close()
    except Exception:
        report['verdict'] = 'FAIL_OR_BLOCKED_BROWSER_QA'
        report['exception'] = traceback.format_exc()
        raise
    finally:
        server.shutdown()
        report['completed_at'] = datetime.now(timezone.utc).isoformat()
        save(out / 'browser_result.json', report)
        save(out / 'rollback_proof.json', report['rollback'])
        save(out / 'network_requests.json', {'requests': report['requests'], 'external': report['external_requests'], 'response_hashes': report['response_hashes']})
        print(json.dumps({'verdict': report.get('verdict'), 'cities': len(report['city_results']), 'csv': len(report['csv']), 'rollback': report['rollback'].get('verdict')}), flush=True)


if __name__ == '__main__':
    main()
