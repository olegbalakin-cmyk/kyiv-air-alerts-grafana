# Targeted single-item BBC original URL resolution

SOURCE = frozen 2026-10-12 Google News RSS first BBC item, immutable commit 8334442092a24f5eace79c1d9212610d33e53655.

Only archived RSS and Google HTML gzip raw entities were copied byte-for-byte. No original Set-Cookie or identifier-bearing response headers were copied. If signed params exist, the only permitted source-side request is one POST to Google's Fbv4je endpoint, with no cookies, redirects or retries. No BBC HTTP connection, article-body fetch, fresh RSS, production or DB actions.

This is a new independent research proof, NOT accepted production integration.
Use the independent offline verifier with two clean copies before freezing.
