#!/usr/bin/env bash
# Validate the skill, then zip it for upload (Claude.ai > Settings > Capabilities > Skills).
#   ./dev/scripts/package.sh        -> dist/rag-prototype-builder.zip
set -euo pipefail
cd "$(dirname "$0")/../.."   # repo root
SKILL=rag-prototype-builder
python3 -c "import yaml" 2>/dev/null || { echo "PyYAML missing: pip install pyyaml"; exit 1; }
python3 dev/scripts/validate_skill.py "$SKILL" >/dev/null || { python3 dev/scripts/validate_skill.py "$SKILL"; echo "Validation failed: not packaged"; exit 1; }
mkdir -p dist && rm -f "dist/$SKILL.zip"
zip -qr "dist/$SKILL.zip" "$SKILL" -x '*/__pycache__/*' '*.pyc' '*/.DS_Store' '*/.venv/*' '*/.index/*' '*/logs/*' '*/eval_runs/*' '*/.pytest_cache/*'
echo "Packaged dist/$SKILL.zip ($(du -h "dist/$SKILL.zip" | cut -f1), $(unzip -l "dist/$SKILL.zip" | tail -1 | awk '{print $2}') files)"
