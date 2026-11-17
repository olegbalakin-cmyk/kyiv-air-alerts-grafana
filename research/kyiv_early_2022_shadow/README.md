# Kyiv 24–27 February 2022 — historical start-only research (2026-11-17)

**State:** research branch only, no production/Neon publication, NO-GO for automatically including early records in existing duration statistics.

## Inputs & reproducibility
Owner-provided `alerts_2022-02-24.csv` through `alerts_2022-02-27.csv` exported from alerts.in.ua (file bytes remain owner-supplied, not re-published in this repository). Run from repository root:

```bash
python scripts/kyiv_early_2022_shadow.py \
  --csv /path/to/alerts_2022-02-24.csv \
  --csv /path/to/alerts_2022-02-25.csv \
  --csv /path/to/alerts_2022-02-26.csv \
  --csv /path/to/alerts_2022-02-27.csv \
  --existing kyiv-air-alerts-grafana/data/alerts_combined.json \
  --out /tmp/kyiv_early_2022_shadow.json
python -m unittest discover -s tests -p 'test_kyiv_early_2022_shadow.py' -v
```

The published `site-prod` file was read separately: `kyiv-air-alerts-grafana/data/alerts_combined.json`, blob SHA `b791d40c7bcf5999322648e484298db870bbda21`; first recorded official interval starts **2022-02-28 05:51:22 Europe/Kyiv**. The local first audit ran without `--existing` (thus the initial zero duplicate-candidate count is NOT a verified canonical-parity result). Do not falsely claim a comparison occurred until `--existing` is run with the full canonical dataset from the same frozen release.

## Observed from four supplied CSVs
- 24 February: 1 Kyiv start
- 25 February: 9 Kyiv starts
- 26 February: 6 Kyiv starts
- 27 February: 8 Kyiv starts
- 24 total Kyiv start records / exactly 4 day input files
- Local shadow SHA256 `37d4606d16662ba7c988d193e11f72be0ce062ca071ae947da47c7532c1b39b5`; local 4/4 offline tests PASS. This is local evidence only, not a GitHub Actions attestation.
- Exported ends are explicitly **UNVERIFIED_EXPORT_PLACEHOLDER**. They are stored for source traceability but never counted as exact elapsed time. Source caveat: https://blog.alerts.in.ua/p/data-sources
- Do not conflate `м. Київ` with `Київська область`.
- The final 27 February event has an export end on 28 February; a *start-only* record cannot be interpreted as a confirmed midnight-overlapping interval.

## Required promotion plan (separate owner decision)
1. Freeze exact `site-prod` and Neon canonical lineage and compare early starts, official Kyiv municipal, Kyiv Digital and KМDA source timestamps. For missing ends, preserve `null`, do NOT use 30-minute artificial endings.
2. Identify duplicate starts (e.g. within 3 min) but **review** rather than silently merging real consecutive alerts.
3. Implement explicit `start_only` provenance in historical storage (or a separate evidence sidecar), with nullable end, so current interval-only API/Neon schema remains valid.
4. Add a tested UI distinction: provisional observed announcements versus verified closed intervals. Counts can be displayed as *at least observed*; hours, average duration, occupation %, and forecast input must exclude unknown ends. Handle complete vs partial month/week denominators.
5. Before any Neon migration/publish: repeat same-generation 23/23 KPI parity, unchanged 2022-02-28+ event-level hashes, DST witness selection, rollback proof and C2→Git update stability. No Netlify change without separate release authority.

**Non-goals:** historical correction of all 23 cities, automatic uploads, presumed all-clears, or direct editing of site-prod JSON.
