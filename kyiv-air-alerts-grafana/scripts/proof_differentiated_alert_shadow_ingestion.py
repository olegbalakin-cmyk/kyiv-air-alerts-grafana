#!/usr/bin/env python3
"""Proof-only child persistence around the accepted differentiated-alert schema proof."""
from __future__ import annotations
import copy, hashlib, json, sqlite3, urllib.request
import proof_differentiated_alert_schema_v2 as schema

def cj(x):
    return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":"))

def canonicalize_ukrainealarm(payload, **kw):
    return schema.ua(payload, **kw)

def canonicalize_alerts_in_ua(alert, **kw):
    raw=copy.deepcopy(alert)
    if str(raw.get("alert_type","")).lower()=="air_raid":
        raw["alert_type"]="AIR"
    return schema.aiu(raw, **kw)

def canonicalize_kyiv(payload, **kw):
    return schema.kyiv(payload, **kw)

def bind(record, episodes):
    return schema.bind(record, episodes)

def component_intervals(records, episode_end_at=None):
    return schema.intervals(records, episode_end_at=episode_end_at)

class ShadowStore:
    """Isolated child-only SQLite store: deliberately no parent mutation API."""
    def __init__(self,path):
        self.db=sqlite3.connect(str(path))
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS alert_state_snapshot(
          snapshot_key TEXT PRIMARY KEY, source TEXT NOT NULL, target_city_key TEXT NOT NULL,
          source_geo_scope TEXT NOT NULL, source_geo_type_raw TEXT, source_geo_id_raw TEXT,
          source_alert_id TEXT, alert_type TEXT NOT NULL, observed_at TEXT NOT NULL,
          source_state_at TEXT, source_active INTEGER NOT NULL, source_alert_level_raw TEXT,
          source_state_raw TEXT, binding_status TEXT NOT NULL, episode_id TEXT,
          raw_payload_hash TEXT NOT NULL, raw_object_path TEXT, payload_json TEXT NOT NULL,
          CHECK(binding_status IN ('BOUND','AMBIGUOUS','UNBOUND')),
          CHECK((binding_status='BOUND' AND episode_id IS NOT NULL) OR
                (binding_status<>'BOUND' AND episode_id IS NULL))
        );
        CREATE TABLE IF NOT EXISTS alert_threat_observation(
          observation_key TEXT PRIMARY KEY,
          snapshot_key TEXT NOT NULL REFERENCES alert_state_snapshot(snapshot_key) ON DELETE CASCADE,
          source_threat_id TEXT, component_signature TEXT, component_identity_basis TEXT,
          level_raw TEXT, cause_raw TEXT, reason_raw TEXT, source_message_raw TEXT,
          source_started_at TEXT, source_ended_at TEXT, severity_normalized TEXT,
          threat_type_normalized TEXT, payload_json TEXT NOT NULL
        );
        """)
        self.db.commit()
    def close(self):
        self.db.close()
    def counts(self):
        return {
          "snapshots":self.db.execute("select count(*) from alert_state_snapshot").fetchone()[0],
          "observations":self.db.execute("select count(*) from alert_threat_observation").fetchone()[0],
        }
    def persist(self,record,fail_after_snapshot=False):
        s=copy.deepcopy(record["snapshot"])
        rows=copy.deepcopy(record["threat_observations"])
        if s["binding_state"]!="BOUND":
            s["episode_id"]=None
        before=self.counts()
        with self.db:
            self.db.execute(
              "INSERT OR IGNORE INTO alert_state_snapshot VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (s["snapshot_key"],s["source"],s["target_city_key"],s["source_geography"]["scope"],
               s["source_geography"].get("type_raw"),s["source_geography"].get("id_raw"),
               s.get("source_alert_id"),s["alert_type"],s["observed_at"],s.get("source_state_at"),
               1 if s.get("source_active") else 0,s.get("source_alert_level_raw"),
               None if s.get("source_state_raw") is None else str(s.get("source_state_raw")),
               s["binding_state"],s.get("episode_id"),s["raw_payload_hash"],
               s.get("raw_object_path"),cj({"snapshot":s,"threat_observations":rows}))
            )
            if fail_after_snapshot:
                raise sqlite3.OperationalError("injected persistence failure")
            for r in rows:
                self.db.execute(
                  "INSERT OR IGNORE INTO alert_threat_observation VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (r["observation_key"],s["snapshot_key"],r.get("source_threat_id"),
                   r.get("component_signature"),r.get("component_identity_basis"),r.get("level_raw"),
                   r.get("cause_raw"),r.get("reason_raw"),r.get("source_message_raw"),
                   r.get("source_started_at"),r.get("source_ended_at"),r.get("severity_normalized"),
                   r.get("threat_type_normalized"),cj(r))
                )
        after=self.counts()
        return {"inserted_snapshots":after["snapshots"]-before["snapshots"],
                "inserted_observations":after["observations"]-before["observations"]}
    def snapshot_rows(self):
        return self.db.execute(
          "select snapshot_key,source,binding_status,episode_id,source_geo_scope,observed_at "
          "from alert_state_snapshot order by observed_at,snapshot_key"
        ).fetchall()

def fetch_json(url,timeout=10):
    req=urllib.request.Request(url,headers={"Accept":"application/json","User-Agent":"differentiated-alert-proof/1"})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        if r.status!=200:
            raise RuntimeError(f"HTTP {r.status}")
        return json.loads(r.read().decode("utf-8"))

def parent_fingerprint(corpus):
    cities={}
    for city,episodes in sorted(corpus.items()):
        rows=[]
        for e in episodes:
            rows.append({"episode_id":e.get("episode_id") or e.get("legacy_episode_id"),
                         "start":e.get("start_at") or e.get("alert_start"),
                         "end":e.get("end_at") or e.get("alert_end")})
        rows.sort(key=lambda x:(x["start"] or "",x["end"] or "",x["episode_id"] or ""))
        serial=cj({"city_key":city,"episode_count":len(rows),"episodes":rows})
        cities[city]={"episode_count":len(rows),"sha256":hashlib.sha256(serial.encode()).hexdigest()}
    g=cj({k:cities[k] for k in sorted(cities)})
    return {"city_count":len(cities),"global_sha256":hashlib.sha256(g.encode()).hexdigest(),"cities":cities}

def metric_fingerprint(metrics):
    rows={}
    for city,v in sorted(metrics.items()):
        rows[city]={
          "denominator":v.get("denominator",v.get("total_alerts",v.get("alerts_total"))),
          "strict":v.get("strict",v.get("strict_n")),
          "sensitivity":v.get("sensitivity",v.get("sensitivity_n")),
          "qa":v.get("qa",v.get("qa_count")),
          "positive_identity":sorted(v.get("positive_identity",[])),
        }
    return {"sha256":hashlib.sha256(cj(rows).encode()).hexdigest(),"cities":rows}
