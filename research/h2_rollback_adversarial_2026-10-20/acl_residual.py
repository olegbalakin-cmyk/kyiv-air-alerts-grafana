"""Physical ACL residual D01-D04 and a *proposal*, never automated acceptance."""
from harness import *

def run():
    def d01():
        d=new("d01",stage="raw")
        pre=snapshot(d)
        ns.base(d);ns.temp(d)
        try:ns.run(d,ns.UP,role="h2_migrator_test")
        finally:ns.untemp(d)
        mid=snapshot(d)
        temp_rollback(d,historical(d))
        after=snapshot(d)
        changed=[]
        p=dict((x[0],x) for x in pre["relations"])
        a=dict((x[0],x) for x in after["relations"])
        for rel in sorted(set(p)|set(a)):
            if p.get(rel)!=a.get(rel):
                changed.append({"name":rel,"before":p.get(rel),"after":a.get(rel)})
        ALL["acl"]["catalog_before"]=pre
        ALL["acl"]["catalog_after"]=after
        ALL["acl"]["changed_relations"]=changed
        requires(changed,"expected known physical residual absent; investigate")
        step("D","D01","raw_catalog",d,"relacl NULL vs explicit","RESIDUAL","RESIDUAL")
        return "PARTIAL"
    record("D","D01",d01)
    def d02():
        d=new("d02")
        h=historical(d)
        original=query(d,"SELECT relname,relacl::text FROM pg_class WHERE relnamespace='public'::regnamespace ORDER BY 1")
        temp_rollback(d,h)
        # Compare future grant/revoke behavior against a separate untouched fixture.
        fresh=new("d02control",stage="raw")
        cmds=("GRANT SELECT ON public.alert_episodes TO h2_unrelated_test",
              "REVOKE SELECT ON public.alert_episodes FROM h2_unrelated_test")
        for stmt in cmds:
            query(d,stmt);query(fresh,stmt)
            a=query(d,"SELECT has_table_privilege('h2_unrelated_test','public.alert_episodes','SELECT')")
            c=query(fresh,"SELECT has_table_privilege('h2_unrelated_test','public.alert_episodes','SELECT')")
            requires(a==c,"future GRANT REVOKE drift")
            step("D","D02","future_acl_"+str(len(ALL["steps"])),d,stmt,"MATCH","MATCH")
        ALL["acl"]["pg_dump_caveat"]="raw relacl and pg_dump schema output may differ; exact pg_dump equality not established by this selected semantic control"
        return "PARTIAL"
    record("D","D02",d02)
    def d03():
        # A supported GRANT/REVOKE sequence does not reset relacl back to NULL in the
        # accepted 008 candidate. No catalog update is permitted.
        ALL["acl"]["safe_restoration"]="UNVERIFIED: no supported DDL exact NULL-restoration proof; direct catalog edits and OID-changing table recreation prohibited"
        ALL["limitations"].append("D03 supported DDL NULL restoration not proven; raw equivalence remains PARTIAL")
        return "PARTIAL"
    record("D","D03",d03)
    def d04():
        ALL["acl"]["alternative_acceptance_proposal"]={
            "state":"PROPOSED_ONLY_NOT_ACCEPTED",
            "permitted_catalog_differences":"ONLY verified pg_class.relacl NULL versus exact effective-equivalent explicit relation ACL for enumerated canonical relations",
            "effective_equivalence":"all six relation privileges, columns, schemas, functions, role hierarchy, PUBLIC, grant options, default ACL, foreign owners, and negative controls",
            "future_operations":"GRANT/REVOKE, owner transfer, membership changes, pg_dump schema-only and audit drift require test equivalence or explicit documented divergence",
            "reject_on":"unexpected relation, role, grant option, future operation failure, untrusted CREATE/EXECUTE, corrupt head/history, unexpected owner",
            "risk":"raw catalog drift visible to schema diff and potentially future privilege-management tooling; semantic equivalence not guaranteed outside executed role matrix",
            "authority":"user separate approval mandatory"
        }
        return "PARTIAL"
    record("D","D04",d04)
if __name__=="__main__":run()
