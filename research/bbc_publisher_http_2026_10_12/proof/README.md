# Isolated BBC publisher single-GET HTTP proof (unaccepted)

Exact URL: `https://www.bbc.com/ukrainian/articles/ck9dzex1zp3qo`.

Verdict: `ISOLATED SINGLE-BBC-PUBLISHER HTTP CAPTURE = PARTIAL`.

Original publisher entity bytes were stored only in a GitHub-hosted runner private temporary file (directory mode 0700, file mode 0600) for offline verification. They are not in this repository, its Git objects, logs or Actions artifacts, and were deleted after execution. This is not durable preserved publisher evidence.

`observation.json` contains client-observed transport metadata and the captured raw entity SHA-256. `verify_A.json` is the offline gzip/HTMLParser check, `verify_B.json` is the separate offline zlib/regex check. Both inspect one ephemeral raw snapshot; these are distinct implementations, not third-party independent confirmation or later durable read-back. `adjudication.json` distinguishes transport, exact article identity, completeness and preservation. `sha256_manifest.json` authenticates the public-safe metadata only.

This proof does not establish BBC first availability, casualty detection latency, monitoring recall or G1 eligibility. Production, historical data, main, site-prod, casualty WIP, Neon, source monitors and the predecessor proof were not modified.
