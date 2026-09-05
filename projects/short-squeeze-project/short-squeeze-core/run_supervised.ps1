# Short Squeeze Research Screener - supervised launcher.
#
# Starts the screener via start_local.py and automatically restarts it if it
# ever exits (crash, OOM, unhandled exception). This guarantees the screener
# stays up during use or during a demonstration without manual intervention.
#
# Passes through all arguments to start_local.py (e.g. -Port, -Profile,
# -NoBrowser, -PrivatePath). Use -MaxRestarts 0 to disable restart-on-crash
# (debugging only).
#
#   .\run_supervised.ps1                         supervised, port 8787, browser
#   .\run_supervised.ps1 -NoBrowser              supervised, no browser
#   .\run_supervised.ps1 -Port 8900              custom port
#   .\run_supervised.ps1 -Profile                supervised + auto IB Gateway
#   .\run_supervised.ps1 -MaxRestarts 0          run once, do not restart
#
# RESEARCH TOOL - NOT A TRADING RECOMMENDATION.
# Read-only. Binds 127.0.0.1 only.

[CmdletBinding()]
param(
    [int]$Port = 8787,
    [switch]$NoBrowser,
    [switch]$Profile,
    [switch]$CloudProviders,
    [int]$MaxRestarts = 100,
    [int]$BackoffSeconds = 2,
    [int]$MaxBackoffSeconds = 30,
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$RemainingArgs
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
if ($CloudProviders) {
    $startScript = Join-Path $root 'start_cloud.py'
}
if (-not (Test-Path $startScript)) {
    Write-Host "start script not found - run from the repository root." -ForegroundColor Red
    exit 1
}

$baseArgs = @($startScript, '--port', $Port)
if ($CloudProviders) {
    $baseArgs += '--load-local-providers'
    $env:FINVIZ_AUTO_REFRESH = 'true'
    $env:SQUEEZE_APP_MODE = 'CLOUD_PROVIDER_MODE'
    $env:IBKR_ENABLED = 'true'
    $env:IBKR_HOST = '127.0.0.1'
    $env:IBKR_PORT = '4001'
    $env:IBKR_CLIENT_ID = '124'
    $refreshScript = Join-Path $root 'refresh_finviz_token.ps1'
    if (Test-Path $refreshScript) {
        Write-Host "Preflight: automatic Finviz token refresh..." -ForegroundColor Cyan
        & $refreshScript
    }
}
if ($Profile) { $baseArgs += '--profile' }
if ($RemainingArgs) { $baseArgs += $RemainingArgs }

$prevLocation = Get-Location
Set-Location $root

& $python -c "import apps.research_screener, squeeze_core" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "apps.research_screener is not importable from $python" -ForegroundColor Red
    Write-Host "Install the project into the virtual environment: pip install -e ." -ForegroundColor Red
    Set-Location $prevLocation
    exit 1
}

$restarts = 0
$currentBackoff = $BackoffSeconds
$exitCode = 0

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Short Squeeze Research Screener - SUPERVISED MODE" -ForegroundColor Cyan
Write-Host "  Restarts automatically on crash (max $MaxRestarts)" -ForegroundColor Cyan
Write-Host "  Press Ctrl+C to stop the supervisor entirely." -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

try {
    while ($true) {
        $attempt = $restarts + 1
        $appArgs = @($baseArgs)
        # First launch may open the browser; crash restarts must not reopen tabs.
        if ($NoBrowser -or $attempt -ge 2) {
            $appArgs += '--no-browser'
        }

        $startTime = Get-Date
        Write-Host ("[{0}] Starting screener (attempt {1})..." -f $startTime.ToString('HH:mm:ss'), $attempt) -ForegroundColor Green

        & $python @appArgs
        $exitCode = $LASTEXITCODE

        $endTime = Get-Date
        $uptime = ($endTime - $startTime).TotalSeconds

        if ($exitCode -eq 0) {
            Write-Host ("[{0}] Screener exited cleanly (code 0). Not restarting." -f $endTime.ToString('HH:mm:ss')) -ForegroundColor Yellow
            break
        }

        $restarts++
        if ($restarts -gt $MaxRestarts) {
            Write-Host ("[{0}] Max restarts ({1}) reached. Stopping supervisor." -f $endTime.ToString('HH:mm:ss'), $MaxRestarts) -ForegroundColor Red
            break
        }

        if ($uptime -gt 60) {
            $currentBackoff = $BackoffSeconds
        }

        Write-Host ("[{0}] Screener exited with code {1} after {2}s." -f $endTime.ToString('HH:mm:ss'), $exitCode, [math]::Round($uptime, 1)) -ForegroundColor Yellow
        Write-Host ("[{0}] Restarting in {1} seconds (restart {2} of {3})..." -f $endTime.ToString('HH:mm:ss'), $currentBackoff, $restarts, $MaxRestarts) -ForegroundColor Yellow

        Start-Sleep -Seconds $currentBackoff
        $currentBackoff = [math]::Min($currentBackoff * 2, $MaxBackoffSeconds)
    }
}
finally {
    Set-Location $prevLocation
}

exit $exitCode
