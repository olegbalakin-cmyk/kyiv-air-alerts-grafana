# Kyiv September 2026 — bounded incident reconciliation (Issue #246)

**Research decision: PROPOSED SAFE NEW CREDIT +15; HELD +2; NO PUBLISH.** The +15 is a proposed incident-level delta over the already published partial Kyiv September baseline 18 through Sep 15, not a signed/accepted revision. September remains **PARTIAL**; proposed known minimum would be **33**, pending coordinator #245 + independent owner release approval. `PROMOTE=OFF`, publication_allowed=false. No production writes, no publisher/article GET.

## Pinned source state

- `main@b35ca5c8d189a011c1b7158275f189a195192890`
- `site-prod@f7e0681ca6aa98405638dae7a63c884f4ed55d20` (source-of-truth at evaluation; must revalidate before any later release)
- `PR #243@f8112362beaf6a9a8015c83c86dd8b131df5236c`, offline CI #45147864411 SUCCESS; prior September parent ledger/blob `0f1b252a458ad69465211f33c422336136de0903`.
- Baseline `kyiv-air-alerts-grafana/data/casualties/baseline_monthly.csv`, blob `52238c1e72bdba3b06fc0c0469d699f018d8e353`: `2026-09,18,2026-09-15,partial month through 2026-09-15`.
- Current `site-prod` revision blob `8d7a2e2540bf4bf0f8c6227023821390bf82ce13` has **one Sumy record, zero Kyiv confirmed revisions**; Sumy 20 Sep +1 is already published and excluded from Kyiv.
- Read-only 132-card saved `site-prod` review queue blob `8ae078bc60f2c27838b61e9aebf90b7286e0dd55`. This report uses 29 URL/hash-pinned source cards, with excerpts frozen into `kyiv_2026_09_incident_ledger.json`. Source card count is not death count. No publisher HTTP was executed in Issue #246.
- Prior 27-GET one-shot #45070256716 already spent, artifact #14773425588; this issue does not authorize another.

## Individual decisions (all proposed; NO production revision)

| Attack date | Distinct verified incident identities | Proposed safe delta | Still held |
|---|---|---:|---:|
| Sep 23 | One post-strike hospital death + a second fatality, mayor's cumulative 1→2, 23 Sep Kyiv UAV wave; [source](https://www.pravda.com.ua/news/2026/09/23/8054726/) | 2 | 0 |
| Sep 24 | Podilskyi 57-year-old woman and Solomianskyi 65-year-old man, separate sites in ballistic wave; [source](https://suspilne.media/kyiv/1410884-rosia-vdarila-po-kievu-balisticnimi-raketami-e-zagiblij-ta-poraneni/) | 2 | 0 |
| Sep 25 | Solomianskyi office **4 bodies** per police (two outdoors, one indoors, one in car), plus separate Pecherskyi apartment **one 14-year-old**; citywide 3→4→7 does NOT mean 4+7. Exact identity/sites of **remaining 2** in 7 not proven; [office](https://suspilne.media/kyiv/1412474-u-kievi-rosijskij-dron-pociliv-u-biznes-centr-zaginuli-ludi/), [child](https://suspilne.media/kyiv/1411916-zaginuv-14-ricnij-hlopec-rosijskij-dron-vluciv-u-bagatopoverhivku-u-pecerskomu-rajoni-kieva/) | 5 | 2 |
| Sep 27 | 56-year-old security guard killed at Solomianskyi office; [source](https://hromadske.ua/kyyiv/271614-rosiiany-atakuiut-bezpilotnykamy-kyyiv-ta-oblast-vidomo-pro-zahyblykh-ta-shchonaymenshe-shistyokh-postrazdalykh) | 1 | 0 |
| Sep 28 | Two women killed in National Academy of Sciences building; second body recovered, 1→2 (NOT 1+2); [source](https://suspilne.media/kyiv/1414120-u-kievi-vnaslidok-ataki-rfbudivla-nanu-gorit-budivla-nanu/) | 2 | 0 |
| Sep 30 | Overnight Sviatoshynskyi private home two women aged 46/95; separately morning Solomianskyi municipal truck driver; city total 2→3 (NOT 2+3); [night](https://suspilne.media/kyiv/1414816-u-kievi-cerez-nicnu-ataku-zaginuli-dvi-zinki-se-patero-ludej-postrazdali/), [driver](https://hromadske.ua/viyna/271755-vnaslidok-obstrilu-kyyeva-vden-zahynuv-vodiy-kyyivteploenerho-ulamky-vyiavyly-na-terytoriyi-odnoho-iz-zakhidnykh-posolstv) | 3 | 0 |

**Arithmetic:** six provisional date-group cumulative totals = 2+2+7+1+2+3 = **17**, not independent event IDs. Independently bounded victim/site credits = **2+2+5+1+2+3 = 15**, remaining **2 NEEDS_REVIEW** on Sep 25. At the pinned source, there are **0 preexisting confirmed Kyiv revision rows**, and these six date groups all occur strictly after the explicit September 15 baseline cutoff. For an owner-approved release, revalidate this negative baseline credit against latest `site-prod` and its revisions before converting any proposal to a real addition. A date after cutoff alone does not establish victim identity; each positive credit has a site/victim mapping and pinned source references.

### Exclusions and ambiguity

- Suburban **Sofiivska Borshchahivka** market fatalities 27 Sep are in Bucha raion, not Kyiv city even where Kyiv mayor was quoted; [source](https://www.pravda.com.ua/news/2026/09/27/8055283/).
- **Vyshhorod** child 30 Sep is in another city, not the Kyiv city night deaths; [source](https://suspilne.media/kyiv/1415827-tikali-vid-vijni-na-sumsini-ale-vijna-nazdognala-na-kiivsini-u-visgorodi-pid-cas-obstrilu-zaginuv-14-ricnij-pidlitok/).
- **Hlevakha/Fastiv** three deaths Sep 19 are outside Kyiv; [source](https://www.pravda.com.ua/news/2026/09/19/8054259/).
- Named journalist of Sep 25 Solomianskyi office is within the office incident four, not another +1. Sep 15 Kyiv petrol-station death is at cutoff and not newly credited.
- Late death in hospital on Sep 23 belongs to **attack date Sep 23**, not hospitalization/observation date. Another report that republishes a cumulative total is corroboration, not a separate death.
- Sept 25 two additional citywide deaths are **unallocated**: no victim-level or nonoverlapping site mapping in existing cards. Missing this proof is an **evidence gap**, not proof that those deaths did not occur.
- Daily series must NOT be considered exhaustive month coverage; other after-cutoff incidents may be missing from queue. No claim of complete September or final 2026 annual sum.

## Evidence model / handoff

- `kyiv_2026_09_incident_ledger.json` — 29 saved URL+SHA256+excerpt witnesses, eight safe incident-level proposals, one held residual, nine explicit exclusions, six date-group reconciliation rows, current baseline and branch pins; no guessed victim names. Identity slot labels are **non-identifying audit aliases**, not civil identity or forensic proof.
- `kyiv_2026_09_credit_decisions.csv` — machine-readable `SAFE NEW CREDIT`, `NEEDS_REVIEW`, `EXCLUDED_AS_DUPLICATE_OR_OUT_OF_CITY`; with event/date/site, source refs, baseline proof and per-row delta.
- `check_kyiv_2026_09_credits.py` — offline, no dependencies, no network; validation of city boundary, pinned original baseline, 29 source hashes, 15 unique victim-slot aliases, 17-to-15+2 consistency, source linkages and CSV parity; **16 negative mutations** fail closed (including promotion, wrong baseline, incorrect month, citywide double counting and missing sources).
- CI: existing `.github/workflows/test-explosion-monitor-wip.yml` push-only offline job extends allowlist to this isolated research branch. **Existing HTTP one-shot guard remains unchanged**; `monthly_one_shot` is explicitly restricted to a different branch + fresh owner grant and is not executed here.

## Release gate

**Do not publish, merge to main/site-prod or edit revisions.csv/dashboard_data.json.** Handoff to coordinator #245: verify latest production snapshot and anti-dedup, resolve 2 held Sep 25 deaths if possible, revalidate the 15 victim/site mappings independently, then request a separate exact owner GO for release. If any source or baseline drift cannot be explained, fail closed. This research package is a candidate for improving the real displayed Kyiv September number, not changing its color.

Research checkpoint: `CASUALTY-KYIV-SEPT-246-SAFE15-HELD2-NO-PUBLISH-2026-11-23-01`.
