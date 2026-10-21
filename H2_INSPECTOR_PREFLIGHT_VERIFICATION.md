# H2 inspector catalog-only package — offline verification and coordinator decision record

**State: PACKAGE CANDIDATE / OFFLINE ONLY.** No Neon access, endpoint discovery, credentials, role creation, SQL execution, CI dispatch, or operational promotion was conducted in this task. This report is **not** an authorization to execute its session plan. No production, `site-prod`, operational WIP, R6, casualty, historical or backfill changes are proposed.

## Source and preflight provenance (21 October 2026)

Read current `main:PROJECT_STATE.md` and `main:CHANGELOG.md` first. Verified `main@b5e9b078f171a15ffcf1cb197b61018cd76ca611`; coordinator acceptance `66fbabf20644797bd67d3790893b4103a5dcb8ef` (main is only two coordination-doc commits ahead); eligibility matrix `576ac42b7734106ccc0edc858173c90f82537d85` and its three original blobs `d224cd702512c586ba8ca483131ab13f4812eff3`, `d58e92ad3d17ae020719453100b24664e2915067`, `293e393dc504a9510e55bfca039b115a923c125e`. Current isolated-domain refs inspected: `site-prod@7c9b81e35325b24f5201018e85b2989728876abd`, operational `multicity-wip-2026-09-16@bc87b712b2861621e943f0c05bf6e92afcfe374f`. Those branches were read, not changed. Research branch is independent from accepted matrix branch.

Older accepted evidence **read-only verified, not rerun**: PG18.6 H11/R09 integrated `327caba41942346abc630d7f567d8b0ddc814ae8`, Actions `39499796916` SUCCESS (tested `780348a2a5a2ae294871bf10bf60c5e394f4afb6`) and independent `39500629652`; actual ACL 008 `6084ec1dfc6e885ca35e32bec34c1dcfe67d6ad4`, run `39504096121` SUCCESS (tested `5213a91ae593a3ef80f4936d55c7ec08c4a5737e`) and independent `39504652475`; seven physical relacl dossier `8b16053e031fe84f0b303ad531956b0f319ffbc5`, run `39565210464` SUCCESS (tested `0d156bcea786d015a307f7d0f4c8b49c5a3b5e63`); freeze/catalog audit `566e827dead199210d33f5bc99c5d7f66bbaef80`, independent run `39580004681` SUCCESS, source audit `39579882913` SUCCESS. Old Neon catalog U1–U7 raw freeze at `380e16f4d8e861a30ba899921a7dbc33d5077bd5` (raw blob `e550b35578283b2af4e0e8fba956e98c4bcc0f03`; original run `39273063710` SUCCESS), and old nonsecret URI checker `39309315728` SUCCESS at `3810d2627d3ef8454dd31bdeaa41b9fdfd520888`. None attests an active present-day route or a minimally privileged inspector. The old read-only catalog audit used `read committed` and `neondb_owner` and does not meet this package's proposed controls.

Relevant accepted source contracts: 213 original rows (`203` structural MATCH / `3` DB-invariant MISMATCH ordinals `193,196,197` / `7` UNVERIFIED ordinals `183,190,206,210,211,212,213`); physical `pg_class.relacl` differences remain visible and unaccepted, `UNBOUND_UNRESOLVED=25`, `C4/C5=NOT PROVEN`. This package makes no upgrade to these statuses. R6 remains an independent track.

## Deliverables and deliberately narrow catalog limits

- `H2_INSPECTOR_TARGET_AND_ROLE.md` — names historical proposed project/branch/db/compute, **NULL current host/endpoint evidence**, proposed unprovisioned dedicated `h2_catalog_inspector_ro` and owner approval prerequisites. Default Neon production branch is *not* a fallback.
- `H2_READONLY_QUERY_MANIFEST.json` — 14 exact pinned one-SELECT statements `G01..G14`, per-query SHA-256, result columns, row cap, contract-purpose mapping, single transaction with G01 first and last. Prohibits application rows, user-defined functions, secrets, role switches, writes, fallback, Neon APIs.
- `H2_READONLY_SESSION_PROTOCOL.md` — one direct session, `BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY`, four `SET LOCAL` bounded-time controls, dual G01 checks and explicit `ROLLBACK`, cancel/close/fail-closed conditions. Limits: 1 connection, 1 transaction, 15 SELECT executions, 21 SQL executions, 180 rows total, 65,536 sanitized UTF-8 bytes, 8,192 per cell; 15s statement, 5s lock, 30s idle-in-transaction, 45s transaction, 60s client.
- `h2_readonly_offline_verifier.py`, `H2_INSPECTOR_NEGATIVE_CONTROLS.json` — exact canonical JSON policy and reject-on-tamper synthetic receipt-shape checks. No database/network executable path.
- `h2_independent_manifest_review.py`, `H2_INSPECTOR_INDEPENDENT_REVIEW.json` — separately hard-coded 14 expected SQL hashes and independent static/adversarial inspection; cannot certify real execution.

**Byte/hash discipline:** Per-query SHA-256 in manifest is over the UTF-8 content of the exact `sql` field (no trailing newline added). `manifest_sha256` in synthetic receipt covers `json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(',', ':')) + '\n'`. Git blob hash and normal pretty-JSON file SHA-256 are different domains; do not substitute one for the other. A later accepted runner must independently reject any hash mismatch before connection, and must never generate a permissive manifest itself.

## Executable OFFLINE evidence

Reproduce locally with Python standard library (no credentials, environment read or network):

```bash
python3 h2_readonly_offline_verifier.py --verify
python3 h2_independent_manifest_review.py --verify
```

Expected printed bounds for these exact evidence JSONs: **14/14 SQL fingerprints**, **20/20 manifest-policy mutations rejected**, **23/23 synthetic-receipt violations rejected**, totaling **43/43 independent negative cases in the primary suite**, plus **16/16 reviewer mutations rejected**. These are two implemented verifier designs, not two independently operated human audit teams. The synthetic fixture `FAKE_SNAPSHOT` is deliberately tagged `SYNTHETIC_OFFLINE_ONLY` and cannot be used as a real receipt. Offline negatives include altered target branch, endpoint/route assertion, owner role swap, isolation/read-only guards, out-of-bounds resource budgets, raw ACL loss, secret inclusion, writes, SQL mutation with rehash, unknown catalog table/function and role-switch attempts. Inspect the individual case IDs and failure reasons in the two JSON result files.

## I1–I7 gate outcome **NOW**, before Neon or approvals

| Gate | Offline package shape | Actual runtime outcome / why |
|---|---|---|
| I1 route identity | DESIGNED | **UNVERIFIED**: project/branch/compute/hostname mapping is only historical; no current signed nonsecret proof. |
| I2 inspector identity | DESIGNED | **BLOCKED**: proposed least-privilege inspector has not been shown to exist or to lack memberships/escalation. `neondb_owner` prohibited without new approved exception. |
| I3 server-side read-only and snapshot | DESIGNED | **UNVERIFIED**: cannot observe `transaction_read_only=on`, REPEATABLE READ or rollback without separate access. |
| I4 catalog contract | DESIGNED | **UNVERIFIED**: no live object owner/ACL/view/index/catalog data; previous U1–U7 remain old bounded metadata. |
| I5 data and time limits | OFFLINE STATIC PASS | **UNVERIFIED RUNTIME**: future connector must actually enforce connection, cancellation and byte/row caps. |
| I6 receipt/query source | OFFLINE HASH DESIGN PASS | **NO REAL RECEIPT**: only manifest and synthetic verifier evidence exist. |
| I7 no mutation/authority inflation | OFFLINE ACTIVITY CONSTRAINT MET | **UNVERIFIED RUNTIME**: no authorized session or independent post-session audit exists. |

**Overall: OFFLINE DESIGN READY FOR INDEPENDENT COORDINATOR REVIEW ONLY. ACTUAL READ-ONLY NEON NO-GO.** The package has no SQL execution routine, credentials, DSN, database hostname, Neon API caller or provisioning capability.

## Fail-closed negative controls and known coverage limits

Fail before opening a connection unless a new operator-owned timestamped control-plane **project→branch→endpoint→host** mapping, named role attestation, independent owner approval, explicit new user authorization and fixed reviewer-signed query manifest have been approved. Verify live guards before G02..G14. If any required row, privilege, complete catalog visibility or result schema differs, stop and return incomplete; do not expand to DDL, `SET ROLE`, `neondb_owner` or application-data queries. Missing G01 snapshot invariance, timeout, query budget, rollback acknowledgement, or any unexpected privilege is a hard NO-GO. The exact application writer binding, seven-ACL Option B decision, actual DB-only 193/196/197 enforcement, full 25 UNBOUND adjudication and C4/C5 data-level reconciliation are outside this catalog inspection.

Static checks **cannot prove SQL has no side effects for all PostgreSQL implementation paths** and cannot prove every output field is harmless; real execution would require separate operator-controlled client audit, server-granted minimal rights, server-enforced transaction state, explicit cancellation and receipt review. A read-only transaction may have non-data effects (e.g. compute wake/access logs). A missing rollback acknowledgement is **UNVERIFIED**, not proof of zero attempted writes. This package never claims a production cutover, a migration trial or real Neon access.

## Required later coordinator disposition

1. Independently review SQL, all I1–I7, exact list of catalog objects, evidence receipt schema and cap/timeout design; reject if any gap or different assumption is found. Confirm the research diff contains *only additive package files* and no coordination, secrets, operational workflow, or code changes.
2. Arrange separately authorized non-secret current branch/endpoint/host mapping and demonstrate a dedicated inspector role's current permissions. **Do not automatically create a role:** provisioning is a separately authorized control-plane/write task.
3. Obtain separate explicit user approval, operator identity, reviewer and time-bounded scope. Only then consider a purpose-built executor (not included here) for one catalogue-only read session; a new decision is needed for any other activity.

Preserved holds: `H2_READONLY_NEON_PREFLIGHT_READINESS=BLOCKED/NO-GO`; `H2_DISPOSABLE_NEON_TEST_READINESS=BLOCKED/NO-GO`; `NEON_AUTHORITY_ACTIVE=NO`; `PRODUCTION_CUTOVER_EXECUTED=NO`; `WIP_ACTIVATION=NO-GO`; `H2_ACL_OPTION_B=BLOCKED / PROPOSAL_ONLY`.