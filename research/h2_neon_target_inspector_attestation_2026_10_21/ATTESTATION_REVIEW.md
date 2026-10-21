# H2 target/inspector independent offline review

2026-10-21 | Prepared from GitHub metadata and accepted immutable source records only | No Neon access

## 1. Evidence standard

`VERIFIED_GIT` means an immutable Git/GitHub statement or CI outcome was directly checked; it does not authenticate a Neon control-plane state. `HISTORICAL` identifies past observations/designs and cannot fill a current binding. `UNVERIFIED` means that a current owner-sourced, timestamped, independently reviewed attestation is absent. `NOT_PROVEN_TO_EXIST` is not a finding that a role is absent. Owner narrative without primary provenance remains an assertion, not independent current verification.

Base source of truth: `main@69ae64d6f754542026804cfd742c0c1a4d40ede5` current `PROJECT_STATE.md` and `CHANGELOG.md`. Accepted Candidate A source `a4f30691d89a4206b910b8dfde5dac44aee0ed99`; independent successful CI `39613681469` (job `119268907588`, tested `0ea4093d27cf18d0a6d5af90032e982197c889f5`). The existing eight-file offline verifier suite was neither edited nor rerun. Supplemental `39620712464` remains PARTIAL as instructed, regardless of its green CI conclusion.

## 2. Verified Git vs historical vs current Neon target

| Binding | Historical source value | What Git actually verifies | Current authoritative binding | Required provider |
|---|---|---|---|---|
| Neon project ID | `green-cake-44216048` | 2026-10-10 design and 2026-10-21 accepted proposal contain this ID | **UNVERIFIED** | Authorized Neon owner |
| Branch ID / intent | `br-bold-mode-b5rub8pq`, permanent populated shadow proposed for future authority | The design selected it; selection did not activate authority | **UNVERIFIED** | Authorized Neon owner |
| SQL database | `neondb` | Historical read-only catalog snapshot reported this database | **UNVERIFIED** | Authorized Neon owner |
| Compute/endpoint ID | `ep-calm-rice-b5073ypp` in historical catalog metadata | Candidate A expressly leaves `current_endpoint_id=null` | **UNVERIFIED** | Authorized Neon owner |
| Exact direct TLS hostname | Not pinned in Candidate A; must not derive from endpoint label | Manifest `endpoint_hostname=null` and `host_branch_mapping_verified=false` | **UNVERIFIED** | Authorized Neon owner |
| TLS route / port / pooler status | Historical location and connection labels insufficient | No trusted current direct-route-to-project/branch binding | **UNVERIFIED** | Authorized Neon owner |
| Project -> branch -> endpoint -> hostname -> DB binding | No fresh consolidated signed/exported proof | Old project metadata and SQL session each cover different layers | **UNVERIFIED** | Authorized Neon owner + independent reviewer |
| Confusable default/primary | `br-wandering-sunset-b5835alw` named `production` | Historically distinct from proposed populated shadow | **UNVERIFIED current**; explicitly **NOT A FALLBACK** | Authorized Neon owner |
| Confusable writer compute | `ep-still-violet-b5bg6mhp` | Historically recorded as writer compute label, not inspector route | **UNVERIFIED current**; explicitly **NOT A FALLBACK** | Authorized Neon owner |
| Provenance date | 2026-10-10 authority design; 2026-10-19 selected catalog audit | These are historical record dates | **UNVERIFIED current observation time** | Owner with timestamped export |

**I1 determination: UNVERIFIED / NO-GO.** PostgreSQL session introspection cannot attest Neon project-to-branch-to-endpoint routing by itself. Current direct compute ID, exact full TLS FQDN, TLS verify-full hostname match, branch and database association, and nonsecret observation/provenance timestamp are missing. No connection, guessed hostname, alternate branch, pooler substitution or owner fallback is allowed.

## 3. Proposed dedicated inspector privilege-attestation matrix

Proposed role literal: `h2_catalog_inspector_ro`. An approved role name in a Git manifest is not a created login. No owner-furnished current role attestation was available.

| Inspector control | Required nonsecret attestation (owner must show current state and provenance) | Current status |
|---|---|---|
| Exists and exact principal | One exact PostgreSQL role, attached to pinned project/branch/database, capable of its own authorized login | **NOT_PROVEN_TO_EXIST** |
| Login identity | `rolcanlogin=true`; successful independent session auth binding to exact role later checked under separate authorization | **UNVERIFIED** |
| Elevated role flags | `rolsuper=false`, `rolcreaterole=false`, `rolcreatedb=false`, `rolreplication=false`, `rolbypassrls=false`; no equivalent elevated owner route | **UNVERIFIED** |
| Role memberships | Full direct and transitive membership edges; `admin_option`, `inherit_option`, `set_option`; no privileged inheritance or admin/SET ROLE path | **UNVERIFIED** |
| Ability to switch roles | Independently account for `SET ROLE` reachability through memberships, not just `rolinherit`; no switch to writer/owner/cloud roles | **UNVERIFIED** |
| Ownership | Zero ownership over named canonical tables, checkpoint view, relevant schemas, SECURITY DEFINER routines or other objects conferring DDL/data access | **UNVERIFIED** |
| CONNECT / schema access | Exact database `CONNECT`, intended bounded catalog visibility and needed schema metadata only | **UNVERIFIED** |
| Effective data rights | No application-table `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`, `REFERENCES`, `TRIGGER` via direct grants, PUBLIC, memberships or owner privileges | **UNVERIFIED** |
| DDL and privilege escalation | No relevant schema `CREATE`, object ALTER/ownership, role membership ADMIN, default ACL/grant path or executable privileged function pathway | **UNVERIFIED** |
| Search path / effective grants | Bounded inspector schema grants, default privileges and function EXECUTE exposure independently assessed; unexpected paths fail closed | **UNVERIFIED** |
| Implicit `neondb_owner` fallback | Explicit owner/operator attestation that no access will use that role and no automatic connection failover changes principal | **UNVERIFIED** |
| Named people, allowed scope and freshness | Neon owner, proposed operator, independent reviewer, UTC evidence timestamp and precise catalog-only scope | **UNVERIFIED** |

**I2 determination: BLOCKED / NO-GO.** Role existence is not confirmed; do not label it ABSENT. The 2026-10-19 old SQL audit reported `session_user=current_user=neondb_owner`, which is positive evidence of an *older different principal*, not evidence of `h2_catalog_inspector_ro`. Its `READ COMMITTED` isolation is also insufficient to prove the future `REPEATABLE READ` protocol. No replacement/compensating principal has been approved.

## 4. Independent contradiction and identity-mismatch review

| ID | Comparison | Finding and consequence | Resolution needed |
|---|---|---|---|
| C01 | Proposed populated shadow vs old primary named `production` | Different historical IDs. Human-readable branch names do not prove routing; a default connection risks querying the wrong branch. No claim of current misrouting. | Owner export ties exact desired branch ID to endpoint ID/FQDN/database. |
| C02 | `ep-calm-rice-b5073ypp` vs `ep-still-violet-b5bg6mhp` | Old inspect and writer endpoint labels differ; neither supplies a current inspector TLS route. | Explicit current compute role/type, ID and FQDN mapping; direct/non-pooled route. |
| C03 | `neondb_owner` in old audit vs `h2_catalog_inspector_ro` proposed | Old catalog evidence used the owner principal; this does not attest proposed least-privilege role. Owner login is forbidden as an implicit fallback. | Independent nonsecret role existence, effective rights, membership and ownership proof. |
| C04 | 2026-10-19 READ COMMITTED vs new REPEATABLE READ | Old audit confirmed a read-only transaction with weaker isolation, not new I3 runtime controls. | Separately authorized future session; do not upgrade I3 now. |
| C05 | Historical metadata vs current branch/hostname | Git-pinned Candidate A explicitly has null current endpoint and hostname; 2026-10-10 selection was DESIGN ACCEPTED, not production authority activation. | Timestamped owner control-plane export; prohibit inferred FQDN. |
| C06 | Green supplemental 39620712464 vs coordinator acceptance | Supplemental offline CI reported success but remains PARTIAL and cannot replace Candidate A accepted `39613681469` or imply Neon observation. | Preserve PARTIAL classification until separate coordinator acceptance, no CI rerun. |
| C07 | Offline manifest passes vs actual I1–I7 | 14 independently pinned SQL hashes and synthetic negatives test offline integrity, not runtime server privileges, catalog rows, rollback or no-mutation receipt. | Treat all runtime I1–I7 as pending; no I1–I7 pass claimed. |
| C08 | GitHub repository owner vs Neon project owner | GitHub write access does not establish authority over the Neon project or prove independent-review roles. | Identify accountable Neon owner, operator and distinct reviewer in owner response. |

These are conflicting *candidate interpretations or insufficient proofs*, not independently proven current infrastructure defects. No mismatch is repaired or overridden by inference.

## 5. Evidence provenance and independent findings

- `main@69ae64d6f754542026804cfd742c0c1a4d40ede5`: accepted live coordination source. 2026-10-21 readback: `PROJECT_STATE.md` blob `10f468d262e4d6c36cf4fa202e07161a9f48a5aa`, `CHANGELOG.md` blob `ecb98bae8c92ed5c3990ccafa7cb0aec30f9341d`.
- `a4f30691d89a4206b910b8dfde5dac44aee0ed99`: accepted Candidate A, target/role proposal blob `82c4f02f165d1bd26efb0af17d51f6864c6fd2f3`, SQL manifest blob `c4d4f6174699cd64710a0157da3c1bf1c85cae8d`. Manifest records null `current_endpoint_id` and `endpoint_hostname`, false `actual_role_verified`.
- Independent CI run `39613681469`, job `119268907588`, tested `0ea4093d27cf18d0a6d5af90032e982197c889f5`: GitHub API job SUCCESS and job log exact eight pinned blobs, manifest canonical SHA256 `53577d42b0cf2717df9ed9c3daa083867e8bf6e9e3397b2f1ce5e19d21f0c70e`. See accepted decision at research `9fc3e3e36119a830a74e2df808166d9101170616`. Original ZIP byte-identical reconstruction remains unproven.
- 2026-10-10 DESIGN only: `research/neon_production_authority_contract_2026-10-10.json` at `eabdd380694abe045bf2cd15b7b83d7d1bb0d965`, Git blob `2b9b06f93bc9ff8fddab866eb38fe826d36ebbc6`.
- 2026-10-19 historical catalog audit: `research/h2_live_neon_catalog_readonly_verification_2026-10-19.json` at `380e16f4d8e861a30ba899921a7dbc33d5077bd5`, Git blob `b7d951c18a2aca2a738168b923c6e655c2270e32`, separately cites original raw response Git blob `e550b35578283b2af4e0e8fba956e98c4bcc0f03`. It reports `neondb_owner` / `read committed`, and cannot be promoted to current inspector proof.
- Supplemental run `39620712464` jobs/artifacts checked; successful GitHub execution `4501be23dde27ff04d3f22531b415bb9b2c9a7fd` is PARTIAL as an H2 checkpoint. No new owner attestation is identified in current `main` coordination.
- `EVIDENCE_REGISTER.json` enumerates each missing owner assertion and required proof without speculative current values. No live Neon or external application was contacted.

## 6. I1/I2 readiness and minimum conditions

| Gate | Offline readiness now | Live readiness now | Next independent decision |
|---|---|---|---|
| I1 route/target | OWNER REQUEST PREPARED | **UNVERIFIED / NO-GO** | Obtain timestamped primary nonsecret mapping for exact project, branch, database, direct compute endpoint and full TLS FQDN with provenance and independent review. |
| I2 dedicated inspector | OWNER REQUEST PREPARED | **NOT PROVEN TO EXIST; PRIVILEGES UNVERIFIED / NO-GO** | Obtain exact role-existence and direct/transitive effective privilege attestations. If confirmed absent, separately authorize provisioning proposal first. |
| I3–I7 | Accepted offline protocol and synthetic CI evidence reused, not rerun | **UNVERIFIED RUNTIME / NO-GO** | New scoped owner/operator/reviewer approval, exact immutable Candidate A manifest, separately authorized catalog-only session and independent real receipt. |

Minimum remaining prerequisites, in order: (1) owner-named current target mapping with timestamp, provenance, full direct hostname/TLS identity; (2) owner-named existing dedicated role proof and negative privilege, ownership, membership and `SET ROLE` evidence, or **separate** authorization to provision if confirmed absent; (3) named accountable operator and independent reviewer, bounded allowed catalog result classes, compute-wake/logging effect and retention approval; (4) reviewer accepts source-pinned Candidate A and approved I1–I7 fail-closed budget/protocol without opening a session; (5) fresh coordination preflight and **new explicit user authorization** for one catalog-only read. If any part is missing, stop. Provisioning is never implied by an inspection approval.

Hard holds unchanged: H2 read-only Neon NO-GO; disposable Neon NO-GO; Neon authority NO; production cutover NO; WIP NO-GO; ACL Option B BLOCKED/PROPOSAL_ONLY; 203/3/7, 25 UNBOUND, C4/C5, seven relacl observations. No actual I1–I7 compliance claim.
