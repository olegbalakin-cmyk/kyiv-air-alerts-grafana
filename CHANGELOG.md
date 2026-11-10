# Changelog — recent accepted transitions

Newest first; current coordination lives in [PROJECT_STATE.md](PROJECT_STATE.md). Full historical text, SHA/Actions/artifact references and exact previous roots are preserved in the [archive index](docs/coordination-archive/README.md), verified by its manifest. Maintain 5–10 brief transitions; use the [archival CLI](docs/coordination-maintenance.md) before growth exceeds 12 KiB.

<!-- coordination:history:start -->
### CASUALTY-GNEWS-RPC-PARTIAL-01 — RSS routing improved, source access blocked (2026-11-10)

- [Run #42899975187](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42899975187), PR #58 `603496cc`: offline 18/18 tests; five real WIP RSS URLs, 17 HTTP, 5 signed-RPC destinations. 3 targets rejected by strict allowlist (RSS publisher homepages espreso.tv, vinnitsa.info, zabor.zp.ua); 2 allowed Suspilne pages HTTP 403. Evidence/proposals 0, replay +0; WIP protected hashes unchanged; artifact `13801289333` ZIP SHA-256 and 9/9 manifest PASS. Further source access review offline; HTTP requires owner approval, publication OFF.
- Prior **CASUALTY-WIP-GNEWS-BLOCKED-01** [#42893729621](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42893729621): 20/20 wrapper unresolved, 40 HTTP, 0 usable; artifact `13798413457`.
- Prior **CASUALTY-EVIDENCE-CAPTURE-01** [#42873836462](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42873836462): 81/81 tests, direct-publisher Odesa +3 shadow; artifact `13789524180`.
- Prior **CASUALTY-OFFLINE-PROOF-01** [#42863730878](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42863730878): reviewer `719c93c6`, 70/70 tests, excerpt Dnipro +2/Odesa +3 shadow.

### C6-EXPORT-DIAGNOSTIC-STAGED-01 — C2 export reason staged, still BLOCKED (2026-11-10)

- First enabled [run 42817288652](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42817288652) published `site-prod@15a3f15b` and 23/23 bootstrap checkpoints; export `C2_BUNDLE_BLOCKED`, no artifact. Owner-approved [PR #54](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/54) merged `main@ee96fa78` with safe allowlisted reason output; [offline run 42829359694](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42829359694) 4/4 PASS. Await next scheduled run for actual reason and cross-cycle receipts. No manual run/cutover/DST; `GLOBAL_CUTOVER=NO`.

### C6-CAPTURE-EXPORT-OPTINS-ON-01 — owner-approved opt-ins enabled; first capture pending (2026-11-10)

- After [updater 42774323341](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42774323341) PASS (canonical writer/23-city QA/Git publication; export SKIPPED), owner separately approved two C2 opt-ins. Isolated read-only [Actions 42792678131](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42792678131) SUCCESS at `c12b2eb7`: both repository variables checked as `true`. First regular collector bootstrap/overlap **PENDING**; no manual updater, Neon readback proof, source switching or DST activation. `publication_allowed=false; GLOBAL_CUTOVER=NO`.

### C6-GATED-RECEIPTS-STAGED-01 — hooks staged OFF; offline CI PASS (2026-11-10)

- Owner-approved [PR #47](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/47) squash-merged to `site-prod@cc8bcbe577196e6484d3a5fd83b4addfabfb9456`, followed by [PR #46](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/46) to `main@2fbe9d1970c6508cbc9c1d66db55327120fe857a`. Exact-head [Actions 42686471326](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42686471326) **32/32 offline PASS**; [preflight 42774215008](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42774215008) **capture/export OFF**. Main push triggered [updater 42774323341](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42774323341), outcome to verify. PR #48 research draft, DST OFF, real 23-city full receipts 0/23; no source switching, Neon cutover or flag activation. Next: post-merge updater check, separately owner-approved flags, bootstrap/overlap and read-only same-run proof. `GLOBAL_CUTOVER=NO`.

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

### C6-LIVE-WRITER-PHYSICAL-03 — child persistence proved; current-source freshness still blocked (2026-10-31)

- [Verified closeout `0617e681`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/0617e6818f34e4a807e535b35fa4a9281d8d0e0b), raw results `ac516e8fe9f25bc6cacbfe566e28bd856ea8fbe1`; [Actions 41203425205](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41203425205) SUCCESS; artifact **13043214025**, all **10** manifest hashes independently matched.
- Protected Environment delivered the verified child-only role/URL. Original Python Phase-1 COMMIT → crash **86** → separate exact retry → independent read-only UUID/source readback PASS. **Existing canonical episode reused**; new observation/checkpoint inserted; retry inserted **0** duplicates. New UUID allocation is not proven. Original consumer builder produced one post-write Kyiv JSON witness; no full-site regeneration claim.
- Capture remains **2026-10-30T22:56:24.503909Z**; original gate rejected **STALE_SOURCE_CAPTURE** (**50,521.9 s > 21,600 s**). Persistence **PASS**, freshness **BLOCKED** pending separately authorized new observation with valid checkpoint continuation. Runtime/credential blockers resolved; **C6/C3 PARTIAL; GLOBAL_CUTOVER NO**. Existing child TTL unchanged; no creation/deletion or production/parent/site-prod/WIP/Netlify/writer changes.

### DOC-AUTO-MAINTENANCE-MERGE-02 — maintenance PR merged and main CI verified (2026-10-31)

- [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34) merged with merge commit [`3735f359d2bf`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/3735f359d2bfa3310cc7f9fd46f9c8f3a2af0e8f). [Actions 41202336197](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202336197) SUCCESS on main: tests, UTF-8 byte gate, history integrity and archival dry-run. Roots reduced from 20,212/11,614 B to 7,990/7,127 B; 10 entries representing 8 distinct checkpoints retained in hashed archives.
- CI and main-only archive-PR proposal are active; below-threshold no-op does **not** prove bot PR-creation rights. GitHub rulesets empty and required status checks disabled: CI detects but does not enforce merge/push blocking. No protection change or Neon/site-prod/WIP/Netlify action. Next optional owner action: enable required `coordination-docs / size-and-integrity` check, and verify PR creation on the next natural threshold event.

<!-- coordination:history:end -->
