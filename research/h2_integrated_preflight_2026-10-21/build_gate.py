#!/usr/bin/env python3
"""Generate an executable, single-transaction research-only H11/R09+007 migration.

The accepted 007 DDL body is included BYTE-FOR-BYTE between its BEGIN/COMMIT;
its wrapper is replaced, not called as a separate transaction. The existing
H11 recursive query and R09 DO guard are similarly reused with pinned Git
blob IDs. No server other than the synthetic PG18 fixture is ever contacted.
"""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
H11 = ROOT / "research/h2_security_closure_2026-10-20/h11_head_history_check.sql"
R09 = ROOT / "research/h2_security_closure_2026-10-20/r09_effective_role_preflight.sql"
UP = ROOT / "research/h2_non_superuser_guard_acl_2026-10-20/007_non_superuser_guard_transfer.sql"
PINS = {
    H11: "da0eec8a55e832f159f368af94a79c21953a3901",
    R09: "1e8e78683cefd147034946ecb191539e2c184a92",
    UP: "8dc20d11f28db2d8c2b6244b5c43e8bd23548abd",
}

def git_blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()

def source_provenance():
    result = {}
    for f, wanted in PINS.items():
        raw = f.read_bytes()
        got = git_blob(raw)
        if got != wanted:
            raise RuntimeError("ACCEPTED_SOURCE_BLOB_MISMATCH " + str(f) + " " + got)
        result[str(f.relative_to(ROOT))] = {
            "git_blob": got, "sha256": hashlib.sha256(raw).hexdigest()
        }
    return result

# Additional mandatory checks beyond the accepted bounded R09 baseline.
# pg_has_role(...,'MEMBER') deliberately rejects SET-only and indirect routes.
EXTRA_R09 = r"""
DO $r09_extended$
DECLARE app text := 'h2_app_ingest_writer_test';
DECLARE app_oid oid;
BEGIN
  SELECT oid INTO app_oid FROM pg_roles WHERE rolname=app;
  IF app_oid IS NULL OR
     EXISTS(SELECT 1 FROM pg_roles WHERE oid=app_oid AND
       (rolsuper OR rolcreaterole OR rolcreatedb OR rolreplication OR rolbypassrls))
  THEN
    RAISE EXCEPTION 'H2_R09_UNSAFE_APP_ATTRIBUTES' USING ERRCODE='42501';
  END IF;
  IF to_regprocedure('public.h2_enforce_revision_head()') IS NULL OR
     (SELECT proowner::regrole::text FROM pg_proc
      WHERE oid='public.h2_enforce_revision_head()'::regprocedure)
       NOT IN ('h2_migrator_test','h2_head_guard_test')
  THEN
    RAISE EXCEPTION 'H2_R09_UNSAFE_GUARD_OWNER' USING ERRCODE='42501';
  END IF;
  IF pg_has_role(app,'h2_migrator_test','MEMBER')
    OR has_table_privilege(app,'public.attack_event_classifications',
                            'UPDATE,DELETE,TRUNCATE,TRIGGER,REFERENCES')
    OR has_table_privilege(app,'public.h2_classification_heads',
                            'INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER,REFERENCES')
    OR has_schema_privilege(app,'public','CREATE')
    OR EXISTS(
        SELECT 1 FROM pg_proc p
        WHERE p.pronamespace='public'::regnamespace
          AND (p.proowner=app_oid OR
               pg_has_role(app,p.proowner,'MEMBER')))
    OR EXISTS(
        SELECT 1 FROM pg_roles r WHERE r.oid<>app_oid
          AND pg_has_role(app,r.oid,'MEMBER') AND
          (r.rolsuper OR r.rolcreaterole OR r.rolcreatedb OR
           r.rolreplication OR r.rolbypassrls OR
           has_schema_privilege(r.oid,'public','CREATE') OR
           has_table_privilege(r.oid,'public.attack_event_classifications',
                              'UPDATE,DELETE,TRUNCATE,TRIGGER,REFERENCES') OR
           has_table_privilege(r.oid,'public.h2_classification_heads',
                              'INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER,REFERENCES'))
       )
  THEN
    RAISE EXCEPTION 'H2_R09_UNSAFE_EFFECTIVE_OR_SET_ROLE_AUTHORITY'
      USING ERRCODE='42501';
  END IF;
END $r09_extended$;
"""

POST = r"""
DO $h2_post$
BEGIN
  IF NOT EXISTS(
    SELECT 1 FROM pg_proc
    WHERE oid='public.h2_enforce_revision_head()'::regprocedure
      AND proowner='h2_head_guard_test'::regrole
      AND prosecdef
      AND proconfig @> ARRAY['search_path=pg_catalog, pg_temp'])
     OR has_function_privilege('h2_app_ingest_writer_test',
                               'public.h2_enforce_revision_head()','EXECUTE')
     OR has_table_privilege('h2_app_ingest_writer_test',
                             'public.h2_classification_heads',
                             'INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER')
  THEN
    RAISE EXCEPTION 'H2_INTEGRATED_MIGRATION_POSTCHECK'
      USING ERRCODE='23514';
  END IF;
END $h2_post$;
"""

def generate(hold_seconds=0, lock_timeout="3s"):
    provenance = source_provenance()
    hold = float(hold_seconds)
    if not 0 <= hold <= 8:
        raise ValueError("hold_seconds must be 0..8")
    if lock_timeout not in ("350ms", "3s", "10s"):
        raise ValueError("unapproved lock timeout")

    # Preserve the accepted R09 DO statements, omitting its standalone transaction.
    r09 = R09.read_text()
    r09_begin = r09.index("DO $guard$")
    r09_end = r09.index("END $guard$;", r09_begin) + len("END $guard$;")
    r09_do = r09[r09_begin:r09_end]
    if "pg_has_role(app,'h2_schema_owner_test','MEMBER')" not in r09_do:
        raise RuntimeError("R09 baseline unexpectedly changed")

    # Transform only H11's final diagnostic SELECT into a SQLSTATE-enforced DO.
    h11 = H11.read_text()
    tail = "SELECT code,key FROM issues ORDER BY code,key;"
    if not h11.strip().endswith(tail):
        raise RuntimeError("H11 diagnostic SELECT unexpectedly changed")
    ctes = h11[:h11.rfind(tail)]
    h11_do = ("""DO $h11$ DECLARE first_issue text; BEGIN
""" + ctes + """
SELECT code||':'||key INTO first_issue FROM issues ORDER BY code,key LIMIT 1;
IF first_issue IS NOT NULL THEN
 RAISE EXCEPTION 'H2_H11_INVALID_HISTORY: %',first_issue USING ERRCODE='23514';
END IF;
END $h11$;
""")

    # The exact accepted 007 DDL statements remain unchanged; only its own
    # BEGIN/COMMIT wrapper is removed so ONE protected transaction surrounds
    # locking, both preconditions, 007 DDL, postconditions and COMMIT.
    up = UP.read_text()
    if up.count("\nBEGIN;") != 1 or up.count("\nCOMMIT;") != 1:
        raise RuntimeError("007 transaction boundary unexpectedly changed")
    body = up.split("\nBEGIN;",1)[1].rsplit("\nCOMMIT;",1)[0]
    if "ALTER FUNCTION public.h2_enforce_revision_head() OWNER TO h2_head_guard_test;" not in body:
        raise RuntimeError("007 owner transfer missing")
    sql_text = (
        "\\set ON_ERROR_STOP on\n"
        "BEGIN;\n"
        f"SET LOCAL lock_timeout = '{lock_timeout}';\n"
        "SET LOCAL statement_timeout = '40s';\n"
        "LOCK TABLE public.attack_event_classifications, public.h2_classification_heads "
        "IN SHARE ROW EXCLUSIVE MODE;\n"
        f"SELECT pg_sleep({hold:g});\n"
        + r09_do + "\n" + EXTRA_R09 + "\n" + h11_do
        + "\n"
        + "SELECT CASE WHEN proowner='h2_migrator_test'::regrole "
          "THEN 'true' ELSE 'false' END AS transfer_needed "
          "FROM pg_proc WHERE oid='public.h2_enforce_revision_head()'::regprocedure \\gset\n"
        + "\\if :transfer_needed\n"
        + body + "\n"
        + "\\endif\n"
        + POST + "\n"
        + "COMMIT;\n"
    )
    if sql_text.count("\nCOMMIT;") != 1:
        raise RuntimeError("INTEGRATED_TRANSACTION_COUNT_NOT_ONE")
    return sql_text, provenance

if __name__ == "__main__":
    import json
    import sys
    script, src = generate()
    target = Path(sys.argv[1]) if len(sys.argv)>1 else Path("/tmp/h2_integrated_candidate.sql")
    target.write_text(script)
    print(json.dumps({"generated_sql":str(target),
      "sha256":hashlib.sha256(script.encode()).hexdigest(),"accepted_sources":src}))
