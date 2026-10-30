#!/usr/bin/env python3
"""Package the accepted frozen candidate and pinned legacy site; no DB/deploy calls."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

PIN = '0ecbb291e8f443f7ab366bc4ac033d096f2c44f4'
CANDIDATE = '741f277f73d1dde1325069d25fa00b44a42d6f03'
CUTOFF = '2026-10-30T15:27:55.138400Z'
NAMES = ['dashboard_data.json', 'site_derived.json', 'alerts_combined.json']


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write_source(root, source):
    if source not in ('legacy', 'neon'):
        raise ValueError(source)
    (root / 'preview-config.js').write_text(
        'window.PREVIEW_DEFAULT_SOURCE = ' + json.dumps(source) + ';\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--site', type=Path)
    ap.add_argument('--candidate', type=Path)
    ap.add_argument('--manifest', type=Path)
    ap.add_argument('--chart-js', type=Path)
    ap.add_argument('--output', required=True, type=Path)
    ap.add_argument('--source', choices=['legacy', 'neon'], default='neon')
    ap.add_argument('--switch-only', action='store_true')
    args = ap.parse_args()
    root = args.output.resolve()
    if args.switch_only:
        assert (root / 'preview-manifest.json').is_file()
        write_source(root, args.source)
        return
    assert all([args.site, args.candidate, args.manifest, args.chart_js])
    actual = subprocess.check_output(['git', '-C', str(args.site), 'rev-parse', 'HEAD'], text=True).strip()
    assert actual == PIN, actual
    # Check every copied frontend/data byte against the immutable reference.
    def pinned(path):
        relative = 'kyiv-air-alerts-grafana/' + str(path.relative_to(args.site))
        expected = subprocess.check_output(['git', '-C', str(args.site), 'rev-parse', f'HEAD:{relative}'], text=True).strip()
        got = subprocess.check_output(['git', 'hash-object', str(path)], text=True).strip()
        assert got == expected, relative
    manifest = json.loads(args.manifest.read_text())
    for name in NAMES:
        assert sha(args.candidate / name) == manifest['site/' + name]['sha256'], name
    if root.exists():
        raise ValueError('Use a new output directory; do not overwrite a preview')
    for path in (args.site / 'pages-preview').iterdir():
        if path.is_file():
            pinned(path)
    shutil.copytree(args.site / 'pages-preview', root)
    consumed = {}
    for source in ('neon', 'legacy'):
        data = root / 'data' / source
        data.mkdir(parents=True)
        for name in NAMES + ['kyiv_threat_mix.json']:
            src = args.candidate / name if source == 'neon' and name in NAMES else args.site / 'data' / name
            if source == 'legacy' or name == 'kyiv_threat_mix.json':
                pinned(src)
            shutil.copy2(src, data / name)
            consumed[f'data/{source}/{name}'] = {'sha256': sha(src), 'origin': 'accepted_neon_candidate' if source == 'neon' and name in NAMES else 'pinned_git_auxiliary' if source == 'neon' else 'pinned_legacy_git'}
        # Existing consumer fallback; candidate bytes stay unchanged. Its embedded
        # index was calculated before dashboard generated_at was finalized.
        dashboard = json.loads((data / 'dashboard_data.json').read_text())
        index = dashboard['historical_daily_kpi']
        assert index['meta']['verified_count'] == 23
        (data / 'historical-daily-kpi.json').write_text(json.dumps(index, ensure_ascii=False) + '\n')
        consumed[f'data/{source}/historical-daily-kpi.json'] = {'sha256': sha(data / 'historical-daily-kpi.json'), 'origin': 'same_dashboard_embedded_index'}
    (root / 'vendor').mkdir()
    shutil.copy2(args.chart_js, root / 'vendor/chart.umd.min.js')
    js = (root / 'app.js').read_text()
    old = '"https://raw.githubusercontent.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/site-prod/kyiv-air-alerts-grafana/data/"'
    assert js.count(old) == 1
    js = js.replace(old, 'window.PREVIEW_CONFIG.dataBase')
    wip = '"https://raw.githubusercontent.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/multicity-wip-2026-09-16/kyiv-air-alerts-grafana/data/explosions_test.json"'
    assert js.count(wip) == 1
    js = js.replace(wip, 'RAW_DATA_BASE + "explosions_test.json"')
    assert js.count('fetch("historical-daily-kpi.json?v="') == 1
    js = js.replace('fetch("historical-daily-kpi.json?v="', 'fetch(RAW_DATA_BASE + "historical-daily-kpi.json?v="')
    switch_anchor = 'function updateUrl() {\n  const params = new URLSearchParams();'
    assert js.count(switch_anchor) == 1
    js = js.replace(switch_anchor, switch_anchor + '\n  params.set("preview_source", window.PREVIEW_CONFIG.source);')
    (root / 'app.js').write_text(js)
    html = (root / 'index.html').read_text()
    html = html.replace('<meta name="robots" content="index,follow,max-snippet:-1">', '<meta name="robots" content="noindex,nofollow">')
    html = html.replace('  <link rel="canonical" href="https://ukraine-air-alerts.netlify.app/">\n', '')
    html = html.replace('https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js', 'vendor/chart.umd.min.js')
    html = html.replace('<body>', '<body>\n<section id="researchNotice" role="region" aria-label="Research preview"></section>')
    html = html.replace('  <script src="vendor/chart.umd.min.js">', '  <script src="preview-config.js"></script>\n  <script src="preview-bootstrap.js"></script>\n  <script src="vendor/chart.umd.min.js">')
    (root / 'index.html').write_text(html)
    shutil.copy2(Path(__file__).with_name('preview-bootstrap.js'), root / 'preview-bootstrap.js')
    (root / '_headers').write_text('/*\n  X-Robots-Tag: noindex, nofollow\n  Cache-Control: no-store\n')
    (root / '.gitignore').write_text('.netlify/\n')
    write_source(root, args.source)
    result = {'schema': 'isolated-frozen-consumer-preview-v1', 'candidate_commit': CANDIDATE,
              'site_reference': PIN, 'cutoff_utc': CUTOFF, 'dst_simulation': True,
              'continuous_freshness_proven': False, 'production_cutover_allowed': False,
              'data_files': consumed, 'chart_js_version': '4.4.7', 'chart_js_sha256': sha(args.chart_js),
              'attack_events': 'disabled by pinned features.json; no WIP request',
              'remaining_git_inputs': ['historical Kyiv display selection', 'kyiv_threat_mix.json', 'casualty track', 'Sevastopol metadata'],
              'historical_index_note': 'Source-specific fallback is the exact same candidate embedded index. Timestamp metadata rejects embedded candidate at frontend init; no legacy fallback is used.'}
    (root / 'preview-manifest.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'preview': str(root), 'sources': 2, 'cities': 23, 'candidate_bytes_verified': True}))


if __name__ == '__main__':
    main()
