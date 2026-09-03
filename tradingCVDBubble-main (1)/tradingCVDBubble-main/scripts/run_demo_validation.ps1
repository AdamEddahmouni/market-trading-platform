# One-command CVD demo validation (Windows). Requires Docker MongoDB on :27017.
param(
    [string[]] $Tickers = @("NVDA"),
    [string] $AuctionDate = "2026-07-22"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    python -m venv .venv
    & $py -m pip install -q -r requirements-demo.txt matplotlib ib_async
}

Write-Host "== offline bundle check =="
& $py -m scripts.offline_demo_bundle_check

Write-Host "== load demo dataset =="
& $py -m scripts.demo_dataset load

foreach ($ticker in $Tickers) {
    Write-Host "== coverage_and_latency ($ticker) =="
    & $py -m scripts.coverage_and_latency --tickers $ticker
    Write-Host "== inspect_auction_conditions ($ticker $AuctionDate) =="
    & $py -m scripts.inspect_auction_conditions --ticker $ticker --date $AuctionDate
}

Write-Host "== validate_moc =="
& $py -m scripts.validate_moc

Write-Host "== backtest_correlation =="
& $py -m scripts.backtest_correlation

Write-Host "== backtest_correlation_wick =="
& $py -m scripts.backtest_correlation_wick

Write-Host "Done. See CVD_BUBBLE_NOTES.md for expected demo-only limitations."
