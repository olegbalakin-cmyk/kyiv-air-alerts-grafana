# C4 Kharkiv #6 - contemporaneous minute-level corroboration of long alert

**Research addendum (2026-10-28), not final source adjudication. No production / Neon writes.**

## New external evidence

1. **ZN.UA, published 2025-03-06 05:01 local and subsequently updated**: ["Шахед" влучив у харківську багатоповерхівку - Терехов](https://zn.ua/ukr/war/shakhed-vluchiv-u-kharkivsku-bahatopoverkhivku-terekhoa.html). The contemporaneous article explicitly says the **city of Kharkiv** air alert continued from **2025-03-05 21:08 local** and was **cancelled at 2025-03-06 05:03 local**, lasting almost eight hours. These are **minute-level reported** times; they corroborate the owner-exported Alerts.in.ua original interval `2025-03-05T19:08:24Z` to `2025-03-06T03:03:45Z` to the minute. Source access: live publisher HTML, 2026-10-28; lines of article indicate it is updated, with post-publication all-clear appended. This is an independent **publication**, but its alert-data upstream is **not established independent of Alerts.in.ua/official app**. It is *not* a primary same-hromada ON/OFF trace and does not certify exact seconds.
2. **Kharkiv Oblast Military Administration, published 2025-03-12**: [Official description of differentiated alerts](https://kharkivoda.gov.ua/news/130659). Confirms Kharkiv began differentiated *city vs oblast* alarms starting 2025-02-22 and names dispatch via regional civil defense to city emergency coordination. This makes identifying the exact municipal territory mandatory. It does not resolve the March 5-6 individual ON/OFF chronology. The production Kharkiv dataset has its own earlier known-coverage convention; this article alone is not permission to alter that implementation.

## What changes in confidence

- Prior [research `3218f76e9078a6c8500825183dedb151437454ac`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/3218f76e9078a6c8500825183dedb151437454ac) judged source end `2025-03-05T19:47:55Z` (Vadimkin/current canonical) vs `2025-03-06T03:03:45Z` (original Alerts.in.ua) **unresolved**.
- ZN.UA now gives **contemporaneous corroboration for the long timeline**, making the long interval more plausible. An unexplained **21:47 local** all-clear remains evidenced **only as a Vadimkin-derived dataset boundary**, not a verified same-hromada official message. The journalistic description of a continuous almost-eight-hour city alert argues against a simple 39-minute-only alert, but it cannot rule out a brief intermediate cancellation and reannouncement.
- **Status remains `BLOCKED_SOURCE_CONFLICT`** because no verified sequence of 2025-03-05 19:47:55Z through 2025-03-06 03:03:45Z AIR state transitions for the exact Kharkiv city territorial community was captured, and the owner CSV's geographic field was not re-opened in this addendum.

## Next narrow test

Seek an archived authenticated primary **city-hromada** AIR ON/OFF log (official authority-operated app/alert channel, or dispatch register), and check specifically (a) whether an OFF occurred at **2025-03-05T19:47:55Z** (21:47:55 local), (b) any subsequent ON until **2025-03-06T03:03:45Z** (05:03:45 local), (c) exact geographic identifier and timezone. If an earlier OFF is verified, determine whether ZN.UA summarized a sequence as one alert. If not, investigate Vadimkin/producer early closure as an isolated candidate. Avoid another broad study or repeated manual CSV request.

**Data remains unchanged:** canonical `a556ee0d-4a90-40b4-adf1-db55646cd05b`; classification `8c01721e-b4e8-4b63-b789-9801efbd63f8` remains `STRICT_EVENT_POSITIVE/UNBOUND`; ACTIVE event `dc3a63ec-d9f8-412c-b0a1-09dd9398b27b` preserved under previously accepted readback. No new SQL readback in this addendum. Other 24 C4 cases and C3 proceed independently.
