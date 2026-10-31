# Offline fixture recovery

Derived ZIPs and cache directories stay local. All 65 original member hashes remain in `provenance.json`.

Immutable sources:

- Evidence commit `9704d5fa02c23ecc28c452c06b44639dc757107b`, tree `52a10e92d22c6ae69f91f01bd27a34937a286221`.
- Archive path `research/neon_23city_continuity_2026_10_31/proof/41208139352/full_evidence.zip`, Git blob `b6e558b201433fe64c4524058dc8807457a3088a`, SHA-256 `5a011fae488c3efc5994b45818f8e473d85aba08eadd3bfa39d0c9be800bcd55`.
- Readback member `cycle-2/generation/neon_readback.json`, SHA-256 `8f1278d3402d9827af2dd262f22c18c9bed36812c85558674e0324bce35fe490`.
- Production input commit `0ecbb291e8f443f7ab366bc4ac033d096f2c44f4`, subtree `kyiv-air-alerts-grafana/`.

With those commits already available in the local Git object database:

```sh
python -m scripts.neon_json_shadow_restore_fixtures
```

This writes `fixtures/cache/` from local `git show` only. It verifies the archive SHA, all 85 original manifest hashes and every reconstructed member hash, including the exact original payload bytes. It never fetches, connects to Neon, captures HTTP or generates frontend JSON. A missing Git object fails explicitly; retrieve only the two exact commits through authenticated Git before retrying. An existing cache is never overwritten.

Three small records under `contracts/` reproduce the original explicitly synthetic C2 receipt/status and snapshot overlay. They do not establish a physical COMMIT or source freshness. The archived SELECT omitted `canonicalization_version`; the declared local overlay adds it and one synthetic corpus run solely for offline contract testing. Physical mode rejects the fixture receipt.

The loader accepts the verified directory cache or the original locally retained ZIPs. No complete AIR episode archive is added to the research branch.
