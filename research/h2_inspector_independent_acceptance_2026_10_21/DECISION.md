# H2 inspector independent coordinator decision — 2026-10-21

**Decision: ACCEPTED — OFFLINE PASS BOUNDED for Candidate A Git revision `a4f30691d89a4206b910b8dfde5dac44aee0ed99` only.**
**Actual Neon connection: BLOCKED / NO-GO.** Candidate B remains an unaccepted competing proposal.

## Independently executed source/proof

- Independent verifier: `research/h2_inspector_independent_acceptance_2026_10_21/verify_acceptance.py`.
- Independently successful CI: run `39613681469`, job `119268907588`, tested commit `0ea4093d27cf18d0a6d5af90032e982197c889f5`. Earlier test runs `39613261424`, `39613364654`, `39613506665`, `39613593686` FAILED and were corrected in the isolated verifier, not retroactively marked successful.
- Exactly eight Candidate A Git sources verified using Git object SHA-1 identity and recorded file SHA-256 in CI logs. Candidate A Git tree source commit `a4f30691d89a4206b910b8dfde5dac44aee0ed99`; predecessor three-file commit `454adb4772c6f58fbce0490e7112252ab3a55881`, one additive five-file commit thereafter. The historical original eight-file ZIP bytes were NOT independently available and ZIP-byte identity is NOT CLAIMED.
- **14 literal query SHA-256 pinned independently**; independently verified all 8 canonical relation name literals and raw `relacl IS NULL` plus physical ACL text. A primary verifier: 43/43 manifest/receipt mutations rejected; secondary pinned-digest checker: 16/16 rejections; independent new verifier: 36/36 rejections. Synthetic receipt only, never Neon evidence.
- `manifest_sha256` (canonical compact JSON + newline): `53577d42b0cf2717df9ed9c3daa083867e8bf6e9e3397b2f1ce5e19d21f0c70e`. Git blob `H2_READONLY_QUERY_MANIFEST.json`: `c4d4f6174699cd64710a0157da3c1bf1c85cae8d`; file SHA-256 `dc55db972ecf3821eecc0e4633b319f9bad8bf47153494739ea7b28e0b07f41d`. Do not confuse these hashes.
- Historical Candidate B run `39598623324`, job `119217125614`, SUCCESS on `827e843b7fb40d84b79091ed0985bfc5091c0249`; 31/31 own negatives witnessed. However two independent adversarial mutations **PASSED B's original regex/hash verifier** when the SQL and its self-stored hash/receipt columns were changed: `SELECT pg_catalog.pg_try_advisory_lock(42) AS db LIMIT 1;` and `SELECT pg_catalog.pg_ls_dir('/tmp') AS db LIMIT 1;`. These two strings were never executed against any database; only the verifier parsed them. Thus **B rejected** as immutable safe allowlist. B is not an exact-source completion of A.
- Candidate A protocol: 1 pinned direct TLS verified target, 1 PG18 transaction, repeatable-read/read-only, 14 unique SELECT / 15 executions / 21 wire SQL statements; max 180 rows / 65536 sanitized output bytes, per-cell 8192; 15s statement / 5s lock / 30s idle / 45s transaction / 60s client wall; repeat guard G01, explicit rollback. **No implementation to connect was developed/executed.**
- Observed independent test caveat: original `h2_readonly_offline_verifier.py` synthetic receipt-negative helper shares nested `columns` list references and can mutate a passed in-memory manifest when a synthetic column-removal case runs. New review passes a deep copy; original eight source files are unchanged. This is an offline-test helper side effect, not an executed SQL mutation; future runtime runner must use immutable inputs. New independent verifier also enforces nonempty expected columns.
- SQL and manifest static audit cannot prove runtime side effects impossible, catalog visibility complete, all SQL-result bytes sanitized, PG roles absent of privileges, endpoint-to-branch mapping current, zero unseen client activity, or rollback actually acknowledged. Exact pinned literal allowlist plus least privilege/read-only/server guard is required later. Query cap sentinel rows indicate INCOMPLETE not PASS.

## Offline I1–I7 disposition

| Contract | Offline | Actual |
|---|---|---|
| I1 target endpoint/branch identity | Historical design/pin | UNVERIFIED: fresh owner control-plane route attestation absent |
| I2 inspector privilege identity | Role assertions specified | BLOCKED: proposed h2_catalog_inspector_ro not verified to exist/authenticate |
| I3 server read-only/snapshot/rollback | Guard protocol static PASS | UNVERIFIED: no SQL session, rollback |
| I4 object/ACL/catalog contents | 14 pinned safe literal queries/static PASS | UNVERIFIED: no current catalog read |
| I5 row/byte/time budgets | Static definition PASS | UNVERIFIED: no approved runtime executor |
| I6 receipt integrity | Synthetic layout and hash checks PASS | UNVERIFIED: no real receipt |
| I7 zero mutation | Offline tests made no Neon calls | UNVERIFIED: no actual client/session proof |

Actual read-only **BLOCKED/NO-GO**. Actual disposable Neon, cutover, WIP activation, ACL Option B all remain **BLOCKED/NO-GO / NO**. Historical 203/3/7, 25 UNBOUND, C4/C5 unproven, physical 7-relacl mismatch remain unchanged.

## Smallest subsequent prerequisite (NOT ACTIVE AUTHORIZATION)

Request an authorized Neon owner **nonsecret** current project/branch/database/compute/endpoint-to-full-TLS-hostname mapping and inspector existence/least-privilege-role attestation, with provenance and independent reviewer. This is not permission to access Neon. If the dedicated inspector does not exist, prepare a separate explicit provisioning authorization; do not create it implicitly. After evidence reviewed, obtain a new user authorization for an exact single-session I1–I7 catalog-only read (see separately drafted conditional prompt).

No Neon SQL/API, credentials, role provisioning, production/site-prod, operational WIP, R6, casualty, historical data, backfill, ACL exception or migration writes in this task.
