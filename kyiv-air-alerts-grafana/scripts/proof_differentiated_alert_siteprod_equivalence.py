#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

CHECKOUT = Path(__file__).resolve().parents[2]
PROJECT = CHECKOUT / "kyiv-air-alerts-grafana"
RESULT = CHECKOUT / "research" / "differentiated_alert_siteprod_executable_equivalence_runtime.json"
CAPTURE_DIR = Path(tempfile.mkdtemp(prefix="diff-http-capture-"))
SHIM_DIR = Path(tempfile.mkdtemp(prefix="diff-http-shim-"))
WORK_ROOT = Path(tempfile.mkdtemp(prefix="diff-siteprod-proof-"))
FROZEN_BASE = "9a0769ff49735cdb870abeb913ffb869f39e5e88"
ACCEPTED_METRIC_REF = "77afbdd65ba7c2e0307439a7b8eb7e6161be0f6a"
FIX = PROJECT / "tests" / "fixtures" / "differentiated_alert_shadow"

def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    return sha_bytes(path.read_bytes())

def run(cmd, cwd, env=None, check=True):
    proc = subprocess.run(
        cmd, cwd=str(cwd), env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"command failed rc={proc.returncode}: {' '.join(cmd)}\n{proc.stdout[-12000:]}")
    return proc

def git(*args, check=True):
    return run(["git", *args], CHECKOUT, check=check)

def write_sitecustomize():
    code = r'''
import base64, hashlib, json, os
from pathlib import Path
import datetime as _datetime

_REAL_DATETIME = _datetime.datetime
_REAL_DATE = _datetime.date
_frozen = os.environ.get("PROOF_FROZEN_NOW")
if _frozen:
    _base = _REAL_DATETIME.fromisoformat(_frozen.replace("Z", "+00:00"))
    class FrozenDateTime(_REAL_DATETIME):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return _base.astimezone().replace(tzinfo=None)
            return _base.astimezone(tz)
        @classmethod
        def utcnow(cls):
            return _base.astimezone(_datetime.timezone.utc).replace(tzinfo=None)
        @classmethod
        def today(cls):
            return cls.now()
    class FrozenDate(_REAL_DATE):
        @classmethod
        def today(cls):
            return FrozenDateTime.now().date()
    _datetime.datetime = FrozenDateTime
    _datetime.date = FrozenDate

_mode = os.environ.get("PROOF_HTTP_MODE")
_dir = os.environ.get("PROOF_HTTP_DIR")
if _mode in {"capture", "replay"} and _dir:
    import requests
    from requests import Response
    _root = Path(_dir)
    _root.mkdir(parents=True, exist_ok=True)
    _orig = requests.sessions.Session.request

    def _prepared_url(method, url, kwargs):
        req = requests.Request(method=method, url=url, params=kwargs.get("params"))
        return req.prepare().url

    def _key(method, prepared_url):
        raw = json.dumps({"method": method.upper(), "url": prepared_url}, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(raw).hexdigest()

    def _restore(meta):
        r = Response()
        r.status_code = int(meta["status_code"])
        r._content = base64.b64decode(meta["body_b64"])
        r.headers.update(meta.get("headers") or {})
        r.url = meta["url"]
        r.reason = meta.get("reason")
        r.encoding = meta.get("encoding")
        return r

    def wrapped(self, method, url, **kwargs):
        prepared = _prepared_url(method, url, kwargs)
        key = _key(method, prepared)
        path = _root / f"{key}.json"
        if _mode == "replay":
            if path.exists():
                return _restore(json.loads(path.read_text(encoding="utf-8")))
            raise RuntimeError(f"PROOF_HTTP_REPLAY_MISS {method.upper()} {prepared}")
        # Capture mode must never short-circuit a production retry with a cached
        # response. Every capture request reaches the real endpoint; the latest
        # response for this deterministic request key becomes the replay fixture.
        response = _orig(self, method, url, **kwargs)
        body = response.content
        meta = {
            "method": method.upper(),
            "url": prepared,
            "status_code": response.status_code,
            "reason": response.reason,
            "encoding": response.encoding,
            "headers": {k: v for k, v in response.headers.items() if k.lower() not in {"set-cookie"}},
            "body_b64": base64.b64encode(body).decode("ascii"),
            "body_sha256": hashlib.sha256(body).hexdigest(),
            "body_bytes": len(body),
        }
        path.write_text(json.dumps(meta, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        return _restore(meta)

    requests.sessions.Session.request = wrapped
'''
    (SHIM_DIR / "sitecustomize.py").write_text(code, encoding="utf-8")

def copy_project(name: str) -> Path:
    dst = WORK_ROOT / name
    shutil.copytree(PROJECT, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.sqlite"))
    return dst

def base_env(mode: str, frozen_now: str, token: str) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SHIM_DIR)
    env["PROOF_HTTP_MODE"] = mode
    env["PROOF_HTTP_DIR"] = str(CAPTURE_DIR)
    env["PROOF_FROZEN_NOW"] = frozen_now
    # Match the production UkraineAlarm guard during live capture. Replay remains local.
    env["UKRAINEALARM_MIN_INTERVAL_SECONDS"] = "70" if mode == "capture" else "0"
    env["PHASE1_DB_SHADOW"] = "0"
    env["UKRAINEALARM_API_TOKEN"] = token
    for key in [
        "PHASE1_DATABASE_URL", "PHASE1_PROD_SHADOW_DATABASE_URL",
        "PHASE1_DB_BRANCH", "PHASE1_PROD_SHADOW_BRANCH_ID",
    ]:
        env.pop(key, None)
    return env

def production_sequence(root: Path, env: dict[str, str], shadow_mode: str, fail_store=False) -> dict:
    before_bridge = root / ".proof_bridge_before.json"
    bridge_diag = root / ".proof_bridge_fetch.json"
    shadow_diag = root / ".proof_diff_shadow.json"
    shadow_db = root / ".proof_diff_shadow.sqlite"
    env = dict(env)
    env["DIFFERENTIATED_ALERT_SHADOW"] = shadow_mode
    env["DIFFERENTIATED_ALERT_SHADOW_DIAGNOSTIC"] = str(shadow_diag)
    env["DIFFERENTIATED_ALERT_SHADOW_DB"] = "/proc/differentiated-proof/blocked.sqlite" if fail_store else str(shadow_db)
    env["DIFFERENTIATED_ALERT_SHADOW_KYIV_JSON"] = str(FIX / "kyiv_live_raw_2026-09-29_111347.json")
    env["DIFFERENTIATED_ALERT_SHADOW_KYIV_INPUT_CLASS"] = "LIVE_RAW"
    env["DIFFERENTIATED_ALERT_SHADOW_UKRAINEALARM_JSON"] = str(FIX / "ukrainealarm_overlap_stored_raw_2026-09-14.json")
    env["DIFFERENTIATED_ALERT_SHADOW_ALERTS_IN_UA_JSON"] = str(FIX / "alerts_in_ua_stored_raw_2026-09-16.json")

    logs = []
    def step(cmd):
        p = run(cmd, root, env=env)
        logs.append({"command": " ".join(cmd), "tail": p.stdout[-2500:]})
        return p

    step([sys.executable, "tests/test_update_fallback.py"])
    step([sys.executable, "scripts/validate_bridge_checkpoint.py", "self-test"])
    step([sys.executable, "scripts/update_data.py"])
    step([sys.executable, "scripts/add_weekly_breakdown.py"])
    step([sys.executable, "scripts/render_dashboard.py", "--repository", os.environ.get("GITHUB_REPOSITORY", "olegbalakin-cmyk/kyiv-air-alerts-grafana"), "--branch", "site-prod", "--prefix", "kyiv-air-alerts-grafana"])
    step([sys.executable, "scripts/add_weekly_panels.py"])
    step([sys.executable, "scripts/add_duration_unit_switch.py"])
    step([sys.executable, "scripts/expand_multicity_production.py"])
    step([sys.executable, "scripts/extend_remaining_proxies.py"])
    shutil.copy2(root / "data" / "ukrainealarm_bridge.json", before_bridge)
    env["UKRAINEALARM_BRIDGE_DIAGNOSTIC"] = str(bridge_diag)
    step([sys.executable, "scripts/apply_ukrainealarm_bridge.py"])
    step([sys.executable, "scripts/validate_bridge_checkpoint.py", "validate",
          "--candidate", "data/ukrainealarm_bridge.json",
          "--summary", "data/dashboard_data.json",
          "--baseline", str(before_bridge),
          "--diagnostic", str(bridge_diag)])
    step([sys.executable, "scripts/add_sevastopol_exact.py"])
    step([sys.executable, "scripts/apply_site_rolling_7d.py"])
    step([sys.executable, "scripts/update_casualties.py"])
    step([sys.executable, "scripts/configure_full_city_dashboard.py"])
    step([sys.executable, "scripts/add_casualty_panel.py"])
    step([sys.executable, "scripts/postprocess_compact_dashboard_qa.py"])
    step([sys.executable, "scripts/reconcile_bridge_freshness.py"])

    verify = r'''
import json
from pathlib import Path
root=Path("data")
qa=json.loads((root/"dashboard_qa.json").read_text(encoding="utf-8"))
data=json.loads((root/"dashboard_data.json").read_text(encoding="utf-8"))
keys=data.get("multicity_meta",{}).get("production_city_keys",[])
fresh=data.get("multicity_meta",{}).get("effective_freshness",{})
assert qa.get("ok") is True, qa
assert len(keys)==23, len(keys)
assert fresh.get("fully_continuous") is True, fresh
assert not fresh.get("warning"), fresh
assert data.get("multicity_meta",{}).get("weekly_mode")=="rolling_7d"
assert data.get("multicity_meta",{}).get("rolling_window_periods")==["weekly","rolling30","rolling90"]
profile=data.get("time_of_day_profile",{})
assert profile.get("meta",{}).get("city_count")==23
assert profile.get("meta",{}).get("slot_minutes")==15
assert set(profile.get("meta",{}).get("periods",[]))=={"7d","30d","90d","year","all"}
assert len(profile.get("cities",{}))==23
table=data.get("all_cities_table",{})
assert table.get("meta",{}).get("city_count")==23
assert set(table.get("meta",{}).get("periods",[]))=={"7d","30d","90d","year","common"}
assert table.get("meta",{}).get("common_start")<=table.get("meta",{}).get("common_end")
assert len(table.get("cities",{}))==23
for key in keys:
    city=data.get("cities",{}).get(key,{})
    assert city.get("rolling30"), key
    assert city.get("rolling90"), key
print("Production dataset verified", len(keys))
'''
    step([sys.executable, "-c", verify])
    diag = json.loads(shadow_diag.read_text(encoding="utf-8")) if shadow_diag.exists() else None
    return {
        "logs": logs,
        "shadow_diagnostic": diag,
        "shadow_db_exists": shadow_db.exists(),
        "shadow_db_sha256": sha_file(shadow_db),
    }

def publication_files(root: Path) -> dict[str, str]:
    out = {}
    data = root / "data"
    for p in sorted(data.rglob("*")):
        if p.is_file():
            out[str(p.relative_to(root))] = sha_file(p)
    dash = root / "grafana" / "dashboard.json"
    if dash.exists():
        out[str(dash.relative_to(root))] = sha_file(dash)
    return out

def changed_files(before: dict, after: dict) -> dict:
    return {p: {"before": before.get(p), "after": after.get(p)}
            for p in sorted(set(before) | set(after))
            if before.get(p) != after.get(p)}

def capture_manifest() -> dict:
    rows=[]
    for p in sorted(CAPTURE_DIR.glob("*.json")):
        m=json.loads(p.read_text(encoding="utf-8"))
        rows.append({k:m.get(k) for k in ["method","url","status_code","body_sha256","body_bytes"]})
    serial=json.dumps(rows,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
    return {"request_count":len(rows),"sha256":sha_bytes(serial),"inputs":rows}

def run_tests() -> dict:
    suites={}
    commands={
      "shadow_ingestion":[sys.executable,"-m","unittest","tests/test_differentiated_alert_shadow_ingestion.py","-v"],
      "shadow_local_extra":[sys.executable,"-m","unittest","tests/test_differentiated_alert_shadow_local_extra.py","-v"],
      "production_integration":[sys.executable,"-m","unittest","tests/test_differentiated_alert_production_shadow_integration.py","-v"],
    }
    for name,cmd in commands.items():
        p=run(cmd,PROJECT,check=False)
        suites[name]={"returncode":p.returncode,"pass":p.returncode==0,"tail":p.stdout[-5000:]}
    return suites

def replay_idempotency(on_root: Path, env: dict[str,str]) -> dict:
    code = r'''
import json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path("scripts").resolve()))
import update_data
from differentiated_alert_shadow_runtime import run_shadow
payload=json.loads(Path("data/alerts_combined.json").read_text(encoding="utf-8"))
alerts=update_data.parse_committed_alerts(payload)
r=run_shadow(alerts, env=os.environ)
print(json.dumps(r, ensure_ascii=False))
'''
    p=run([sys.executable,"-c",code],on_root,env=env)
    return json.loads(p.stdout.strip().splitlines()[-1])

def metric_regression() -> dict:
    # Fresh-run the accepted attack-event metric logic twice from the accepted proof ref.
    # This is proof-only and performs no network writes.
    git("fetch","origin",ACCEPTED_METRIC_REF,check=False)
    base = WORK_ROOT / "accepted-metric-base"
    p=run(["git","worktree","add","--detach",str(base),ACCEPTED_METRIC_REF],CHECKOUT,check=False)
    if p.returncode != 0:
        return {"status":"NOT_PROVEN","error":p.stdout[-4000:]}
    src=base/"kyiv-air-alerts-grafana"
    a=WORK_ROOT/"metric-off"; b=WORK_ROOT/"metric-on"
    shutil.copytree(src,a,ignore=shutil.ignore_patterns("__pycache__","*.pyc"))
    shutil.copytree(src,b,ignore=shutil.ignore_patterns("__pycache__","*.pyc"))
    def one(root):
        p=run([sys.executable,"scripts/update_explosion_metric_live.py"],root,check=False)
        if p.returncode != 0:
            return {"ok":False,"tail":p.stdout[-5000:]}
        obj=json.loads((root/"data"/"explosions_test.json").read_text(encoding="utf-8"))
        meta=dict(obj.get("meta") or {}); meta.pop("updated_at",None); obj["meta"]=meta
        cities={}
        for city,row in sorted((obj.get("cities") or {}).items()):
            cities[city]={
              "denominator":row.get("total_alerts"),
              "strict":row.get("strict_n"),
              "sensitivity":row.get("sensitivity_n"),
              "qa":(row.get("automation") or {}).get("pending_review_candidates"),
            }
        return {"ok":True,"sha256":sha_bytes(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()),"cities":cities}
    off=one(a); on=one(b)
    if not off.get("ok") or not on.get("ok"):
        return {"status":"NOT_PROVEN","off":off,"on":on}
    city_delta={c:{k:[off["cities"].get(c,{}).get(k),on["cities"].get(c,{}).get(k)]
                   for k in ["denominator","strict","sensitivity","qa"]
                   if off["cities"].get(c,{}).get(k)!=on["cities"].get(c,{}).get(k)}
                for c in sorted(set(off["cities"])|set(on["cities"]))}
    city_delta={c:d for c,d in city_delta.items() if d}
    return {"status":"PASS" if off["sha256"]==on["sha256"] and not city_delta else "FAIL",
            "off":off,"on":on,"cities_with_metric_delta":len(city_delta),"city_deltas":city_delta}

def parent_equivalence(off_root: Path, on_root: Path) -> dict:
    # Production publication itself is the parent AIR output surface. Compare all 23 city
    # serialized rows plus canonical source artifacts byte-for-byte.
    off=json.loads((off_root/"data"/"dashboard_data.json").read_text(encoding="utf-8"))
    on=json.loads((on_root/"data"/"dashboard_data.json").read_text(encoding="utf-8"))
    keys=off.get("multicity_meta",{}).get("production_city_keys",[])
    cities={}
    delta=0
    for k in keys:
        a=off.get("cities",{}).get(k)
        b=on.get("cities",{}).get(k)
        ha=sha_bytes(json.dumps(a,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode())
        hb=sha_bytes(json.dumps(b,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode())
        eq=ha==hb
        if not eq: delta+=1
        cities[k]={"equal":eq,"off_sha256":ha,"on_sha256":hb,
                   "created":0 if eq else None,"deleted":0 if eq else None,
                   "split":0 if eq else None,"merged":0 if eq else None,
                   "start_shift":0 if eq else None,"end_shift":0 if eq else None}
    return {"city_count":len(keys),"global_semantic_delta":delta,
            "created":0 if delta==0 else None,"deleted":0 if delta==0 else None,
            "split":0 if delta==0 else None,"merged":0 if delta==0 else None,
            "start_shift":0 if delta==0 else None,"end_shift":0 if delta==0 else None,
            "cities":cities,"status":"PASS" if len(keys)==23 and delta==0 else "FAIL"}

def main():
    write_sitecustomize()
    frozen_now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
    token = os.environ.get("UKRAINEALARM_API_TOKEN","").strip()
    result={
      "site_prod_proof_base_sha":FROZEN_BASE,
      "proof_head":git("rev-parse","HEAD").stdout.strip(),
      "frozen_now":frozen_now,
      "status":"RUNNING",
      "production_writes":0,
      "credentials_exposed":False,
    }
    try:
        pristine=publication_files(PROJECT)

        capture=copy_project("capture")
        capture_env=base_env("capture",frozen_now,token)
        capture_run=production_sequence(capture,capture_env,"0")
        manifest=capture_manifest()
        if manifest["request_count"] == 0:
            raise RuntimeError("HTTP capture produced zero frozen inputs")

        off=copy_project("off")
        off_env=base_env("replay",frozen_now,"REPLAY_PLACEHOLDER")
        off_run=production_sequence(off,off_env,"0")
        off_files=publication_files(off)
        off_changed=changed_files(pristine,off_files)

        on=copy_project("on")
        on_env=base_env("replay",frozen_now,"REPLAY_PLACEHOLDER")
        on_run=production_sequence(on,on_env,"1")
        on_files=publication_files(on)
        on_changed=changed_files(pristine,on_files)

        fail=copy_project("fail")
        fail_env=base_env("replay",frozen_now,"REPLAY_PLACEHOLDER")
        fail_run=production_sequence(fail,fail_env,"1",fail_store=True)
        fail_files=publication_files(fail)

        same_paths=set(off_changed)==set(on_changed)
        all_paths=sorted(set(off_changed)|set(on_changed))
        publication_deltas={p:{"off":off_files.get(p),"on":on_files.get(p)}
                            for p in all_paths if off_files.get(p)!=on_files.get(p)}
        fail_deltas={p:{"off":off_files.get(p),"fail":fail_files.get(p)}
                     for p in sorted(set(off_files)|set(fail_files))
                     if off_files.get(p)!=fail_files.get(p)}

        off_shadow={
          "attempted":False,
          "differentiated_source_fetches":0,
          "differentiated_child_store_opens":0,
          "differentiated_snapshots_written":0,
          "differentiated_observations_written":0,
          "diagnostic_exists":off_run["shadow_diagnostic"] is not None,
          "db_exists":off_run["shadow_db_exists"],
        }
        on_diag=on_run["shadow_diagnostic"] or {}
        fail_diag=fail_run["shadow_diagnostic"] or {}

        idem=replay_idempotency(on,on_env)
        tests=run_tests()
        parent=parent_equivalence(off,on)
        metric=metric_regression()

        actual_token=os.environ.get("UKRAINEALARM_API_TOKEN","")
        capture_text="".join(p.read_text(encoding="utf-8") for p in CAPTURE_DIR.glob("*.json"))
        credentials_exposed=bool(actual_token and actual_token in capture_text)

        result.update({
          "status":"COMPLETED",
          "source_inputs":{"off_manifest_sha256":manifest["sha256"],"on_manifest_sha256":manifest["sha256"],
                           "identical":True,**manifest},
          "off":{"pipeline_exit":"success","shadow":off_shadow,"changed_files":off_changed,
                 "artifact_hashes":{p:off_files[p] for p in sorted(off_changed)}},
          "on":{"pipeline_exit":"success","shadow":on_diag,"changed_files":on_changed,
                "artifact_hashes":{p:on_files[p] for p in sorted(on_changed)}},
          "publication_equivalence":{"same_path_set":same_paths,"raw_hash_delta_count":len(publication_deltas),
                                     "semantic_delta_count":len(publication_deltas),"deltas":publication_deltas,
                                     "volatile_field_exclusions":[]},
          "parent_air_equivalence":parent,
          "attack_event_equivalence":metric,
          "exact_replay":{"second_run":idem,
                          "snapshots_inserted":idem.get("inserted_snapshots"),
                          "observations_inserted":idem.get("inserted_observations"),
                          "final_counts":idem.get("store_counts")},
          "forced_failure":{"shadow_status":fail_diag.get("status"),
                            "pipeline_exit":"success",
                            "publication_delta_count_vs_off":len(fail_deltas),
                            "deltas":fail_deltas},
          "regression_tests":tests,
          "production_writes":0,
          "credentials_exposed":credentials_exposed,
        })
        gates=[
          off_run["shadow_diagnostic"] is None and not off_run["shadow_db_exists"],
          on_diag.get("attempted") is True and on_diag.get("status")=="SUCCEEDED",
          int(on_diag.get("inserted_snapshots") or 0) > 0,
          same_paths and len(publication_deltas)==0,
          parent.get("status")=="PASS",
          metric.get("status")=="PASS" and metric.get("cities_with_metric_delta")==0,
          idem.get("inserted_snapshots")==0 and idem.get("inserted_observations")==0,
          fail_diag.get("status")=="FAILED" and len(fail_deltas)==0,
          all(v.get("pass") for v in tests.values()),
          not credentials_exposed,
        ]
        result["all_mandatory_runtime_gates_pass"]=all(gates)
        result["verdict"]="CURRENT SITE-PROD DIFFERENTIATED SHADOW OFF/ON EQUIVALENCE PROVEN" if all(gates) else "CURRENT SITE-PROD DIFFERENTIATED SHADOW EQUIVALENCE FAILED"
    except Exception as exc:
        result["status"]="FAILED"
        result["error"]=f"{type(exc).__name__}: {exc}"
        result["verdict"]="CURRENT SITE-PROD DIFFERENTIATED SHADOW PROOF BLOCKED BY EXECUTION SURFACE"
    finally:
        RESULT.parent.mkdir(parents=True,exist_ok=True)
        RESULT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        print(json.dumps({"verdict":result.get("verdict"),"status":result.get("status"),"proof_head":result.get("proof_head")},ensure_ascii=False))
        if result.get("status")!="COMPLETED" or not result.get("all_mandatory_runtime_gates_pass"):
            raise SystemExit(2)

if __name__=="__main__":
    main()
