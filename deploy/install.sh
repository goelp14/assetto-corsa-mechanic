#!/usr/bin/env bash
# Deploy Virtual Race Engineer into Assetto Corsa apps/python/
# Run from repo root:  ./deploy/install.sh
#
# On WSL, defaults to rsync copy into the Windows AC tree (/mnt/c/...).
# Use --link for a Windows junction when the repo lives on the same NTFS drive
# (e.g. /mnt/c/Users/you/github/...). Junctions to \\wsl$ paths are not supported.
# Use --watch to keep copying on file changes (requires inotifywait).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE="${REPO_ROOT}/ac_app"
APP_NAME="VirtualRaceEngineer"
MODE="copy"
WATCH=0
OPEN_CM=0
AC_ROOT="${AC_ROOT:-}"

usage() {
    cat <<'EOF'
Usage: ./deploy/install.sh [options]

Options:
  --copy              Copy ac_app into AC with rsync (default on WSL)
  --link              Windows junction (only if repo is under /mnt/c, /mnt/d, ...)
  --watch             After install, re-sync when ac_app/ changes (needs inotifywait)
  --open-cm           Launch Content Manager after install (Windows)
  --ac-root PATH      Assetto Corsa install directory (WSL path)
  -h, --help          Show this help

Environment:
  AC_ROOT             Same as --ac-root

Examples:
  ./deploy/install.sh
  ./deploy/install.sh --watch
  ./deploy/install.sh --link    # repo cloned under /mnt/c/...
  AC_ROOT="/mnt/d/Games/assettocorsa" ./deploy/install.sh
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --copy) MODE="copy"; shift ;;
        --link) MODE="link"; shift ;;
        --watch) WATCH=1; shift ;;
        --open-cm) OPEN_CM=1; shift ;;
        --ac-root)
            AC_ROOT="${2:?--ac-root requires a path}"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

if [[ ! -d "$SOURCE" ]]; then
    echo "error: ac_app not found at $SOURCE" >&2
    exit 1
fi

on_windows_mount() {
    [[ "$1" == /mnt/[a-z]/* ]]
}

find_ac_root() {
    local candidates=(
        "/mnt/c/Program Files (x86)/Steam/steamapps/common/assettocorsa"
        "/mnt/c/Program Files/Steam/steamapps/common/assettocorsa"
        "/mnt/d/Program Files (x86)/Steam/steamapps/common/assettocorsa"
        "/mnt/d/Program Files/Steam/steamapps/common/assettocorsa"
        "/mnt/d/SteamLibrary/steamapps/common/assettocorsa"
        "/mnt/e/SteamLibrary/steamapps/common/assettocorsa"
    )
    local c
    for c in "${candidates[@]}"; do
        if [[ -f "${c}/acs.exe" ]]; then
            echo "$c"
            return 0
        fi
    done
    return 1
}

find_cm_exe() {
    local base
    for base in \
        /mnt/c/Users/*/Documents/content_manager \
        /mnt/c/Users/*/OneDrive/Documents/content_manager \
        /mnt/c/Users/*/Desktop/asseto_corsa_content_manager; do
        if [[ -f "${base}/Content Manager.exe" ]]; then
            echo "${base}/Content Manager.exe"
            return 0
        fi
    done
    return 1
}

rsync_excludes() {
    echo --exclude 'data/baselines/*'
    echo --exclude 'data/setup_memory/*'
    echo --exclude 'data/sessions/*'
    echo --exclude 'data/grip_map/*'
    echo --exclude 'data/engineer_voice.txt'
    echo --exclude '__pycache__'
    echo --exclude '*.pyc'
}

if [[ -z "$AC_ROOT" ]]; then
    if ! AC_ROOT="$(find_ac_root)"; then
        echo "error: could not find Assetto Corsa (acs.exe)." >&2
        echo "Set AC_ROOT or pass --ac-root /mnt/c/.../assettocorsa" >&2
        exit 1
    fi
fi

if [[ ! -f "${AC_ROOT}/acs.exe" ]]; then
    echo "error: acs.exe not found in AC_ROOT=$AC_ROOT" >&2
    exit 1
fi

TARGET="${AC_ROOT}/apps/python/${APP_NAME}"
PARENT="${AC_ROOT}/apps/python"
mkdir -p "$PARENT"

win_path() {
    # Use forward slashes so bash does not eat backslashes in cmd.exe arguments.
    wslpath -m "$1"
}

remove_target() {
    if [[ ! -e "$TARGET" ]]; then
        return 0
    fi
    if [[ -L "$TARGET" ]]; then
        rm -f "$TARGET"
        return 0
    fi
    if [[ "$MODE" == "link" ]]; then
        local win_target
        win_target="$(win_path "$TARGET")"
        cmd.exe /c "if exist \"$win_target\" rmdir \"$win_target\"" </dev/null >/dev/null 2>&1 || true
    fi
    if [[ -e "$TARGET" ]]; then
        rm -rf "$TARGET"
    fi
}

install_link() {
    if ! on_windows_mount "$SOURCE"; then
        echo "note: repo is on the WSL filesystem; junction to \\\\wsl$ is not supported." >&2
        echo "      Using rsync copy instead. Clone the repo under /mnt/c/... for --link." >&2
        install_copy
        return
    fi
    if ! command -v wslpath >/dev/null 2>&1; then
        echo "error: wslpath not found (are you on WSL?)" >&2
        exit 1
    fi
    local win_target win_source
    win_target="$(win_path "$TARGET")"
    win_source="$(win_path "$SOURCE")"
    remove_target
    cmd.exe /c "mklink /J \"$win_target\" \"$win_source\"" </dev/null
    echo "Linked (junction): $TARGET -> $SOURCE"
}

install_copy() {
    mkdir -p "$TARGET"
    if command -v rsync >/dev/null 2>&1; then
        # shellcheck disable=SC2046
        rsync -a --delete $(rsync_excludes) "${SOURCE}/" "${TARGET}/"
    else
        cp -a "${SOURCE}/." "${TARGET}/"
    fi
    # Stale cp314 bytecode from dev machines breaks CSP Python 3.3 import.
    find "$TARGET" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
    find "$TARGET" -name '*.pyc' -delete 2>/dev/null || true
    echo "Copied: $SOURCE -> $TARGET"
}

case "$MODE" in
    link)
        remove_target
        install_link
        ;;
    copy) install_copy ;;
esac

DATA_DIRS=(data/baselines data/setup_memory data/sessions data/grip_map)
for d in "${DATA_DIRS[@]}"; do
    mkdir -p "${TARGET}/${d}"
done

if [[ "$WATCH" -eq 1 ]]; then
    if ! command -v inotifywait >/dev/null 2>&1; then
        echo "error: --watch requires inotifywait (sudo apt install inotify-tools)" >&2
        exit 1
    fi
    echo ""
    echo "Watching ${SOURCE} — Ctrl+C to stop"
    while inotifywait -r -e modify,create,delete,move "$SOURCE" >/dev/null 2>&1; do
        install_copy
    done
fi

CM_EXE=""
if CM_EXE="$(find_cm_exe)"; then
    :
fi

if [[ "$OPEN_CM" -eq 1 && -n "$CM_EXE" ]]; then
    WIN_CM="$(win_path "$CM_EXE")"
    # Empty title ("") must be a separate arg — escaped quotes inside /c break on WSL.
    cmd.exe /c start "" "$WIN_CM" </dev/null >/dev/null 2>&1 &
    echo "Launched Content Manager"
elif [[ "$OPEN_CM" -eq 1 ]]; then
    echo "note: Content Manager.exe not found; enable the app manually in CM settings" >&2
fi

cat <<EOF

Virtual Race Engineer deployed.
  AC app:     $TARGET
  Setups out: Documents/Assetto Corsa/setups/rss_formula_hybrid_x_2026/<track>/Auto_Tweak.ini

Content Manager (required):
  1. Settings → Assetto Corsa → Apps
  2. Check "Enable Python apps"
  3. Under Activated apps, check "Virtual Race Engineer"
  4. (Dev) CSP → Developer → Python Apps Debug → Live reload / Reload automatically

Alternative CM install: drag dist/VirtualRaceEngineer.zip onto CM (run ./deploy/package.sh first)

Re-deploy after edits:  ./deploy/install.sh  or  ./deploy/sync.sh
Live sync while editing: ./deploy/install.sh --watch

Replay viewer (after a stint):
  ./replay.sh
  ./replay.sh --force-sync

Docs: docs/INSTALL.md  docs/USAGE.md

Optional TTS (run from Windows Python for audio):
  pip install -r external/tts_daemon/requirements.txt
  python external/tts_daemon/engineer_voice.py --voice-file "$TARGET/data/engineer_voice.txt"
EOF
