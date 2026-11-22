# October 2026 casualty evidence: offline incident/baseline reconciliation

Checkpoint: `CASUALTY-OCT2026-13-INCIDENT-REVIEW-OFFLINE-PASS-2026-11-22-01`

**Outcome: PARTIAL EVIDENCE, 0 CONFIRMED FOR PUBLICATION.** This is not an October 23-city casualty series. No publisher GET, promotion, casualty credits, WIP, Neon, site-prod, or Netlify changes occurred in this offline work.

## Immutable physical input and published baseline

- Exact prior one-shot [run #45070256716](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/45070256716) SUCCESS, approved owner grant spent once, 27 attempts (21 HTTP200, five HTTP403, one blocked HTTP301). [Artifact #14773425588](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/45070256716/artifacts/14773425588): ZIP SHA256 `f2a95945e98dc92cdc49529be2bb127a5d4c3fe8a9e71ad82ebf2437b7c2eb9f`, `capture_report.json` SHA256 `be053f77ade09db833eb976a67a6bcb036fb42cff1c98f81bfd90dde1fbe7ed8`. All hash checks PASS independently. **Short excerpts only**, not complete HTML. The original source URLs are in `approved_sources_manifest.json`.
- Latest read-only [`site-prod`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/tree/site-prod) at `175c4254f11084005523e423e98a307da98c0fe9`. For 20 cities, `kyiv-air-alerts-grafana/data/casualties/master_20cities_monthly_wide.csv` (Git blob `f3b7fdf6750e12d7b9af05ffd094bb47aa9ed801`); Kherson/Odesa/Zaporizhzhia use three separate monthly CSV files in `data/casualties/cities/`. **All 23 published series end in September 2026**. The September snapshots are explicitly partial and have city-specific last validated dates. **No October 2026 published row**, so a missing October value cannot be interpreted as zero.
- `site-prod:data/casualties/revisions.csv` (Git blob `8d7a2e2540bf4bf0f8c6227023821390bf82ce13`) has one confirmed **Sumy 2026-09-20** row, not an October credit. This CSV is not a comprehensive event-identity ledger for October.
- `site-prod:data/casualties/review_queue.json` (Git blob `839d21cedbaf5f0be18b49036df6c050e18a9e16`) contains 130 items, **all `needs_review`**, many related to Kyiv and October. **Those records are candidate reports, not confirmed unique attacks or credits**. They cannot be counted or used to assert that a specific October event is already credited.

## Evidence groups (candidates, not accepted totals)

Files:
- `baseline_23city_2026_10_coverage.csv`: **23 rows**; September baseline only; October absent/UNKNOWN for every city; 11 city slugs have some retrieved article evidence, 12 have none.
- `incident_reconciliation_2026_10.csv`: **13 provisional groups across 10 cities**, all `NEEDS_REVIEW`, `automatic_credit=0`. A group is a triage unit, **not necessarily a unique incident**. Date and cumulative-count cells are tentative, not a confirmed final total.
- `check_october_reconciliation.py`: stdlib-only validation, no network, no data exports/promotion; [CI #45071216287](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/45071216287) SUCCESS. Network job SKIPPED.

### High-priority event-specific reconciliation

| City / candidate | Captured evidence and offline comparison | Safety decision |
|---|---|---|
| **Kyiv — 7 Oct morning** | s11 says 2 killed in Darniytskyi district after ballistic strike. Existing Kyiv review queue also contains 7 Oct separate reports of two ballistic deaths. | Candidate **2**, exact attack identity and time need confirmation; do **not** blend with evening UAV attack |
| **Kyiv — 7 Oct evening UAV** | Existing review queue reports 4 killed across Obolonskyi and Desnianskyi districts, 2+2; different locations/weapon from early 7 Oct ballistic. | Candidate **4**, group/district evidence needs review; no double count of 4 versus district 2+2 |
| **Kyiv — 8 Oct UAV** | Captured s10 contains an interim citywide count of **3**. Existing site-prod review queue includes Oct8 19:26 news citing mayor/KMVA **4** after one wounded person died in hospital. | **4 supersedes 3** in these reports; do **not** add 3+4, and confirm whether overnight attacks are attributed to Oct7/Oct8 |
| **Kyiv — 20 Oct UAV** | Existing site-prod review queue reports 1 death near Holosiivskyi petrol station. It separately describes **3 deaths in Chabany, Kyiv oblast**, outside Kyiv city limits. | City candidate 1; **exclude Chabany 3** from Kyiv |
| **Lutsk — 14 Oct UAV** | s21 and s22 both describe six killed in one drone strike on depot; one deceased was a resident of Ternopil region but killed **in Lutsk**. | Cumulative **6**, not 6+6 or Ternopil-city deaths; final October-month completeness unverified |
| **Poltava — 17 Oct** | Municipal s12: one dead after attack on Poltava. | Candidate 1 pending full-source/attack-type verification |
| **Kropyvnytskyi — 14/15 Oct** | Regional Police s14: three killed; municipality s13 was HTTP403. | City geography, exact date and possible multiple strikes remain unverified |
| **Chernihiv — 29 Oct** | Police s16 confirms fatalities in central Chernihiv; 150-character excerpt does not securely resolve count. s15 lists 26 **across oblast**, mostly Pryluky, outside city. | Numeric **UNKNOWN**, never import oblast 26 |
| **Ivano-Frankivsk — 8/9 Oct** | s17 identifies one deceased after a city drone strike; page updated Oct9. | Candidate 1, confirm attack occurred Oct8 (publication/update date ≠ attack date) |
| **Khmelnytskyi — 19/20 Oct** | s19 reports two killed in attack in Khmelnytskyi **region**, s18 (later hospital death) was HTTP403. | City attribution unresolved; cannot use reported 2 as city-only or assume +1 later |
| **Dnipro — 20 Oct** | s23 contains three deaths in Dnipro and references later hospital update. s24 HTTP403. | Candidate 3 only, later cumulative total unresolved |
| **Zaporizhzhia — 22 Oct** | s25 and s26 both mention three; older Work AH T03/T04/T05 reported 2/3/3. Some texts refer to **Zaporizhzhia district** rather than city. | Likely clarification 2→3, not 8; **identity, city boundary and baseline credit remain unproven** |
| **Kherson — 23 Oct** | s27 references one fatal drone incident in **Kherson oblast**, no city identification. s03/s04 OVA region-wide monthly and s05 community monthly numbers are incompatible. | Do not count as Kherson city until exact locality verified |

### Why monthly authority totals are not an October city series

UN HRMMU October figures for Kyiv, Kharkiv and Zaporizhzhia include different conflict-related weapon types and verification standards. Kherson OVA monthly **oblast** totals, Kherson MVA **community** totals, Sumy regional summaries and Chernihiv **oblast** totals cannot be copied into the site's **city administrative boundaries + aerial attacks** measure. One source often contains multiple attacks, and several sources may describe one incident and its later revisions.

The 21 successful articles covered 11 city-slug categories from the pinned search list. This is **source coverage**, not confirmed 11-city mortality coverage. The 12 other city series remain unknown for October; none are automatically set to zero. In particular, no usable direct Kharkiv city HTML was retrieved because s06 was HTTP403.

## Physical proof and open gates

- [CI #45071216287](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/45071216287) SUCCESS on research HEAD `f1b58c120dea22210ca481fb324d719a94b7f7bf`: 12 old collector tests plus new 23-city October coverage/13-group anti-dup guard PASS; the `monthly_one_shot` network job was **SKIPPED**.
- There are **0 confirmed October publication-ready city totals**, because the baseline is only a monthly aggregate ending September, the collector keeps 150-character excerpts not full corroborated incident records, and later revisions/event identities require checking.
- Do not merge this prototype into casualty WIP or site-prod as a side effect; network GO `casualty-23city-monthly-20261122-001` is spent and never reusable. The next specific **non-network** task is an evidence reviewer that uses existing site-prod review_queue snippets for Kyiv to resolve October duplicate links, with city/time/district discipline; other 22 cities require equivalent coverage.
- Separate owner approval is required for any newly sourced HTTP fetch, changing the casualty generator, changing monthly counts or publishing a Git-only casualty data revision.

**Status:** `PROMOTE=OFF`; 0 attempted new publisher GET; 0 casualty edits, production writes or publisher activations. October 2026 remains unpublished.
