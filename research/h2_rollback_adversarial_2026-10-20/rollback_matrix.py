"""Rollback R01-R16: real PostgreSQL sessions and independent readback."""
import threading
import time
from harness import *

def run():
    ns.roles()
    def r01():
        d=new("r01"); hist=historical(d);before=truth(d)
        before_acl=snapshot(d)["relations"]
        step("R","R01","rollback",d,"008", "00000",temp_rollback(d,hist))
        requires(historical(d)==hist and truth(d)["history_count"]==before["history_count"],"history mismatch")
        requires(query(d,"SELECT to_regclass('public.h2_classification_heads')")[0][0] is None,"head survived")
        requires(not ns.q("postgres","SELECT pg_has_role('h2_migrator_test','h2_head_guard_test','MEMBER')")[0][0],"membership survived")
        changed=before_acl!=snapshot(d)["relations"]
        ALL["acl"]["R01_residual_after_downgrade"]=changed
        step("R","R01","raw_acl_residual_identified",d,"physical relacl","PRESENT" if changed else "ABSENT","PRESENT" if changed else "ABSENT")
    record("R","R01",r01)
    def r02():
        d=new("r02"); orig=historical(d);put(d,"r02"); prior=fingerprint(d)
        step("R","R02","committed_revision_rejected",d,"008", "23514",temp_rollback(d,orig,ok=False),prior,fingerprint(d))
        requires(fingerprint(d)==prior,"rejected rollback mutated state")
    record("R","R02",r02)
    def r03():
        # Interleaving I: writer transaction locks table and inserts, rollback blocks on ACCESS EXCLUSIVE,
        # writer commits first; rollback must reject stale history fingerprint.
        d=new("r03a");h=historical(d)
        c=conn(d,"h2_app_ingest_writer_test","synthetic_only_local_role",autocommit=False,application_name="H2_R03_A")
        c.execute("SET LOCAL statement_timeout='12s'")
        uid=put(d,"race-a",session=c)
        requires(uid,"writer insert missing")
        ns.temp(d)
        p=process(d,ns.DOWN,h,"H2_R03_B")
        try:
            seen=observed(d,lambda ls:any(x["app"]=="H2_R03_B" and not x["granted"] and x["relation"] in ("attack_event_classifications","h2_classification_heads") for x in ls))
            ALL["race_timelines"].append({"interleaving":"writer-first","lock_evidence":seen,"writer_committed":False})
            c.commit()
            ALL["race_timelines"][-1]["writer_committed"]=True
            result=finish_process(p)
            ALL["race_timelines"][-1]["rollback_result"]=result
            step("R","R03","writer_first_rollback_fail_closed",d,"concurrent rollback","23514",result["sqlstate"])
            requires(result["returncode"]!=0,"unexpected rollback COMMIT")
            requires(truth(d)["history_count"]==1 and len(heads(d))==1,"history/head lost")
        finally:
            c.close()
            if p.poll() is None:p.kill()
            ns.untemp(d)
        # Interleaving II: hold table ACCESS EXCLUSIVE in a pre-rollback guard transaction,
        # then begin restricted writer; RELEASE guard and run actual rollback.
        # PostgreSQL DDL and writer serialize; if the rollback wins, writer must fail closed.
        d2=new("r03b"); h2=historical(d2)
        guard=conn(d2,autocommit=False,application_name="H2_R03_A")
        guard.execute("BEGIN")
        guard.execute("LOCK TABLE public.attack_event_classifications IN ACCESS EXCLUSIVE MODE")
        ns.temp(d2)
        rollbackp=process(d2,ns.DOWN,h2,"H2_R03_B")
        observed(d2,lambda ls:any(x["app"]=="H2_R03_B" and not x["granted"] and x["relation"]=="attack_event_classifications" for x in ls))
        # Real writer uses a second independent connection and actual INSERT.
        outcome={}
        def writer():
            try:
                with conn(d2,"h2_app_ingest_writer_test","synthetic_only_local_role",autocommit=True,application_name="H2_R03_WRITER2") as cc:
                    cc.execute("SET statement_timeout='12s'")
                    put(d2,"race-b",session=cc)
                outcome["sqlstate"]="00000"
            except psycopg.Error as e:outcome["sqlstate"]=e.sqlstate
            except Exception as e:outcome["error"]=repr(e)
        t=threading.Thread(target=writer,daemon=True);t.start()
        seen=observed(d2,lambda ls:any(x["app"]=="H2_R03_WRITER2" and not x["granted"] and x["relation"]=="attack_event_classifications" for x in ls))
        guard.commit();guard.close()
        rp=finish_process(rollbackp);t.join(timeout=15)
        ns.untemp(d2)
        ALL["race_timelines"].append({"interleaving":"rollback-first","lock_evidence":seen,"rollback":rp,"writer":outcome,
                                      "post_truth":truth(d2)})
        step("R","R03","rollback_first",d2,"rollback with queued writer","00000",rp["sqlstate"])
        requires(rp["returncode"]==0 and outcome.get("sqlstate")=="42501", "unexpected writer result "+str(outcome))
        requires(truth(d2)["history_count"]==0 and heads(d2) is None,"orphaned revision")
    record("R","R03",r03)
    def r04():
        d=new("r04");h=historical(d)
        query(d,"DROP TABLE public.h2_classification_heads CASCADE")
        before=fingerprint(d)
        step("R","R04","missing_head",d,"008","23514",temp_rollback(d,h,ok=False),before,fingerprint(d))
        requires(fingerprint(d)==before,"partial rollback")
    record("R","R04",r04)
    def r05():
        for what in ("trigger","function"):
            d=new("r05"+what);h=historical(d)
            if what=="trigger":query(d,"DROP TRIGGER h2_revision_head_after_insert ON public.attack_event_classifications")
            else:query(d,"DROP FUNCTION public.h2_enforce_revision_head() CASCADE")
            before=fingerprint(d)
            step("R","R05",what,d,"008","23514",temp_rollback(d,h,ok=False),before,fingerprint(d))
            requires(before==fingerprint(d),"partial rollback")
    record("R","R05",r05)
    def r06():
        d=new("r06");h=historical(d)
        query(d,"GRANT CREATE ON SCHEMA public TO h2_schema_owner_test")
        query(d,"ALTER FUNCTION public.h2_enforce_revision_head() OWNER TO h2_schema_owner_test")
        before=fingerprint(d)
        step("R","R06","wrong_guard_owner",d,"008","42501",temp_rollback(d,h,ok=False),before,fingerprint(d))
        requires(before==fingerprint(d),"partial rollback")
    record("R","R06",r06)
    def r07():
        d=new("r07");h=historical(d)
        before=fingerprint(d)
        step("R","R07","missing_membership",d,"008","42501",rollback(d,h,ok=False),before,fingerprint(d))
        requires(before==fingerprint(d),"partial rollback")
    record("R","R07",r07)
    def r08():
        d=new("r08",stage="base")
        ns.temp(d)
        try:
            query(d,"REVOKE CREATE ON SCHEMA public FROM h2_head_guard_test")
            before=fingerprint(d)
            step("R","R08","missing_schema_create",d,"007","42501",ns.run(d,ns.UP,role="h2_migrator_test",ok=False),before,fingerprint(d))
            requires(before==fingerprint(d),"transfer altered state despite missing CREATE")
        finally:ns.untemp(d)
    record("R","R08",r08)
    def r09():
        d=new("r09")
        for name,inherit in [("h2_inherit_r09","TRUE"),("h2_noinherit_r09","FALSE")]:
            query("postgres",f"CREATE ROLE {name} LOGIN PASSWORD 'synthetic_acl_only' NOSUPERUSER NOINHERIT")
            query("postgres",f"GRANT h2_schema_owner_test TO {name} WITH INHERIT {inherit}, SET TRUE, ADMIN FALSE")
            authority=query(d,"SELECT has_table_privilege(%s,'public.attack_event_classifications','UPDATE')",(name,))[0][0]
            if inherit=="TRUE":
                # This role has inherited *owner* rights. This configuration is unsafe;
                # report as risk, not as a passing restrictive-control test.
                ALL["limitations"].append("R09 synthetic inherited schema-owner role has owner-level history authority; external role hygiene required")
                requires(authority,"expected dangerous inherited UPDATE grant")
                step("R","R09","inherit_true_exposure",d,"effective owner UPDATE","EXPOSED","EXPOSED")
            else:
                requires(not authority,"NOINHERIT should not inherit UPDATE")
                step("R","R09","inherit_false",d,"effective owner UPDATE","DENIED","DENIED")
            step("R","R09","set_role_"+name,d,"SET ROLE h2_schema_owner_test","00000",
                sqlstate(d,name,"SET ROLE h2_schema_owner_test",password="synthetic_acl_only"))
        negative("R","R09","app_guard_owner_membership",d,"h2_app_ingest_writer_test","SET ROLE h2_head_guard_test","42501")
        return "PARTIAL"  # Unsafe external inheritance demonstrated, not corrected by 007.
    record("R","R09",r09)
    def r10():
        d=new("r10",stage="base");query(d,"GRANT CREATE ON SCHEMA public TO PUBLIC")
        before=fingerprint(d)
        step("R","R10","public_create",d,"v3","42501",ns.run(d,ns.ROLE,role="h2_migrator_test",ok=False),before,fingerprint(d))
        requires(before==fingerprint(d),"migration changed ACL")
    record("R","R10",r10)
    def r11_12(i,fault):
        d=new(i);h=historical(d);before=fingerprint(d)
        step("R",i,"fault_"+fault,d,"008","23514",temp_rollback(d,h,fault=fault,ok=False),before,fingerprint(d))
        requires(before==fingerprint(d),"fault not atomic")
    record("R","R11",lambda:r11_12("R11","acl"))
    record("R","R12",lambda:r11_12("R12","owner"))
    def r13():
        d=new("r13");query(d,"GRANT USAGE ON SCHEMA public TO h2_head_guard_test")
        step("R","R13","cross_database_role_delete",d,"DROP ROLE","2BP01",
             sqlstate("postgres","h2_local","DROP ROLE h2_head_guard_test"))
        requires(query("postgres","SELECT count(*) FROM pg_roles WHERE rolname='h2_head_guard_test'")==[(1,)],"role deleted")
    record("R","R13",r13)
    def r14():
        d=new("r14")
        attacks=["ALTER FUNCTION public.h2_enforce_revision_head() RESET ALL",
            "CREATE OR REPLACE FUNCTION public.h2_enforce_revision_head() RETURNS trigger LANGUAGE plpgsql AS 'BEGIN RETURN NEW; END'",
            "ALTER TABLE public.attack_event_classifications DISABLE TRIGGER h2_revision_head_after_insert",
            "DROP TRIGGER h2_revision_head_after_insert ON public.attack_event_classifications",
            "UPDATE public.h2_classification_heads SET changed_at=now()",
            "INSERT INTO public.h2_classification_heads (city_key,historical_episode_id,alert_start_at,alert_end_at,tip_classification_uid) VALUES ('a','b',now(),now(),gen_random_uuid())",
            "UPDATE public.attack_event_classifications SET city_key='x'",
            "DELETE FROM public.attack_event_classifications",
            "TRUNCATE TABLE public.attack_event_classifications"]
        for n,a in enumerate(attacks):negative("R","R14",str(n+1),d,"h2_app_ingest_writer_test",a,"42501")
    record("R","R14",r14)
    # R15 is populated by the C1-C8 full independent suite.
    def r16():
        d=new("r16");h=historical(d)
        before=fingerprint(d)
        step("R","R16","second_007",d,"007","23514",ns.run(d,ns.UP,role="h2_migrator_test",ok=False),before,fingerprint(d))
        requires(before==fingerprint(d),"second transfer modified state")
        step("R","R16","rollback",d,"008","00000",temp_rollback(d,h))
        before=fingerprint(d)
        step("R","R16","double_008",d,"008","23514",temp_rollback(d,h,ok=False),before,fingerprint(d))
        requires(before==fingerprint(d),"second rollback modified state")
        # Re-install on same schema; raw ACL representation remains an unresolved residual.
        ns.base(d);ns.temp(d)
        try:step("R","R16","reinstall",d,"007","00000",ns.run(d,ns.UP,role="h2_migrator_test"))
        finally:ns.untemp(d)
        d2=new("r16partial",stage="raw");before=fingerprint(d2)
        step("R","R16","partially_initialised_008",d2,"008","23514",temp_rollback(d2,h,ok=False),before,fingerprint(d2))
        requires(before==fingerprint(d2),"partial case modified state")
        # Unexpected existing object before 001.
        d3=new("r16object",stage="raw")
        query(d3,"CREATE TABLE public.h2_classification_heads (x int)")
        before=fingerprint(d3)
        step("R","R16","unexpected_object_001",d3,"001",{"42P07","42710"},ns.run(d3,ns.REF/"001_revision_invariants.sql",role="h2_migrator_test",ok=False),before,fingerprint(d3))
        requires(before==fingerprint(d3),"001 non-atomic")
    record("R","R16",r16)
if __name__=="__main__":run()
