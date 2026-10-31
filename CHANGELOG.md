# Changelog — recent accepted checkpoints

Accepted coordination transitions, newest first. **This root file is intentionally small.** The complete prior changelog, with every original accepted checkpoint, remains byte-for-byte intact at [docs/coordination-archive/CHANGELOG_full_before_compaction_2026-10-30.md](docs/coordination-archive/CHANGELOG_full_before_compaction_2026-10-30.md). Historical technical detail and older judgments can be read in targeted ranges from that archive. Read the root [PROJECT_STATE.md](PROJECT_STATE.md) for the authoritative *current* coordination state.

<!-- coordination:checkpoints:start -->
## 2026-10-31

### COORDINATION-DOCS-AUTOMATION-01 — bounded roots and lossless archive automation

- Root history moved verbatim into dated snapshots with SHA-256, Git blob SHA and per-checkpoint byte ranges in [the archive index](docs/coordination-archive/index.json). The two original pre-compaction blobs remain unchanged. Nine historical records archived: five state checkpoints and four changelog transitions.
- Added UTF-8 size CI (12/16 KiB), dry-run/idempotent archival, history-preservation checks and an archive-by-PR workflow. No automatic direct push to main or automatic merge. See [procedure and permission requirements](docs/coordination-maintenance.md).
- Maintenance branch proof commit, Actions run and artifact are recorded in the PR validation; this branch does not establish activation on main. GitHub reports main unprotected and no rulesets; required checks must be configured by the owner after merge. No application, production, site-prod, operational WIP, Neon or Netlify change.

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

### C6-RECOVERED-PARITY-VERIFICATION-02 — frozen replay reproduced; difference causes verified

- Physically executed pinned offline replay: **31,935 → 31,939** rows after DST simulation, **23 cities**, original reports byte-identical. First saved replay checkpoint `9ea0693fa5b8d24959d88c1ba55981d059c5fc23`; final verified research commit [`741f277f`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/741f277f73d1dde1325069d25fa00b44a42d6f03). Direct 22-city differences **0 without / 366 with DST projection**.
- Corrected accounting of **1,354** exact JSON paths: **847 DST + 457 legacy derived omission of accepted C4-KH-06 + 49 cutoff timestamps + 1 research marker; unexplained 0**. Single-interval Kharkiv counterfactual reproduces published derived fields exactly. Minimal loader correction passes isolated real-loader regression checks; candidate already uses the accepted long interval. No deployed generator or Neon modification.
- All seven DST proposal tuples match pinned source events. Four physical DST cases remain open. Reproducible harness, complete classified diff, tests, patch, source witnesses and hashes saved under `research/neon_cutover_work_2026_10_30/`; candidate ready for bounded research preview with DST simulation. Fresh database/primary receipt, complete upstream CSV, browser/CSV, freshness and switch/rollback are outside this proof. **C6/C3 PARTIAL; GLOBAL_CUTOVER=NO**. Next: authorized preview consumer and rollback rehearsal.

<!-- coordination:checkpoints:end -->

## Maintenance policy

Update current state and prepend a bounded accepted transition after each state-changing checkpoint. Keep 5–10 recent transitions here; save full proofs in archives/artifacts. PASS ≤12,288 UTF-8 bytes; WARNING ≤16,384; FAIL above 16,384. Run `python scripts/coordination_docs.py archive --dry-run`, then `archive` on a branch. [Maintenance procedure](docs/coordination-maintenance.md). Never treat exploratory runs as accepted production evidence.
