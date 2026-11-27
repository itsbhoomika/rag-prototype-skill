#!/usr/bin/env bash
# Functional test: scaffold the template into a fresh temp folder, install it, and run its own CI.
# Proves the bundled app works exactly as a user would get it. No API keys needed.
set -euo pipefail
cd "$(dirname "$0")/../.."   # repo root
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
python3 rag-prototype-builder/scripts/scaffold.py "$WORK/app" >/dev/null
cd "$WORK/app"
git init -q .   # ci.sh checks that .env is not tracked by git
if command -v uv >/dev/null; then uv venv -q && uv pip install -q -r requirements.txt
else python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt; fi
cp .env.example .env
./ci.sh
python3 "$OLDPWD/rag-prototype-builder/scripts/check_rules.py" .
