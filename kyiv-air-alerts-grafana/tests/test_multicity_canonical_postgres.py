import copy
import os
import sys
import unittest
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import multicity_canonical_postgres as m
from db_phase1_core import CANONICALIZATION_VERSION, legacy_episode_id


def episode(city, start, end, uid=None):
    return {
        "episode_uid": uid or str(uuid.uuid4()),
        "legacy_episode_id": legacy_episode_id(city, start, end),
        "city_key": city, "alert_type": "AIR", "start_at": start, "end_at": end,
        "episode_state": "closed", "canonicalization_version": CANONICALIZATION_VERSION,
    }


class Cursor:
    def __init__(self, c): self.c=c; self.one=None; self.many=[]; self.commands=[]
    def execute(self, sql, params=()):
        self.commands.append(sql); s=self.c.state
        if "MULTICITY:BEGIN" in sql: self.c.snap=copy.deepcopy(s); return
        if "MULTICITY:EXISTING_EPISODES" in sql:
            self.many=[(r["episode_uid"],r["legacy_episode_id"],r["city_key"],r["alert_type"],r["start_at"],r["end_at"],r["episode_state"],r["canonicalization_version"]) for r in s["episodes"]]; return
        if "PHASE1:RUN_INSERT" in sql: s["runs"].append({"run_id":str(params[0])}); return
        if "PHASE1:EPISODE_LOOKUP" in sql:
            r=next((x for x in s["episodes"] if x["legacy_episode_id"]==params[0]),None)
            self.one=None if r is None else (r["episode_uid"],r["legacy_episode_id"],r["city_key"],r["alert_type"],r["start_at"],r["end_at"],r["episode_state"],r["canonicalization_version"],r.get("created_by_run_id"),r.get("updated_by_run_id")); return
        if "PHASE1:EPISODE_INSERT" in sql:
            uid=str(uuid.uuid4()); s["episodes"].append({"episode_uid":uid,"legacy_episode_id":params[0],"city_key":params[1],"alert_type":params[2],"start_at":params[3],"end_at":params[4],"episode_state":params[5],"canonicalization_version":params[6],"created_by_run_id":str(params[7]),"updated_by_run_id":str(params[8])}); self.one=(uid,); return
        if "PHASE1:RUN_FINALIZE" in sql: return
        raise AssertionError(sql)
    def fetchone(self): return self.one
    def fetchall(self): return self.many
    def close(self): pass


class Connection:
    def __init__(self,state=None): self.state=copy.deepcopy(state or {"episodes":[],"runs":[],"sources":[1],"checkpoints":[1],"snapshots":[1],"threats":[1]}); self.snap=None; self.commits=0
    def cursor(self): return Cursor(self)
    def commit(self): self.commits+=1; self.snap=None
    def rollback(self):
        if self.snap is not None: self.state=self.snap; self.snap=None


def prov(): return {"run_kind":m.RUN_KIND,"schema_version":"001_phase1_core","canonicalization_version":CANONICALIZATION_VERSION,"parameters":{}}


class TestMulticity(unittest.TestCase):
    def setUp(self):
        self.a=episode("lviv","2026-01-01T00:00:00Z","2026-01-01T00:10:00Z")
        self.b=episode("kyiv","2026-01-02T00:00:00Z","2026-01-02T00:10:00Z")
        self.c=episode("kharkiv","2026-01-03T00:00:00Z","2026-01-03T00:10:00Z")

    def test_preflight_mixed(self):
        x=m.classify_candidates([self.a,self.b,self.c],[self.a])
        self.assertEqual((x["exact_existing"],x["missing_to_insert"],x["semantic_conflict"]),(1,2,0))

    def test_exact_existing_zero_write_and_uid_preserved(self):
        c=Connection({"episodes":[self.a],"runs":[],"sources":[],"checkpoints":[],"snapshots":[],"threats":[]})
        out=m.persist_canonical_episodes(c,[self.a],provenance=prov(),db_branch="proof")
        self.assertEqual((out["status"],out["writes"]),("already_persisted",0))
        self.assertEqual(c.state["episodes"][0]["episode_uid"],self.a["episode_uid"])

    def test_new_and_mixed_no_update(self):
        c=Connection({"episodes":[copy.deepcopy(self.a)],"runs":[],"sources":[],"checkpoints":[],"snapshots":[],"threats":[]})
        original=copy.deepcopy(c.state["episodes"][0])
        out=m.persist_canonical_episodes(c,[self.a,self.b],provenance=prov(),db_branch="proof")
        self.assertEqual((out["episodes_existing"],out["episodes_inserted"],out["episodes_updated"]),(1,1,0))
        self.assertEqual(c.state["episodes"][0],original)

    def test_atomic_rollback_preserves_other_state(self):
        c=Connection({"episodes":[self.a],"runs":[],"sources":[{"x":1}],"checkpoints":[{"x":2}],"snapshots":[{"x":3}],"threats":[{"x":4}]}); before=copy.deepcopy(c.state)
        with self.assertRaises(m.ForcedMulticityFailure):
            m.persist_canonical_episodes(c,[self.a,self.b,self.c],provenance=prov(),db_branch="proof",force_failure_after_new=1)
        self.assertEqual(c.state,before)

    def test_exact_and_fresh_process_retry(self):
        c=Connection(); m.persist_canonical_episodes(c,[self.b,self.c],provenance=prov(),db_branch="proof")
        state=copy.deepcopy(c.state)
        r1=m.persist_canonical_episodes(Connection(state),[self.b,self.c],provenance=prov(),db_branch="proof")
        r2=m.persist_canonical_episodes(Connection(copy.deepcopy(state)),[self.b,self.c],provenance=prov(),db_branch="proof")
        self.assertEqual((r1["writes"],r2["writes"]),(0,0))

    def test_protected_state_and_lviv_uid_immutability(self):
        state={"episodes":[copy.deepcopy(self.a)],"runs":[],"sources":[{"id":"src"}],"checkpoints":[{"seq":1}],"snapshots":[{"id":"snap"}],"threats":[{"id":"threat"}]}
        c=Connection(state); before=copy.deepcopy(c.state)
        m.persist_canonical_episodes(c,[self.a,self.b],provenance=prov(),db_branch="proof")
        self.assertEqual(c.state["episodes"][0]["episode_uid"],before["episodes"][0]["episode_uid"])
        for key in ("sources","checkpoints","snapshots","threats"):
            self.assertEqual(c.state[key],before[key])

    def test_duplicate_classification_covers_legacy_and_interval(self):
        x=m.scan_candidates([self.b,copy.deepcopy(self.b)])
        self.assertEqual(x["duplicate_candidate_legacy_id"],1)
        self.assertEqual(x["duplicate_candidate_interval"],1)

    def test_rejections(self):
        bad=copy.deepcopy(self.b); bad["end_at"]=bad["start_at"]
        with self.assertRaises(m.CorpusValidationError): m.scan_candidates([bad])
        bad=copy.deepcopy(self.b); bad["city_key"]=""
        with self.assertRaises(m.CorpusValidationError): m.scan_candidates([bad])
        bad=copy.deepcopy(self.b); bad["alert_type"]=""
        with self.assertRaises(m.CorpusValidationError): m.scan_candidates([bad])
        bad=copy.deepcopy(self.b); bad["canonicalization_version"]="v2"
        with self.assertRaises(m.CorpusValidationError): m.scan_candidates([bad])
        with self.assertRaises(m.CorpusValidationError):
            m.persist_canonical_episodes(Connection(),[self.b,copy.deepcopy(self.b)],provenance=prov(),db_branch="proof")


if __name__=="__main__": unittest.main()
