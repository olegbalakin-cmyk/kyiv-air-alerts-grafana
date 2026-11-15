# Project State — current coordination snapshot

**Date:** 2026-11-15. **Historical Neon cutover `GLOBAL_CUTOVER=YES`; C6 owner-approved one-shot Neon→Git #43706909819 PASS; scheduled four-hour stabilization OPEN.** `DST_CORRECTION=OFF`; live active-alert status not certified. **English `/en/` LIVE, Netlify production locked.** Final Netlify workflow's post-deploy HTML assertion FAILED; independent public HTTP bilingual proof PASS. Browser historical data remains Git JSON.
Latest accepted transition: **UI-BILINGUAL-LIVE-LOCKED-2026-11-15-01**; latest prior C6 code pin **C6-DST-READER-PIN-MERGED-2026-11-15-01**.

## Working instructions

1. Read this root file and [CHANGELOG.md](CHANGELOG.md) before repository work. This file governs current coordination; newer accepted repository checkpoints govern older chat memory.
2. Verify the relevant immutable commits, actual Actions runs and proof artifacts before technical action. A successful research job does not prove production deployment or a release PASS.
3. Keep production, development/WIP, historical reference, backfill, casualty and Neon/persistence tracks separate. Do not overwrite another worker's commits, force-push shared branches, expose credentials or infer a production change from research.
4. Keep unresolved blockers, track status and next tasks **outside** the history markers below. Put detailed accepted checkpoints inside them, newest first; retain the latest checkpoint. Prepend brief accepted transitions inside CHANGELOG's markers. Full evidence belongs in immutable archives or proof files.
5. Aim for **5–8 KiB** here and **5–10 recent transitions** in CHANGELOG. UTF-8 byte gate: ≤12,288 PASS; 12,289–16,384 WARNING; >16,384 FAIL. Before an oversized update, run `python scripts/coordination_docs.py archive --dry-run`, then `archive` on a separate branch. See [maintenance instructions](docs/coordination-maintenance.md).
6. Never load entire historical archives, large JSON/SQL dumps or full Actions logs into Work context. Search an exact checkpoint ID and read bounded lines. Save reproducible work promptly; recover interrupted commits before new research.

## Current tracks and open release gates

- **Historical production cutover/C3:** PR #78 accepted `C6-C3-WORKS-NEON-CUTOVER-PASS-01`; owner-gated [Netlify #43496568449](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43496568449) and [Git #43497605769](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43497605769) SUCCESS, 23-city historical KPI/CSV/browser QA PASS. `GLOBAL_CUTOVER=YES` applies to historical JSON only.
- **Scheduled C2/C6:** first four-hour Neon→Git #43625014243 PASS. Next two #43655729191/#43686460909: writer PASS, reader hash blocked. PR #167 fixed pin on main. Owner-approved one-shot [#43706909819](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43706909819) SUCCESS, C2 Neon receipt, 23/23 readback, [Git-only `site-prod@048af474`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/048af474d98c953bbac351936092ee2bd08c6fad), zero Netlify. Temporary one-shot trigger removed via PR #176 (`main@63a614ca`). **Still no successful scheduled post-pin cycle; C6_STABILIZATION=OPEN**.
- **Netlify/UI:** owner-authorized bilingual `/` + `/en/` code PR #164–166; production KPI root initially blocked (19/23 legacy recomputation), PR #178 replaced it with exact same-generation Git-stored Neon 23/23 index; PR #179 fixed file staging, PR #180 restricted RUM-only HTML injection, PR #181 added guarded unlock/publish/relock. **`site-prod@901dab2f`, Netlify `6af9a134186a8e5d83bb3cdf` is LIVE and `locked=true`** (read-only Netlify readback); independent public HTML read-only Actions #43712522543 SUCCESS for both languages, `23/23` production KPI HTTP PASS. Production [#43712415014](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43712415014) overall FAILURE only on its stricter post-deploy HTML assertion; investigate this remaining QA harness discrepancy separately. **Do not claim workflow PASS.**
- **Independent open work:** full historical completeness, DST/active-alert semantics, casualty, WIP and backfill retain separate gates. `DST_CORRECTION=OFF`: three stale overlapping Neon physical parents coexist with eight exact accepted correct witnesses; no physical rows deleted. Draft [PR #182](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/182) offline exact-UID calculation selector #43712682104 PASS but NOT integrated, not 23-city physical proof, not publication. Keep automatic C2 intact.

## Concrete next tasks

1. Check 1–2 **scheduled** post-pin C2→Neon→Git cycles: 21/21 continuity, writer, 23/23 readback, Git-only publication, no Netlify. Do not mistake manual #43706909819 for scheduled proof.
2. DST: independently rebind exact 3-old/8-witness v2 selection (draft PR #182) to actual pinned reader and same-run 23-city read-only proof, then separately authorize production correction. No direct SQL edits, no premature switch.
3. UI: preserve bilingual live+locked Netlify; reconcile remaining standard post-deploy HTML QA harness failure before the next frontend release. No extra UI deploy just for documentation.
4. Mark C6 stabilization CLOSED only after repeat-cycle proof; keep casualty/backfill separate.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## UI-BILINGUAL-LIVE-LOCKED-2026-11-15-01 — physically published, independent public HTTP proof PASS, workflow post-smoke FAIL

- Owner-approved bilingual UI at `site-prod@901dab2f`. Netlify production `6af9a134186a8e5d83bb3cdf` published and read back `locked=true`; independent read-only [HTTP Actions #43712522543](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43712522543) PASS for `/`, `/en/`, exact HTML except Netlify-injected RUM and locale metadata. Production [#43712415014](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43712415014) 23-city static historical KPI and published assets PASS, **overall FAILURE at remaining stricter HTML post-smoke**; do not report production workflow green. Neon/Git data unchanged by Netlify.
- One-shot C2→Neon→Git [#43706909819](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43706909819) SUCCESS, `site-prod@048af474`; temporary trigger removed, scheduled stabilization pending. Historical DST source UTC code PR #161/#167 merged, but physical three old parents still present; `DST_CORRECTION=OFF`. Draft PR #182 offline guarded projection only. No physical correction or scheduled activation claimed.

<!-- coordination:history:end -->

## Evidence and documentation maintenance

- [Complete archive index and integrity](docs/coordination-archive/README.md): exact previous roots, original large historical blobs and dated snapshots; [machine manifest](docs/coordination-archive/manifest.json).
- [Maintenance contract and CLI](docs/coordination-maintenance.md). CI verifies byte limits, exact historical record coverage and immutable archives. Automatic archival proposes a PR only; no direct main push or auto-merge.
- **DOC-AUTO-MAINTENANCE-MERGE-02:** [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34) merged at `main@3735f359d2bfa3310cc7f9fd46f9c8f3a2af0e8f`; [Actions 41202336197](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202336197) SUCCESS on main (unit tests, byte gate, archive integrity and dry-run). Roots: PROJECT_STATE **7,990 B**, CHANGELOG **7,127 B** at merge; 10 records / 8 unique checkpoint IDs archived with hashes. Main-only PR-proposal job is now active but no over-threshold PR-creation attempt yet; bot permission remains unproven. No required status checks/rulesets; protection unchanged. CLI/patch fallback remains available. This documentation checkpoint is not a Neon release.
