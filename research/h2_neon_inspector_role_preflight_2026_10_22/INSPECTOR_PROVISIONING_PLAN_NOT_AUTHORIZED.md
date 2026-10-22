# CONDITIONAL PostgreSQL inspector provisioning (NOT AUTHORIZED)

Decision at 2026-10-22: ROLE_EXISTS=UNVERIFIED; CREATE_ROLE=NOT_AUTHORIZED / BLOCKED. Do not run any SQL, Neon API/Console/CLI mutation or Secrets operation based on this plan.

## Condition and roles

Creation can be considered only after a *separately authorized*, independently reviewed existence-only pg_catalog.pg_roles read returns FALSE for the exact role on the exact project green-cake-44216048, branch br-bold-mode-b5rub8pq, database neondb. There must then be a second, separate **explicit** user authorization for a precisely pinned primary writable route and exact SQL creation operation, naming the Neon owner, SQL operator and independent reviewer. The only owner-observed writer endpoint is ep-still-violet-b5bg6mhp; it is NOT yet attested and cannot be inferred or used without new permission. Do not confuse the GitHub repo owner with automatically approved Neon operational authority.

Neon roles created through Console/API/CLI get neon_superuser membership, including data-wide privileges. Those interfaces MUST NOT create this inspector. Use a future approved SQL-only creation from an authorized existing administrative SQL principal on an independently pinned writable compute of the exact branch. Neon docs: https://neon.com/docs/manage/roles ; https://neon.com/docs/manage/database-access . The inspector must never get neon_superuser, neondb_owner or a PostgreSQL pg_* predefined role.

## Mandatory BEFORE-CREATE blocker resolution

PostgreSQL 18 documents that a non-superuser CREATEROLE creator is automatically given ADMIN membership in its newly created role. That is an incoming pg_auth_members edge (creator MEMBER OF the new inspector role), not necessarily a privilege for the inspector. But accepted Candidate A G03 checks *both* directions and requires no direct memberships. The regular creator may be unable to revoke its automatic ADMIN edge; managed Neon does not expose the bootstrap superuser. This is a concrete unresolved **protocol-compatibility blocker**, not a reason to silently relax G03 or grant additional rights. Confirm creator identity, automatic edges and supported removal (if any) with independent isolated PostgreSQL 18 / permitted disposable-Neon evidence and explicit owner review BEFORE any permanent-branch creation. If unchanged G03 cannot pass, STOP. Revision/exception to Candidate A, use of privileged support controls, or a nonstandard creation route requires separate design and acceptance; none is authorized here.

Also verify current PUBLIC database CONNECT/TEMP privileges, public/application schema CREATE, implicit PUBLIC function EXECUTE and any SECURITY DEFINER entry points. A role may receive such rights without any explicit GRANT. Revoking from inspector does not override grants to PUBLIC. No global revoke or ACL redesign is authorized; if these defaults prevent zero application access/DDL/object-write capability, provisioning remains blocked. PostgreSQL default transaction_read_only is only a session policy and cannot replace a physically read-only compute.

## Proposed literal CREATE ROLE statement, conditional and inert

~~~sql
-- PROPOSAL ONLY; NEVER EXECUTE UNDER THIS AUTHORIZATION.
-- Run only on independently attested writable compute for the exact shadow branch,
-- after positive ABSENT proof, reviewed zero-privilege baseline and separate approval.
CREATE ROLE h2_catalog_inspector_ro WITH
    LOGIN
    NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS NOINHERIT
    CONNECTION LIMIT 1 PASSWORD NULL;
~~~

Expected attributes: rolcanlogin=true, rolsuper=false, rolcreatedb=false, rolcreaterole=false, rolreplication=false, rolbypassrls=false, rolinherit=false and rolconnlimit=1. LOGIN with PASSWORD NULL is intentionally **unable to authenticate using password** until a later secret-issuance step. Do not place a real password in research SQL, GitHub, CI, logs, screenshots, issues, chat or manifests. The authorized operator must use a private Neon-compatible credential-management method that meets Neon password entropy requirements, with out-of-band secret storage, short lifetime, no plaintext SQL history/CI logs, and independent audit. Password provisioning and enabling a usable inspector connection are **separate controlled steps**; do not claim creation alone makes I2 true. Consider a time-limited credential and immediate revoke on completion.

Explicitly do NOT add GRANT CONNECT/USAGE/SELECT on application schema, table, view, sequence or function; do NOT grant pg_read_all_data, pg_monitor, neon_superuser, neondb_owner or any other role; do NOT make the inspector owner of anything. Catalog reads via pg_catalog and PostgreSQL builtins normally need no application table privileges. If effective CONNECT on neondb is unavailable, pause and seek a new ACL-change authorization rather than quietly granting it.

## Expected state changes and seven physical ACL differences

A successful PostgreSQL CREATE ROLE changes branch-scoped role catalog state (pg_authid/pg_roles projection and shared role dependencies) and may add the creator ADMIN edge in pg_auth_members; credential setting / LOGIN adjustments subsequently change role metadata. It may affect role counts/audit events, even with no application grants. It SHOULD NOT rewrite existing application pg_class.relacl, pg_namespace.nspacl, pg_database.datacl, pg_default_acl or application rows: no object-level GRANT/REVOKE/ALTER is proposed. However this is a design expectation, NOT actual proof. Before/after authorized mutation must compare all seven known raw pg_class.relacl tuples with both NULL bit and unnormalized text/array byte representation, plus application ownership and relevant ACLs. Any unexpected delta is an incident and STOP; do not normalize, mask, choose Option B or accept semantic equivalence. Current physical ACL restoration is not proven, so rollback is not equivalent to arbitrary object ACL repair.

## Required future execution envelope if blocker resolved

1. Freeze signed owner authorization identifying SQL-created role, target, exact writable compute, TLS verified routing, approved operator and independent reviewer; preflight against current main docs and role absence immediately before mutation. Do not silently take another branch or role.
2. Take nonsecret baseline role/membership/privilege, pg_class.relacl, pg_namespace.nspacl, pg_database.datacl, pg_default_acl, schema/ownership fingerprints, all with raw NULL distinctions. No application rows or secrets.
3. If still absent, execute only the approved CREATE ROLE in an explicit transaction on the authorized writable compute, with short server-enforced timeouts and abort on any pre/postcondition mismatch. Pre-commit check actual new role flags, memberships and raw seven ACLs; if G03 auto creator-edge exists, issue ROLLBACK and stop. Never drop or modify creator's role grant without another authorization. PostgreSQL CREATE ROLE supports transaction rollback, but operator must verify ROLLBACK and after-state, not infer it.
4. Only if all required invariants hold, commit; independently read back role flags, direct/transitive memberships/SET/ADMIN, ownership, PUBLIC/explicit effective privileges and seven raw ACL states. Do not enable credential issuance or inspector session before independent acceptance.
5. Handle credential issuance privately; separately authorize a dedicated read-only compute session later, with Candidate A unchanged and bounded 14 SQL queries. Do not count owner-side verification as I1-I7 runtime acceptance.

## Rollback, revocation, removal

For a failed in-transaction creation, ROLLBACK and independently verify role absence, memberships and unchanged raw physical ACLs. After commit, first revoke login/credential through a later specifically authorized SQL operation (illustrative only):

~~~sql
-- NOT AUTHORIZED: later emergency credential revocation example.
ALTER ROLE h2_catalog_inspector_ro WITH NOLOGIN PASSWORD NULL;
~~~

Reconfirm no active inspector sessions before claiming access revoked; ending existing sessions may require separate approval. A later approved DROP ROLE may be attempted only if the new role has **zero owned objects, no dependent application grants, no sessions and no unexpected role memberships**, with a recorded before/after diff. If dependencies block DROP ROLE, STOP and escalate. DO NOT run DROP OWNED, REASSIGN OWNED, CASCADE, global PUBLIC REVOKE or ACL Option B: these could change other roles, objects or the seven physical relacl differences. DROP ROLE can remove memberships automatically, so account for the creator ADMIN edge in the rollback model. Restoring old state requires independent exact readback, not an assumption.

Role creation, rollback, secret issuance, security-attestation and later I1-I7 catalog session are distinct authorizations. Current H2 and operational holds remain BLOCKED/NO-GO.
