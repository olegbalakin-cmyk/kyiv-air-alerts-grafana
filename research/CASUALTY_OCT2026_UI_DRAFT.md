# CASUALTY — October verified-event lower-bound UI integration (isolated draft)

Status: PREVIEW / OFFLINE PROOF PENDING, NO PUBLICATION, PROMOTE=OFF.

Source of truth: PR #236, commit 270702ccc4a76d81ee8cc5b9cf73059fd19df025, Actions #45073045655 SUCCESS, frozen 23-city partial snapshot. 4 event groups: Lutsk 6, Poltava 1, Ivano-Frankivsk 1, Khmelnytskyi 3; 19 city-months unknown, not zero. The 11 is an **event-only lower-bound subtotal**, not an October monthly total.

This separate branch is based on locked site-prod@175c4254f11084005523e423e98a307da98c0fe9. It does NOT modify the generator, real casualty data, confirmed revisions, historical baselines, main, site-prod or Neon.

Frontend draft only:
- Read local frozen sidecar with explicit feature gate, default OFF in production. Validate all 23 series end at 2026-09; reject data drift/October duplicates and unsafe schema.
- Single city: October sidecar bar is orange, explicitly **at least** N. Unknown is null (not zero), with a visible note.
- Comparison: all 23 cities carry October display-month; each selected city has independent lower-bound / unknown semantics.
- Annual data: October lower bounds excluded from 2026 sums; label as January–September only.
- CSV: per-city status column identifies lower bound, unknown, and reconstructed month/year. Source links are displayed for verified cities.
- UA/EN texts, mobile and browser rendering must be physically checked before proposing promotion.

Next gates: independent CI pass; actual 23-city browser QA in a draft-only preview, including UA+EN mobile and CSV; generator/site-prod Git-only sidecar authoring contract with fresh baseline/credited proof; explicit owner publication GO. No Netlify production deploy, site-prod mutation, Neon writes or collector GET under this checkpoint.
