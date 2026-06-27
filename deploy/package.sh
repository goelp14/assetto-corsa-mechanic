#!/usr/bin/env bash
# Build a Content Manager–installable zip (drag onto CM window).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE="${REPO_ROOT}/ac_app"
OUT_DIR="${REPO_ROOT}/dist"
ZIP="${OUT_DIR}/VirtualRaceEngineer.zip"
STAGE="${OUT_DIR}/.package_stage/VirtualRaceEngineer"

rm -rf "${OUT_DIR}/.package_stage"
mkdir -p "$STAGE" "$OUT_DIR"

if command -v rsync >/dev/null 2>&1; then
    rsync -a \
        --exclude 'data/baselines/*' \
        --exclude 'data/setup_memory/*' \
        --exclude 'data/sessions/*' \
        --exclude 'data/grip_map/*' \
        --exclude 'data/engineer_voice.txt' \
        --exclude '__pycache__' \
        --exclude '*.pyc' \
        "${SOURCE}/" "${STAGE}/"
else
    cp -a "${SOURCE}/." "${STAGE}/"
    rm -rf "${STAGE}/data/baselines/"* "${STAGE}/data/setup_memory/"* \
        "${STAGE}/data/sessions/"* "${STAGE}/data/grip_map/"* 2>/dev/null || true
fi

mkdir -p "${STAGE}/data/baselines" "${STAGE}/data/setup_memory" "${STAGE}/data/sessions" "${STAGE}/data/grip_map"
touch "${STAGE}/data/baselines/.gitkeep" \
      "${STAGE}/data/setup_memory/.gitkeep" \
      "${STAGE}/data/sessions/.gitkeep" \
      "${STAGE}/data/grip_map/.gitkeep"

rm -f "$ZIP"
if command -v zip >/dev/null 2>&1; then
    (
        cd "${OUT_DIR}/.package_stage"
        zip -rq "$ZIP" VirtualRaceEngineer
    )
else
    python3 - "$OUT_DIR/.package_stage/VirtualRaceEngineer" "$ZIP" <<'PY'
import os, sys, zipfile
root, out = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
    for dirpath, _, files in os.walk(root):
        for name in files:
            path = os.path.join(dirpath, name)
            arc = os.path.relpath(path, os.path.dirname(root))
            zf.write(path, arc)
PY
fi

rm -rf "${OUT_DIR}/.package_stage"
echo "Built: $ZIP"
echo ""
echo "Content Manager install:"
echo "  1. Drag $ZIP onto the Content Manager window, or"
echo "  2. Content Manager → Content → Install → select the zip"
echo "  3. Settings → Assetto Corsa → Apps → enable Virtual Race Engineer"
