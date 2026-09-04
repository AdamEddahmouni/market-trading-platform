# Local UI API restart (not hot reload). Code changes require this restart.
# IMP_MOOMOO_LIVE enables observational market data only — it does not authorize execution.
param(
    [int]$Port = 8766,
    [string]$HostName = "127.0.0.1"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $Root

Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -match "python" -and
        $_.CommandLine -and
        $_.CommandLine -match "run_ui_api.py" -and
        $_.CommandLine -match "--serve"
    } |
    ForEach-Object {
        Write-Host "Stopping stale UI API PID $($_.ProcessId)"
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

Start-Sleep -Seconds 1

$env:IMP_LIVE_OBSERVATIONAL = "1"
$env:IMP_MOOMOO_LIVE = "1"
$env:IMP_PAPER_EXECUTION = "1"
$env:IMP_LIVE_INTERNAL_SIMULATION = "1"
$env:IMP_PERSIST_STATE = "1"
$env:PYTHONUNBUFFERED = "1"

$MoomooPython = Join-Path $env:USERPROFILE "moomoo-api-test\.venv\Scripts\python.exe"
$Python = if (Test-Path $MoomooPython) { $MoomooPython } else { "python" }
Write-Host "Starting UI API with $Python from $Root on ${HostName}:${Port} (restart required after code changes)"
& $Python tools/ui1/run_ui_api.py --serve --host $HostName --port $Port
