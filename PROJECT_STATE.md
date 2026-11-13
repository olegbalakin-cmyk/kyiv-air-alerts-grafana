# Project State — coordination snapshot

**2026-11-13. Latest accepted: C6-C3-WORKS-NEON-CUTOVER-PASS-01. CUTOVER_RESULT=PASS; GLOBAL_CUTOVER=YES; ADMIN_FREEZE_VERIFIED=YES; DST_CORRECTION=OFF.**

Read main documentation first; newer accepted PR #78 checkpoints govern. Historical records below remain verbatim; root byte gate ≤12,288 B PASS.

## Current production

- One owner-approved historical Neon cutover completed before the deadline. Main `1dbacef11367b97805c43be112cfeb2c23c12072`; site-prod `54079326ae2b4e691e2bfcf7cd1a51c9705404eb` (parent `99648321e64037a6dcf3ae0072d66eedcccc2839`). Netlify production `6af76b2d67c5074986728b62`, ready/locked. Generation `2026-11-13T10:08:11.334497+02:00`; all six FINAL JSON verified through Git and live HTTP.
- Netlify run [43496568449](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43496568449) SUCCESS, independently verified at 19:55:58Z; one temporary unlock, then approved deployment relocked before separate Git grant. Git run [43497605769](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43497605769) SUCCESS, owner-reviewed environment; publication at 20:03:12Z. Freshness 23/23 and 60 data/rollback identities passed before release; no bypass.
- Production QA PASS: 23 cities × 8 modes, 23 CSV/644 rows, rendered graphs/Kyiv causes/casualty, site JS errors 0. All 2,858 Kyiv source interval tuples, 12 casualty blobs and two audit auxiliaries preserved. Rollback not needed. [Full execution receipt](docs/work-s-final-execution-2026-11-13.json) retains the earlier stopped attempt.
- Final safe state: Auto publishing OFF, independent `locked=true`; both production workflows disabled manually; pause=true; both owner grants, 13 temporary repository variables and Git release flag removed. Protected environment retained empty. No new C2/writer/source HTTP, proof rerun, merge, DST or casualty/WIP change.

## Next

Keep the approved freeze. Do not resume automatic Git-only C2. This checkpoint certifies the completed historical snapshot cutover; recurring delivery and live alert status are not certified. Any later publication requires fresh applicable gates and owner scope.

## Latest accepted checkpoints

<!-- coordination:history:start -->
## C6-C3-WORKS-NEON-CUTOVER-PASS-01 — controlled historical Neon cutover (2026-11-13)

- Separate owner production GO and one temporary unlock/relock approval executed. Netlify `6af76b2d67c5074986728b62` independently verified before Git publication `54079326ae2b4e691e2bfcf7cd1a51c9705404eb`; Actions #43496568449/#43497605769 SUCCESS. Freshness 23/23, data/rollback hashes, production QA and final administrative freeze PASS. Both grants/temporary flags removed; rollback not needed. `CUTOVER_RESULT=PASS; GLOBAL_CUTOVER=YES`. [Receipt](docs/work-s-final-execution-2026-11-13.json).

## C6-C3-WORKT-MERGE123-DISPATCH-REGISTERED-01 — approved PR #123 merge (2026-11-13)

- Screenshots: publisher pause=true, both workflows Disabled manually; Netlify API locked/ready on `6adb629bc3ebc570117d82e1`. PR #123 `eeaca9f3`, two exact-head CI PASS, one workflow file matching site-prod. Squash-merged `main@1dbacef11367b97805c43be112cfeb2c23c12072`. Job remains site-prod-only, default-OFF; no publisher or cutover. `GLOBAL_CUTOVER=NO`.


## C6-C3-WORKS-DISPATCH-DEFAULT-BRANCH-BLOCK-01 — manual dispatch blocked (2026-11-13)

- `main@d68e35e3` lacks `.github/workflows/netlify-production.yml` (404); `site-prod@99648321` contains `workflow_dispatch`. [GitHub docs](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch) require a default-branch file. Small separate approved PR and new main SHA pins required before retry. No production action; `GLOBAL_CUTOVER=NO`.


## C6-C3-WORKS-OWNER-GATES-NOGO-01 — release bytes/freshness/rollback PASS; production gates not installed (2026-11-13)

- Read-only Work S confirms `main@d68e35e35c8d50954a77adf99a7dda668724734b`, `site-prod@99648321e64037a6dcf3ae0072d66eedcccc2839`; merged N/R code equals exact previously passing research code. C2 exact failure-before-runner identity unchanged; Work L/M SUCCESS and pinned artifacts unexpired. FINAL #14025629654 physical ZIP SHA `f2252da0014ce4ed28d5d52a7164e077b8fcd8c99380dd752ee0650412b051ed`; six final SHA, 23 cities, generation `2026-11-13T10:08:11.334497+02:00` verified.
- Current Work N #14028565807 is still byte-compatible after code-only #120: five runtime JSON, 12 casualty blobs, audit auxiliaries and frontend unchanged; all 18 backup member hashes pass. Embedded casualty preserved, Kyiv 2,858→2,858 intervals, auxiliary bytes equal. Existing Work P production restoration remains valid for this tested configuration; no retest/new snapshot needed. `ROLLBACK_READY=YES` at pinned state; refresh/reconcile if later data changes.
- Current-clock Work L publication gate PASS 23/23. First expiry **2026-11-14T10:40:40.888431Z (12:40:40 Kyiv)**, oldest Kyiv source receipt. No current-alert certification. Browser verified pause=true, both production workflows manually disabled and Netlify locked; active/queued/waiting/pending/requested all 0. Netlify current `6adb629bc3ebc570117d82e1` ready, no deployment/publication.
- Execution remains blocked: protected `c6-neon-git-release` environment absent; new independent Netlify/Git production grants and required release variables absent. Owner admin/Actions policy and publisher contents:write/actions:read are available; NETLIFY_AUTH_TOKEN name exists, no token value/scope test. Minimal unblock: distinct production GO authorizing the exact temporary gate setup and one Netlify-first→Git release sequence before freshness expiry. No new data/code research required at unchanged refs. [Exact procedure](docs/work-s-release-2026-11-13.md), [machine receipt/templates](docs/work-s-release-2026-11-13.json).
- `FINAL_RELEASE_PREFLIGHT=FAIL; CUTOVER_READY=NO; ROLLBACK_READY=YES; ADMIN_FREEZE_VERIFIED=YES; GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`. No C2/writer/source HTTP, Git JSON publication, Netlify deployment/unlock, workflow enable, merge or casualty/WIP change. Only coordination documentation updated; production GO not granted.

## C6-C3-MERGE119-120-FREEZE-PASS-01 — both approved code merges, guards retained, production unchanged (2026-11-13)

- Owner requested resumption of the same conditional merge task. Fresh Cloud Browser preflight positively confirmed `C6_GIT_ONLY_PUBLISHER_PAUSED=true`, GitHub `Deploy Netlify production site` manually disabled, and Netlify `Published & locked deploy` / `Publishing is locked to this deploy.` for `6adb629bc3ebc570117d82e1`. All GitHub in-progress/queued/waiting/pending/requested queries 0; Netlify deploy list showed completed entries only. Previous unconfirmed-lock hold is superseded by this fresh positive observation; no unlock or settings change was needed. #119 remained merged; #120 exact HEAD `ac32540fcb0074afaed20ec9f6849b32777dc9c7` unchanged, mergeable, UI checks PASS and [Work R #43422122898](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43422122898) still SUCCESS on that exact SHA.
- **MERGE_119=YES:** earlier authorized Cloud Browser squash merge at 12:43:55Z, source HEAD `6f8502e043b5c57d4e44db4b435d9a885a1abe79`, exact main/merge SHA **`d68e35e35c8d50954a77adf99a7dda668724734b`**. Not repeated. **MERGE_120=YES:** marked ready and squash-merged via Cloud Browser at **14:38:55Z**, exact site-prod/merge SHA **`99648321e64037a6dcf3ae0072d66eedcccc2839`**. GitHub merged=true and branch SHA readbacks agree; both proof branches retained.
- Post-merge #120 SHA has **0 Actions runs**, so automatic Netlify production workflow did not start. #119 SHA has Coordination docs #43427654796 SUCCESS and two later unrelated WIP canary/monitor runs SKIPPED; no C2, writer or Git publisher run. Final all-five active/queued status queries 0. Fresh Netlify latest-five readback: newest deploy remains Work O `6af6eac51390a92065e9164f`, created 10:47:33Z; all ready, `hasActiveDeploys=false`; **no new deployment**. Independent project read current production **`6adb629bc3ebc570117d82e1`, ready**.
- Final Cloud Browser verification at **14:39:50Z (16:39:50 Kyiv)** after reloading all guard pages: persisted pause=true; workflow `This workflow was disabled manually.`; Netlify `Published & locked deploy` on the exact original production ID. **`ADMIN_FREEZE_VERIFIED=YES; PRODUCTION_UNCHANGED=YES`**. No JSON publication, C2, Neon writer, Netlify deployment/publish/unlock, unrelated workflow/settings changes or cutover. This is code promotion only: `CUTOVER_READY=NO; GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`. Distinct production owner GO and refreshed release-time no-loss/freshness proof remain required.

## C6-C3-MERGE119-PASS-MERGE120-HOLD-01 — first approved merge completed; second stopped on unconfirmed guard (2026-11-13)

- Owner explicitly authorized #119→main, then #120→site-prod only while all three administrative guards are reconfirmed. Before #119: Cloud Browser verified persisted `C6_GIT_ONLY_PUBLISHER_PAUSED=true`, Netlify production workflow `This workflow was disabled manually.`, and exact Netlify production `6adb629bc3ebc570117d82e1` visibly published/locked. Netlify recent deploy list showed completed entries only; GitHub all in-progress/queued/waiting/pending/requested runs 0. Both PR exact HEADs unchanged: #119 `6f8502e043b5c57d4e44db4b435d9a885a1abe79`, #120 `ac32540fcb0074afaed20ec9f6849b32777dc9c7`. Exact-head Work N #43407785056 and Work R #43422122898 SUCCESS; #119 PR checks also PASS, #120 UI 1 successful check. Work N artifact #14028565807 still unexpired with SHA `e2914fac206e0ec2d7c2d5ff466703126cd47d5c9023490a71c9ae816d9a727a`.
- Cloud Browser marked #119 ready and **squash-merged once** at **2026-11-13T12:43:55Z**. `MERGE_119=YES`; exact resulting main/merge SHA **`d68e35e35c8d50954a77adf99a7dda668724734b`**. GitHub UI success banner and API merged=true agree. Only post-merge run on this SHA: [Coordination docs #43427654796](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43427654796) SUCCESS. No C2, Neon writer or Git publisher run created. All five active/queued status queries again returned 0 at final readback.
- Before #120, GitHub pause=true and production workflow manually disabled reconfirmed after reload. The Netlify heading visibility probe immediately following reload returned **false**; this establishes **unconfirmed lock**, not evidence of an actual unlock. The subsequent task-relevant wait/verification call was rejected by automatic approval review with the reason that proceeding after an unconfirmed guard violates the owner's explicit stop condition. **Stopped; no further Netlify lock verification or second merge attempted.** `MERGE_120=NO`; actual merge SHA=null; PR #120 remains Draft, exact HEAD unchanged. Final `site-prod@f0cfcbc862ca3dbf1b853e72de07ffcf6042856f` unchanged. No protection/workflow settings changed; no branches deleted.
- Independent final read-only Netlify project read: current deploy **`6adb629bc3ebc570117d82e1`**, state **ready**. `PRODUCTION_UNCHANGED=YES`. No Git JSON publication, C2/writer, Netlify deploy/publish/unlock or cutover. Current combined guard verdict **`ADMIN_FREEZE_VERIFIED=NO`** pending a newly approved read-only preflight; prior before-merge verified observations retained above. No claim that Auto publishing actually changed. `CUTOVER_READY=NO; GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

<!-- coordination:history:end -->

## Evidence and documentation maintenance

- [Archive index](docs/coordination-archive/README.md), [manifest](docs/coordination-archive/manifest.json), and [maintenance CLI](docs/coordination-maintenance.md) retain historical proofs; archive via a PR, no direct main push.
- **DOC-AUTO-MAINTENANCE-MERGE-02:** [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34) merged `main@3735f359`; [Actions #41202336197](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202336197) PASS. Ten archived records indexed above. Bot archival PR permission unverified; not a Neon release.

