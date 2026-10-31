# Changelog — recent accepted transitions

Newest first; current coordination lives in [PROJECT_STATE.md](PROJECT_STATE.md). Full historical text, SHA/Actions/artifact references and exact previous roots are preserved in the [archive index](docs/coordination-archive/README.md), verified by its manifest. Maintain 5–10 brief transitions; use the [archival CLI](docs/coordination-maintenance.md) before growth exceeds 12 KiB.

<!-- coordination:history:start -->
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

### DOC-AUTO-MAINTENANCE-01 — lossless archival and CI proposed (2026-10-31)

- Separate maintenance branch adds UTF-8 byte limits (12 KiB warning / 16 KiB fail), deterministic archival with dry-run/idempotency, immutable hash manifest and historical-record coverage tests. Original root snapshots and both pre-compaction Git blobs remain exact.
- Main-only automation proposes a docs-only PR above 12 KiB; it never pushes main or merges. Runtime permission denial leaves an explicit CLI/patch fallback. Main has no required checks; no protection settings changed. Workflow activation requires merge. No migration or production result is asserted.
- Implementation `f683980230282c0696717d8d9b43438482300b15`: [Actions 41202012561](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202012561) SUCCESS, artifact **13042892819**; 17/17 tests, byte limits, archive integrity and no-op replay PASS. [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34). Concurrent accepted main `5f64048c2b8de40c336c75b263941598a606a3bf` is preserved in full snapshots and reflected in current state; integration receives its own CI run.

### C6-LIVE-WRITER-PHYSICAL-02 — one isolated child verified; physical execution blocked

- Research proof commit [`e9226f3bd92b9341cc6910772034b10612012088`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/e9226f3bd92b9341cc6910772034b10612012088) saved/verified as a non-force fast-forward from `0f0d7181e04cb053b773fb5c0ecf284bb82bc66a`.
- Created exactly one child **`br-crimson-star-b59u7ge3`** from authorized shadow parent **`br-bold-mode-b5rub8pq`**. Separate branch/compute/connection-host reads verify isolation; inventory **9/10→10/10**. TTL **2026-11-01T12:20:00Z**; no manual deletion.
- Local Python cannot resolve Neon (`gaierror [Errno -3]`); psycopg missing. Child-targeted URL obtained privately, child-only role scope not attested; no exposed secure Actions credential-injection operation. Existing Actions child-secret availability UNKNOWN. **No SQL or writer invocation**; COMMIT/crash/retry/physical UUID/readback/JSON remain NOT EXECUTED.
- Frozen HTTP/canonical hash verification PASS. Unchanged gate rejects real saved capture **STALE_SOURCE_CAPTURE**, age **48,881.8 s** versus **21,600 s**. No recapture or synthetic retest; this is bounded stale-input rejection only.
- Accepted bounded blocker: `BLOCKED_RUNTIME_AND_STALE_SOURCE`; **production preflight ready NO**, **C6/C3 PARTIAL; GLOBAL_CUTOVER NO**. No production Neon, site-prod, operational WIP or Netlify changes. Next: reuse this child with a network-capable runner and verified scoped credentials; retain original timestamp and obtain separate authority for current-source freshness evidence.


### NEON-BRANCH-SLOT-FREED-01 — capacity recovered (coordination-only)

- Owner deleted obsolete historical Neon leaf `br-cold-sky-b5jhai9p`; independently checked Neon project `green-cake-44216048`: **9/10** existing branches, deleted ID absent. Quota blocker removed, but **no child created or writer run** by this verification.
- Next: execute saved `isolated_writer.py` on a new disposable child of `br-bold-mode-b5rub8pq` in an authorized runner with independently verified child-scoped credentials; require crash-after-COMMIT, retry, UUID/readback, freshness and fail-closed evidence. **Production remains NO-GO**; no production or Neon writes during this checkpoint.


### C6-LIVE-WRITER-FRESHNESS-01 — bounded live HTTP identity accepted, writer blocked at 10/10 branches

- Independently checked [Actions 41141326530](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41141326530) SUCCESS with artifact **13018209142**: genuine Kyiv Digital HTTP 200, 917,331 raw entity bytes and a prospective canonical source identity; 15/15 **synthetic** freshness/fail-closed tests PASS. No physical Neon UUID.
- Follow-on [Actions 41196606039](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41196606039) SUCCESS; original HTTP proof now saved in research commit `0f0d7181e04cb053b773fb5c0ecf284bb82bc66a`, backup artifact **13040277727**. Machine verdict `PARTIAL_HTTP_IDENTITY_ONLY`.
- Neon project `green-cake-44216048` independently shows Free **10/10** non-deleted branches (4 ready, 6 archived), consistent with reported isolated create `HTTP 422 branches limit exceeded`. **No child created, no SQL write, no independent UUID/readback or new rendered JSON.** `C6/C3=PARTIAL`, `GLOBAL_CUTOVER=NO`.
- Next owner decision: authorize deleting one verified obsolete isolated leaf, or raise branch limit; then execute the saved physical isolated writer/freshness gate. No production or Neon mutations in this docs-only checkpoint.


### C6-PREVIEW-ROLLBACK-01 — 23-city frozen browser package and source-only rollback accepted

- [Actions 41139538902](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41139538902) **SUCCESS**, tested source `9c006f84d1b647d717e2ba27db0ceed5fbccd9c1`, [proof commit `66f87241`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/66f872413f67668c9bd23b94cff17520fea705f9), artifact **13018841540**. Authorized runner-local Chrome: **23 cities (4 exact / 19 proxy), eight city modes, comparisons, September historical KPI control, derived charts/table, 45 downloaded CSV content checks and four visible HTTP/JSON failure cases PASS**; browser response digests match candidate, 0 cross-origin requests and 0 uncaught page errors.
- Preview-only switch survives URL updates/reload. Source-only rollback changes **only preview-config.js**, restores all **23 legacy** monthly/history views and a real legacy CSV; frontend/data hashes unchanged. Kharkiv October witness **313 → 312 alerts**. Accepted candidate JSON bytes unchanged; same-source historical fallback and Git auxiliaries documented.
- Candidate visibly marked **RESEARCH / NEON CANDIDATE / DST SIMULATION**, cutoff **2026-10-30T15:27:55.138400Z**, no ongoing-freshness claim. Complete downloadable preview/proofs plus screenshots retained. No external Netlify deployment: connector lacks upload/deploy and CLI lacks authorization; local browser execution completed on the authorized Actions runner.
- **C6/C3 PARTIAL; GLOBAL_CUTOVER=NO.** Four physical DST cases, live writer/fail-closed/ongoing freshness, Kyiv current provenance and production switch/operational rollback remain separate gates. No Neon, writer, site-prod, operational WIP or production Netlify changes. Next: close those gates; frozen parity/browser/CSV/preview rollback need no new general audit.

<!-- coordination:history:end -->
