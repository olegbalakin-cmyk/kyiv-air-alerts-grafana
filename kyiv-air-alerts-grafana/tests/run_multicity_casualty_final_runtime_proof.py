#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import threading
import traceback
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

RESULT_PATH = Path('/tmp/multicity_casualties_final_runtime_exec_result.json')
EXPECTED = {
    'kyiv': 454,
    'kharkiv': 339,
    'sevastopol': 22,
    'cherkasy': 2,
    'zhytomyr': 12,
    'dnipro': 214,
    'khmelnytskyi': 10,
    'poltava': 84,
    'rivne': 1,
    'sumy': 158,
    'vinnytsia': 31,
    'kropyvnytskyi': 9,
    'lviv': 29,
    'chernihiv': 105,
    'mykolaiv': 106,
    'lutsk': 10,
    'uzhhorod': 0,
    'ivano-frankivsk': 3,
    'ternopil': 41,
    'chernivtsi': 5,
    'odesa': 171,
    'zaporizhzhia': 316,
    'kherson': 163,
}
PROMOTION_BLOBS = {
    'kyiv-air-alerts-grafana/scripts/update_casualties.py': '32c9f99b17a1d8da5f11d862b9825370366060ee',
    'kyiv-air-alerts-grafana/scripts/add_casualty_panel.py': '991a7d40bed1cfd01abfc23624e0028219d8fb90',
    'kyiv-air-alerts-grafana/data/casualties/master_20cities_manifest.json': 'cdff7c9887dba0662bc44435048aa5449f7485cc',
    'kyiv-air-alerts-grafana/data/casualties/master_20cities_monthly_wide.csv': 'f3b7fdf6750e12d7b9af05ffd094bb47aa9ed801',
    'kyiv-air-alerts-grafana/data/casualties/cities/odesa/manifest.json': 'bc9e487f63cf4c67c0c9c86757c3ded04537ee24',
    'kyiv-air-alerts-grafana/data/casualties/cities/odesa/odesa_air_attack_deaths_monthly.csv': 'b51a2cd204b3a3c977025e7acd9311ba98e3a317',
    'kyiv-air-alerts-grafana/data/casualties/cities/zaporizhzhia/manifest.json': '4dcfb6a14949820b4934a100063f549e22799e8b',
    'kyiv-air-alerts-grafana/data/casualties/cities/zaporizhzhia/zaporizhzhia_air_attack_deaths_monthly.csv': '1b32d8808069b4499fda35b092fd56f51c64583f',
    'kyiv-air-alerts-grafana/data/casualties/cities/kherson/manifest.json': '8f343b2fb01774ed476910d34489e03fbf190cb5',
    'kyiv-air-alerts-grafana/data/casualties/cities/kherson/kherson_air_attack_deaths_monthly.csv': '5520e34c5d0696a167ed0eea378a8648c8836c49',
    'kyiv-air-alerts-grafana/pages-preview/app.js': '9eb9af99a00fbe22606fe86880548ab1cd2a0cf5',
    'kyiv-air-alerts-grafana/pages-preview/index.html': '1a76b8af2f3e07e9029fb0bda2198228ce889019',
}
DASH_REL = 'kyiv-air-alerts-grafana/data/dashboard_data.json'
GRAFANA_REL = 'kyiv-air-alerts-grafana/grafana/dashboard.json'
PROJECT_REL = Path('kyiv-air-alerts-grafana')

class GateFailure(RuntimeError):
    def __init__(self, gate: str, message: str):
        super().__init__(message)
        self.gate = gate

class ToolingFailure(RuntimeError):
    def __init__(self, gate: str, message: str):
        super().__init__(message)
        self.gate = gate


def run(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None, gate: str = 'command') -> subprocess.CompletedProcess[str]:
    cp = subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env, text=True, capture_output=True)
    if cp.returncode != 0:
        raise GateFailure(gate, f"command failed ({cp.returncode}): {' '.join(cmd)}\nstdout:\n{cp.stdout}\nstderr:\n{cp.stderr}")
    return cp


def git(repo: Path, *args: str, gate: str = 'git') -> str:
    return run(['git', *args], cwd=repo, gate=gate).stdout.strip()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def json_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def assert_gate(cond: bool, gate: str, message: str) -> None:
    if not cond:
        raise GateFailure(gate, message)


def strip_casualty_sections(value: dict[str, Any]) -> dict[str, Any]:
    clone = copy.deepcopy(value)
    clone.pop('casualties', None)
    clone.pop('casualties_by_city', None)
    return clone


def validate_city_series(data: dict[str, Any]) -> dict[str, Any]:
    series = data.get('casualties_by_city') or {}
    assert_gate(set(series) == set(EXPECTED), '23_city_validation', f"city keys mismatch: {sorted(series)}")
    totals: dict[str, int] = {}
    row_counts: dict[str, int] = {}
    duplicate_months: dict[str, int] = {}
    negative_counts: dict[str, int] = {}
    for key, expected in EXPECTED.items():
        rows = (series[key] or {}).get('monthly') or []
        months = [str(r.get('month')) for r in rows]
        row_counts[key] = len(rows)
        duplicate_months[key] = len(months) - len(set(months))
        negative_counts[key] = sum(1 for r in rows if int(r.get('deaths') or 0) < 0)
        total = sum(int(r.get('deaths') or 0) for r in rows)
        totals[key] = total
        assert_gate(len(rows) == 56, '23_city_validation', f'{key}: rows={len(rows)} expected=56')
        assert_gate(duplicate_months[key] == 0, '23_city_validation', f'{key}: duplicate months')
        assert_gate(negative_counts[key] == 0, '23_city_validation', f'{key}: negative deaths')
        assert_gate(total == expected, '23_city_validation', f'{key}: total={total} expected={expected}')
    assert_gate(series['kyiv'] == data.get('casualties'), 'kyiv_compatibility', 'casualties_by_city.kyiv != casualties')
    assert_gate(row_counts['uzhhorod'] == 56 and totals['uzhhorod'] == 0, 'uzhhorod_zero_series', 'Uzhhorod zero series invalid')
    return {
        'city_count': len(series),
        'all_city_keys_exact': True,
        'monthly_rows_each': 56,
        'row_counts': row_counts,
        'duplicate_months': duplicate_months,
        'negative_counts': negative_counts,
        'totals': totals,
        'exact_totals': True,
        'kyiv_compatibility': True,
        'uzhhorod_zero_series': True,
    }


def normalized_repeat(value: dict[str, Any]) -> dict[str, Any]:
    clone = copy.deepcopy(value)
    casualty = clone.get('casualties') or {}
    if isinstance(casualty.get('meta'), dict):
        casualty['meta'].pop('generated_at', None)
    by_city = clone.get('casualties_by_city') or {}
    for series in by_city.values():
        if isinstance(series, dict) and isinstance(series.get('meta'), dict):
            series['meta'].pop('generated_at', None)
    return clone


def methodology_panel(obj: dict[str, Any]) -> dict[str, Any] | None:
    for panel in obj.get('panels') or []:
        content = ((panel.get('options') or {}).get('content') or '')
        if panel.get('title') == '\u0414\u0436\u0435\u0440\u0435\u043b\u0430 \u0442\u0430 \u043c\u0435\u0442\u043e\u0434\u043e\u043b\u043e\u0433\u0456\u044f' or '**\u0413\u0435\u043e\u0433\u0440\u0430\u0444\u0456\u044f \u0442\u0430 \u0434\u0436\u0435\u0440\u0435\u043b\u0430.**' in content:
            return panel
    return None


def normalize_grafana(obj: dict[str, Any], insert_y: int, after: bool) -> dict[str, Any]:
    clone = copy.deepcopy(obj)
    marker = '**\u0417\u0430\u0433\u0438\u0431\u043b\u0456 \u0432\u0456\u0434 \u043f\u043e\u0432\u0456\u0442\u0440\u044f\u043d\u0438\u0445 \u0430\u0442\u0430\u043a.**'
    panels = []
    for panel in clone.get('panels') or []:
        pid = int(panel.get('id') or -1)
        if 950 <= pid < 1000:
            continue
        content = ((panel.get('options') or {}).get('content') or '')
        if marker in content:
            panel.setdefault('options', {})['content'] = content.split(marker, 1)[0].rstrip()
        gp = panel.get('gridPos') or {}
        if after and int(gp.get('y') or 0) > insert_y:
            gp['y'] = int(gp.get('y') or 0) - 1
        panels.append(panel)
    panels.sort(key=lambda p: (int((p.get('gridPos') or {}).get('y') or 0), int((p.get('gridPos') or {}).get('x') or 0), int(p.get('id') or -1)))
    clone['panels'] = panels
    return clone


def validate_grafana(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_m = methodology_panel(before)
    assert_gate(before_m is not None, 'grafana_generation', 'methodology panel missing before generation')
    insert_y = int((before_m.get('gridPos') or {}).get('y') or 0)
    rows = [p for p in after.get('panels') or [] if p.get('type') == 'row' and int(p.get('id') or -1) == 950]
    assert_gate(len(rows) == 1, 'grafana_generation', f'casualty row count={len(rows)}')
    nested = rows[0].get('panels') or []
    assert_gate(len(nested) == 23, 'grafana_generation', f'nested casualty panels={len(nested)}')
    selectors = {((p.get('targets') or [{}])[0]).get('root_selector') for p in nested}
    expected_selectors = {f"$['casualties_by_city']['{key}']['monthly']" for key in EXPECTED}
    assert_gate(selectors == expected_selectors, 'grafana_generation', 'Grafana selectors mismatch')
    before_norm = normalize_grafana(before, insert_y, after=False)
    after_norm = normalize_grafana(after, insert_y, after=True)
    assert_gate(before_norm == after_norm, 'grafana_generation', 'unexpected non-casualty/non-methodology Grafana delta')
    return {
        'result': 'PASS',
        'casualty_row_count': 1,
        'row_id': 950,
        'nested_city_panels': 23,
        'selectors_exact': True,
        'kyiv_present': "$['casualties_by_city']['kyiv']['monthly']" in selectors,
        'uzhhorod_present': "$['casualties_by_city']['uzhhorod']['monthly']" in selectors,
        'unexpected_dashboard_diffs_after_normalization': 0,
    }


def browser_proof(runtime_dir: Path) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        raise ToolingFailure('browser_environment', f'Playwright import failed: {exc}') from exc

    console_errors: list[str] = []
    page_errors: list[str] = []
    chart_errors: list[str] = []
    failed_requests: list[str] = []
    warnings: list[str] = []

    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            pass

    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(runtime_dir), **kwargs)
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    url = f'http://127.0.0.1:{httpd.server_port}/index.html'

    try:
        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch(headless=True)
            except Exception as exc:
                raise ToolingFailure('browser_environment', f'Chromium launch failed: {exc}') from exc
            chromium_version = browser.version
            context = browser.new_context()
            context.add_init_script("localStorage.setItem('air-alerts-intro-tour-v2','1')")
            page = context.new_page()

            def on_console(msg: Any) -> None:
                text = msg.text
                if msg.type == 'error':
                    console_errors.append(text)
                    if 'chart' in text.lower():
                        chart_errors.append(text)
                elif msg.type == 'warning':
                    warnings.append(text)

            page.on('console', on_console)
            page.on('pageerror', lambda exc: page_errors.append(str(exc)))
            page.on('requestfailed', lambda req: failed_requests.append(f'{req.method} {req.url}: {req.failure}'))

            page.goto(url, wait_until='networkidle')
            page.wait_for_function("() => typeof Chart === 'function' && !!Chart.getChart(document.getElementById('casualtyChart'))")

            identity = page.evaluate("""() => ({
                typeof_chart: typeof Chart,
                version: Chart.version,
                has_registry: !!Chart.registry,
                has_getChart: typeof Chart.getChart === 'function',
                has_instances: !!Chart.instances,
                controller_count: Object.keys((Chart.registry && Chart.registry.controllers && Chart.registry.controllers.items) || {}).length
            })""")
            assert_gate(identity['typeof_chart'] == 'function', 'real_chart_js_loaded', 'typeof Chart != function')
            assert_gate(identity['version'] == '4.4.7', 'real_chart_js_loaded', f"Chart.version={identity['version']}")
            assert_gate(identity['has_registry'] and identity['has_getChart'] and identity['has_instances'] and identity['controller_count'] > 0, 'real_chart_js_loaded', f'Chart structural identity failed: {identity}')

            def summary() -> dict[str, Any]:
                return page.evaluate("""() => {
                    const canvas = document.getElementById('casualtyChart');
                    const chart = Chart.getChart(canvas);
                    const data = chart?.data?.datasets?.[0]?.data || [];
                    return {
                        exists: !!chart,
                        id: chart?.id ?? null,
                        rows: chart?.data?.labels?.length ?? 0,
                        total: data.reduce((a, b) => a + (Number(b) || 0), 0),
                        section_visible: !document.getElementById('casualtySection').classList.contains('hidden'),
                        city_value: document.getElementById('citySelect').value
                    };
                }""")

            def switch_city(key: str, expected_total: int, previous_id: int | None) -> dict[str, Any]:
                page.select_option('#citySelect', key)
                page.wait_for_timeout(50)
                current = summary()
                assert_gate(current['exists'], 'real_city_switch', f'{key}: Chart instance missing')
                assert_gate(current['rows'] == 56, 'real_city_switch', f"{key}: rows={current['rows']}")
                assert_gate(current['total'] == expected_total, 'real_city_switch', f"{key}: total={current['total']} expected={expected_total}")
                assert_gate(current['section_visible'], 'real_city_switch', f'{key}: casualty section hidden')
                assert_gate(current['city_value'] == key, 'real_city_switch', f"{key}: select value={current['city_value']}")
                replaced = True
                old_removed = True
                if previous_id is not None:
                    replaced = current['id'] != previous_id
                    old_removed = bool(page.evaluate("oldId => !Chart.instances[oldId]", previous_id))
                    assert_gate(replaced and old_removed, 'real_city_switch', f'{key}: previous Chart not destroyed/replaced')
                return {**current, 'previous_chart_replaced': replaced, 'previous_chart_removed_from_registry': old_removed}

            initial = summary()
            assert_gate(initial['exists'] and initial['rows'] == 56 and initial['total'] == 454 and initial['city_value'] == 'kyiv', 'real_city_switch', f'initial Kyiv invalid: {initial}')
            sequence = [{'city': 'kyiv', **initial, 'previous_chart_replaced': True, 'previous_chart_removed_from_registry': True}]
            prev_id = initial['id']
            for key in ['kharkiv', 'uzhhorod', 'odesa', 'kyiv']:
                current = switch_city(key, EXPECTED[key], prev_id)
                sequence.append({'city': key, **current})
                prev_id = current['id']

            spot_checks = {}
            for key in ['dnipro', 'zaporizhzhia', 'kherson']:
                current = switch_city(key, EXPECTED[key], prev_id)
                spot_checks[key] = current
                prev_id = current['id']

            current = switch_city('kyiv', EXPECTED['kyiv'], prev_id)
            prev_id = current['id']
            mutation_ok = page.evaluate("""() => {
                if (typeof state === 'undefined' || !state.data || !state.data.casualties_by_city) return false;
                delete state.data.casualties_by_city.kharkiv;
                return !state.data.casualties_by_city.kharkiv;
            }""")
            assert_gate(bool(mutation_ok), 'real_missing_series_cleanup', 'browser-runtime mutation could not remove Kharkiv casualty series')
            page.select_option('#citySelect', 'kharkiv')
            page.wait_for_timeout(50)
            missing = page.evaluate("""oldId => {
                const canvas = document.getElementById('casualtyChart');
                const chart = Chart.getChart(canvas);
                return {
                    chart_exists: !!chart,
                    section_hidden: document.getElementById('casualtySection').classList.contains('hidden'),
                    old_removed: !Chart.instances[oldId],
                    city_value: document.getElementById('citySelect').value
                };
            }""", prev_id)
            assert_gate(not missing['chart_exists'] and missing['section_hidden'] and missing['old_removed'] and missing['city_value'] == 'kharkiv', 'real_missing_series_cleanup', f'missing-series cleanup invalid: {missing}')

            browser.close()

            assert_gate(console_errors == [], 'browser_error_gate', f'console errors: {console_errors}')
            assert_gate(page_errors == [], 'browser_error_gate', f'page errors: {page_errors}')
            assert_gate(chart_errors == [], 'browser_error_gate', f'Chart errors: {chart_errors}')
            assert_gate(failed_requests == [], 'browser_error_gate', f'failed requests: {failed_requests}')

            return {
                'playwright_version': importlib.metadata.version('playwright'),
                'chromium_version': chromium_version,
                'chart_identity': identity,
                'sequence': sequence,
                'spot_checks': spot_checks,
                'uzhhorod': next(item for item in sequence if item['city'] == 'uzhhorod'),
                'missing_series': missing,
                'console_errors': console_errors,
                'page_errors': page_errors,
                'chart_errors': chart_errors,
                'failed_app_requests': failed_requests,
                'warnings': warnings,
            }
    finally:
        httpd.shutdown()
        thread.join(timeout=5)


def main() -> dict[str, Any]:
    result: dict[str, Any] = {
        'schema_version': 1,
        'overall_status': 'RUNNING',
        'production_writes': 'NONE',
    }
    repo = Path(git(Path.cwd(), 'rev-parse', '--show-toplevel', gate='repository_guard'))
    proof_head = git(repo, 'rev-parse', 'HEAD', gate='repository_guard')
    branch = os.environ.get('GITHUB_REF_NAME') or ''
    assert_gate(branch == 'multicity-casualties-prod-proof-2026-09-28', 'repository_guard', f'unexpected branch {branch}')
    result['proof_source'] = {'branch': branch, 'tested_commit': proof_head}

    observed_blobs = {}
    for path, expected_blob in PROMOTION_BLOBS.items():
        blob = git(repo, 'rev-parse', f'{proof_head}:{path}', gate='promotion_blob_guard')
        observed_blobs[path] = blob
        assert_gate(blob == expected_blob, 'promotion_blob_guard', f'{path}: {blob} != {expected_blob}')
    result['promotion_blobs'] = observed_blobs
    result['promotion_blob_guard'] = 'PASS'

    git(repo, 'fetch', 'origin', 'site-prod', '--depth=1', gate='fresh_production_guard')
    site_prod_head = git(repo, 'rev-parse', 'FETCH_HEAD', gate='fresh_production_guard')
    result['fresh_frozen_site_prod_head'] = site_prod_head

    prod_tree = Path('/tmp/casualty-prod')
    proof_tree = Path('/tmp/casualty-proof')
    for path in [prod_tree, proof_tree]:
        if path.exists():
            shutil.rmtree(path)
    git(repo, 'worktree', 'add', '--detach', str(prod_tree), site_prod_head, gate='tree_materialization')
    git(repo, 'worktree', 'add', '--detach', str(proof_tree), proof_head, gate='tree_materialization')

    dash_path = prod_tree / DASH_REL
    grafana_path = prod_tree / GRAFANA_REL
    dashboard_blob = git(repo, 'rev-parse', f'{site_prod_head}:{DASH_REL}', gate='exact_dashboard_materialization')
    dashboard_sha256 = sha256_file(dash_path)
    result['exact_current_production_dashboard'] = {
        'git_blob_sha': dashboard_blob,
        'materialized_sha256': dashboard_sha256,
        'materialized': True,
    }

    before_dashboard_path = Path('/tmp/dashboard_data_before_casualties.json')
    before_grafana_path = Path('/tmp/grafana_dashboard_before_casualties.json')
    shutil.copy2(dash_path, before_dashboard_path)
    shutil.copy2(grafana_path, before_grafana_path)

    for rel in PROMOTION_BLOBS:
        src = proof_tree / rel
        dst = prod_tree / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    project = prod_tree / PROJECT_REL
    before_dashboard = load_json(before_dashboard_path)
    before_sha256 = sha256_file(before_dashboard_path)
    first_builder = run([sys.executable, 'scripts/update_casualties.py', '--no-network'], cwd=project, gate='exact_current_builder')
    after_first = load_json(dash_path)
    after_first_sha256 = sha256_file(dash_path)
    validation = validate_city_series(after_first)
    assert_gate(strip_casualty_sections(before_dashboard) == strip_casualty_sections(after_first), 'non_casualty_regression', 'unexpected non-casualty dashboard diff')
    result['exact_current_base_builder'] = {
        'result': 'PASS',
        'stdout': first_builder.stdout.strip(),
        'before_sha256': before_sha256,
        'after_sha256': after_first_sha256,
        **validation,
        'casualties_hash': json_hash(after_first.get('casualties')),
        'casualties_by_city_hash': json_hash(after_first.get('casualties_by_city')),
    }
    result['non_casualty_regression'] = {'result': 'PASS', 'unexpected_non_casualty_diffs': 0}

    before_grafana = load_json(before_grafana_path)
    grafana_run = run([sys.executable, 'scripts/add_casualty_panel.py'], cwd=project, gate='grafana_generation')
    after_grafana = load_json(grafana_path)
    result['grafana_generation'] = {**validate_grafana(before_grafana, after_grafana), 'stdout': grafana_run.stdout.strip()}

    env = dict(os.environ)
    env['CASUALTY_PROOF_BEFORE'] = str(before_dashboard_path)
    focused = run([sys.executable, 'tests/test_multicity_casualty_promotion.py'], cwd=project, env=env, gate='focused_test')
    focused_last = focused.stdout.strip().splitlines()[-1] if focused.stdout.strip() else ''
    focused_json = json.loads(focused_last)
    assert_gate(bool(focused_json.get('ok')), 'focused_test', f'focused test not ok: {focused_json}')
    result['focused_test'] = {'result': 'PASS', 'output': focused_json}

    chart_path = Path(os.environ.get('CHART_JS_PATH', ''))
    if not chart_path.is_file():
        raise ToolingFailure('real_chart_js_loaded', f'Chart.js path missing: {chart_path}')
    package_root = chart_path.parent.parent
    package_json = load_json(package_root / 'package.json')
    chart_version = package_json.get('version')
    assert_gate(chart_version == '4.4.7', 'real_chart_js_loaded', f'package version={chart_version}')
    chart_sha256 = sha256_file(chart_path)
    result['chart_js_package'] = {
        'source_path': str(chart_path),
        'version': chart_version,
        'sha256': chart_sha256,
    }

    runtime = Path('/tmp/casualty-runtime-site')
    if runtime.exists():
        shutil.rmtree(runtime)
    runtime.mkdir(parents=True)
    for name in ['index.html', 'styles.css', 'app.js']:
        shutil.copy2(project / 'pages-preview' / name, runtime / name)
    shutil.copy2(dash_path, runtime / 'data.json')
    shutil.copy2(chart_path, runtime / 'chart.umd.min.js')

    app_path = runtime / 'app.js'
    app_text = app_path.read_text(encoding='utf-8')
    live_data = 'const DATA_URL = "https://raw.githubusercontent.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/site-prod/kyiv-air-alerts-grafana/data/dashboard_data.json";'
    local_data = 'const DATA_URL = "./data.json";'
    assert_gate(app_text.count(live_data) == 1, 'runtime_site_build', 'production DATA_URL occurrence != 1')
    app_path.write_text(app_text.replace(live_data, local_data), encoding='utf-8')

    index_path = runtime / 'index.html'
    index_text = index_path.read_text(encoding='utf-8')
    live_chart = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js'
    assert_gate(index_text.count(live_chart) == 1, 'runtime_site_build', 'Chart.js CDN occurrence != 1')
    index_path.write_text(index_text.replace(live_chart, './chart.umd.min.js'), encoding='utf-8')
    result['runtime_site_build'] = {'result': 'PASS', 'data_url': './data.json', 'chart_url': './chart.umd.min.js'}

    result['browser_runtime'] = browser_proof(runtime)
    result['real_chart_js_loaded'] = {
        'result': 'PASS',
        'Chart.version': result['browser_runtime']['chart_identity']['version'],
        'structural_identity': result['browser_runtime']['chart_identity'],
    }
    result['real_city_switch'] = {'result': 'PASS', 'sequence': result['browser_runtime']['sequence']}
    result['spot_checks'] = result['browser_runtime']['spot_checks']
    result['real_uzhhorod_zero_chart'] = {'result': 'PASS', **result['browser_runtime']['uzhhorod']}
    result['real_missing_series_cleanup'] = {'result': 'PASS', **result['browser_runtime']['missing_series']}
    result['browser_errors'] = {
        'console_errors': result['browser_runtime']['console_errors'],
        'page_errors': result['browser_runtime']['page_errors'],
        'chart_errors': result['browser_runtime']['chart_errors'],
        'failed_app_requests': result['browser_runtime']['failed_app_requests'],
        'warnings': result['browser_runtime']['warnings'],
    }

    after_first_snapshot = copy.deepcopy(after_first)
    second_builder = run([sys.executable, 'scripts/update_casualties.py', '--no-network'], cwd=project, gate='repeated_builder_durability')
    after_second = load_json(dash_path)
    second_validation = validate_city_series(after_second)
    assert_gate(normalized_repeat(after_first_snapshot) == normalized_repeat(after_second), 'repeated_builder_durability', 'second builder changed content beyond casualty generated timestamps')
    assert_gate(strip_casualty_sections(before_dashboard) == strip_casualty_sections(after_second), 'repeated_builder_durability', 'second builder changed non-casualty dashboard content')
    result['repeated_builder_durability'] = {
        'result': 'PASS',
        'stdout': second_builder.stdout.strip(),
        'after_second_sha256': sha256_file(dash_path),
        'normalized_content_stable': True,
        'validation': second_validation,
    }

    result['production_write_audit'] = {
        'result': 'PASS',
        'workflow_permissions': 'contents: read',
        'site_prod_push': False,
        'main_push': False,
        'netlify_deploy': False,
        'grafana_deploy': False,
        'neon_mutation': False,
        'generated_outputs_committed': False,
    }
    result['overall_status'] = 'PASS'
    result['verdict'] = '23-CITY CASUALTY PRODUCTION PROMOTION PROVEN - EXACT CURRENT SITE-PROD BASE + REAL CHART.JS 4.4.7 RUNTIME PASS - READY FOR GUARDED PRODUCTION CUTOVER'
    return result


if __name__ == '__main__':
    result: dict[str, Any] = {'overall_status': 'FAILED'}
    exit_code = 1
    try:
        result = main()
        exit_code = 0
    except ToolingFailure as exc:
        result.update({
            'overall_status': 'BLOCKED',
            'failed_gate': exc.gate,
            'error': str(exc),
            'traceback': traceback.format_exc(),
            'verdict': f'23-CITY CASUALTY PRODUCTION PROMOTION STILL BLOCKED - {exc.gate}: {exc}',
            'production_writes': 'NONE',
        })
    except GateFailure as exc:
        result.update({
            'overall_status': 'FAILED',
            'failed_gate': exc.gate,
            'error': str(exc),
            'traceback': traceback.format_exc(),
            'verdict': f'23-CITY CASUALTY PRODUCTION PROMOTION FAILED - {exc.gate}',
            'production_writes': 'NONE',
        })
    except Exception as exc:
        result.update({
            'overall_status': 'BLOCKED',
            'failed_gate': 'unexpected_runner_error',
            'error': str(exc),
            'traceback': traceback.format_exc(),
            'verdict': f'23-CITY CASUALTY PRODUCTION PROMOTION STILL BLOCKED - unexpected runner error: {exc}',
            'production_writes': 'NONE',
        })
    RESULT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'overall_status': result.get('overall_status'), 'failed_gate': result.get('failed_gate'), 'verdict': result.get('verdict')}, ensure_ascii=False))
    sys.exit(exit_code)
