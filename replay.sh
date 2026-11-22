#!/usr/bin/env bash
# One command: sync all VRE sessions and open the replay viewer.
#   ./replay.sh                                  AC sessions + existing Lap Studio bundles
#   ./replay.sh --rpy me.rpy[:Label] [--ref fast.rpy[:Label]] [--id NAME]
#                                                build an ACC Lap Studio bundle first, then open it
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
BUNDLE_ARGS=()
LAUNCH_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --rpy|--ref|--id|--car-index|--ref-car-index|--setups-dir|--laps)
      BUNDLE_ARGS+=("$1" "$2"); shift 2 ;;
    *) LAUNCH_ARGS+=("$1"); shift ;;
  esac
done
if [[ ${#BUNDLE_ARGS[@]} -gt 0 ]]; then
  python3 -m external.query_tools.acc_replay_bundle "${BUNDLE_ARGS[@]}"
fi
exec python3 external/query_tools/replay_launcher.py "${LAUNCH_ARGS[@]+"${LAUNCH_ARGS[@]}"}"
