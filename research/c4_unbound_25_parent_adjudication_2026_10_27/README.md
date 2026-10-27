# C4 — exact 25 historically UNBOUND classification parents (research only)

The immutable 25-row cohort comes from `3d10cb3c3509c6945f9c9f3cdf02d8cfae46d143` / Git blob `9676e3d559a22ef8989c43604dce85dab95fa38b`. It is **not** the separate 25 H1 first-state repair cases. No classifier rerun or Neon query was used.

## Bounded findings

- The **exact 25** accepted classification UIDs/keys/cities/cohorts have **25 exact, independent historical alert-interval witnesses** in six pre-existing Git source slices (5 H1 / 20 H2). Each record includes a pinned **source commit + path + blob SHA + original row index**.
- All **25 canonical deterministic episode keys** are independently computable from original historical city and UTC start/end. The 18 Kyiv municipality records carry **native municipal source IDs different from the canonical SHA24**: their original exact timezone-aware intervals, rather than fuzzy proximity, independently recover the accepted canonical ID. The five H1 and two Kharkiv original IDs match directly.
- Three Lviv source records retain microsecond fractions absent from the previously frozen Neon snapshot projection at millisecond precision. The immutable full-precision source establishes the deterministic canonical key. A rounded/truncated timestamp must **not** be used for parent admission.
- **Zero** of the 25 cases has a positively established, eligible canonical *database parent row UID* or accepted permanent UNBOUND exception. The accepted historical read-only snapshot found **0/25** matches by canonical ID and **0/25** exact city+interval matches. This does **not** establish causal failure of the parent writer, durable parent absence, or that the historical episode is false.
- The accepted contract blob `e9dcbdf21551ca086fbf096138f885f453a8c2b0` permits `UNBOUND` / NULL when there is no exact eligible parent; this is a **conditional storage rule**, not an automatic acceptance of any historical exception. No reparenting or fuzzy-time admission is approved.
- All 25 final **parent-admission** determinations remain `NOT_PROVEN`: 25 real original historical episode identities are distinct from 25 demonstrated Neon parent entities. Affirmative contradictions: **0 established**, not proof of universal consistency. `C4 = NOT PROVEN`.

## Follow-up under separate authorization

Inspect the precise canonical-parent ingestion and materialization scope for the 25 original source intervals, and obtain an independently pinned canonical Neon-parent UID / closed AIR row / exact full-precision start-end / canonicalization-v1 and historical writer lineage before proposing any binding. For Kyiv, preserve the exact municipal-ID crosswalk. For Lviv, preserve original microsecond precision. If no eligible parent was ever materialized, evaluate the contractual `UNBOUND` exception per case; no repair/backfill/production change under this research authorization.

## Verification

Run:

```bash
python3 research/c4_unbound_25_parent_adjudication_2026_10_27/verify_independent.py --negative-tests
```

The checker uses `git rev-parse <commit>:<path>` to confirm each expected commit/blob SHA, loads **actual immutable original Git blobs** with `git cat-file`, compares every classification identity with the immutable 25-row original proof, rederives each source episode key with full timezone and microsecond precision, and rejects 17 tampered or incomplete cases. The workflow `.github/workflows/c4-unbound-25-offline.yml` obtains exact historical commits and emits an offline receipt. This does not inspect live Neon or run the classifier. Nothing is deployed to production.

**Important limit:** the registry deliberately does not claim to establish *why* the materialized canonical parent is missing. The historical cause remains `NOT_PROVEN` until an independently reviewed historical writer/inventory proof is available.
