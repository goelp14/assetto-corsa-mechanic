#!/usr/bin/env bash
# One command: sync all VRE sessions and open the replay viewer.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
exec python3 external/query_tools/replay_launcher.py "$@"
