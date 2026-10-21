# H2 Neon catalog-only inspector: target, role, and approval boundary

**2026-10-21 | OFFLINE RESEARCH PROPOSAL ONLY | NO Neon access, provisioning, credential handling, or authority change.** This is an inspect-only proposal for separate coordinator acceptance. The machine-readable allowlist is `H2_READONLY_QUERY_MANIFEST.json`; session sequencing is in `H2_READONLY_SESSION_PROTOCOL.md`.

## Pinned Git preflight and scope

Verified at preparation: `main@b5e9b078f171a15ffcf1cb197b61018cd76ca611`; `site-prod@7c9b81e35325b24f5201018e85b2989728876abd`; operational `multicity-wip-2026-09-16@bc87b712b2861621e943f0c05bf6e92afcfe374f`; eligibility research `576ac42b7734106ccc0edc858173c90f82537d85` and accepted coordination `66fbabf20644797bd67d3790893b4103a5dcb8ef`. Latest `main:PROJECT_STATE.md` and `main:CHANGELOG.md` were read first. `main` is two coordination-only commits ahead of `66fbabf` (no superseding H2 acceptance). **Recheck before any future access**; a changed state invalidates this preflight pin.

Accepted lineage retained, not re-executed: integrated H11/R09 `327caba41942346abc630d7f567d8b0ddc814ae8` (PG18.6 A/B run `39499796916`, independent `39500629652`); actual 008 `6084ec1dfc6e885ca35e32bec34c1dcfe67d6ad4` (run `39504096121`, independent `39504652475`, residual seven physical `relacl` deltas); ACL dossier `8b16053e031fe84f0b303ad531956b0f319ffbc5` (run `39565210464`); catalog consumer freeze `566e827dead199210d33f5bc99c5d7f66bbaef80` (runs `39580004681`, `39579882913`). These historical runs were verified successful at their tested commits, **not live Neon readiness**. Prior Neon catalog audit `380e16f4d8e861a30ba899921a7dbc33d5077bd5`, raw Git blob `e550b35578283b2af4e0e8fba956e98c4bcc0f03`, verified by `39273063710`, is an **old snapshot**, not a route/access grant; original SQL byte-exact retention was not proven. See `H2_READONLY_PREFLIGHT_ELIGIBILITY.md` and `H2_BLOCKER_MATRIX.json` at research `576ac42b`.

## Target distinction (historical versus current)

| Binding | Historically documented | Current authoritative verification |
|---|---|---|
| Neon project | `green-cake-44216048` | **NOT VERIFIED** |
| Candidate permanent populated shadow branch ID | `br-bold-mode-b5rub8pq` | **NOT VERIFIED** |
| SQL database | `neondb` | **NOT VERIFIED** |
| Candidate inspected compute ID | `ep-calm-rice-b5073ypp` | **NOT VERIFIED** (old catalog metadata) |
| Exact DNS hostname, TLS name, port, direct/non-pooled routing | **Not established in this package** | **NOT VERIFIED — hard stop** |
| Competing Neon default/primary | `br-wandering-sunset-b5835alw` (branch named `production`) | Distinct branch; **never a fallback** |
| Historic writer compute | `ep-still-violet-b5bg6mhp` | **Not** an inspector endpoint by inference |
| Target-role/host mapping as of inspection time | No current pin | **NOT VERIFIED — hard stop** |

Source: accepted future-authority **design**, not an activation, `research/neon_production_authority_contract_2026-10-10.json` at `eabdd380694abe045bf2cd15b7b83d7d1bb0d965`, plus eligibility report `576ac42b`. The older main workflow secret reference `PHASE1_PROD_SHADOW_DATABASE_URL` and one-time run `39309315728` (`neondb_owner` metadata at `main@3810d262`) do not establish today's endpoint, writer, permissions, or inspector identity. No secret was read.

**I1 cannot be proven from PostgreSQL alone.** `current_database()`, `current_user`, `session_user`, `inet_server_addr()` or `server_version` cannot authenticate a Neon project/branch/endpoint mapping. A future, separately authorized operator must supply a fresh, independently reviewed **nonsecret** project/branch/compute ID → exact host mapping from trusted Neon control-plane records, verify TLS `verify-full` on that hostname and verify the inspected SQL session against the pinned role/database. Hostname must not be derived from the `ep-` label, historical writer DSN or presumed Neon default. If provenance or mapping is unavailable, **STOP**; do not connect, probe another branch, or fall back. The future operator should document whether opening the connection may wake a compute and obtain scope approval for that effect.

## Inspector principal

**Proposed exact SQL role: `h2_catalog_inspector_ro` — NOT CREATED / NOT VERIFIED.** It should be a dedicated LOGIN principal with catalog-only read capability, no ownership of relevant objects/schema, no application-table `SELECT` or DML, no CREATEDB/CREATEROLE/SUPERUSER/BYPASSRLS/REPLICATION and no membership allowing inheritance or `SET ROLE` into a privileged actor. Capture `rol*` flags, direct membership edges and effective privileges using only pinned catalog/introspection SQL. The proposed name is a reviewer anchor, **not a claim it exists**. A one-time ability to connect as `neondb_owner` in a READ ONLY transaction is **not** an acceptable shortcut. Alternative principal/compensating controls: **NONE ACCEPTED**. A replacement requires a revised manifest, independent review, and fresh explicit user approval; not an automatic escalation.

Role creation, privilege revocation, secret creation, connection provisioning, and any Neon API or SQL are excluded from this offline task. If this role does not already exist with independently attestable nonsecret binding and permissions, first request **separate provisioning authorization**, then re-run fresh offline and owner approval. `READ ONLY` is a defense in depth: PostgreSQL documentation explicitly says it is a high-level restriction that does not prevent all writes to disk; it does not replace least privilege or an exact function-free allowlist (PostgreSQL 18 SET TRANSACTION: https://www.postgresql.org/docs/18/sql-set-transaction.html).

## What the first inspector can and cannot close

Permitted metadata: one database/session guard; proposed inspector role/membership; public schema owner/ACL; the **eight exact** canonical public relation names; raw `pg_class.relacl` (including NULL bit), 18-column checkpoint view and definition; selected constraints/indexes; selected effective inspector privileges; selected default ACL; three named `pg_catalog` built-in function signatures **without calling those functions**; `plpgsql` catalog entry and three PG session defaults. No application rows, personal records, H1/H2 row-level C4 comparison, source exports, functions' source/body, `EXPLAIN ANALYZE`, writes, role switch, or broad `pg_catalog` enumeration.

Catalog-only evidence can add bounded facts for original 183, 190, 206, 210, 211, 212, 213 and U1–U7, **not resolve the runtime/write aspects**. Contract 193/196/197 remain DB-only enforcement `MISMATCH`, seven physical ACL differences remain real and **Option B is not accepted**. Historical `203 MATCH / 3 MISMATCH / 7 UNVERIFIED`; 25 `UNBOUND_UNRESOLVED`, C4/C5 NOT PROVEN, and R6 remain separate. Any later historical row-level read, disposable SQL, CAS write, migration or cutover requires a distinct scope and authorization.

## Unresolved prerequisites / STOP checklist

1. Fresh checked Git coordination and exact accepted checkpoint state; verify no newer accepted H2 supersession.
2. Owner/operator named and independently reviewed *current* Neon project + candidate branch ID + compute ID + precise hostname/TLS/direct route; endpoint still attached to target branch and database; no default/pooler fallback.
3. Named `h2_catalog_inspector_ro` existence, actual authentication binding (no password exposure), non-owner/non-superuser/non-inheriting privilege attestation; no role-switch path or application-data privilege. Currently unknown.
4. Permission to inspect even catalog metadata and to wake target compute if necessary; nonsecret attestation scope and permitted output retention agreed. Currently absent.
5. Approved exact SQL hashes/byte caps/timeouts/abort and post-session independent receipt reviewer. No live runner approved; actual ability to enforce `READ ONLY` + `REPEATABLE READ` must be demonstrated only under later authorization.
6. Separate **explicit user authorization for actual Neon access**, absent. Do not treat offline reviewer PASS or this proposal as it.
7. All actual I1–I7 runtime checks pending. Historic `neondb_owner` is not the proposed identity; no role provisioning is included.

## Preserved gates

`H2_READONLY_NEON_PREFLIGHT_READINESS=BLOCKED/NO-GO` · `H2_DISPOSABLE_NEON_TEST_READINESS=BLOCKED/NO-GO` · `NEON_AUTHORITY_ACTIVE=NO` · `PRODUCTION_CUTOVER_EXECUTED=NO` · `WIP_ACTIVATION=NO-GO` · `H2_ACL_OPTION_B=BLOCKED / PROPOSAL_ONLY`. **No coordinator files on `main` modified.**