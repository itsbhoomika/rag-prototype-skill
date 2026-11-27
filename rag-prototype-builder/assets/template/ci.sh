#!/usr/bin/env bash
# Local CI pipeline. Run before every commit of a major change.
#   ./ci.sh          all offline stages (free, deterministic, no keys)
#   ./ci.sh --live   also runs a real-provider smoke + eval (uses your .env key, costs money)
# Stops at the first failing stage, like a CI server.
set -uo pipefail
cd "$(dirname "$0")"

PY=.venv/bin/python
LIVE=0; [ "${1:-}" = "--live" ] && LIVE=1
RESULTS=()

stage() {  # stage "<name>" <command...>
  local name="$1"; shift
  echo -e "\n=== $name ==="
  local start=$SECONDS
  if "$@"; then
    RESULTS+=("PASS  $name ($((SECONDS - start))s)")
  else
    RESULTS+=("FAIL  $name")
    summary; echo -e "\nCI FAILED at: $name"; exit 1
  fi
}

summary() { echo -e "\n=== Summary ==="; printf '%s\n' "${RESULTS[@]}"; }

setup_check() {
  [ -x "$PY" ] || { echo "No .venv. Run: uv venv && uv pip install -r requirements.txt"; return 1; }
  $PY -c "import fastapi, numpy, pypdf, anthropic, openai" && echo "dependencies import OK"
}

static_checks() {
  $PY -m compileall -q backend tests >/dev/null && echo "syntax OK" || return 1
  # The skill's rule checker (copied in by scaffold.py): client filters, silent fallbacks, the
  # citation guard, untrusted-text handling, innerHTML, CDNs, key-shaped strings, .env in git.
  [ -f scripts/check_rules.py ] || { echo "scripts/check_rules.py is missing: re-copy it from the skill"; return 1; }
  $PY scripts/check_rules.py .
}

live_smoke() {
  # A live check must use a real model and must fail when golden items fail.
  $PY -m backend.cli doctor --require-real || return 1
  $PY -m backend.cli ingest >/dev/null && $PY -m backend.cli eval --label ci-live --strict
}

stage "1. Setup"              setup_check
stage "2. Static checks"      static_checks
stage "3. Unit tests"         $PY -m pytest -q tests/test_pipeline.py
stage "4. API tests"          $PY -m pytest -q tests/test_api.py
stage "5. Regression tests"   $PY -m pytest -q tests/test_regression.py
[ $LIVE = 1 ] && stage "6. Live provider eval" live_smoke

summary
echo -e "\nCI PASSED$([ $LIVE = 0 ] && echo ' (offline stages; run ./ci.sh --live before a demo)')"
