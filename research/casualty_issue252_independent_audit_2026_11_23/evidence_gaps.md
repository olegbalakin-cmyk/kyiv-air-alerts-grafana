# Casualty Issue #252 — independent source and credit audit (NO PUBLISH)

**Decision (2026-11-23):** `NEW_RELEASABLE_SEP=NOT_YET_VERIFIED`; `NEW_RELEASABLE_OCT=NOT_YET_VERIFIED`; **new delta authorized by this audit = 0**. This is **not** a claim that no one died. Both research candidates remain plausible but not independently release-certified from the available evidence. `READY_FOR_OWNER_GO=NO`, `PROMOTE=OFF`.

## Verifiable scope and immutable inputs

- Root coordination read from **main@b35ca5c8d189a011c1b7158275f189a195192890**: `PROJECT_STATE.md` and `CHANGELOG.md`. The C6/Neon/Netlify updates are **not** casualty revisions.
- Direct read-only HEAD verification: **site-prod@f7e0681ca6aa98405638dae7a63c884f4ed55d20**, twice before audit. Its casualty `review_queue.json` blob **8ae078bc60f2c27838b61e9aebf90b7286e0dd55**, 132 candidate rows.
- Baseline Kyiv `baseline_monthly.csv` blob **52238c1e72bdba3b06fc0c0469d699f018d8e353**: `2026-09,18,2026-09-15,partial month`; 15 September **included** in baseline. City-month `master_20cities_monthly_wide.csv` blob **f3b7fdf6750e12d7b9af05ffd094bb47aa9ed801** has September row, **no October**.
- Published `revisions.csv` blob **8d7a2e2540bf4bf0f8c6227023821390bf82ce13**: **one** confirmed Sumy 2026-09-20 +1, **zero** Kyiv September after-cutoff credits, **zero** October credits. Sumy is already published and cannot be added again.
- September source **PR #249@8212719ef9b6ea46a00520c78f5629ba6128d310**, research ledger blob **f54d6dae912f940a1c54ef89edffde4b482f1bab**, offline Actions [#45156236536](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/45156236536) **SUCCESS** (not publisher-body capture). Independently matched **all 29/29** URL/title/short-content SHA256 fingerprints against pinned site-prod queue entries.
- October source **PR #248@9b832784970de951129685119aa2b6f471cfd349**, research ledger blob **3ab131b72a13f4d6daed87ece1f8a482c8fc18e7**, offline Actions [#45155998766](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/45155998766) **SUCCESS**. Independently matched **10/10** URL/SHA256 entries against pinned queue; checked two other exact decoded-HTML SHA256 strings against source metadata in the old collector report.
- Prior collector [#45070256716](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/45070256716), artifact **#14773425588**: **physically downloaded ZIP (8,022 bytes) and rehashed** SHA256 `f2a95945e98dc92cdc49529be2bb127a5d4c3fe8a9e71ad82ebf2437b7c2eb9f`; extracted `capture_report.json` rehashed `be053f77ade09db833eb976a67a6bcb036fb42cff1c98f81bfd90dde1fbe7ed8`. Exactly **27 attempted GET**, **21 HTTP200**, zero credits/writes, `source_full_text_saved=false`. The archived JSON records **metadata and short context, not 21 full publisher bodies**. Earlier GO is spent and cannot be reused.
- Git source hashes are chain-of-custody evidence for **saved excerpts**; URL matching or a prior Actions SUCCESS **is not a primary-source attestation**. No new publisher HTTP request was made here.

## Concurrent site-prod advance — independent latest readback

While this audit branch was being tested, a separate Git-only C6 publication advanced `site-prod` **one commit** from `f7e0681ca6aa98405638dae7a63c884f4ed55d20` to **`58634812155ddc6b4324c26d694cf3de6cfb9bbe`**. This audit did **not** push that commit. Read-only compare revealed 11 file changes (air-alert metrics/checkpoints plus casualty review queue/source state), **no revisions, baseline, or monthly casualty rows changes**.

Directly fetched latest: Kyiv Sep baseline blob unchanged `52238c1e72bdba3b06fc0c0469d699f018d8e353`; revisions unchanged `8d7a2e2540bf4bf0f8c6227023821390bf82ce13`; wide CSV unchanged `f3b7fdf6750e12d7b9af05ffd094bb47aa9ed801`. Review queue changed blob from `8ae078bc...` to **`280eff9296fc872510462e7d4f3ff02e3ff4a4ce`**, still **132 entries**. Independently compared every entry in the old/new decoded JSON: **only index 0** changed its saved content hash; **all 29 September and 10 October issue witnesses are at other unchanged indices**. Thus the historical **old queue blob remains an immutable exact reference** used in the audit matrix, and the current live queue is shown separately as a readback; its one updated candidate does not alter the pending Kyiv groups. This does **not** eliminate the need to re-pin production again just before any eventual release.

## Incident-by-incident acceptance (see full 36-row matrix)

| Date and group | Source-backed proposal; **not release-certified** | Reconciliation issue |
|---|---:|---|
| Kyiv Sep 23, UAV | +2 held | One hospital death from *same* attack; interim 1→final 2, not 1+2. Need independent dated primary account / victim-level nonoverlap. |
| Kyiv Sep 24, ballistic | +2 held | Podilskyi woman 57 and Solomianskyi man 65 cited by prosecutors. Two districts, not two separate article credits. |
| Kyiv Sep 25, Solomianskyi office | +4 held | Police details four bodies: outdoors 2, inside 1, car 1. Named journalist is one of four, **not** fifth. Full police account needed. |
| Kyiv Sep 25, Pecherskyi apartment | +1 held | A separate 14-year-old child; independently reconcile inclusion in citywide 7 (which updates 3→4→7). |
| Kyiv Sep 25, citywide residual | **+2 still held/unallocated** | Seven citywide reported minus five location-bounded. Cannot infer two additional *identifiable* city attack victims by subtraction alone. Do not sum 7+4+1. |
| Kyiv Sep 27, Solomianskyi | +1 held | One office security guard aged 56. Separate *suburban market* victims are not Kyiv. **Additional source-scope discrepancy:** q81 explicitly says two city deaths while q82 reports one city guard plus one oblast death; an additional Kyiv victim is **not established**. Potential unknown one is **not** in parent +15/+2 and was not invented as new credit. |
| Kyiv Sep 28, NAS building | +2 held | Rescue update initial one→two after finding another worker; never add interim + final. |
| Kyiv Sep 30, Sviatoshynskyi home | +2 held | Two women 46 and 95 in Kyiv; distinct from a child in Vyshhorod (outside city). |
| Kyiv Sep 30, Solomianskyi driver | +1 held | Separate municipal utility driver; Kyiv day cumulative 2→3 is **total three**, not 2+3. |
| **Kyiv September proposed subtotal** | **+15 held; +2 unresolved within Sep 25** | Research-only hypothetical 18+15=33, **not published, not certified complete**. Exclude Sep 15 already within published 18, Sep 19 Hlevakha (Fastiv raion), Sep 27 Sofiivska Borshchahivka (Bucha raion), Sep 30 Vyshhorod, repeat article updates and Sumy. |
| Kyiv Oct 7 pre-dawn ballistic | +2 held | Darnytskyi garage, two older men; separate from **evening** drone wave, distinguish dates/waves in independent primary accounts. |
| Kyiv Oct 7 evening UAV | +4 held | Obolonskyi courtyard 2 + Desnianskyi home 2. Desnianskyi recovered/reported Oct 8 but strike **Oct 7**. Do not add 2 twice. |
| Kyiv Oct 8 daytime UAV | +4 held | Holosiivskyi 1 + Solomianskyi shop 3. Early shop 2→police 3; daily 3→4 including hospital death; additive error prevented. |
| Kyiv Oct 20 UAV | +1 held | Holosiivskyi near AЗС. **Exclude Chabany 3** (Fastiv raion, Kyiv oblast), and duplicated daily citywide one. |
| **Kyiv October proposed subtotal** | **+11 held** | Six physically distinguished subincidents across four date groups. October has **no complete published city-month total**; 11 is an incident subtotal, not a monthly statistic. |

October additionally has **five** held groups needing exact first-hand sources: Dnipro Oct 20 (three vs later hospital death); Zaporizhzhia Oct 22 (2→3 and city boundary, must reconcile T03–T05); Kropyvnytskyi Oct 14/15 (oblast three cannot imply city three); Chernihiv Oct 29 (city count missing, not oblast 26); Kherson Oct 23 (city location, attack type, civilian causality). **Do not turn source absence into a zero.**

## Separate Release-1 issue #251 — DO NOT BLOCK

The **four already reviewed** October attack minima from PR #236 remain **11 across Lutsk 6, Poltava 1, Ivano-Frankivsk 1, Khmelnytskyi 3**. They are *already approved for inclusion in the separately owner-gated Release-1 package*, **not currently published in site-prod**, and they are not Issue #252's +11. No overlapping event exists in our proposed **Kyiv** October group, but this is not permission to publish any proposed Kyiv figure.

Issue #251 can pursue the separately gated first Release-1 **without waiting for these Kyiv additions**. Ensure future October sidecar inserts are additive by **unique event**, not `11 old + 11 new` without source signoff.

## Owner article-GET request — **NOT AUTHORIZED**

See `owner_article_go_request.json` for the exact **12 URL allowlist entries**, original pinned source hashes and safety envelope. In priority order: Sep23; Sep24; Sep25 office; Sep25 child; Sep25 citywide revised total; Sep27 citywide scope conflict; Sep28 two NAS workers; Sep30 original 2+1 citywide; Oct7 ballistic; Oct7 evening UAV; Oct8 final police correction; Oct20 city one. This is a **small bounded proposal**, not an HTTP permission.

A subsequent owner one-shot grant must pin exact **research HEAD and immutable manifest digest**, claim GO once **before** any request, and allow at most **12 HTTPS public-IP publisher GETs; one per exact URL; 15 seconds; 2 MiB each; redirects OFF, retries OFF, sequential**, with zero RSS GET, zero writes, zero automatic credit, zero Netlify/C6/Neon changes and `PROMOTE=OFF`. This workflow is **not dispatched** by this PR.

After capturing exact primary bodies, retain source byte hashes and dates and independently adjudicate event identity, civilian status, locality, reporting revisions and the latest production baseline. Only then may a later **research-only proposed casualty sidecar delta patch** and a separately owner-approved release be prepared. **No revision or release patch is currently warranted.**

## Offline tests and stop gate

`test_independent_audit.py` reads only four frozen audit files, validates row ↔ source SHA cross-links, exact group totals, no overlap with Release-1 11, explicit exclusions, non-additive interim revisions, production refs, safety GO request, and **19+ fail-closed test cases**, including tampering with source hashes, Chabany, Sep25, Oct8, date attribution, fake credit, GO budget or URL, promotions, and published baseline.

Command: `python -m unittest discover -s research/casualty_issue252_independent_audit_2026_11_23 -p 'test_*.py' -v`. No network or workflow dispatch. `PROMOTE=OFF`. Neither `revisions.csv`, `site-prod`, `main`, C6, Neon nor Netlify changed.
