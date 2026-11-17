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
1. Freeze exact `site-prod` and Neon canonical lineage and compare early starts, official Kyiv municipal, Kyiv Digital and KМDA source timestamps. For missing independently verified ends, preserve canonical `end=null`; retain the source-exported end in separate estimated fields, never claiming confirmation.
2. Identify duplicate starts (e.g. within 3 min) but **review** rather than silently merging real consecutive alerts.
3. Implement provisional estimated-end provenance in a sidecar with nullable confirmed end, keeping the current interval-only API/Neon schema intact.
4. Add a tested UI distinction: provisional observed announcements versus verified closed intervals. Counts can show provisional observed announcements; estimated hours and average durations must be marked approximate; verified KPI, occupation %, and forecast input exclude unknown confirmed ends. Handle complete vs partial month/week denominators.
5. Before any Neon migration/publish: repeat same-generation 23/23 KPI parity, unchanged 2022-02-28+ event-level hashes, DST witness selection, rollback proof and C2→Git update stability. No Netlify change without separate release authority.

**Non-goals:** historical correction of all 23 cities, automatic uploads, presumed all-clears, or direct editing of site-prod JSON.

## Approximate end overlay — research-only continuation 2026-11-17

The owner requested retaining all original exported end times as **approximate**, including the 19/24 durations exactly 30 minutes. The additive script `scripts/kyiv_early_2022_estimated.py` preserves the original start-only v1 audit while producing a v2 preview: each record has `estimated_end`, `estimated_duration_seconds`, `end_confidence=UNVERIFIED`, source/provenance, and *null* canonical `end`/`duration_seconds`. The v2 summary contains estimated union occupied time per Kyiv local day and isolates any spillover into 28 February. No data are promoted, no Neon or canonical Git files are mutated.

**Physical four-CSV read result:** 24 records; 24 exported approximate ends; 19 exactly 30 minutes. Event-sum = 709.7 min, calendar-day union for 24-27 Feb = 686.1 min (24 Feb: 60, 25 Feb: 255, 26 Feb: 180, 27 Feb: 191.1), and a separate 23.6 minutes into 28 Feb, explicitly excluded from verified 28 Feb data. These are provisional estimates and must never be described as exact. The local v2 shadow JSON SHA256 is `e597f12fe2fd391fb9d4c94f74ce51321850b791c96ddeef2240dfef3b3cd463`. Local 11/11 synthetic tests PASS. No GitHub Actions evidence of v2 execution is claimed.

To run, invoke `python scripts/kyiv_early_2022_estimated.py` with four `--csv /path/to/alerts_2022-02-DD.csv` arguments and a *new* `--out /tmp/kyiv_shadow_v2.json`. Optional `--existing` accepts read-only pinned canonical intervals. The local v2 run did **not** use this optional argument; zero automatic near matches therefore is not a canonical-duplicate proof.

Read-only site-prod canonical inspection found 2896 records, first `2022-02-28T05:51:22+02:00`, none with an earlier start; blob `aa098b680e7c08f4648e30866ef54d6179ebd9d3`. Before promoting any v2 result, check frozen canonical lineage, all existing dates, same-generation 23-city KPI and four-hour C2→Git stability, the UI label for approximate end estimates, and obtain separate owner GO for Neon/production. No production changes were made in this checkpoint.
