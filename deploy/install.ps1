# Deploy Virtual Race Engineer into Assetto Corsa apps/python/
# Run from repo root:  powershell -ExecutionPolicy Bypass -File deploy/install.ps1

param(
    [string]$AcRoot = "",
    [switch]$Copy
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Source = Join-Path $RepoRoot "ac_app"
$AppName = "VirtualRaceEngineer"

$RuntimeDataPatterns = @(
    "data\baselines\*",
    "data\setup_memory\*",
    "data\sessions\*",
    "data\grip_map\*",
    "data\engineer_voice.txt"
)

function Copy-AppWithoutRuntimeData {
    param([string]$From, [string]$To)
    if (Get-Command robocopy -ErrorAction SilentlyContinue) {
        robocopy $From $To /E /NFL /NDL /NJH /NJS /nc /ns /np `
            /XD "__pycache__" `
            /XF "engineer_voice.txt" | Out-Null
        foreach ($sub in @("baselines", "setup_memory", "sessions", "grip_map")) {
            $d = Join-Path $To "data\$sub"
            if (Test-Path $d) {
                Get-ChildItem $d -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
            }
        }
    } else {
        Copy-Item -Path $From -Destination $To -Recurse -Force
        foreach ($pat in $RuntimeDataPatterns) {
            Get-ChildItem -Path (Join-Path $To $pat) -ErrorAction SilentlyContinue |
                Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
        }
        Get-ChildItem -Path $To -Recurse -Directory -Filter "__pycache__" |
            Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    }
}

if (-not (Test-Path $Source)) {
    Write-Error "ac_app folder not found at $Source"
}

if (-not $AcRoot) {
    $candidates = @(
        "${env:ProgramFiles(x86)}\Steam\steamapps\common\assettocorsa",
        "$env:ProgramFiles\Steam\steamapps\common\assettocorsa",
        "$env:LOCALAPPDATA\Programs\assettocorsa"
    )
    foreach ($c in $candidates) {
        if (Test-Path (Join-Path $c "acs.exe")) {
            $AcRoot = $c
            break
        }
    }
}

if (-not $AcRoot -or -not (Test-Path (Join-Path $AcRoot "acs.exe"))) {
    Write-Error "Could not find Assetto Corsa. Pass -AcRoot 'C:\path\to\assettocorsa'"
}

$Target = Join-Path $AcRoot "apps\python\$AppName"
$Parent = Split-Path $Target -Parent
if (-not (Test-Path $Parent)) {
    New-Item -ItemType Directory -Path $Parent -Force | Out-Null
}

if (Test-Path $Target) {
    if ((Get-Item $Target).LinkType) {
        Remove-Item $Target -Force
    } else {
        Write-Warning "Removing existing folder $Target"
        Remove-Item $Target -Recurse -Force
    }
}

if ($Copy) {
    Copy-AppWithoutRuntimeData -From $Source -To $Target
    Write-Host "Copied ac_app -> $Target (runtime telemetry excluded)"
} else {
    New-Item -ItemType Junction -Path $Target -Target $Source | Out-Null
    Write-Host "Linked ac_app -> $Target"
}

$dataDirs = @(
    "data\baselines",
    "data\setup_memory",
    "data\sessions",
    "data\grip_map"
)
foreach ($d in $dataDirs) {
    $p = Join-Path $Target $d
    if (-not (Test-Path $p)) {
        New-Item -ItemType Directory -Path $p -Force | Out-Null
    }
}

Write-Host ""
Write-Host "Virtual Race Engineer deployed."
Write-Host "  AC app:     $Target"
Write-Host "  Setups out: $env:USERPROFILE\Documents\Assetto Corsa\setups\rss_formula_hybrid_x_2026\<track>\Auto_Tweak.ini"
Write-Host ""
Write-Host "Content Manager:"
Write-Host "  1. Settings -> Assetto Corsa -> Apps"
Write-Host "  2. Enable Python apps"
Write-Host "  3. Activate Virtual Race Engineer"
Write-Host ""
Write-Host "Replay (from WSL repo): ./replay.sh"
Write-Host "Docs: docs/INSTALL.md  docs/USAGE.md"
Write-Host ""
Write-Host "Or drag dist/VirtualRaceEngineer.zip onto CM (build with ./deploy/package.sh on WSL)"
Write-Host "Optional TTS: python external/tts_daemon/engineer_voice.py --voice-file `"$Target\data\engineer_voice.txt`""
