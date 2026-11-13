# Work N — live launch-present pre-HTTP test fix

**Status:** research-only; no owner authorization for this modified HEAD, and no live HTTP.

## Proven latent blocker
At immutable approved Work N `4ae85477491c6d5ada65200ad470f0f9964978b3`, the live workflow insists on a `launch.json`-only push then runs all 68 offline tests. Two offline-only cases require `launch.json` to be absent (`test_workk.py:test_01_exact_three_targets_default_off`, `test_workl.py:test_03_no_grant_and_no_live_launch_in_tree`). A real launch commit would necessarily fail both before the HTTP step. The previously approved exact Work N SHA therefore must NOT be activated.

## Narrow isolated repair
- Fresh research branch from Work N frozen head; do not change PR #127.
- Rebind the single-use live workflow and `run_capture.py` branch guard to this fresh branch. All publisher source URLs, hard resource limits, provenance rules and prior one-shot protections stay unchanged.
- Execute all 68 offline tests with the tracked launch file temporarily moved out of the checkout, with an EXIT trap restoring it even on failure. Refuse to continue to capture unless the tests pass, the launch file has been restored byte-for-byte and Git shows no changes.
- The offline CI proves this sequence with a synthetic `launch.json`, no owner authorization and no source HTTP.

## Next approval
After exact-head GitHub Actions proof, request a new owner grant naming the **new** exact prelaunch SHA/branch. Do not reuse earlier approvals, grant IDs or launch commits. No merge, deploy, WIP/casualty JSON/C2/Neon, auto credit, or production mutation.
