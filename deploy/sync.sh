#!/usr/bin/env bash
# Re-sync ac_app/ into the installed AC app (same as install.sh --copy).
exec "$(dirname "$0")/install.sh" --copy "$@"
