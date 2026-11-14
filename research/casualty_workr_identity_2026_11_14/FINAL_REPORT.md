# WORK R — incident identity preflight (OFFLINE ONLY)

Verdict: **SOURCE_REVIEW_REQUIRED**. All three pair decisions: **INSUFFICIENT_EVIDENCE**. No matching, death credit, PROMOTE, casualty JSON, production publication, or source HTTP.

## Frozen upstream and verified original evidence

- Parent Work Q: `858e255ebea543383a9ca95d07847a40e22742e6`, PR #135, Actions #43571952329 SUCCESS (145 PASS, 0 FAIL, 1 SKIP), proof #14104761484 SHA256 `90ec4ef12c967facc743914316da41e99b6d9d0237350b16437cd820bad451d5`.
- Work P run #43521321878, artifact #14082589637, externally SHA256-verified `67133a7b2e94fdcdf8c1a4bf3871788b691e35b3666430b976e082355675b99f`; 4/4 internal manifest hashes matched. 3 HTTP 200, 3 GET, no redirect; four short excerpts, three NEEDS_REVIEW, zero credits.
- Work P T03: 22 Oct publication at 15:26 UTC; excerpt "Загинули двоє людей"; separate excerpt says deceased couple aged 37/38. Count 2 is only locally proven; article-wide count unverified.
- Work P T04: 22 Oct publication at 19:39:52 UTC; excerpt "Пізніше стало відомо, що загинула також 69-річна жінка." Additional death, NOT a cumulative total, and 69 is an age.
- Work P T05: police excerpt explicitly lists 3 dead: husband 37, wife 38, another woman 69. Article published_at missing. `attack_slot_hint_not_identity=09:56` is not proven the time of the attack. No explicit attack date or verified independent linkage. No article HTML or full text retained.
- Age overlaps support an investigative hypothesis; they do not establish incident identity. The case_id `oct22` and Zaporizhzhia queue candidate city label are routing metadata, not source-level proof of attack date or locality.

## Pair decisions

| Pair | Supporting retained evidence | Critical gaps | Decision |
|---|---|---|---|
| T03 / T04 | Same calendar date of publication; T03 37/38-year-old spouses, T04 later 69-year-old woman | Date/time of actual attack; same location and target; explicitly connected sequence | INSUFFICIENT_EVIDENCE |
| T03 / T05 | Exact couple ages and relationships 37/38 | Attack date, locality, temporal slot, same struck object and direct police link | INSUFFICIENT_EVIDENCE |
| T04 / T05 | 69-year-old female deceased | Actual attack date/place/time/object and police attribution to this event | INSUFFICIENT_EVIDENCE |

The same locality/date/number (even if later established) is insufficient by itself. No automatic 2+1 calculation and no police 3 transferred to a publisher.

## Narrow in-memory evidence adaptation

Reuses existing `run_capture.retain_results` after `controlled_capture`. Adds only bounded, optional incident-review clues to `minimal_capture_facts.json`, extracted from volatile article text in memory; **not** a new parser, collector, publisher, matching service, or new network path. Clues are labeled unverified: date mention, geographic mention, time mention, weapon/impact, struck-object mention, sequence cue and reference to official source. Sentence-order is retained but is **not** an attack timeline. Maximum eight stand-alone deidentified excerpts per source, each <=170 chars, combined max 650 chars and <=25% of transient source text, with hashes; unsafe names, full addresses, contact data, longer sentences and paragraphs are withheld. Response SHA256 and extracted text SHA256 remain recorded by existing code. Explicit source-independent fields remain null; all cards NEEDS_REVIEW.

Runner exact branch and existing one-shot live workflow branch restricted to the new research branch. Work K/Work M ancestry, scope, owner identity, grant expiry, source URL allowlist, single-launch SHA/commit, one-shot controls, redirect limits, default OFF, no automatic publish all remain enforced. The Work O offline workflow triggers on Work R; the only live trigger remains an owner actor first-attempt push containing `launch.json` and must pass exact owner/ancestry checks. No launch file or new owner grant was created.

### Information required in a separately authorized **future** one-time capture

For **each** T03/T04/T05: source attack date separate from publication time; whether location is Zaporizhzhia city or another part of oblast; explicit time/period of attack; attack type and struck object; safely deidentified chronology of earlier/later casualty statements, without adding deaths; explicit evidence, if any, of cumulative 2->3 correction; evidence police report relates to the same location/time/target. Capture text transiently in memory, retain only bounded evidence clues and the existing hash receipts; no full HTML, full article, victim names or private street addresses. If an ambiguity remains, no incident match. Do not enlarge source list. T05 needs special attention because its URL and excerpt do not independently establish the specific incident.

URL allowlist exactly frozen at `research/casualty_one_time_capture_2026_11_13/capture_plan.json`:
1. https://www.ukrinform.ua/amp/rubric-regions/4177207-armia-rf-zavdala-udaru-po-zaporizzu-zaginuli-dvoe-ludej.html
2. https://mig.com.ua/vorozhyy-udar-po-pryvatnomu-budynku-v-zaporizhzhi-zahynuly-troye-lyudey/
3. https://zp.npu.gov.ua/news/na-zaporizhzhi-cherez-rosiiski-ataky-zahynulo-troie-liudei-shche-odna-otrymala-poranennia-politsiia-dokumentuie-naslidky-voiennykh-zlochyniv

## Owner approval request, **NOT AUTHORIZATION**

New clean branch: `research-casualty-workr-identity-2026-11-14`; exact **prelaunch** HEAD must be the final HEAD of this PR after physical exact-head CI success. Owner must confirm the exact 40-character SHA in a **new and separate explicit approval**; this report is not an authorization.

- Exactly those three original URLs; maximum 3 initial GET, 6 total including redirects; **no redirects preapproved**; >=1s between requests; <=1,000,000 bytes per response; 15-second timeout, no retries; one single use, authorization expires within 24h.
- In-memory full extracted text, never persist full HTML/articles, victim names, private exact addresses; store only bounded review facts/excerpts <=170 chars and response/text SHA256. All results NEEDS_REVIEW and no incident matching/credits/PROMOTE/publication.
- Do NOT create authorization ID or launch.json before a new owner reply. This Work R task grants no HTTP permission.

Proof gates on final HEAD: frozen 68 + Work O/J/E + Work A + Work P/Q + Work R, launch and ancestry, original 18->20->23 unchanged; five blocked groups remain blocked. Artifact SHA256 must be physically recorded before final release preflight can be marked PASS.

Do not merge, deploy, touch PR #71/#117 or prior research PRs, casualty JSON, WIP, C2, Neon, or production.
