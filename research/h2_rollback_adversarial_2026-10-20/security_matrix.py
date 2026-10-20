"""SECURITY DEFINER C1-C8 SQL controls, bound to real installed 001/003/007."""
from harness import *

def run():
    def secure(db):
        v=query(db,"SELECT proowner::regrole::text,prosecdef,proconfig::text,pg_get_functiondef(oid) FROM pg_proc WHERE oid='public.h2_enforce_revision_head()'::regprocedure")[0]
        requires(v[0]=="h2_head_guard_test" and v[1] and "pg_catalog, pg_temp" in v[2],"installed guard config incorrect")
        requires("public.attack_event_classifications" in v[3] and "public.h2_classification_heads" in v[3],"untrusted relation name")
        return v[3]
    def c01():
        d=new("c01");definition=secure(d)
        with conn(d,"h2_app_ingest_writer_test","synthetic_only_local_role",autocommit=True) as c:
            c.execute("CREATE TEMP TABLE h2_classification_heads (tip_classification_uid uuid,city_key text)")
            c.execute("CREATE TEMP TABLE attack_event_classifications (classification_uid uuid)")
            uid=put(d,"c01",session=c)
            shadow=c.execute("SELECT count(*) FROM pg_temp.h2_classification_heads").fetchone()[0]
        requires(shadow==0 and query(d,"SELECT count(*) FROM public.h2_classification_heads")==[(1,)],"TEMP shadow polluted")
        step("C","C1","pg_temp_relation_shadow",d,"actual INSERT","00000","00000")
    record("C","C1",c01)
    def c02():
        d=new("c02");definition=secure(d)
        query(d,"CREATE SCHEMA attacker")
        query(d,"GRANT CREATE,USAGE ON SCHEMA attacker TO h2_app_ingest_writer_test")
        negative("C","C2","public_guard_replacement",d,"h2_app_ingest_writer_test",
                 "CREATE OR REPLACE FUNCTION public.h2_enforce_revision_head() RETURNS trigger LANGUAGE plpgsql AS 'BEGIN RETURN NEW; END'","42501")
        # Creating a same-name function in an untrusted namespace must not redirect the trigger.
        query(d,"GRANT USAGE ON SCHEMA attacker TO PUBLIC")
        query(d,"CREATE FUNCTION attacker.now() RETURNS timestamptz LANGUAGE sql AS 'SELECT ''2000-01-01''::timestamptz'")
        with conn(d,"h2_app_ingest_writer_test","synthetic_only_local_role",autocommit=True) as c:
            c.execute("SET search_path=attacker, public, pg_catalog")
            put(d,"c02",session=c)
        requires(len(heads(d))==1,"guard redirected")
        step("C","C2","untrusted_helper_shadow",d,"attacker.now","00000","00000")
        return "PARTIAL" if "now()" not in definition else None
    record("C","C2",c02)
    def c03():
        d=new("c03");definition=secure(d)
        # Explicit pg_catalog names and qualified tables, but ordinary operators are parsed
        # at function definition time; tested hostile session path plus synthetic operator.
        query(d,"CREATE SCHEMA attack_op")
        query(d,"GRANT USAGE ON SCHEMA attack_op TO h2_app_ingest_writer_test")
        query(d,"CREATE FUNCTION attack_op.eqtext(text,text) RETURNS boolean LANGUAGE sql AS 'SELECT false'")
        query(d,"CREATE OPERATOR attack_op.= (LEFTARG=text, RIGHTARG=text, PROCEDURE=attack_op.eqtext)")
        with conn(d,"h2_app_ingest_writer_test","synthetic_only_local_role",autocommit=True) as c:
            c.execute("SET search_path=attack_op,pg_temp,public,pg_catalog")
            put(d,"c03",session=c)
        requires(len(heads(d))==1,"operator shadow altered guard")
        step("C","C3","hostile_operator_resolution",d,"actual INSERT","00000","00000")
    record("C","C3",c03)
    def c04():
        d=new("c04");secure(d)
        with conn(d,"h2_app_ingest_writer_test","synthetic_only_local_role",autocommit=True) as c:
            c.execute("SET search_path=pg_temp,pg_catalog")
            uid=put(d,"c04",session=c)
        requires(len(heads(d))==1,"caller path changed function")
        step("C","C4","session_path",d,"actual INSERT","00000","00000")
    record("C","C4",c04)
    def c05():
        d=new("c05");secure(d)
        for n,sql in enumerate(("SET ROLE h2_head_guard_test",
             "ALTER FUNCTION public.h2_enforce_revision_head() OWNER TO h2_app_ingest_writer_test",
             "ALTER TABLE public.attack_event_classifications DISABLE TRIGGER h2_revision_head_after_insert"),1):
            negative("C","C5",str(n),d,"h2_app_ingest_writer_test",sql,"42501")
    record("C","C5",c05)
    def c06():
        d=new("c06");secure(d)
        for n,statement in enumerate(("UPDATE public.h2_classification_heads SET changed_at=now()",
                    "DELETE FROM public.h2_classification_heads",
                    "TRUNCATE TABLE public.attack_event_classifications"),1):
            negative("C","C6",str(n),d,"h2_app_ingest_writer_test",statement,"42501")
    record("C","C6",c06)
    def c07():
        d=new("c07");secure(d)
        priv=query(d,"SELECT has_function_privilege('h2_unrelated_test','public.h2_enforce_revision_head()','EXECUTE')")[0][0]
        requires(not priv,"PUBLIC EXECUTE unexpectedly available")
        dangerous=query(d,"SELECT has_schema_privilege('h2_app_ingest_writer_test','public','CREATE')")[0][0]
        requires(not dangerous,"writer can create trusted objects")
        step("C","C7","public_execute_and_create",d,"catalog readback","DENIED","DENIED")
        negative("C","C7","unrelated_set_guard",d,"h2_app_ingest_writer_test","SET ROLE h2_head_guard_test","42501")
    record("C","C7",c07)
    def c08():
        d=new("c08");secure(d)
        negative("C","C8","trigger_drop_denied",d,"h2_app_ingest_writer_test",
                 "DROP TRIGGER h2_revision_head_after_insert ON public.attack_event_classifications","42501")
        negative("C","C8","guard_definition_denied",d,"h2_app_ingest_writer_test",
                 "ALTER FUNCTION public.h2_enforce_revision_head() RESET ALL","42501")
        # Owner-level drift must be identified as elevated authority, not blocked.
        query(d,"ALTER FUNCTION public.h2_enforce_revision_head() OWNER TO h2_schema_owner_test")
        old=fingerprint(d);h=historical(d)
        step("C","C8","owner_drift_rollback_rejected",d,"008","42501",
             temp_rollback(d,h,ok=False),old,fingerprint(d))
        requires(old==fingerprint(d),"rollback side effects")
        ALL["limitations"].append("C8 owner/DDL role is outside restricted writer boundary; external controls must protect owners")
    record("C","C8",c08)
    # R15 is satisfied only if every applicable C subcase completed.
    c=[r for r in ALL["records"] if r["section"]=="C"]
    ALL["records"].append({"section":"R","id":"R15","status":"PASS" if len(c)==8 and all(x["status"]=="PASS" for x in c) else "PARTIAL",
         "expected":"Security controls C1-C8","executed_subcases":sum(x["executed_subcases"] for x in c),
         "steps":[],"error":None})
if __name__=="__main__":run()
