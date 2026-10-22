# Inspector security attestation: future read-only protocol (not authorized)

This is the exact *proposed* PostgreSQL 18 catalog-only follow-up if an authorized existence read later returns TRUE or after separately authorized creation. It is not part of the one-SELECT absence/existence test; no SQL below was executed. Candidate A's immutable G01-G14 SQL and receipt/negative controls stay unchanged. A privileged owner may perform an expressly approved role *audit*, but Candidate A G10 (current_user) cannot be interpreted as the inspector's rights when run as neondb_owner. To satisfy Candidate A I2/I3-I7, the dedicated role must later authenticate directly under a further separately approved read-only session, not through SET ROLE from an owner session.

## Verification envelopes and fail-closed policy

Target must be the independently pinned project green-cake-44216048, branch br-bold-mode-b5rub8pq, database neondb, direct read-only endpoint ep-calm-rice-b5073ypp, owner-observed FQDN ep-calm-rice-b5073ypp.c-7.us-east-2.aws.neon.tech, with authenticated current routing provenance, port and TLS verify-full. No primary/default/pooled fallback. Named Neon owner, SQL operator and organizationally independent reviewer must approve a precise query list and retention separately. Allowed principal for owner-side audit: specifically preapproved neondb_owner or another explicitly named existing owner principal; it is NOT the inspector. Never connect under an unlisted principal.

Proposed future owner-side audit envelope: one direct read-replica connection, one REPEATABLE READ READ ONLY transaction, SET LOCAL statement_timeout='5s', lock_timeout='500ms', idle_in_transaction_session_timeout='15s', transaction_timeout='75s'; client wall clock <=90s, ten SELECTs V01-V10 exactly once, at most 16 SQL statements including BEGIN / four SET LOCAL / ROLLBACK. Combined row ceiling 747, cell 8192 UTF-8 bytes, sanitized total <=262144 bytes. If any query reaches its LIMIT (a possible truncated result), exceeds budgets or hits an error, treat whole attestation as PARTIAL/BLOCKED; no bigger unapproved query or retry. Operator must verify current_database=neondb, current_user=session_user=explicit approved owner, server_version_num >= 180000 and transaction_read_only=on (the narrow existence-check identity row is a separate authorized reference, not proof for this new session). Before any attestation claim, an independent reviewer must verify actual session guards and completed ROLLBACK.

Use the following explicit SQL blocks only with later approval and server-enforced readonly compute. All are catalog views or PostgreSQL privilege-inspection builtins, never SELECT rows from application relations. If the inspector is absent, do not run V02-V10; mark missing.

### V01: existence, LOGIN, role attributes (limit 2; require exactly 1)

~~~sql
SELECT r.oid, r.rolname, r.rolcanlogin, r.rolinherit,
       r.rolsuper, r.rolcreaterole, r.rolcreatedb,
       r.rolreplication, r.rolbypassrls, r.rolconnlimit
FROM pg_catalog.pg_roles AS r
WHERE r.rolname = 'h2_catalog_inspector_ro'
LIMIT 2;
~~~

PASS requires canlogin true and all five privileged flags false. NOINHERIT helps avoid accidental privilege inheritance but does not prevent SET ROLE across edges.

### V02: all direct incoming and outgoing memberships (limit 33; require zero)

~~~sql
SELECT granted.rolname AS granted_role, member.rolname AS member_role,
       m.admin_option, m.inherit_option, m.set_option
FROM pg_catalog.pg_auth_members AS m
JOIN pg_catalog.pg_roles AS granted ON granted.oid = m.roleid
JOIN pg_catalog.pg_roles AS member ON member.oid = m.member
WHERE granted.rolname = 'h2_catalog_inspector_ro'
   OR member.rolname = 'h2_catalog_inspector_ro'
ORDER BY granted.rolname, member.rolname
LIMIT 33;
~~~

Important: ordinary PostgreSQL 18 CREATEROLE-created roles may carry an automatic creator -> newly created role ADMIN edge. That edge is not an inspector escalation by itself, but it violates accepted Candidate A G03's stricter zero-edge policy. It cannot be silently ignored. Verify this creation mechanism on isolated PG18 before approving any creation; do not attempt privileged Neon remediation in this research task.

### V03: transitive grant paths, effective inherited/SET/ADMIN reachability (limit 65; require zero)

~~~sql
WITH RECURSIVE root AS (
    SELECT oid, rolname FROM pg_catalog.pg_roles
    WHERE rolname = 'h2_catalog_inspector_ro'
), paths AS (
    SELECT root.oid AS target_oid, 0 AS depth,
           ARRAY[root.oid]::oid[] AS visited,
           ARRAY[root.rolname]::name[] AS name_path,
           true AS inherits_path, true AS set_path
    FROM root
    UNION ALL
    SELECT m.roleid, p.depth + 1,
           pg_catalog.array_append(p.visited, m.roleid),
           pg_catalog.array_append(p.name_path, granted.rolname),
           p.inherits_path AND m.inherit_option,
           p.set_path AND m.set_option
    FROM paths AS p
    JOIN pg_catalog.pg_auth_members AS m ON m.member = p.target_oid
    JOIN pg_catalog.pg_roles AS granted ON granted.oid = m.roleid
    WHERE p.depth < 16 AND NOT m.roleid = ANY(p.visited)
)
SELECT p.name_path::text AS membership_path, p.depth, p.inherits_path,
       p.set_path,
       pg_catalog.pg_has_role(root.oid, p.target_oid, 'MEMBER') AS member_reachable,
       pg_catalog.pg_has_role(root.oid, p.target_oid, 'USAGE') AS inherited_reachable,
       pg_catalog.pg_has_role(root.oid, p.target_oid, 'SET') AS set_role_reachable,
       pg_catalog.pg_has_role(root.oid, p.target_oid, 'MEMBER WITH ADMIN OPTION') AS admin_reachable
FROM paths AS p
CROSS JOIN root
WHERE p.depth > 0
ORDER BY p.depth, p.name_path::text
LIMIT 65;
~~~

A row, a depth-16 boundary, or limit hit is a STOP. PostgreSQL 18 pg_has_role implements transitive MEMBER/USAGE/SET and ADMIN checks, and NOINHERIT alone is insufficient. Independently inspect V02 incoming edges even if V03 is empty. A path to neondb_owner, neon_superuser, cloud_admin, pg_read_all_data, pg_write_all_data, pg_maintain or another owner/privileged role is an immediate veto, even if no direct row grants are visible.

### V04: database, schema, application objects and executable ownership (limit 33; require zero)

~~~sql
WITH i AS (
    SELECT oid FROM pg_catalog.pg_roles
    WHERE rolname = 'h2_catalog_inspector_ro'
), owned AS (
    SELECT 'database' AS kind, d.datname::text AS object_name
    FROM pg_catalog.pg_database d, i WHERE d.datdba = i.oid
    UNION ALL
    SELECT 'schema', n.nspname::text
    FROM pg_catalog.pg_namespace n, i WHERE n.nspowner = i.oid
    UNION ALL
    SELECT 'relation', (n.nspname || '.' || c.relname)::text
    FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
    CROSS JOIN i WHERE c.relowner = i.oid
    UNION ALL
    SELECT 'function', p.oid::pg_catalog.regprocedure::text
    FROM pg_catalog.pg_proc p, i WHERE p.proowner = i.oid
    UNION ALL
    SELECT 'type', t.oid::pg_catalog.regtype::text
    FROM pg_catalog.pg_type t, i WHERE t.typowner = i.oid
    UNION ALL
    SELECT 'extension', e.extname::text
    FROM pg_catalog.pg_extension e, i WHERE e.extowner = i.oid
    UNION ALL
    SELECT 'publication', p.pubname::text
    FROM pg_catalog.pg_publication p, i WHERE p.pubowner = i.oid
    UNION ALL
    SELECT 'foreign_server', f.srvname::text
    FROM pg_catalog.pg_foreign_server f, i WHERE f.srvowner = i.oid
)
SELECT kind, object_name FROM owned
ORDER BY kind, object_name LIMIT 33;
~~~

No owned object is allowed. This covers key local object families, not every PostgreSQL object class; any unexamined relevant class or another database on the same branch requires additional authorization and holds completion.

### V05: database privileges, including default PUBLIC (limit 33)

~~~sql
SELECT d.datname, (d.datacl IS NULL) AS raw_acl_is_null, d.datacl::text AS raw_acl,
       pg_catalog.has_database_privilege(i.oid, d.oid, 'CONNECT') AS can_connect,
       pg_catalog.has_database_privilege(i.oid, d.oid, 'CREATE') AS can_create,
       pg_catalog.has_database_privilege(i.oid, d.oid, 'TEMPORARY') AS can_temp
FROM pg_catalog.pg_database AS d
CROSS JOIN pg_catalog.pg_roles AS i
WHERE i.rolname = 'h2_catalog_inspector_ro'
ORDER BY d.datname LIMIT 33;
~~~

Target neondb CONNECT must be available; database CREATE must be false everywhere. TEMPORARY (often PUBLIC by default) allows object changes on a writable server and requires explicit risk adjudication: never claim a no-object-write proof if it is true. Default PUBLIC CONNECT on other databases also requires documented isolation; role-level REVOKE cannot subtract PUBLIC rights from just one member.

### V06: relevant schema ACLs, including PUBLIC grants (limit 65)

~~~sql
SELECT n.nspname, (n.nspacl IS NULL) AS raw_acl_is_null, n.nspacl::text AS raw_acl,
       pg_catalog.has_schema_privilege(i.oid, n.oid, 'USAGE') AS can_use,
       pg_catalog.has_schema_privilege(i.oid, n.oid, 'CREATE') AS can_create
FROM pg_catalog.pg_namespace AS n
CROSS JOIN pg_catalog.pg_roles AS i
WHERE i.rolname = 'h2_catalog_inspector_ro'
  AND n.nspname <> 'pg_catalog' AND n.nspname <> 'information_schema'
  AND n.nspname NOT LIKE 'pg_toast%'
ORDER BY n.nspname LIMIT 65;
~~~

Any application-schema CREATE is a STOP. Catalog metadata normally requires no new application-schema grants. Do not alter public schema privileges to make this check pass.

### V07: every non-system application table/view privilege (limit 257)

~~~sql
SELECT n.nspname, c.relname, c.relkind, (c.relacl IS NULL) AS raw_acl_is_null,
       c.relacl::text AS raw_acl,
       pg_catalog.has_table_privilege(i.oid, c.oid, 'SELECT') AS can_select,
       pg_catalog.has_table_privilege(i.oid, c.oid, 'INSERT') AS can_insert,
       pg_catalog.has_table_privilege(i.oid, c.oid, 'UPDATE') AS can_update,
       pg_catalog.has_table_privilege(i.oid, c.oid, 'DELETE') AS can_delete,
       pg_catalog.has_table_privilege(i.oid, c.oid, 'TRUNCATE') AS can_truncate,
       pg_catalog.has_table_privilege(i.oid, c.oid, 'REFERENCES') AS can_reference,
       pg_catalog.has_table_privilege(i.oid, c.oid, 'TRIGGER') AS can_trigger,
       pg_catalog.has_table_privilege(i.oid, c.oid, 'MAINTAIN') AS can_maintain
FROM pg_catalog.pg_class AS c
JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
CROSS JOIN pg_catalog.pg_roles AS i
WHERE i.rolname = 'h2_catalog_inspector_ro'
  AND n.nspname <> 'pg_catalog' AND n.nspname <> 'information_schema'
  AND n.nspname NOT LIKE 'pg_toast%'
  AND c.relkind IN ('r','p','v','m','f')
ORDER BY n.nspname, c.relname LIMIT 257;
~~~

All eight Candidate A relations/views must appear when present. All access bits (including SELECT, MAINTAIN) must be false for application objects. A missing object, unexpected relkind, view dependency or limit hit is not PASS. The seven known physical relacl differences must remain literal, including NULL versus explicit, without normalization.

### V08: application sequence privilege (limit 65)

~~~sql
SELECT n.nspname, c.relname,
       pg_catalog.has_sequence_privilege(i.oid, c.oid, 'SELECT') AS can_select,
       pg_catalog.has_sequence_privilege(i.oid, c.oid, 'USAGE') AS can_use,
       pg_catalog.has_sequence_privilege(i.oid, c.oid, 'UPDATE') AS can_update
FROM pg_catalog.pg_class AS c
JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
CROSS JOIN pg_catalog.pg_roles AS i
WHERE i.rolname = 'h2_catalog_inspector_ro'
  AND n.nspname <> 'pg_catalog' AND n.nspname <> 'information_schema'
  AND n.nspname NOT LIKE 'pg_toast%' AND c.relkind = 'S'
ORDER BY n.nspname, c.relname LIMIT 65;
~~~

Any positive sequence privilege is a STOP.

### V09: executable application routines and SECURITY DEFINER exposure (limit 129)

~~~sql
SELECT n.nspname, p.oid::pg_catalog.regprocedure::text AS signature,
       p.prosecdef AS security_definer, p.prokind,
       (p.proacl IS NULL) AS raw_acl_is_null, p.proacl::text AS raw_acl,
       pg_catalog.has_function_privilege(i.oid, p.oid, 'EXECUTE') AS can_execute
FROM pg_catalog.pg_proc AS p
JOIN pg_catalog.pg_namespace AS n ON n.oid = p.pronamespace
CROSS JOIN pg_catalog.pg_roles AS i
WHERE i.rolname = 'h2_catalog_inspector_ro'
  AND n.nspname <> 'pg_catalog' AND n.nspname <> 'information_schema'
  AND n.nspname NOT LIKE 'pg_toast%'
ORDER BY n.nspname, p.oid LIMIT 129;
~~~

An executable SECURITY DEFINER path is a veto; other executable application functions require a reviewed no-write/no-app-row security assessment, without calling them or dumping function bodies. Inherited PUBLIC EXECUTE may be impossible to remove for this role alone without changing global ACLs. No proof is implied by metadata alone about unsafe side effects of extension or user-defined functions.

### V10: default privilege changes and future-object exposure (limit 65)

~~~sql
SELECT owner.rolname AS owner_name, COALESCE(n.nspname, '') AS schema_name,
       d.defaclobjtype, (d.defaclacl IS NULL) AS raw_acl_is_null,
       d.defaclacl::text AS raw_acl
FROM pg_catalog.pg_default_acl AS d
JOIN pg_catalog.pg_roles AS owner ON owner.oid = d.defaclrole
LEFT JOIN pg_catalog.pg_namespace AS n ON n.oid = d.defaclnamespace
WHERE n.nspname IS NULL OR
      (n.nspname <> 'pg_catalog' AND n.nspname <> 'information_schema'
       AND n.nspname NOT LIKE 'pg_toast%')
ORDER BY owner.rolname, schema_name, d.defaclobjtype LIMIT 65;
~~~

Future PUBLIC default function EXECUTE and table defaults require analysis alongside explicit grants. The query sees metadata only; its absence cannot certify future grant policies.

## Independent interpretation / reject criteria

The reviewer must match exact SQL bytes and ordered row/column/byte hashes, role OID/name, date, target, session identity, direct and transitive memberships (including ADMIN/INHERIT/SET), ALL relevant ownership/privilege outcomes and prohibited call paths. A nonempty V02 or V03 is a stop under immutable Candidate A G03; absence of a path to neon_superuser does not waive an incoming creator ADMIN edge. Any app SELECT/DML/MAINTAIN, app-schema CREATE, owner privilege, SECURITY DEFINER executable risk, unexplained PUBLIC privilege, TEMP/other-db capability, missing rows, truncation, error or changed physical ACL is PARTIAL/BLOCKED until separately adjudicated. This proposal does not modify Candidate A and never upgrades its I1-I7 on owner-session evidence.

The 10 illustrative V queries and bounds are a *new* future authorization scope. Original Candidate A's 14-query/15-SELECT/21-statement limits apply only to its own later dedicated-inspector protocol, not to this audit.
