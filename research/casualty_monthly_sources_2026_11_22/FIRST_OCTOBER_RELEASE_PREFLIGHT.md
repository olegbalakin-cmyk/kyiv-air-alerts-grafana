# First October casualty data update — four verified event groups, no publish

Checkpoint: `CASUALTY-OCT2026-FOUR-EVENT-PARTIAL-PREVIEW-OFFLINE-PASS-2026-11-22-01`.

**Release status: RESEARCH PREVIEW ONLY. No production approval, no Git-only publication, no Netlify or Neon mutation. `PROMOTE=OFF`.**

## Current verified civilian-event minimum (NOT complete monthly totals)

| City | Attack date | Count from this verified incident | Evidence summary |
| --- | --- | ---: | --- |
| Lutsk | 2026-10-14 | **6** | [Lutsk City Council](https://www.lutskrada.gov.ua/publications/u-lutsku-vnaslidok-vorozhoi-ataky-zahynuly-shestero-liudei-shche-12-travmovani) and [15 Oct municipal commission](https://www.lutskrada.gov.ua/publications/komisiia-1510) distinguish five bodies recovered and one later death in hospital; [National Police](https://npu.gov.ua/news/shestero-zahyblykh-trynadtsiat-poranenykh-sered-nykh-dytyna-politseiski-dokumentuiut-naslidky-vorozhoi-ataky-u-lutsku) corroborates six |
| Poltava | 2026-10-17 | **1** | [City Council 19 Oct](https://rada-poltava.gov.ua/ua/news/u-poltavi-likviduvali-naslidki-vorozhoyi-ataki-17-zhovtnya), [National Police](https://npu.gov.ua/news/odna-liudyna-zahynula-ta-chetvero-postrazhdalykh-politsiia-ta-sbu-poltavshchyny-dokumentuiut-naslidky-vorozhoho-obstrilu); [prosecutor clarification via Poltavshchyna](https://poltava.to/news/88633/): aerial **cruise missile Banderol**, not a confirmed UAV |
| Ivano-Frankivsk | 2026-10-08 | **1** | [Suspilne](https://suspilne.media/ivano-frankivsk/1422981-vnaslidok-ataki-rosijskogo-reaktivnogo-bpla-po-ivano-frankivsku-zaginuv-colovik-marcinkiv/) and [Ukrainska Pravda](https://www.pravda.com.ua/news/2026/10/09/8057142/) quote mayor/OVA regarding deceased **civilian** security guard; separate Oct 11 strike killed **three soldiers**, not civilian series |
| Khmelnytskyi | 2026-10-19 | **3** | [Mayor's Oct19 bulletin](https://www.khm.gov.ua/index.php/uk/all-news/miskiy-golova-informue-operativna-informaciya-shchodo-situacii-v-gromadi-onovleno): two women found dead; [Mayor's Oct22 bulletin](https://www.khm.gov.ua/uk/all-news/tragichna-zvistka-dlya-gromadi-u-likarni-pomerla-zhinka-poranena-pid-chas-ataki-na): a **different** injured 54-year-old woman later died; [Suspilne hospital](https://suspilne.media/khmelnytskiy/1434043-pomerla-zinka-aka-otrimala-travmi-vnaslidok-vibuhu-u-hmelnickomu-19-zovtna/) confirms Oct19 injury and Oct22 death |

**Subtotal = 11 civilian deaths from FOUR distinct Oct 2026 aerial attacks.** This is an evidence-backed *minimum for these four cities*, not the total of all October deaths in these cities or across the 23-city coverage set. If other incidents occurred, the final monthly number may be larger. In particular, do not use `0` for the 19 other city cells, do not count the Oct 11 three military deaths in Ivano-Frankivsk, and do not add the same six fatalities in Lutsk more than once.

## Versioned research output and proof

- `october_2026_verified_event_candidates.json`: four event identities, cumulative deaths, official/media dated URLs, specific earlier/later update identities. Records are **not production revisions**.
- `october_2026_partial_preview.json`: 23 city rows with four `confirmed_event_lower_bound` values (6,1,1,3), **19 nulls**, `monthly_exact_total=null` for every city, and `ready_for_monthly_data_publishing=false` for all. The 11-death subtotal is an incident-only subtotal, **not a complete monthly value**.
- `prepare_october_partial_preview.py`: repeatable offline gate verifying four incident identities, weapon/civilian scope, double-counting, late death, 23-city coverage and byte-compatible preview semantics. Reads files only; it **cannot update** main, site-prod, casualties revision files, or the dashboard. Network job disabled on this branch.
- Existing [one-shot run #45070256716](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/45070256716) is the only authorized capture; GO spent, 27 requests/21 HTML200. This update additionally uses **public web-retrieved official documents**, not another private Actions collector GET.

## Important integration blocker before publication

The existing `site-prod` casualty generator `kyiv-air-alerts-grafana/scripts/update_casualties.py` can materialize October values from confirmed revisions, but its `monthly` rows and Grafana numeric casualty panel are not designed to render a **lower bound** separately from a **complete month**. The dashboard title simply states fatalities and uses numeric `deaths`. Appending an incomplete month without changing this label would incorrectly imply an exact monthly total.

**Therefore DO NOT insert the preview as regular `deaths` rows or change `site-prod` yet.** Before an owner-approved release:

1. Stage a separate, isolated test of the existing generator + front end that can show `Жовтень 2026 — щонайменше N підтверджених` (EN: `October 2026 — at least N confirmed`) or omit the partial month from the exact-series panel, with explicit last-verified coverage. A zero or null missing city must not become an actual plotted zero. Existing historical exact months must stay unchanged.
2. Generate compliant evidence-backed revision candidates with stable incident IDs, `count_kind=cumulative`, `baseline_credited=0` **only after an immutable credited-proof check** against the frozen source. Supply distinct `identity_proof` and `credited_proof` hashes for each incident and ensure the generator's older pinned Sumy revision remains untouched.
3. Run complete offline regression and an actual preview/browser QA: bilingual UA/EN title/legend, mobile, partial-vs-exact tooltip, 23-city unknown fields, year totals, source references and historical September end unchanged.
4. Only when numbers and UI semantics match may the owner issue separate `site-prod` publish GO. Zero Netlify redeploy for regular Git-only JSON updates and preserve the production lock.

## What is still unverified

- Full October coverage even in those four cities; current four-event dataset is a **minimum**, not necessarily complete city monthly total.
- Other city deaths (including Kyiv where distinct Oct 7/8 updates may overlap) and remaining 19 city values are not certified.
- No network/autonomous monitor or publication is enabled by this preview. Later source corrections remain possible.

This research branch is not a production branch and must not be merged into `site-prod` without a separate explicitly owner-authorized release process.
