# CASUALTY 23-city monthly-source one-shot: physical evidence review

Checkpoint: `CASUALTY-MONTHLY-27GET-PHYSICAL-21OF27-REVIEWONLY-2026-11-22-01`.

**Research only. No data credits or publication.** Authorized exact GO `casualty-23city-monthly-20261122-001` was spent once in [GitHub Actions #45070256716](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/45070256716) on 2026-11-22 21:07 UTC; HEAD `11f9f2d7779671beaa7b5609c776ffedb2ef4b1c`, owner actor and triggering actor, attempt 1. Network job `monthly_one_shot` SUCCESS. Offline job SKIPPED.

## Bounded physical evidence

- Exactly **27 unique publisher GET attempts** of 27 permitted; no retry. **21 HTTP 200** with parseable HTML, **5 HTTP 403**, and **1 HTTP 301** rejected because redirects are OFF. This is not 21 complete city monthly series.
- **11/23** cities have at least one successful retrieved source. The other 12 have no successful body in this one-shot (only Kharkiv has a failed URL among these; 11 cities were not in the 27 URL candidate list). Missing is UNKNOWN, not 0.
- [Artifact #14773425588](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/45070256716/artifacts/14773425588) ZIP SHA256 `f2a95945e98dc92cdc49529be2bb127a5d4c3fe8a9e71ad82ebf2437b7c2eb9f`; embedded `capture_report.json` SHA256 `be053f77ade09db833eb976a67a6bcb036fb42cff1c98f81bfd90dde1fbe7ed8`. Independently rehashed both; the embedded `sha256_manifest.json` confirms the report digest.
- Grant SHA256 `0b655665f8e058c9cbbe89f6a9360c686d5d95f9bd524232562a82fddb9c48eb`; source-manifest byte SHA256 `9896815fb6e800883d95182499c4d12c00b273651d8733e4d5ab7a552e566585`. Atomic spent tag `refs/tags/casualty-monthly-go-consumed/casualty-23city-monthly-20261122-001` points to the exact approved SHA. No replay of this GO allowed.
- Receipt fields: `production_writes=0`, `wip_writes=0`, `automatic_credits=0`, `promotion=OFF`, `rss_gets=0`, `source_full_text_saved=false`, `finished=true`. No file content was produced for website publication.

## URL-by-URL outcomes

| ID | City | Reporting scope | Status | Exact source |
|---|---|---|---|---|
| s01 | kyiv | city-all | 200 | [source](https://ukraine.ohchr.org/en/Protection-of-Civilians-in-Armed-Conflict-October-2026) |
| s02 | kyiv | city-all | 200 | [source](https://ukraine.ohchr.org/uk/Protection-of-Civilians-in-Armed-Conflict-September-2026) |
| s03 | kherson | oblast-all | 200 | [source](https://khoda.gov.ua/news/informatsiia-shchodo-vorozhykh-obstriliv-khersonskoi-oblasti-z-01102026-po-31102026) |
| s04 | kherson | oblast-all | 200 | [source](https://khoda.gov.ua/news/informatsiia-shchodo-vorozhykh-obstriliv-khersonskoi-oblasti-z-01092026-po-30092026) |
| s05 | kherson | community-all | 200 | [source](https://suspilne.media/kherson/1442401-u-zovtni-cerez-rosijski-ataki-u-hersonskij-gromadi-zaginuli-visim-ludej-135-poraneni/) |
| s06 | kharkiv | city-unspecified | 403 | [source](https://suspilne.media/kharkiv/1442317-rekordni-153-udari-za-misac-u-zovtni-rosiani-vbili-22-ludej-u-harkovi/) |
| s07 | sumy | community-all | 301 redirect blocked | [source](https://tv.sumy.ua/y-jovtni-rosiiany-zdiisnili-182-obstrili-symskoi-gromadi-zaginylo-p-iatero-mistian-novini-sym/) |
| s08 | sumy | community-all | 200 | [source](https://cukr.city/city/obstrily-sumshchyna-zhovten-rosiyany/) |
| s09 | sumy | community-all | 200 | [source](https://sumycma.gov.ua/novyny/2026/10/02/gennadij-demyanenko-u-sumah-zaginulo-56-meshkancziv-772-postrazhdalo/) |
| s10 | kyiv | city-incident | 200 | [source](https://dnipr.kyivcity.gov.ua/news/vorozha-ataka-na-stolytsiu-8-zhovtnia-informatsiia-onovliuietsia) |
| s11 | kyiv | city-incident | 200 | [source](https://darn.kyivcity.gov.ua/news/vnochi-voroh-atakuvav-stolytsiu-balistychnymy-raketamy) |
| s12 | poltava | city-incident | 200 | [source](https://www.rada-poltava.gov.ua/ua/news/u-poltavi-likviduvali-naslidki-vorozhoyi-ataki-17-zhovtnya) |
| s13 | kropyvnytskyi | city-incident | 403 | [source](https://kr-rada.gov.ua/news/koli-misto-perezhiva-bil-poruch-ti-hto-gotoviy-dopomogti_17-10-2026.html) |
| s14 | kropyvnytskyi | city-incident | 200 | [source](https://kg.npu.gov.ua/news/troie-zahyblykh-ta-shestero-travmovanykh-politsiia-dokumentuie-naslidky-naimasovanishoi-ataky-rf-na-kirovohradshchynu) |
| s15 | chernihiv | oblast-all | 200 | [source](https://suspilne.media/chernihiv/1454545-cerez-rosijski-ataki-u-zovtni-na-cernigivsini-zaginuli-26-ludej-sered-nih-semero-ditej/) |
| s16 | chernihiv | city-incident | 200 | [source](https://cn.npu.gov.ua/news/politsiia-dokumentuie-naslidky-rosiiskoho-udaru-po-tsentru-chernihova-ie-zahybli-ta-poraneni) |
| s17 | ivano-frankivsk | city-incident | 200 | [source](https://suspilne.media/ivano-frankivsk/1403254-rosijskij-reaktivnij-bpla-atakuvav-ivano-frankivsk/) |
| s18 | khmelnytskyi | city-incident | 403 | [source](https://suspilne.media/khmelnytskiy/1434043-pomerla-zinka-aka-otrimala-travmi-vnaslidok-vibuhu-u-hmelnickomu-19-zovtna/) |
| s19 | khmelnytskyi | city-incident | 200 | [source](https://suspilne.media/khmelnytskiy/1432345-dvoe-zagiblih-patero-travmovanih-naslidki-rosijskoi-ataki-na-hmelniccini-19-zovtna/) |
| s20 | lutsk | city-incident | 403 | [source](https://suspilne.media/lutsk/1427273-u-lucku-cerez-ataku-rf-travmuvalisa-sestero-ludej-dvoe-iz-nih-u-vazkomu-stani/) |
| s21 | lutsk | city-incident | 200 | [source](https://suspilne.media/lutsk/1429437-patero-volinan-i-zitelka-ternopilsini-imena-zertv-ataki-bpla-na-luck-14-zovtna/) |
| s22 | lutsk | city-incident | 200 | [source](https://suspilne.media/lutsk/1432227-rodini-sistoh-zagiblih-vnaslidok-ataki-rf-po-gurtivni-u-lucku-otrimaut-materialnu-dopomogu/) |
| s23 | dnipro | city-incident | 200 | [source](https://suspilne.media/dnipro/1431893-armia-rf-atakuvala-dnipro-poraneno-troh-ludej-stalas-pozeza-na-skladah/) |
| s24 | dnipro | oblast-mixed | 403 | [source](https://suspilne.media/dnipro/1432557-rosijski-vijska-protagom-20-zovtna-atakuvali-dnipropetrovsinu-majze-70-raziv-aki-naslidki/) |
| s25 | zaporizhzhia | oblast-mixed | 200 | [source](https://suspilne.media/zaporizhzhia/1434121-rosijski-vijskovi-atakuvali-zaporizkij-rajon-22-zovtna-so-vidomo/) |
| s26 | zaporizhzhia | uncertain-incident | 200 | [source](https://zp.npu.gov.ua/news/na-zaporizhzhi-cherez-rosiiski-ataky-zahynulo-troie-liudei-shche-odna-otrymala-poranennia-politsiia-dokumentuie-naslidky-voiennykh-zlochyniv) |
| s27 | kherson | oblast-all | 200 | [source](https://khoda.gov.ua/news/operatyvna-informatsiia-z-0600-31102026-po-0600-01112026) |

## Methodology and specific follow-up

- **Kherson:** regional October **11** and September **31** fatalities (all-hostilities, oblast); community October **8** (all-hostilities). All retrieved; none can replace a Kherson-city air-only monthly count.
- **Sumy:** official 2026 September city/community update and broader regional October report retrieved. The October community monthly report itself returned HTTP 301 (blocked by design). Avoid mixing cumulative year-to-date and monthly casualties.
- **Kyiv:** UN monthly October and September multi-weapon city totals retrieved, plus district administrative attack notices for Oct 7/8. Do not use UN all-weapon count as an air-only replacement; reconcile distinct attacks by attack timestamp.
- **Lutsk:** two successfully retrieved stories independently refer to **six deaths** in an October 14 UAV attack; treat as one candidate incident, not 6+6 and not a certified October monthly total.
- **Poltava:** municipal notice reports **one death** Oct 17; confirm baseline credit and attack modality before any revision.
- **Khmelnytskyi:** initial Oct 19 report mentions two killed; late-death follow-up was **403**. No promotion of an unverified +1 from this capture.
- **Kropyvnytskyi:** police report of three deaths in a regional attack retrieved; city council page was **403**, so exact city attribution still requires review.
- **Zaporizhzhia:** Oct 22 Suspilne chronology and regional police statement fetched, each mentions three; corroboration is not proof of city-boundary attribution or baseline credit. Existing T03–T05 2→3 clarification still NEEDS_REVIEW.
- **Dnipro:** city Oct 20 candidate retrieved; other region/mixed report was 403. Do not infer final 20 October death count or unrelated incidents from the one 150-character excerpt.
- **Kharkiv:** the only target was 403. The earlier web-search report of a municipal monthly figure is not physical capture proof and cannot be imported here.
- **Remaining 11 cities:** no vetted URL in this particular exact-27 grant; source absence != 0 deaths, and successful HTTP never proves full October coverage.

## Next gated work

1. Offline reconcile existing **short evidence fragments and historical city baselines** by city/attack date/weapon/identity; record `NEEDS_REVIEW` where exact date, geography, air modality or baseline credited status is unknown. No more source GET covered by this spent grant.
2. Develop a separate source-coverage plan for the 12 cities without retrieved responses and for six failed URLs, distinguishing city monthly official report from community/oblast all-hostilities totals.
3. Prepare a fully reconciled October air-only **city** monthly dataset with explicit partial coverage and an approval gate; request **separate owner GO** for new publisher GET or any site-prod publication. Do not silently backfill with zeros or double-count updates.

Production, C2, Neon, Netlify, `site-prod` and operational WIP were not modified by this research one-shot. `PROMOTE=OFF`.
