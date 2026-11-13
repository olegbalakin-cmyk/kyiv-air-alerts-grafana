# Project State — coordination snapshot

**2026-11-13: ADMIN_FREEZE_VERIFIED=YES (12:22:49 UTC). Latest accepted: C6-C3-ADMIN-FREEZE-VERIFIED-01. Preparation only; merge/release NOT authorized. ROLLBACK_OPERATIONAL_READY=YES (Work P tested); CUTOVER_READY=NO; GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF.**

Read main documentation first; PR #78 newer accepted checkpoints govern. Keep production, Neon, casualty and DST separate.

## Current gates

- **C2:** #43321997695 attempt 1: update-site SUCCESS, Neon 33,315 (+48), 23/23 capture receipts; dependent C6 failed pre-run. No repeat C2.
- **Work L:** [#43390770985](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43390770985), artifact #14020616892, 6/6 JSON and 23/23 historical freshness PASS; read-only, no publication.
- **Work M:** [prepare-only #43403595621](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43403595621) SUCCESS at exact PR #116 `9d846279b91b44b324a722ca00276a99956b4fca`. FINAL artifact #14025629654 SHA-256 `f2252da0014ce4ed28d5d52a7164e077b8fcd8c99380dd752ee0650412b051ed`. Independently downloaded: 8/8 final members, 6/6 parseable JSON and hashes, six source hashes matched original Work L; binding/manifest/report hashes PASS. Prepare report #14025729121 independently SHA-256 checked. No publisher/C2/Netlify job ran.
- **Work N:** Draft PR #119 exact `6f8502e043b5c57d4e44db4b435d9a885a1abe79`, [offline #43407785056](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43407785056) SUCCESS: publisher 20/20, physical C2→Work L→Work M ZIP/source SHA, and refreshed `site-prod@f0cfcbc8` Git-only 23-city rollback, 18 entries, eight no-loss cases. Artifact #14028565807 SHA `e2914fac206e0ec2d7c2d5ff466703126cd47d5c9023490a71c9ae816d9a727a`. Publisher code offline-ready; subsequent Work P physical Netlify restore PASS supersedes earlier recovery blocker. Fresh no-loss recapture still required immediately before cutover. `ROLLBACK_OFFLINE_READY=YES; CUTOVER_READY=NO`.

- **Work O / Netlify:** #43411738247 SUCCESS, hosted alias `6af6eac51390a92065e9164f` ready; 13/13 HTTP, 23/23 cities, 184/184 browser views, 23 CSV PASS, JS errors 0. Original Netlify production unchanged before Work P. Full evidence in accepted Work O checkpoint below.

- **Work P / operational Netlify rollback:** Owner-authorized one temporary production publication of Work O alias `6af6eac51390a92065e9164f`, followed by real restoration of original `6adb629bc3ebc570117d82e1`. Netlify API independently shows candidate `published_at=2026-11-13T11:22:01Z` and original `published_at=2026-11-13T11:23:02Z`; original now current/ready. Git `site-prod@f0cfcbc862ca3dbf1b853e72de07ffcf6042856f` unchanged. Owner Work P receipt reports identical rendered UI before/during/after, 23 cities, casualties present, and Netlify Auto publishing restored ON. Work P did not perform a fresh CDN byte-hash audit; inherited Work N/O historical per-file checks. `ROLLBACK_OPERATIONAL_READY=YES` for the tested configuration only; fresh cutover-time data/auto-publish locks, release-code promotion and distinct production release approval remain OPEN.

## Next

Administrative freeze is verified and must remain in place: `C6_GIT_ONLY_PUBLISHER_PAUSED=true`, `Deploy Netlify production site` disabled, Netlify published deploy locked. Next: obtain separate owner approval for PR #119/#120 merges while keeping all three guards. No merge or publication is authorized by this checkpoint. A later distinct release GO requires refreshed C2/casualty/aux, historical freshness and rollback hashes; Netlify-first static KPI proof precedes Git JSON publication. No new C2/writer run is authorized. Restore only the settings changed in this freeze, using the order below; do not enable a workflow or unpause a publisher as routine cleanup.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## C6-C3-ADMIN-FREEZE-VERIFIED-01 — administrative pre-merge freeze verified (2026-11-13)

- Authorized Cloud Browser verification completed at **2026-11-13 12:22:49 UTC (14:22:49 Kyiv)**. Initial → final: repository `C6_GIT_ONLY_PUBLISHER_PAUSED` **true → true**, already persisted (last update 09:31 UTC), confirmed after reload and on its value form; GitHub [`Deploy Netlify production site`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/workflows/netlify-production.yml) **manually disabled → manually disabled**, banner `This workflow was disabled manually.` and `Enable workflow` control observed; no enable/disable cycle performed. Netlify **Auto publishing ON → OFF/locked**, using `Lock to stop auto publishing` → `Lock published deploy`, verified after reload. Exact [production deployment](https://app.netlify.com/projects/ukraine-air-alerts/deploys/6adb629bc3ebc570117d82e1) remains `6adb629bc3ebc570117d82e1`, visibly `Published & locked deploy` / `Publishing is locked to this deploy.`
- GitHub all-workflow filters `is:in_progress`, `is:queued`, `is:waiting`, `is:pending`, `is:requested` each returned **0 runs**; final in-progress recheck 0. Netlify production activity shows the same currently published deployment and completed older deployments; recent deploy list contains completed entries, no active competitor observed. No jobs cancelled. Other workflows, casualty monitoring and WIP settings untouched. No merge #119/#120, Git JSON publication, C2, Neon writer, Netlify deployment/publication or cutover.
- **Restoration order (later, after owner ends the freeze; not executed):** (1) leave the two original GitHub settings unchanged (`true` and manually disabled); check no active/queued publisher or unapproved newer deploy would publish; (2) on the approved currently published Netlify deployment, use `Unlock to start auto publishing` and confirm the unlock to restore original ON; (3) verify Auto publishing ON and the intended production pointer, with both GitHub guards still unchanged. If a newer unapproved deploy is present, stop before unlock. Enabling the production workflow or setting the pause to false would exceed restoration and needs distinct release authorization.
- Scope: `ADMIN_FREEZE_VERIFIED=YES; CUTOVER_READY=NO; GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`. Previous technical proofs reused; no repeated data audit. Older root history was byte-exactly archived using the existing CLI before this update; no historical checkpoint rewritten.

## C6-C3-PREMERGE-GUARDS-UNVERIFIED-01 — read-only release preparation, administrative freeze pending (2026-11-13)

- Owner authorized preparation, **not merges/publishing**. GitHub verified `main@712c9e351fc3548325cf594cf0617bb33e70a002` protected, `site-prod@f0cfcbc862ca3dbf1b853e72de07ffcf6042856f`; Draft PR #119 `6f8502e0` and #120 `ac32540f` open/mergeable. Exact-head offline Actions #43407785056 (Work N) and #43422122898 (Work R) SUCCESS; immutable Work M #14025629654 and Work N rollback #14028565807 artifacts not expired. No site-prod drift against Work N baseline. Netlify production still `6adb629bc3ebc570117d82e1` ready, Work O `6af6eac51390a92065e9164f` ready; Work P restore previously proven.
- **Pre-merge hazard:** PR #119 updates `update-netlify-site.yml` which triggers normal C2 on main push unless `C6_GIT_ONLY_PUBLISHER_PAUSED=true`. PR #120 updates `netlify-production.yml` which triggers a GitHub Actions `--prod` deploy on site-prod push, even if Netlify Auto publishing is OFF. Current admin switches/permissions cannot be independently read or changed using connected tools. **ADMIN_FREEZE_VERIFIED=NO; NO MERGES**. Work P receipt says Auto publishing restored ON. Release publisher requires Netlify-first static SHA/proof before one-shot Git JSON write. No source HTTP, C2, Neon writer, publication, merge or cutover in this preparation. `ROLLBACK_OPERATIONAL_READY=YES` tested configuration; `CUTOVER_READY=NO; GLOBAL_CUTOVER=NO`.


<!-- coordination:history:end -->

## Evidence and documentation maintenance

- [Archive index](docs/coordination-archive/README.md), [manifest](docs/coordination-archive/manifest.json), and [maintenance CLI](docs/coordination-maintenance.md) retain historical proofs; archive via a PR, no direct main push.
- **DOC-AUTO-MAINTENANCE-MERGE-02:** [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34) merged `main@3735f359`; [Actions #41202336197](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202336197) PASS. Ten archived records indexed above. Bot archival PR permission unverified; not a Neon release.
