# Changelog — recent accepted transitions

Newest first; current coordination lives in [PROJECT_STATE.md](PROJECT_STATE.md). Full historical text, SHA/Actions/artifact references and exact previous roots are preserved in the [archive index](docs/coordination-archive/README.md), verified by its manifest. Maintain 5–10 brief transitions; use the [archival CLI](docs/coordination-maintenance.md) before growth exceeds 12 KiB.

<!-- coordination:history:start -->
### C6-DST-PROJECTION-01 — offline correction ready for review; cutover NO (2026-11-09)

- Research-only proposal: explicit v1 historical calculation correction in the existing generator; three excluded projected UUIDs, seven accepted source intervals, +4 episodes / -9,059,359,958 microseconds. Physical Neon rows unchanged; no schema migration. Exact corpus/evidence/schema drift stops generation. 17 targeted tests PASS, including Kyiv 2,819 unchanged, casualty/auxiliary/CSV contract and exact rollback. UTC union regression fix prepared separately from production.
- [Implementation and proofs](research/c6_dst_projection_2026_11_09/README.md). Reused `9ba2c04c`, `7265e40a`, `741f277f`, run 42487688608 and PR #45 `3e08daf4`; no repeat physical proof, SQL, source HTTP, deployment or changes to PR #42/#44/#45. Publication false; `GLOBAL_CUTOVER=NO`. Pending review; main acceptance unchanged.

### C6-UA-CURRENT-ONEGET-01 — current API access PASS; active semantics OPEN (2026-10-31)

- Owner-authorized one GET `/api/v3/alerts`: HTTP 200, 72 rows, 9/21 mapped IDs directly present with AIR, 12 absent but UNKNOWN. [Actions 41219158954](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41219158954) SUCCESS; [proof d6a6340f](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/d6a6340f8941799d873f02a9bce27881bce81a01), encrypted artifact **13049271828**, 5/5 hashes verified. History 21/21 separately proven by existing production client.
- No status-negative/ancestor/cache completeness certification, Neon writes or production mutations; **C6/C3 PARTIAL; GLOBAL_CUTOVER NO**. Next: offline interpretation of official contract, no further API GET authorized.

### C6-23CITY-CONTINUITY-02 — bounded Kyiv repetition PASS; 23-city publication still BLOCKED (2026-10-31)

- [Closeout f5bbd5a4](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/f5bbd5a4d51fea66283cb4202d1bcf8dacb11939/research/neon_23city_continuity_2026_10_31/ACCEPTANCE.md); [Actions 41208139352](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41208139352) SUCCESS, artifact **13046430297**, all **85** hashes independently verified. Two rounds / **5 upstream GET attempts** / **27m31s**, same authorized child and protected Environment. Kyiv HTTP → C2/C3 → separate read-only readback PASS, stable UUID pair, seq **2 → 3 → 4**, zero duplicates. Both 23-city JSON candidates generated; two fresh persisted captures **1/23**, complete current/active certification **0/23**.
- UkraineAlarm Swagger HTTP 403 stopped the provider before its 21 history/active calls; data endpoint availability untested. Sevastopol: first page 0 completed pairs, second GET timeout. **PUBLICATION_BLOCKED**, no retry/redirect/fallback/publish/scheduler. Full evidence archive `9704d5fa` ([preservation Actions 41210485947](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41210485947)); independently reproduced archive hash/Git blob. Current-status/cache, separate DST/Kyiv and operational preflight gates remain; C6/C3 PARTIAL; GLOBAL_CUTOVER NO. No production or operational track changes.

### C6-23CITY-PUBLICATION-01 — full persisted-data generation PASS, current publication BLOCKED (2026-10-31)

- [Implementation 37a87029](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/37a8702972c7b875f60aa73e3b0b890b869ab73b), [proof bdb08b14](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/bdb08b148b07f3bc6030adda09a071400ba30c9b); [Actions 41206457252](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41206457252) SUCCESS, artifact **13044522236**. Independently verified all 37 hashes and Git proof bytes. Existing child read twice: **31,977 AIR parents, 23 cities, 145 observations**; identical content fingerprints. Four generated JSON + two pinned Git auxiliaries; UUID/proxy/timezone preserved; no DST simulation or rebind.
- **PUBLICATION_BLOCKED**: one accepted Kyiv capture only; Lviv historical, other 21 without current source receipts. Continuity, active status, source contracts, recurring writer and separate release dependencies remain OPEN. Source/commit/generation clocks distinct; no silent Git fallback or publish directory. No source HTTP, Neon writes or production changes. **C6/C3 PARTIAL; GLOBAL_CUTOVER NO.** Next owner decision: bounded isolated two-round 23-city source-continuity run; proposed 60 GETs / 70 minutes, no enabled capture or scheduler.

### C6-LIVE-FRESHNESS-04 — new physical poll / episode UUID / bounded freshness PASS (2026-10-31)

- Owner-authorized single HTTP GET; [Actions 41204874911](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41204874911) SUCCESS, [research 1cf607b3](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/1cf607b3ca00568f416fa5fc8a087ff53f4b9190), artifact **13044202361**. New source HTTP 200, 918,908 bytes, original old capture unchanged.
- On existing isolated child, Phase-1 inserted **new episode UUID** `478ea32b-e567-4f8d-a11a-b822648c41ee`, new source observation and correct chained poll checkpoint **seq 2**. Independent direct Neon readback; original freshness gate PASS, single-episode JSON PASS.
- **Bounded only:** `continuity_verified=false`, no full 23-city generator, upstream cache certification, recurring writer, active-status or production cutover. **C6/C3 PARTIAL; GLOBAL_CUTOVER NO**, no production changes.

<!-- coordination:history:end -->
