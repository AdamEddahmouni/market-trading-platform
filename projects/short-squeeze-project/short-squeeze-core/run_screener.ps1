# Short Squeeze Research Screener — one-command local launcher.
#
# RESEARCH TOOL — NOT A TRADING RECOMMENDATION.
# Read-only. Binds 127.0.0.1 only. No orders, no account data, no credentials printed.
#
# Delegates to start_local.py — the canonical local entry point.
#
#   .\run_screener.ps1                           start on port 8787 with browser
#   .\run_screener.ps1 -NoBrowser                start without browser
#   .\run_screener.ps1 -Check                    print availability and exit
#   .\run_screener.ps1 -Port 8900                choose port
#   .\run_screener.ps1 -Profile                  auto-start IB Gateway via Docker
#   .\run_screener.ps1 -Profile -DetectOnly      detect Gateway port and exit
#   .\run_screener.ps1 -PrivatePath /path/to/providers.env
#   .\run_screener.ps1 -Doctor                   print credential report and exit
#   .\run_screener.ps1 -ClearCache               remove port cache and exit

[CmdletBinding()]
param(
    [int]$Port = 8787,
    [switch]$NoBrowser,
    [switch]$Check,
    [switch]$VerboseHttp,
    [switch]$Profile,
    [switch]$Doctor,
    [switch]$ClearCache,
    [switch]$DetectOnly,
    [string]$PrivatePath,
    [string]$DockerImage,
    [string]$DockerImageTag,
    [int]$DockerPaperPort = 4002,
    [int]$DockerLivePort = 4001,
    [int]$DockerContainerPaperPort,
    [int]$DockerContainerLivePort,
    [string[]]$DockerImageEnv
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    Write-Host "Project virtual environment not found at $python" -ForegroundColor Red
    Write-Host "Create it first, then re-run this script." -ForegroundColor Red
    exit 1
}

$startScript = Join-Path $root 'start_local.py'
if (-not (Test-Path $startScript)) {
    Write-Host "start_local.py not found — run from the repository root." -ForegroundColor Red
    exit 1
}

# Build arguments for start_local.py
$appArgs = @(
    $startScript,
    '--port', $Port
)
if ($Profile)    { $appArgs += '--profile' }
if ($Doctor)     { $appArgs += '--doctor' }
if ($ClearCache) { $appArgs += '--clear-cache' }
if ($DetectOnly) { $appArgs += '--detect-only' }
if ($NoBrowser)  { $appArgs += '--no-browser' }
if ($Check)      { $appArgs += '--check' }
if ($VerboseHttp){ $appArgs += '--verbose' }
if ($PrivatePath) { $appArgs += '--private-path'; $appArgs += $PrivatePath }
if ($DockerImage) { $appArgs += '--docker-image'; $appArgs += $DockerImage }
if ($DockerImageTag) { $appArgs += '--docker-image-tag'; $appArgs += $DockerImageTag }
if ($DockerContainerPaperPort) { $appArgs += '--docker-container-paper-port'; $appArgs += $DockerContainerPaperPort }
if ($DockerContainerLivePort) { $appArgs += '--docker-container-live-port'; $appArgs += $DockerContainerLivePort }
foreach ($env in $DockerImageEnv) {
    $appArgs += '--docker-image-env'; $appArgs += $env
}
# Always pass port params even with defaults so start_local.py's parser sees them
$appArgs += '--docker-paper-port'; $appArgs += $DockerPaperPort
$appArgs += '--docker-live-port'; $appArgs += $DockerLivePort

Push-Location $root
try {
    # Fail early and clearly if packages are not importable.
    & $python -c "import apps.research_screener, squeeze_core" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "apps.research_screener is not importable from $python" -ForegroundColor Red
        Write-Host "Install the project into the virtual environment: pip install -e ." -ForegroundColor Red
        exit 1
    }

    & $python @appArgs
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
