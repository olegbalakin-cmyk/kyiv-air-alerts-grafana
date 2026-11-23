# CASUALTY — private encrypted full-body evidence (research only)

**Scope:** Work associated with PR #234 and Issue #257/PR #258. This is an **OFFLINE/DRAFT** upgrade, not permission to repeat the 27-GET collector or fetch the proposed 12 URLs. `PROMOTE=OFF`. No production, C6, Neon, Netlify or website writes.

## What changes

Previously `monthly_one_shot_collector.py` kept only `title`, a 150-character `context` and SHA-256 receipts. A successful publisher GET did not leave a replayable body. The new `private_body_archive.py` encrypts **the exact original HTTP response bytes and decoded body bytes** for each successful HTML/PDF response, in one authenticated AES-256-GCM record. The conventional `capture_report.json` still contains only brief context and hashes, plus **encrypted-record metadata**; no full text appears in logs, Git, CSV, JSON or unencrypted artifacts.

- `private-archive/sealed/<target_id>.sealed`: encrypted, authenticated original and decoded publisher bytes. Authenticated data includes URL, content type, target ID, observation timestamp, lengths, two SHA-256 hashes. Nonces are random and unique.
- `private-archive/evidence_index.json`: source URL, byte and cipher digests, sizes and ciphertext path. **No body**.
- Reviewers can recover and rehash the full article **locally in memory**, using their separately protected owner key. No plaintext copy is written to disk by `verify`.
- Encryption is **mandatory before any owner one-shot GO tag is spent or media GET attempted**. Missing/invalid key or unsafe output path means STOP, without network. An archive write error STOPs further GETs; there is no automatic retry or credit.
- Original 2 MiB raw and decompressed bounds, public-IP HTTPS, no redirects, no retries, owner actor/HEAD/manifest expiry, spent-GO one-shot tag and `PROMOTE=OFF` remain unchanged.
- The collector uses only a private `/tmp/casualty-monthly-*` output directory, with modes 0700 (directory) and 0600 (sealed file). It will not write evidence inside the git checkout.
- Each ciphertext artifact is useful only when the owner maintains the **32-byte key** independently. Key loss is permanent evidence loss; leaking the key defeats encryption. Do not put it into the repo, logs, pull request, workflow inputs, or any source manifest.

## Archive lifecycle and authorization

The workflow references a repository secret `CASUALTY_MONTHLY_ARCHIVE_KEY_B64`, containing a random, Base64-encoded **32-byte** key. Its value is never stored in artifacts. This secret is **not yet configured or verified**. Owner also needs a separate offline secure backup. The current GitHub Actions artifact retention is **30 days**; after a real approved run, the owner must move encrypted evidence into approved durable **access-controlled private storage** before expiry. Never put original publisher article bodies in a public repository or ordinary public artifact.

The current collector manifest in the inherited PR #234 remains the **old 27-target, already-spent** grant and its workflow is still pinned to `research-casualty-monthly-collector-2026-11-22`. **This Draft PR does not register a new live manual 12-URL collector.** Preparing a separate immutable 12-URL official publisher manifest, fresh owner one-shot grant, key provision, privacy/copyright review, and carefully gated network workflow remains a separate later task. Never auto-run this legacy collector because the code now archives encrypted bodies.

Capturing full text proves what a particular response said at capture time; it **does not** prove that a death is new, civilian, city-bound, non-duplicated or that all 23 city-month series are complete. Credit/revision release needs independent incident adjudication and a **separate owner publication GO**.

## Tests / proof

- Local offline synthetic encryption proof: eight tests run successfully in the preparatory environment (AES round trip HTML/PDF, original vs decoded, cipher tampering, metadata authentication, bad/missing key, invalid IDs, oversized body, symlinks/permissions, index replay protection).
- `test_private_body_archive.py`: same isolated unit regression included in the Draft branch; `test_monthly_one_shot_collector.py` adds whole-collector fake publisher-body replay and missing-key-before-GO regression. These tests make no publisher GET.
- The new branch is **not** a physically tested GitHub Actions collector; existing workflow is intentionally bound to its previous research branch. Any future owner-approved network run must obtain physical code/CI proof on its *exact* new pinned HEAD first.

To run only offline tests, in a private Python 3.12+ environment with `cryptography==46.0.4` installed, run:

```sh
python research/casualty_monthly_sources_2026_11_22/test_private_body_archive.py
python research/casualty_monthly_sources_2026_11_22/test_monthly_one_shot_collector.py
```

The second test exercises only synthetic transport, not a real source. Do not use `--capture` without a later separately owner-approved exact manifest.
