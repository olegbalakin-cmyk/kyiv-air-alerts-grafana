# H2 inspector target: owner-observed nonsecret evidence (22 October 2026)

State: OWNER_REPORTED / PARTIAL; not independently attested PostgreSQL or Neon control plane. This is a Git-only research record, not Neon authority.

## Preflight and reference hierarchy

Read main:PROJECT_STATE.md and main:CHANGELOG.md before preparing this record. Pinned preflight main is d4b5b5753733ec80586526e8666b31f344437e31; current at authoring, not a future guarantee. Other observed heads: site-prod 63d42ee984c11d1cc8b33a95b2f8a4bf4a08e170; multicity-wip-2026-09-16 27b11ad3a0982f4905a1675157866aad8016a4f0. These refs and independent R6, production, historical/backfill and casualty checkpoints are not changed.

Accepted Candidate A: a4f30691d89a4206b910b8dfde5dac44aee0ed99 (eight pinned files). Independently accepted offline-only run 39613681469 (SUCCESS; job 119268907588; tested 0ea4093d27cf18d0a6d5af90032e982197c889f5). Supplemental 39620712464 stays PARTIAL even if its job is green. Previous offline target/inspector review: 43ae07403e059e75dfe2ce402b0c01ad842b5904. Correct 40-character main coordination commit: a62c3afd67e91bd7e5b40c99a9125d5b98d5d7dd (the authorization text omitted four characters). Git proves these records and decisions, not today's Neon state.

## Owner-observed values, not provider attestations

| Parameter | Owner-supplied observation | Evidence status |
|---|---|---|
| Project | green-cake-44216048 | Owner-reported UI |
| Branch ID | br-bold-mode-b5rub8pq | Owner-reported UI |
| Branch name | lviv-phase1-production-shadow-2026-09-28 | Owner-reported UI |
| Database | neondb | Owner-reported UI |
| Intended read-only compute ID | ep-calm-rice-b5073ypp | Owner-reported UI |
| Intended direct hostname | ep-calm-rice-b5073ypp.c-7.us-east-2.aws.neon.tech | Owner-reported UI, TLS-to-branch binding unverified |
| Pooling | Disabled | Owner-reported UI |
| Compute state | Suspended/Idle when observed | Owner-reported UI; the later check could wake it |
| Console-listed role | neondb_owner | Owner-reported UI; not approved inspector |
| Proposed inspector | h2_catalog_inspector_ro not visible | NOT proof of PostgreSQL nonexistence |
| Separate primary compute | ep-still-violet-b5bg6mhp | Owner-reported; never an existence-read fallback |

Owner observations were described in the 2026-10-22 task, attributed to project owner screenshots. Original screenshot bytes, capture UTC, current independent control-plane export, SHA-256 and full port/TLS verification are not preserved in this Git artifact. This record contains no screenshot, credentials, DSN or connection string. Do not silently elevate owner-report to verified routing.

The previous 2026-10-10 authority design selected this shadow branch but is historical only; an independently verified live route and a signed primary source linking project -> branch -> read-only compute ID -> direct FQDN -> database remain needed. The historically named production/default branch br-wandering-sunset-b5835alw must not be substituted. A Neon compute can be a read replica, but the Console screenshot alone does not prove server-enforced read-only semantics, its current type, port or identity at query time.

## Five evidence classes

- VERIFIED_GITHUB: exact commits, accepted Candidate A SQL manifest SHA, run SUCCESS, coordination status and historical comparisons.
- OWNER_REPORTED_UI: values above, as observed on 22 October 2026. Current view and specific time are not independently authenticated.
- LIVE_SQL_REQUIRED: role existence from pg_catalog.pg_roles, session identity, PostgreSQL server version and transaction_read_only at execution. No query occurred.
- CONDITIONAL_PROVISIONING_REQUIRED: only after role absence is positively shown and a *separate* owner/user approval is issued. Nothing created here.
- POST_PROVISION_INDEPENDENT_REVIEW_REQUIRED: effective permissions, membership paths, ownership, credentials out-of-band, application data exclusions and any changes in raw ACL/catalog state. No such review occurred.

Neon officially distinguishes roles created by Console/API/CLI (automatically members of neon_superuser) from SQL-created roles (limited defaults). Source: https://neon.com/docs/manage/roles (checked 2026-10-22). Therefore Console absence is insufficient and its Add Role control is prohibited for this inspector. Source for membership and attributes: https://www.postgresql.org/docs/18/catalog-pg-auth-members.html and https://www.postgresql.org/docs/18/functions-info.html.

## Next gate

Before any new connection, a named authorized Neon owner must supply a timestamped, independently reviewable nonsecret branch/compute/host/database routing attestation, approved read-only compute type, actual port, TLS verify-full hostname match, owner/operator/reviewer identities, and express permission for one existence-only SQL read. An owner's privileged PostgreSQL session can be used *only* for this narrow role-existence read under that separate permission; it is not the Candidate A inspector login or an I1-I7 pass.

Current: I1=OWNER_REPORTED_PARTIAL/NO-GO; I2=EXISTENCE_UNVERIFIED/NO-GO; I3-I7=RUNTIME_UNVERIFIED. All hard holds remain unchanged.
