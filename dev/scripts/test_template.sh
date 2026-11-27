#!/usr/bin/env bash
# Functional test: scaffold the template into fresh temp folders, install, and run the app's own CI.
# Proves the bundled app works as a user gets it, on both paths. No API keys needed.
#   1. with sample data: ./ci.sh passes, rule check passes, and ./ci.sh --live REFUSES the stub
#   2. --no-sample (owner brings documents): ./ci.sh still passes, because tests use tests/fixtures
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT

build() {  # build DIR [scaffold flags...]
  local dir="$1"; shift
  python3 "$ROOT/rag-prototype-builder/scripts/scaffold.py" "$dir" "$@" >/dev/null
  cd "$dir"
  git init -q .   # ci.sh checks that .env is not tracked by git
  if command -v uv >/dev/null; then uv venv -q && uv pip install -q -r requirements.txt
  else python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt; fi
  cp .env.example .env
}

echo "### 1. Sample data"
build "$WORK/sample"
./ci.sh
python3 "$ROOT/rag-prototype-builder/scripts/check_rules.py" .
sed -i.bak 's/^LLM_PROVIDER=.*/LLM_PROVIDER=offline/' .env && rm -f .env.bak
if ./ci.sh --live > live.log 2>&1; then
  echo "FAIL: ./ci.sh --live passed with the offline stub"; tail -20 live.log; exit 1
fi
grep -q "needs a real model" live.log || { echo "FAIL: --live failed for the wrong reason"; tail -20 live.log; exit 1; }
echo "OK: ./ci.sh --live refuses the offline stub"

echo "### 2. --no-sample"
build "$WORK/nosample" --no-sample
./ci.sh
echo "TEMPLATE FUNCTIONAL TEST PASSED (sample, live-refuses-stub, no-sample)"
