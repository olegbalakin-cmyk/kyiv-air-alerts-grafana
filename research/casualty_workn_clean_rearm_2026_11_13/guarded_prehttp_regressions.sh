#!/usr/bin/env bash
# Safe conversion from the live launch-present checkout to a temporary
# offline test state. The source capture step MUST NOT run if tests fail.
set -euo pipefail
launch=research/casualty_one_time_capture_2026_11_13/launch.json
test -f "$launch"
before="$(sha256sum "$launch" | cut -d' ' -f1)"
temporary="$(mktemp)"
restore() {
  if [ -f "$temporary" ]; then
    mv -f "$temporary" "$launch"
  fi
}
trap restore EXIT
mv -f "$launch" "$temporary"
test ! -e "$launch"
python -m unittest research.casualty_evidence_ingestion_2026_11_13.test_ingest research.casualty_controlled_capture_preflight_2026_11_13.test_preflight research.casualty_strict_redirect_2026_11_13.test_redirect research.casualty_fact_retention_workj_2026_11_13.test_workj research.casualty_one_time_capture_2026_11_13.test_workk research.casualty_one_time_capture_2026_11_13.test_workl -q
restore
trap - EXIT
test -f "$launch"
test "$(sha256sum "$launch" | cut -d' ' -f1)" = "$before"
git diff --exit-code -- "$launch"
echo 'WORKN_LIVE_SAFETY_TESTS_68_PASS_GRANT_RESTORED_ZERO_SOURCE_GET'
