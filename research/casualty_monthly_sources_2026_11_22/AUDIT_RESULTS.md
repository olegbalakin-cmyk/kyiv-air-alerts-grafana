# October 2026 audit — 23-city casualty coverage (research only)

Checkpoint: `CASUALTY-MONTHLY-23CITY-WEB-AUDIT-PARTIAL-2026-11-22-01`

**Decision: PARTIAL WEB EVIDENCE / CONTROLLED COLLECTION NOT EXECUTED / NO PUBLISH.**

Owner explicitly authorized up to 50 bounded HTTP GET and no production mutation. The tool-backed repository and ordinary web searches were inspected. The separate direct HTTP execution environment failed at DNS resolution before any source response. **Zero executable collector GET can be evidenced.** Search engine retrieval is not equivalent to auditable one-shot publisher GET; do not report any consumed collection budget, response logs, body hashes, or batch success. No Actions one-shot was dispatched, no site-prod/WIP/Neon edits, no casualty credits and `PROMOTE=OFF`.

## October source leads with verified published content

* **Kherson OVA** [October official monthly report](https://khoda.gov.ua/news/informatsiia-shchodo-vorozhykh-obstriliv-khersonskoi-oblasti-z-01102026-po-31102026): 11 killed in **oblast** from all attacks, six in drone strikes. [September report](https://khoda.gov.ua/news/informatsiia-shchodo-vorozhykh-obstriliv-khersonskoi-oblasti-z-01092026-po-30092026): 31 total, 23 drone; reports recurring monthly. Neither is a Kherson city air-only monthly count.
* **Kherson MVA** [reported by Suspilne](https://suspilne.media/kherson/1442401-u-zovtni-cerez-rosijski-ataki-u-hersonskij-gromadi-zaginuli-visim-ludej-135-poraneni/): eight killed in **Kherson community**. Territorial community boundaries differ from Kherson city.
* **Kharkiv mayor** [reported by Suspilne](https://suspilne.media/kharkiv/1442317-rekordni-153-udari-za-misac-u-zovtni-rosiani-vbili-22-ludej-u-harkovi/): 22 killed in **Kharkiv city** from attacks in October; includes Tornado-S MLRS and other weapon types, so the total cannot be credited directly to an air-only series.
* **UN HRMMU** [October monthly report](https://ukraine.ohchr.org/en/Protection-of-Civilians-in-Armed-Conflict-October-2026): Kyiv 25, Kharkiv 19, Zaporizhzhia 31 confirmed killed across conflict-related weapon types. UN 19 vs mayor 22 for Kharkiv is **a measurement discrepancy to investigate**, not a permission to choose one number.
* **Chernihiv regional police** [reported by Suspilne](https://suspilne.media/chernihiv/1454545-cerez-rosijski-ataki-u-zovtni-na-cernigivsini-zaginuli-26-ludej-sered-nih-semero-ditej/): 26 in **oblast**, including 22 killed in Pryluky, which is **not Chernihiv city**. Separate city incidents (Oct 21, 23, 29) require event-level reconciliation.
* **Lutsk** [city executive decision via Suspilne](https://suspilne.media/lutsk/1432227-rodini-sistoh-zagiblih-vnaslidok-ataki-rf-po-gurtivni-u-lucku-otrimaut-materialnu-dopomogu/): Oct 14 UAV attack, **six** killed in same incident (five at location and one died after hospitalisation). An incident-specific candidate, NOT a complete monthly total.
* **Khmelnytskyi** [hospital follow-up via Suspilne](https://suspilne.media/khmelnytskiy/1434043-pomerla-zinka-aka-otrimala-travmi-vnaslidok-vibuhu-u-hmelnickomu-19-zovtna/): two died in Oct 19 attack initially; a 54-year-old wounded woman died Oct 22. **Same-incident late-death candidate**, needs exact person/date/attribution review before +1.
* **Kropyvnytskyi city council** [Oct 17 report](https://www.kr-rada.gov.ua/news/koli-misto-perezhiva-bil-poruch-ti-hto-gotoviy-dopomogti_17-10-2026.html): reports three residents killed in air attacks Oct 14–15. Must verify whether one or several incident IDs, and the city-boundary/air-only context.
* **Zaporizhzhia**: the existing Work AH [one-shot evidence](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/45020948794) got 3/3 HTTP200 but 1/3 numerics; T03/T04/T05 identity remains open. UN monthly 31 is all-weapon monthly verified total, not proof of an additional 31 beyond known cases.

These sources contain evidence for research **only**. The `audit_23cities_2026_10.csv` contains exactly 23 rows. Ten cities have no verified city-specific October report in this bounded search; this means **UNKNOWN, never zero**.

## Metrics and gates

- Current published historical casualty series is **air-attack fatalities inside city administrative boundaries**, attributed to month of attack, with later death revisions guarded. A community, oblast, all-hostilities or UN-verified total must never replace it.
- **Even a proven city-specific air-only incident is not an automatic +N.** It first needs a known attack date, identity proof, previous baseline credit status and corrected cumulative deaths for that event.
- For Kyiv, Kharkiv, Sumy, Kherson, Chernihiv and Zaporizhzhia, candidate monthly totals use different boundaries and/or weapons. For Lutsk, Khmelnytskyi and Kropyvnytskyi, individual attack evidence is promising but does not finalize October month.
- Missing monthly evidence for a city is `UNKNOWN`, not `0` or `NO_ATTACKS`. Verified partial months are marked partial.

## Physical collection: blocking prerequisites

A real 50-GET max collector needs (1) a **preflight** that checks allowlisted HTTPS URLs, max body bytes, redirects OFF, retries OFF, timeouts, and no reruns; (2) a script-enabled executor with network/DNS and a **single-use owner-supplied grant**; (3) exact versioned input manifest and auditable source response receipts; (4) no automated credits. No such executed job exists in this audit.

The newly added `approved_sources_manifest.json` has **27 candidate URLs**, not 27 independently HTTP-validated URLs. Every URL must be HEAD/GET-validated and redirects/replies verified before claiming collection PASS; do not consume the 23 unallocated requests by silently broadening scope. That file is an operator-reviewed input list, **not a network execution grant**.

## Next bounded engineering step

Prepare a **separate research-only, manual** one-shot collector using the 27 candidate URLs and no more than the approved ceiling, with exact head and fresh proof; no automatic trigger, default OFF. If a registered GitHub Actions workflow is required, register a fail-closed manual stub first without merging the research executor. Ask the owner to dispatch once; then inspect status, body lengths and hashes and offline extraction per source, and reconcile 23 city/month rows. Do **not** deploy or update `site-prod` in the absence of owner approval and complete attribution evidence.
