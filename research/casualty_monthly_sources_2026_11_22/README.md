# CASUALTY: monthly official-source feasibility (research-only)

Status: **SOURCE_DISCOVERY_PARTIAL / NO DATA PROMOTION / NO AUTOMATIC PUBLISHING**  
Prepared 2026-11-22. This branch is a separate, read-only prototype based on `main`, not the casualty WIP or `site-prod`.

## Finding: monthly summaries exist, but are not interchangeable

* [Kherson regional military administration — October 2026](https://khoda.gov.ua/news/informatsiia-shchodo-vorozhykh-obstriliv-khersonskoi-oblasti-z-01102026-po-31102026), published Nov 1: 11 deaths in **Kherson oblast** across Russian attacks; 6 deaths in drone attacks. The oblast totals cannot be assigned to the city.
* [Kherson city military administration via Suspilne — October 2026](https://suspilne.media/kherson/1442401-u-zovtni-cerez-rosijski-ataki-u-hersonskij-gromadi-zaginuli-visim-ludej-135-poraneni/), published Nov 1: 8 deaths in the **Kherson territorial community**, all reported attacks. This is not the same as the **city administrative boundary**.
* [UN Human Rights Monitoring Mission in Ukraine — October 2026 PDF](https://ukraine.ohchr.org/sites/default/files/2026-11/Ukraine%20-%20protection%20of%20civilians%20in%20armed%20conflict%20%28October%29_ENG.pdf), released Nov 17: named cities Kyiv 25, Kharkiv 19, Zaporizhzhia 31, with 372 killed nationally. Its city totals cover **verified conflict-related civilian fatalities from multiple weapon types**, not strictly aerial attacks.
* [Kherson regional military administration — September 2026](https://khoda.gov.ua/news/informatsiia-shchodo-vorozhykh-obstriliv-khersonskoi-oblasti-z-01092026-po-30092026), published Oct 1: 31 deaths across oblast, of which 23 reported drone attacks. Demonstrates recurrence of the same source's format, not 23-city coverage.
* [UN HRMMU September 2026](https://ukraine.ohchr.org/uk/Protection-of-Civilians-in-Armed-Conflict-September-2026) included figures for selected cities; good cross-check, not a consistent public 23-city all-weapons monthly matrix.

**These monthly totals are candidate reference measurements, not proposed revisions.**
The existing site's monthly casualty series is `city administrative boundaries` + `air-attack-only` + `late deaths attributed to attack month`. A community, oblast, all-weapon, or verification-date series must not overwrite it. Even a city + air-only official figure would require checking baseline credit, double counting and attribution date. The present site-prod snapshot includes a 20-city master ending 2026-09 and separate Kherson, Odesa and Zaporizhzhia series ending 2026-09; the generator also has an explicit incident-aware revision safety gate. Published September 2026 may be partial: do not silently finalize it.

## Prototype files

* `source_examples.csv` — five **documented source rows** for 2026-10 (not the 23-city metric; two Kherson scopes are intentionally different).
* `validate_monthly_sources.py` — offline, stdlib-only validation and 23-city coverage presentation. Missing city reports remain `NO_MONTHLY_SOURCE_REPORT_NOT_ZERO`. Any reported death count remains a source candidate with `published_air_only_deaths: null`. There is **no HTTP, scheduling, Git write, deploy or promotion path**.
* Run locally: `python3 research/casualty_monthly_sources_2026_11_22/validate_monthly_sources.py --self-test --month 2026-10`.

## How to reach regularly updated *site* data

1. **Source coverage audit:** for each of 23 cities, identify whether the authority publishes a consistently retrievable city-specific monthly figure with weapon scope and attack-month attribution. Look for official MVA pages or official social posts; include dated citations and exact geographic boundaries. Use UN HRMMU as a monthly cross-check for cities it reports, and Suspilne/Police/DSNS for missing incidents.
2. **Separate source collection from scoring:** scheduled read-only discovery gathers candidate monthly statements with original URL, page time, reporting month, geography, weapon type, later corrections. Parser stores `unknown` when source missing; no implicit zero. A scheduled discovery workflow will require explicit owner approval for HTTP budget/hosts and separate CI proof.
3. **Reconciliation gate:** existing event-specific confirmed data must be checked before any monthly total is incorporated. Where a source reports all attacks or a community, it may corroborate but cannot be directly credited. Mark mismatches `NEEDS_REVIEW`, not `+N`.
4. **Produce a monthly *air-only city* reconciled table**, with source evidence, exact coverage end, dedup/baseline proof, partial-month status, and a deterministic offline build. Keep `PROMOTE=OFF` until 23-city parity and one full controlled cycle pass.
5. **Owner-gated release to `site-prod`:** only validated, approved casualty JSON/CSV via Git-only update path, no normal Netlify redeploy; follow with live 23-city browser parity. Do not merge this research branch into production or enable monitoring as a side effect.

## Measurement decisions requiring explicit owner approval

* Whether the website should retain the existing **air attacks only** series or add a separately labeled **all conflict-related deaths** monthly series. Never silently switch a series definition.
* Whether city reporting should allow **territorial communities** as an additional, clearly separate geography (not as city boundaries).
* Data freshness and coverage policy: label partial month explicitly; `missing != zero`; never call a month final solely because a news summary exists.

## Limits of this pilot

This is **not an operational monitor**: sources are manually identified and examples have not been fetched by a scheduled GitHub job. No RSS or article HTTP was authorized here, no publisher requests performed, no casualty revisions created, no Neon/WIP/site-prod mutations. Sample data does not imply coverage beyond the five rows or demonstrate matching to air-only fatalities. Production and casualty research tracks remain separate.
