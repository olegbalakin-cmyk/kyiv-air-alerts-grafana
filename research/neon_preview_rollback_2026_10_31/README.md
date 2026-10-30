# Isolated Neon preview and source rollback

**C6-PREVIEW-ROLLBACK-01: PASS within frozen research scope.**
Final [Actions run 41139538902](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41139538902),
[full preview/proof artifact 13018841540](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41139538902/artifacts/13018841540),
code commit `9c006f84d1b647d717e2ba27db0ceed5fbccd9c1`.

23/23 cities (4 exact, 19 proxy), eight city time modes, comparisons, independently
summed September historical KPIs, 45 downloaded CSV files with content checks,
four load-failure cases and config-only rollback of all 23 cities passed.
Browser response SHA-256 matches the packaged source. Zero external requests
and zero uncaught page errors. The source selection survives browser reload.
Rollback changes only `preview-config.js`; Kharkiv October alerts return from
313 candidate to 312 pinned legacy. Full evidence: `proof/machine_verdict.json`,
`proof/browser_result.json`, `proof/rollback_proof.json` and screenshots.

Production remains **NO-GO**: four physical DST cases, writer durability/fail-closed
activation/ongoing freshness, Kyiv current provenance and the production source
switch remain separate release gates. The preview is a fixed snapshot.

Candidate: `741f277f73d1dde1325069d25fa00b44a42d6f03`.
Legacy/UI reference: `0ecbb291e8f443f7ab366bc4ac033d096f2c44f4`.
Neon input cutoff: `2026-10-30T15:27:55.138400Z`.

This package uses the accepted frozen Neon-generated JSON and an in-memory DST
simulation. It does not demonstrate ongoing Neon freshness. Kyiv historical
selection, alert-cause and casualty auxiliary data, and Sevastopol metadata retain
their accepted Git dependencies. No database, production writer, operational WIP,
site-prod, or published deployment is changed.

The copied frontend reads only `data/neon/` or `data/legacy/`. The original
hardcoded production and WIP data URLs are replaced in this preview copy.
Chart.js 4.4.7 is included locally. Attack-event WIP features remain disabled by
the pinned feature configuration. Browser tests reject cross-origin requests.

The three accepted candidate JSON files remain byte-exact. The existing
historical KPI fallback is supplied from the same candidate's embedded index;
its embedded timestamp predates the finalized dashboard timestamp. Without this
source-specific fallback, the existing frontend rejects the embedded index and
loses precise historical KPI coverage. No legacy index is substituted for Neon.

## Run the saved package

Download the accepted Actions artifact, extract its `preview-package.zip` into
an empty directory, and serve that directory with Python:

```bash
python -m http.server 8765 --bind 127.0.0.1 --directory /path/to/preview
```

Open `http://127.0.0.1:8765/?preview_source=neon` for the candidate or
`?preview_source=legacy` for the pinned Git bundle. The visible preview selector
performs the same switch. A preview-only URL update preserves the selected
source across city/filter changes, shared links and reloads. Labels distinguish the candidate, DST simulation and
fixed cutoff. After the rollback rehearsal, the saved package defaults to legacy.

The config-only rehearsal removes the query override, changes only
`preview-config.js` from neon to legacy, reloads the same frontend, and checks all
23 legacy monthly/history views and an actual legacy CSV download. Data files and
frontend bytes must stay unchanged.

## Reproduce browser QA

Install `playwright==1.64.1` and use an installed official Chrome binary:

```bash
python research/neon_preview_rollback_2026_10_31/browser_qa.py \
  --preview /path/to/preview --out /path/to/browser-proof --chrome /usr/bin/google-chrome
```

`build_preview.py` packages the accepted replay output, a clean pinned site
checkout and Chart.js. `expected-package-manifest.json` and
`expected-preview-files.json` pin the complete original package. The initial
workflow at commit `cc185512aa63ea679aba7625f5e9238fb6950b12` records the one-time
assembly command from frozen inputs. Subsequent QA runs retrieve that immutable
package rather than rerunning parity. Actions artifacts expire after 30 days;
the pinned assembly source, input archive and expected hashes remain in Git.

Workspace Chromium could not start because its process socket was denied.
The cloud browser could not access workspace loopback. The connected Netlify
project is known, but the connector lacks a file-upload deployment operation and
the CLI is not signed in. Tests therefore run on an isolated authorized GitHub
Actions runner, using its loopback server. This is not an external preview deploy.

Historical KPI checks use the independently summed September 2026 daily index
for every city. Unsupported ranges may show an explicit unavailable state (—),
including the default full-history selection in the pinned frontend; this
behavior is present in both source modes. These tests do not claim all arbitrary
partial ranges have complete underlying daily coverage.
