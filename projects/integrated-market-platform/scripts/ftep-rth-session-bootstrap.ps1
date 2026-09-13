#Requires -Version 5.1
<#
.SYNOPSIS
  FTEP-V1-002 governed SIGNAL_ONLY RTH operator bootstrap (no orders, no fabricated data).

.DESCRIPTION
  Consolidates SIGNAL_ONLY_LAUNCH_PREP machine gates: persistence, readiness, integrity,
  session-start dry-run, optional live session-start (owner confirm), catalyst watch.
  Aborts when US_EQUITY_RTH is closed unless -ClosedMarketSmokeOnly is set (fixture watch only).

.EXAMPLE
  .\scripts\ftep-rth-session-bootstrap.ps1 -ClosedMarketSmokeOnly
#>
[CmdletBinding()]
param(
    [switch] $ClosedMarketSmokeOnly,
    [switch] $SkipCatalystWatch
)

$ErrorActionPreference = "Stop"
$ImpRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ImpRoot

$env:IMP_PERSIST_STATE = "1"

function Invoke-ImpJson {
    param([string[]] $CommandArgs)
    $raw = & python tools/imp.py @CommandArgs 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "imp.py failed ($($CommandArgs -join ' ')): $raw"
    }
    return ($raw | Out-String).Trim() | ConvertFrom-Json
}

Write-Host "== FTEP-V1-002 RTH bootstrap (IMP root: $ImpRoot) ==" -ForegroundColor Cyan

$status = Invoke-ImpJson @("ftep", "campaign-status", "FTEP-V1-002", "--json")
Write-Host ("campaign-status: rth_open={0} readiness={1} sessions={2} locks={3}" -f `
    $status.us_equity_rth_open, `
    $status.campaign_readiness_disposition, `
    $status.governed_session_count, `
    $status.empirical_lock_count)

if (-not $status.signal_only_authorized) {
    throw "signal_only_authorized=false - abort."
}
if ($status.campaign_readiness_disposition -ne "READY") {
    throw "campaign_readiness not READY - abort."
}
if ($status.manifest_status -ne "FROZEN") {
    throw "manifest not FROZEN - abort."
}

$readiness = Invoke-ImpJson @("providers", "campaign-readiness", "FTEP-V1-002", "--json", "--probe-local")
if ($readiness.disposition -ne "READY") {
    throw "providers campaign-readiness not READY - abort."
}

$integrity = Invoke-ImpJson @("ftep", "integrity-check", "FTEP-V1-002", "--json")
if ($integrity.disposition -ne "PASS") {
    throw "integrity-check not PASS - abort."
}

if ($ClosedMarketSmokeOnly) {
    if ($status.us_equity_rth_open) {
        Write-Warning "RTH is open; -ClosedMarketSmokeOnly skips live session-start."
    }
    if (-not $SkipCatalystWatch) {
        $watch = Invoke-ImpJson @("ftep", "watch-catalysts", "--fixture", "--json")
        Write-Host ("watch-catalysts (fixture): disposition={0}" -f $watch.disposition)
    }
    Write-Host "Closed-market smoke complete (no session lock)." -ForegroundColor Green
    exit 0
}

if (-not $status.us_equity_rth_open) {
    Write-Host "US_EQUITY_RTH closed - use -ClosedMarketSmokeOnly for fixture smoke only." -ForegroundColor Yellow
    exit 2
}

$dryRun = Invoke-ImpJson @("ftep", "session-start", "FTEP-V1-002", "--dry-run", "--json")

if ($dryRun.would_create_session -ne $true) {
    $blockers = ($dryRun.blockers | ForEach-Object { $_ }) -join ", "
    throw "session-start dry-run would_create_session=false blockers=$blockers"
}

Write-Host "Dry-run gates passed. Live governed session-start requires explicit owner confirmation." -ForegroundColor Yellow
$confirm = Read-Host "Type YES to run: python tools/imp.py ftep session-start FTEP-V1-002 --json"
if ($confirm -ne "YES") {
    Write-Host "Live session-start skipped by operator."
    exit 0
}

$live = Invoke-ImpJson @("ftep", "session-start", "FTEP-V1-002", "--json")
if ($live.session_errors -and $live.session_errors.Count -gt 0) {
    throw "session-start reported errors: $($live.session_errors | ConvertTo-Json -Compress)"
}

Write-Host ("sessions_created: {0}" -f ($live.sessions_created | ConvertTo-Json -Compress))
if ($live.evidence_paths) {
    Write-Host ("evidence_paths: {0}" -f ($live.evidence_paths -join "; "))
}

if (-not $SkipCatalystWatch) {
    $watch = Invoke-ImpJson @("ftep", "watch-catalysts", "--json")
    Write-Host ("watch-catalysts: disposition={0}" -f $watch.disposition)
}

Write-Host "Bootstrap complete (SIGNAL_ONLY; zero orders)." -ForegroundColor Green
exit 0
