# REQUEST TO AUTHORIZED NEON OWNER — NONSECRET H2 TARGET/INSPECTOR ATTESTATION

Request date: 2026-10-21. This requests nonsecret documentation for independent review. It does **not** authorize anyone in this research task to access Neon, run SQL/API/console commands, create a role, change grants, expose credentials, wake a compute or launch an inspection.

To: **Authorized Neon project owner (name not yet supplied)**. Independent reviewer and proposed operator: **not yet named**. Return a signed/attributed, date-stamped evidence bundle and short attestation through an approved private review channel. Do not include tokens, passwords, private keys, connection strings/DSNs, Secrets values, environment variables or unredacted authentication panels. A plain FQDN and nonsecret ID fields are requested.

## A. Exact current route and target — supply every field

1. Current Neon project ID **and** authoritative project identifier/name; project creation/ownership context (nonsecret). Historical proposal: `green-cake-44216048` — do not assume unchanged.
2. Current branch ID, branch human-readable name, project ownership, parent/primary/default flags, and whether the intended target is `br-bold-mode-b5rub8pq`. If the target differs, label the mismatch and STOP; do not silently substitute the branch historically named `production` (`br-wandering-sunset-b5835alw`).
3. Database name and existence on that precise branch. Historical proposal: `neondb`.
4. Current compute/endpoint ID; branch association; compute type/state and whether endpoint is direct or pooled. Historical old inspector compute ID `ep-calm-rice-b5073ypp` is not a fresh pin. Old writer label `ep-still-violet-b5bg6mhp` is not a fallback.
5. **Full current direct TLS hostname (FQDN)**, the expected TLS verify-full server name, port, routing mode, branch ID/endpoint ID tied to that FQDN, and any hostname alias that could lead to a pooled/default or other branch. Provide no DSN.
6. One coherent project -> branch -> endpoint/compute -> FQDN -> database mapping, observed at one UTC timestamp. State the source (Neon owner-authorized nonsecret control-plane export/screenshot or approved preexisting audit record), artifact name and SHA-256, observation time, export time, owner identity and data freshness. Distinguish an old design value from current verification.

## B. Exact `h2_catalog_inspector_ro` identity and effective rights

7. State one of: `EXISTS_CONFIRMED`, `DOES_NOT_EXIST_CONFIRMED`, or `UNVERIFIED`, with dated primary evidence; provide exact role spelling and project/branch/database context. Do not infer absence from missing documentation.
8. If it exists, attest its login ability (`rolcanlogin`) and role attributes: `rolsuper`, `rolcreaterole`, `rolcreatedb`, `rolreplication`, `rolbypassrls`, inheritance policy, and any other privileged flag that changes effective authority. Do not send authentication material.
9. Provide **all direct and transitively reachable** role memberships and for each edge its inherit, set and admin options; specify privileged-role reachability and whether the inspector can `SET ROLE` to any writer, owner, cloud admin or other actor. A global `NOINHERIT` flag alone is not adequate evidence.
10. Supply ownership of the database, `public` and relevant schemas, the eight manifest-selected canonical relations/checkpoint view, and the relevant callable/SECURITY DEFINER objects. Identify any owned object or inherited membership that enables DDL, DML or grant escalation.
11. Supply effective rights on the database, relevant schemas, eight application objects and affected functions: `CONNECT`, `USAGE`, `CREATE`, application `SELECT/INSERT/UPDATE/DELETE/TRUNCATE/REFERENCES/TRIGGER`, function `EXECUTE`, default privileges, inherited/`PUBLIC` grants, and ability to ALTER/GRANT/REVOKE. Explicitly distinguish catalog visibility from application data read rights. Any unexpected rights should be documented, not normalized away.
12. Explicitly confirm **no `neondb_owner` implicit or emergency fallback** for the proposed inspection and no substitution via pooled/default branch. If current role is missing, return `DOES_NOT_EXIST_CONFIRMED`; do not provision it under this request.

## C. Responsibility, permission and evidence handling

13. Name the authorized Neon owner (name/role/approval authority), proposed operator (name/role), and independent reviewer (name/role), with organizational separation for the reviewer and an explicit approval state for each. GitHub repo ownership alone is not Neon owner authorization.
14. State approved future catalog-only object/field scope, owner permission to access catalog metadata, whether a direct connection could wake compute or create access logs, acceptable retention and redaction, time window and resource limits. If any permission is unavailable, indicate `NOT APPROVED`.
15. List every evidence artifact with source system, observation UTC, capture UTC, author, SHA-256, redactions, covered fields, and primary-vs-derived status. Allow an independent reviewer to reproduce the mapping from nonsecret identifiers. A prose assertion alone is not primary control-plane proof.

Use the following **nonsecret response shape** (blanks are deliberately not evidence):

```text
owner_name_and_authority: UNVERIFIED
operator_name_and_approval: UNVERIFIED
independent_reviewer_name_and_approval: UNVERIFIED
observed_at_utc: UNVERIFIED
capture_source_and_artifact_sha256: UNVERIFIED
current_project_id: UNVERIFIED
current_branch_id_and_name: UNVERIFIED
current_database: UNVERIFIED
current_direct_compute_endpoint_id: UNVERIFIED
current_direct_tls_fqdn_and_port: UNVERIFIED
direct_or_pooler_and_tls_verify_full_name: UNVERIFIED
project_branch_endpoint_host_db_mapping: UNVERIFIED
inspector_role_existence: UNVERIFIED
inspector_role_flags_and_login: UNVERIFIED
inspector_direct_and_transitive_membership: UNVERIFIED
inspector_role_switch_possible: UNVERIFIED
inspector_ownership_and_effective_privileges: UNVERIFIED
neondb_owner_fallback_prohibited_confirmed: UNVERIFIED
catalog_scope_compute_wake_retention_approval: UNVERIFIED
evidence_artifact_index_and_digests: UNVERIFIED
```

## Stop / conditional branch

If existing owner-authorized nonsecret evidence cannot satisfy these fields without performing a new Neon operation, return `UNVERIFIED` and request separate permission for that evidence-collection operation. This request does not authorize a new query, console visit or API call. If the owner positively confirms the inspector does not exist, the attached separate provisioning authorization proposal may be considered, but role creation and credential handling remain outside this checkpoint.

No actual catalog-only inspection is authorized. After evidence arrives: independent review, fresh main checkpoint, no guessed fallback, and a **new explicit user authorization** are mandatory. Keep seven physical relacl mismatches and Option B unaccepted; 203/3/7, 25 UNBOUND, C4/C5 and all NO-GO gates unchanged.
