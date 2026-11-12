# C6 — same-run Neon episode parity, C2 #43262387718

**2026-11-12.** This is a scoped independent read-only Neon SQL comparison to the immutable C2 corpus. It does **not** claim a current six-JSON physical generator proof.

## Result

- `NEW_C2_EPISODE_NEON_PARITY=PASS`: 23/23 cities, 33,267/33,267 canonical episode rows, zero unexplained differences. Deterministic SHA-256 checks per city cover seven fields: legacy ID, city, alert type, state, canonicalization version, UTC start, UTC end.
- `NEW_C2_NEON_JSON_PARITY=BLOCKED`: no new-run physical Neon read-only JSON generator was executed, and no new six-file Neon output artifact exists. Prior [physical proof #43187464328](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43187464328) still belongs to the older corpus, not this run.
- Current Neon database contained 33,529 closed AIR rows: 33,267 same-run canonical rows plus the **262 independently inventoried older superseded versions** from [PR #74](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/74). These 262 rows were *excluded only from the canonical comparison*, **not deleted**. 23-city SHA-256 equality is in [NEON_SQL_WITNESS.json](NEON_SQL_WITNESS.json).
- C2 input history captures: 23/23 run/attempt/workflow/input SHA consistent, continuity verified; no old Sevastopol `25006→25008` resolution or closing of open `25100` claimed. C2 archived source snapshots are not evidence of current live active-alert status.
- C2 existing dashboard and embedded historical KPI source generation are identical. C2 has 2,857 Kyiv display intervals, casualty metadata and auxiliary files intact. **These are preserved in the C2 inputs; preservation of a *new generated* Neon JSON is not yet proven.**

## Immutable inputs

- [Scheduled C2 #43262387718](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43262387718), attempt 1, success, workflow SHA `375e69351e6a5aee1be16892821f7cdde2a8f21a`.
- C2 source `site-prod@68629fdae5534ec3a136e666bcb7d5c84dcd05aa`; Git output `site-prod@d0a7d22de2828c93236562cccc9d2e68c6a66e3d`.
- [C2 artifact #13967335571](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43262387718/artifacts/13967335571), inner ZIP SHA-256 `927343c620c1d55438823ad9203a16e986f540a816b35790d496200fe861944f`, manifest SHA-256 `5c3e2326eeb98ae6e90234183764525483e64fbc6a203b20dda8deb685d9b501`, corpus SHA-256 `a90bf403c6ac1ded943af2bf16b66a407ad9e4e67d2a365691c3704d4cde6e87`.
- Neon project `green-cake-44216048`, branch `br-bold-mode-b5rub8pq`. Actual database run `306bda37-e4e9-406f-b09b-ec20090e22c1`, `succeeded`, persisted corpus SHA equals C2.
- Superseded inventory file blob `958bc6e679a77d7145d76ab713858f2e2b335319` on PR #74 HEAD `2fe50c323171393ab2fa725010bf3d203416af6b`.

## Proof execution / limitations

A new read-only `SELECT` ran against existing Neon branch through the Neon connector. It excluded only 262 pinned superseded legacy IDs, then computed per-city canonical counts and SHA-256 over seven fields. C2 archive was downloaded from the specified GitHub artifact and independently verified. `verify_witness.py` rechecks archive SHA, inner file SHA, corpus SHA, 23 receipts and exact 23-city Neon witness hashes; its GitHub Actions run provides a non-sensitive proof JSON and SHA-256.

**The CI workflow does not itself query Neon.** Neon SQL was separately executed live and pinned as a witness in this Draft PR. This boundary matters: the accepted physical generator requires a separately approved read-only workflow/Environment SHA binding; it was not silently bypassed.

Remaining one narrowly scoped gate: run the existing, owner-approved read-only physical generator against C2 #43262387718 and compare its six candidate files (dashboard, derived, Kyiv cause, auxiliary, root KPI) with the same-run manifest/generation. Until its Action artifact and six SHA exist, final status remains `NEW_C2_NEON_JSON_PARITY=BLOCKED`.

**NO MERGE / NO SITE-PROD WRITE / NO SOURCE HTTP / NO NEON WRITER / NO NETLIFY / NO CUTOVER.**
`GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.
