# DRAFT ONLY — NOT ACTIVE AUTHORIZATION: H2 FIRST REAL NEON CATALOG INSPECTION

**STOP. Do not use this prompt until separately authorized explicitly by the user after a fresh route/role preflight.** An accepted offline package is not permission to connect.

## Immutable offline source
- Accepted Candidate A commit `a4f30691d89a4206b910b8dfde5dac44aee0ed99`.
- Manifest Git blob `c4d4f6174699cd64710a0157da3c1bf1c85cae8d`, file SHA256 `dc55db972ecf3821eecc0e4633b319f9bad8bf47153494739ea7b28e0b07f41d`, canonical manifest SHA256 `53577d42b0cf2717df9ed9c3daa083867e8bf6e9e3397b2f1ce5e19d21f0c70e`. All 14 G01–G14 SQL text and per-query hashes must match the frozen Candidate A manifest, not a regenerated proposal.
- Independent CI `39613681469` / job `119268907588` / review commit `0ea4093d27cf18d0a6d5af90032e982197c889f5`. Recheck against any newer accepted coordinated state.

## Mandatory separate owner/operator preconnection evidence
1. Exact verified current project `green-cake-44216048`, target branch `br-bold-mode-b5rub8pq`, database `neondb`, fresh nonsecret endpoint/compute/FQDN-to-branch attestation, independently reviewed and dated. Historical `ep-calm-rice-b5073ypp` is NOT a verified current endpoint.
2. Named and independently authorized principal `h2_catalog_inspector_ro` proved to exist with least privilege, direct authentication, no elevated owner/membership/SET ROLE path/application data rights. `neondb_owner` forbidden fallback. No role provisioning here.
3. Named operator, independent reviewer, explicit user consent for **this exact inspection**, retention and budget; confirmation that compute wake is in scope. If any fact missing: NO CONNECTION.
4. No secrets/connection strings shown in public evidence. No guessed host, wrong branch, default branch `br-wandering-sunset-b5835alw`, writer endpoint `ep-still-violet-b5bg6mhp`, pooler/fallback/retry.

## Only after renewed explicit access authorization
One TLS verify-full direct connection to the approved FQDN, one PG18 transaction `REPEATABLE READ READ ONLY`. Server-confirm exact `transaction_read_only=on`, role/database/identity, isolation, 15s statement, 5s lock, 30s idle transaction, 45s transaction timeouts. Client wall 60s. Exactly manifest `session_sql_order`: BEGIN, four SET LOCAL, G01..G14, G01 repeat, ROLLBACK. No DDL/DML/role switching, no arbitrary functions, no application rows, no external Neon API/endpoint changes, no secrets or DSNs in logs. Maximum 180 returned rows and 65536 sanitized output bytes (8192/cell). At sentinel/incomplete/privilege unexpected/missing data: STOP; cancel, attempt ROLLBACK, close, and record ROLLBACK UNVERIFIED if not acknowledged. No retries.
Deliver independently reviewed, sanitized receipt identifying exact target and source manifest, route provenance, actual server session/role assertions, all G01..G14 column schemas/rows/bytes/physical relacl NULL/text/result digests, I1–I7 PASS/PARTIAL/FAIL/UNVERIFIED, client attempted-mutation counters, and explicit rollback acknowledgement. This would only accept a bounded observational catalog snapshot, not migration/disposable testing/cutover or a seven-relacl exception.
Hard holds: read-only preflight remains BLOCKED pending new authorization, disposable Neon BLOCKED, NEON_AUTHORITY_ACTIVE=NO, PRODUCTION_CUTOVER_EXECUTED=NO, WIP_ACTIVATION=NO-GO, H2_ACL_OPTION_B=BLOCKED/PROPOSAL_ONLY; no production/site-prod/WIP/R6/casualty/history/backfill changes.
