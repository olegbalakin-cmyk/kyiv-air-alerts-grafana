#!/usr/bin/env python3
"""Create temporary local frontend copies from pinned site-prod; no fixture injection.

The shadow copy reads the actual Work A generator output qualified by bridge.py.
The rollback copy reads unmodified original site-prod JSON, without the overlay.
No files in either Git branch or production paths are modified.
"""
import argparse
import pathlib
import shutil

HERE=pathlib.Path(__file__).resolve().parent

def build(site_root, chartjs, dashboard, output, overlay):
    output=output.resolve()
    source=site_root / "pages-preview"
    assert source.is_dir() and (site_root / "data/dashboard_data.json").is_file()
    assert output != source and source not in output.parents
    assert output != site_root and site_root not in output.parents
    assert not output.exists(), "Output directory must not already exist"
    output.mkdir(parents=True)
    for path in source.iterdir():
        if path.is_file():
            shutil.copy2(path,output/path.name)
    (output/"data").mkdir()
    for name in ("dashboard_data.json","site_derived.json","kyiv_threat_mix.json"):
        shutil.copy2(site_root/"data"/name,output/"data"/name)
    shutil.copy2(dashboard,output/"data"/"dashboard_data.json")
    shutil.copy2(chartjs,output/"chart.umd.js")
    app=(output/"app.js").read_text(encoding="utf-8")
    remote='const RAW_DATA_BASE = "https://raw.githubusercontent.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/site-prod/kyiv-air-alerts-grafana/data/";'
    assert app.count(remote)==1, "Unrecognized production data base"
    (output/"app.js").write_text(app.replace(remote,'const RAW_DATA_BASE = "/data/";'),encoding="utf-8")
    index=(output/"index.html").read_text(encoding="utf-8")
    external="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"
    tag='<script src="app.js?v=20261023-daily28-allcities180-prod1"></script>'
    assert index.count(external)==1 and index.count(tag)==1, "Unrecognized script contract"
    index=index.replace(external,"chart.umd.js")
    if overlay:
        shutil.copy2(HERE/"coverage-preview.js",output/"coverage-preview.js")
        index=index.replace(tag,tag+'\n  <script src="coverage-preview.js"></script>')
    index=index.replace('<meta name="robots" content="index,follow,max-snippet:-1">',
                        '<meta name="robots" content="noindex,nofollow">')
    index=index.replace("</body>",'<div id="research-watermark" style="position:fixed;bottom:4px;left:6px;font:12px system-ui;color:#f8e45c;z-index:9999;pointer-events:none">LOCAL SHADOW · NOT PUBLISHED</div>\n</body>')
    (output/"index.html").write_text(index,encoding="utf-8")

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for name in ("site_root","chart_js","shadow_dashboard","preview","rollback"):
        p.add_argument("--"+name.replace("_","-"),type=pathlib.Path,required=True)
    a=p.parse_args()
    site=a.site_root.resolve()
    original=site/"data/dashboard_data.json"
    build(site,a.chart_js.resolve(),a.shadow_dashboard.resolve(),a.preview,True)
    build(site,a.chart_js.resolve(),original,a.rollback,False)
    print("LOCAL_PREVIEW_DIR="+str(a.preview))
    print("LOCAL_ROLLBACK_DIR="+str(a.rollback))
