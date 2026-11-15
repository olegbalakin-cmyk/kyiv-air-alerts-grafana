# CASUALTY Work AC — bounded RSS/source evidence (staging OFF)

## Immutable bases / scope

- Work AB PR #163: `4604004bd7399975c7b4d4cc87c0a43fcb4cd403`.
- WIP baseline: `e30f109837a07b43d21dd83db175fb9bf5ccaa29`.
- Work AA PR #160 technical PASS, saved Work Z evidence PARTIAL; T03–T05 remain NEEDS_REVIEW.
- Main checked at `b98bfb15f86098818bb3ce44cad4e6a39b17f99b`; PR #147 already merged with operator and generator hard-OFF.
- Existing schedule unchanged: `45 */4 * * *`.

## Minimal code change

- `monitor_casualty_candidates.py`: maximum 23 RSS GET attempts/tick, timeout 15s, zero automatic retries, no redirects, one combined search/city, independent eight-day window + 48h overlap; only successful RSS advances cursor.
- `casualty_workac_capture.py`: technically allowlisted HTTPS publisher capture, 10 attempts/tick, 8s socket connect, 20s total deadline, max 2 MiB compressed/decompressed, redirects OFF, no auth/proxy, all resolved IPs must be globally routable and TLS must validate original hostname. Bodies exist only in memory; Work J-style article/main stripping and existing Work AA sentence evidence go to existing Work X index; never creates incident IDs/automatic credits.
- New opt-in switches `--source-http`, `--article-http`, `--wip-evidence-writes` are separate; all default OFF. Legacy `--retained-facts` continues to work.
- RSS state remains `data/casualties/candidate_monitor_state.json`; article attempts and retained indexed cards live in separate proposed WIP paths `data/casualties/candidate_article_capture_state.json`, `data/casualties/candidate_evidence_index.json`.
- Offline tests live under `research/casualty_workac_shadow_2026_11_15/` and reuse the existing `test-explosion-monitor-wip.yml` CI only on isolated Work AC branch.

## Exact original-host allowlist (code policy, not owner HTTP consent)

`suspilne.media`, `zprz.city`, `ukrinform.ua`, `www.ukrinform.ua`, `mig.com.ua`, `zabor.zp.ua`, `shelter.in.ua`, `radiosvoboda.org`, `interfax.com.ua`, `1news.zp.ua`, `spravzhne.media`, `zp.npu.gov.ua`.

Allowlist is rooted in existing Work J research source list, not a new authorization. Google News opaque redirect URLs cannot be unwrapped by this adapter. Such candidates remain unresolved for separate reviewer/source mapping. First controlled cycle therefore may produce fewer than 10 captured pages, including zero, depending on source direct-link availability.

## Draft existing-workflow activation patch — NOT APPLIED

Change only `.github/workflows/casualty-monitor-wip.yml` after a separate owner GO and exact new WIP code pin. Keep its current cron and checkout semantics. Replace the current `--local-only` runner step with a command that passes `--independent-source-check --source-http --article-http --wip-evidence-writes` only when *each* separately reviewed repository variable is true. Preserve a local-only fallback when disabled. Before any enabled run, confirm Work AC code is present on the workflow's checked-out WIP ref; main-only code does not suffice.

Add to the existing WIP-only git add allowlist precisely the two files above, alongside the existing queue/state/report files, *only when WIP evidence writes opt-in is on*. In the validation step assert `automatic_credits == 0`, `PROMOTE == "OFF"`, `article_gets <= 10`, `rss_http_requests_this_run <= 23`, and 23-city summary. The WIP report should emit new/retained cards, errors, duplicates and follow-up cursor status. No new workflow, no schedule change.

## First controlled cycle gates (not authorized)

Owner specifies exact code HEAD, source allowlist, RSS 23 GET/15s, article 10 GET/8s connect/20s deadline/2 MiB, and the two WIP persistence paths. Pin live WIP HEAD/queue/state hashes before and after. Require 23 planned cities, all attempted GET counted, at least one direct-first-party article transformed into reviewable bounded card, 0 raw HTML, 0 automatic credits, no PROMOTE and no main/site-prod/C2/Neon/Netlify changes. Halt and disable all opt-ins for any unexpected egress, missing continuity, duplicate publication, corrupt evidence or mutated production. Do NOT reuse Work Z launch.

Rollback: disable three opt-in flags first, preserve exact WIP queue/cursor snapshot, revert only approved changes on current WIP using a fresh PR/fast-forward commit (no force-push), never rewind other track's changes. Existing WIP HEAD before changes `e30f109837a07b43d21dd83db175fb9bf5ccaa29`.

## Outstanding readiness checks

- Google News feed often contains opaque aggregator URL; current strict no-redirect, publisher allowlist intentionally blocks these until a separately verified direct-source mapping exists. 23 city RSS polling is possible, but automatic publisher body coverage for arbitrary new candidates is not yet established.
- Existing Work AA context selection extracts reviewable hints, not reliable counted deaths. Without the real Work J counting/incident-scope mechanism wired in, automatic evidence cards have `claim_deaths=null` and must not be treated as full Work J factual extraction.
- CI result, exact SHA/ZIP inner hashes and saved-proof audit must be recorded from GitHub Actions before any READY_FOR_SHADOW_GO.
- T03/T04/T05 and all unresolved new incidents stay NEEDS_REVIEW.

**Activation:** strictly OFF. **PROMOTE:** OFF. **Production mutation:** none from this branch.
