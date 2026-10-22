# H2 Neon inspector role: bounded offline decision, 22 October 2026

**Verdict for the next separate existence-only authorization: PARTIAL / CONDITIONAL ELIGIBILITY TO REQUEST; EXECUTION CURRENTLY BLOCKED.** A single, narrow catalog existence SELECT is an appropriate next step. It is not authorized by this research task. The current owner-reported host and branch are not a timestamped independent control-plane-to-PostgreSQL route attestation, and the named operator/reviewer plus separate user approval remain missing. Provisioning stays BLOCKED even if future absence is proven until the automatic creator-ADMIN edge and PUBLIC privilege constraints are resolved without weakening Candidate A.

## Evidence and independent review

- Current GitHub preflight: main d4b5b5753733ec80586526e8666b31f344437e31; site-prod 63d42ee984c11d1cc8b33a95b2f8a4bf4a08e170; WIP 27b11ad3a0982f4905a1675157866aad8016a4f0. PROJECT_STATE.md and CHANGELOG.md read; newest accepted H2 owner-attestation checkpoint a62c3afd67e91bd7e5b40c99a9125d5b98d5d7dd (authorization text SHA was missing four characters). No new accepted inspector runtime checkpoint was found during preflight.
- GitHub-proven offline Candidate A: a4f30691d89a4206b910b8dfde5dac44aee0ed99; independently successful GitHub Actions 39613681469; prior standalone review 43ae07403e059e75dfe2ce402b0c01ad842b5904. Supplemental 39620712464 stays PARTIAL. No Candidate A byte or manifest changes.
- Owner-reported Neon UI: green-cake-44216048 -> br-bold-mode-b5rub8pq (lviv-phase1-production-shadow-2026-09-28) -> read-only ep-calm-rice-b5073ypp -> ep-calm-rice-b5073ypp.c-7.us-east-2.aws.neon.tech -> neondb; no pooling shown, compute Idle/Suspended. Separate primary ep-still-violet-b5bg6mhp; Console shows neondb_owner and does not show proposed inspector. This is an observed UI route, **not** an independently verified current control-plane or pg_roles claim.
- Missing primary evidence: exact UTC screenshot/export hashes, owner/operator/reviewer named approvals, current compute type/host/port/TLS binding, a PostgreSQL role read, effective privileges and credential/inspection authorizations. GitHub ownership does not replace Neon SQL authority.
- Offline syntax/security review: compared the existence-only transaction and proposed role attributes against official PostgreSQL 18 CREATE ROLE, pg_auth_members, pg_has_role and Neon role docs (URLs below). Checked existence SQL is one pg_roles-only SELECT, no application relations, no DML/DDL or role switch; 7 statements in one READ ONLY transaction, single result, explicit ROLLBACK. This is static/document review, **not** PostgreSQL 18 parser execution; local PG18 server/parser and Neon credentials were not used. A PG18 live SQL proof and privilege graph remain unverified.
- Independent threat assessment: Neon Console/API/CLI auto-grant neon_superuser; SQL path required. Ordinary CREATEROLE creation may auto-add creator ADMIN membership which violates immutable Candidate A G03 zero-edge negative control. NOINHERIT does not disable SET ROLE; PUBLIC grants and SECURITY DEFINER can expose data despite no explicit inspector GRANT. App write privileges and raw relacl MUST be checked; role flags alone cannot establish safety. No mitigation/waiver is accepted.

## Exact first, separate authorization to seek: EXISTENCE ONLY

Proposed user authorization, NOT given by this document:

> Authorize one named Neon owner/operator, with a separately named independent reviewer, to perform **one** read-only PostgreSQL existence-check on project green-cake-44216048, branch br-bold-mode-b5rub8pq, database neondb, provider-verified direct read-replica ep-calm-rice-b5073ypp with exact FQDN ep-calm-rice-b5073ypp.c-7.us-east-2.aws.neon.tech, verified port and TLS verify-full. A named existing owner SQL principal (possibly neondb_owner) may connect for this **existence-only** check, and must never be treated as the proposed inspector. Permit only the exact INSPECTOR_ROLE_EXISTENCE_CHECK_NOT_AUTHORIZED.sql contents after pinning its Git SHA: one session, READ ONLY REPEATABLE READ, four SET LOCAL guards, one pg_roles-only SELECT, explicit ROLLBACK, <=7 SQL statements, <=1 result row, <=2048 sanitized bytes, <=20s client wall-clock and abort on any guard/identity/route/receipt error. No retry, fallback, other SQL, Neon API, role creation or Secrets access. Provide a credential-free sanitized receipt with UTC times, independent routing source + hash, operator/reviewer names, PostgreSQL principal, version, database, transaction guard, boolean result, result hash/byte size, rollback and zero attempted write attestation. This authorizes neither a full privilege attestation nor Candidate A I1-I7.

Require explicit separately signed acceptance of the independent routing evidence and dedicated operator/reviewer before execution. A FALSE result is ABSENT_CONFIRMED only under all these guards. TRUE means EXISTS_CONFIRMED but no rights inferred. Missing output/error means UNVERIFIED; rerun needs new authorization.

## Second, separate authorization path: CONDITIONAL PROVISIONING

Request this only if first approved query positively returns FALSE, independent reviewer accepts the result and an updated security decision resolves the PostgreSQL 18 automatic creator ADMIN edge and PUBLIC permissions, all without amending accepted Candidate A or touching unrelated ACLs. A new consent must name the *writable* compute (not the read replica) and explicitly allow a single role creation with SQL, pre/post raw ACL checks, credential controls outside Git/CI and rollback. The exact SQL proposal is in INSPECTOR_PROVISIONING_PLAN_NOT_AUTHORIZED.md; creating via Neon Console, CLI or API is prohibited. Absence alone is necessary but not sufficient to proceed. No permission for this second action is granted by the first.

## Gate ledger after this research artifact

| Gate | Decision |
|---|---|
| Current owner-observed target | PARTIAL; screenshot observations only |
| Role existence | UNVERIFIED; no live SQL |
| First existence-only authorization | PARTIAL to request, BLOCKED to execute until independent routing and explicit approval |
| Conditional role creation | BLOCKED/NOT_AUTHORIZED, including PG18 creator-ADMIN compatibility |
| I1 | UNVERIFIED / NO-GO |
| I2 | BLOCKED / NO-GO |
| I3-I7 | RUNTIME UNVERIFIED |
| H2_READONLY_NEON_PREFLIGHT_READINESS | BLOCKED/NO-GO |
| H2_DISPOSABLE_NEON_TEST_READINESS | BLOCKED/NO-GO |
| NEON_AUTHORITY_ACTIVE | NO |
| PRODUCTION_CUTOVER_EXECUTED | NO |
| WIP_ACTIVATION | NO-GO |
| H2_ACL_OPTION_B | BLOCKED / PROPOSAL_ONLY |

Physical seven pg_class.relacl differences remain unresolved; do not normalize, mask or accept. H2 203/3/7, UNBOUND_UNRESOLVED=25 and C4/C5 unproven. No production, main coordination, site-prod, WIP, R6, casualty, historical/backfill, schema or application source changes.

Official references used: https://neon.com/docs/manage/roles ; https://neon.com/docs/manage/database-access ; https://neon.com/docs/manage/endpoints/ ; https://www.postgresql.org/docs/18/sql-createrole.html ; https://www.postgresql.org/docs/18/role-attributes.html ; https://www.postgresql.org/docs/18/catalog-pg-auth-members.html ; https://www.postgresql.org/docs/18/functions-info.html ; https://www.postgresql.org/docs/18/sql-droprole.html .
