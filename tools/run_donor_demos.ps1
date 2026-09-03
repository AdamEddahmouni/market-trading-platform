# Read-only multi-donor demo launcher for the market-trading-platform workspace.
# Does NOT start execution schedulers (internship main.py, FuturesX live_trader.py).

param(
    [ValidateSet("squeeze", "squeeze-cloud", "squeeze-cloud-providers", "cvd", "internship", "futures", "lanes", "all", "status")]
    [string[]] $Start = @("status")
)

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

$Donors = @{
    squeeze = @{
        Name = "Short Squeeze Screener (FROZEN_DEMO)"
        Port = 8787
        Health = "http://127.0.0.1:8787/health"
        Manifest = "http://127.0.0.1:8787/api/v1/integration/manifest"
        Dir = Join-Path $Root "short-squeeze-project\short-squeeze-core"
        Command = @(
            ".\.venv\Scripts\python.exe", "-m", "apps.research_screener", "--no-browser", "--port", "8787"
        )
        Env = @{ SQUEEZE_APP_MODE = "FROZEN_DEMO" }
    }
    squeeze-cloud = @{
        Name = "Short Squeeze Screener (CLOUD_PROVIDER_MODE live scanner)"
        Port = 8787
        Health = "http://127.0.0.1:8787/health"
        Manifest = "http://127.0.0.1:8787/api/v1/integration/manifest"
        Dir = Join-Path $Root "short-squeeze-project\short-squeeze-core"
        Command = @(
            ".\.venv\Scripts\python.exe", "start_cloud.py", "--no-browser", "--port", "8787"
        )
        Env = @{
            SQUEEZE_APP_MODE = "CLOUD_PROVIDER_MODE"
            SEC_ENABLED = "true"
            CLOUD_BOOTSTRAP_SYMBOLS = "AVTX,GME,BIYA"
        }
        Prereq = "Set FINVIZ_API_KEY / NEWSAPI_KEY in env for provider discovery; SEC-only uses bootstrap symbols"
    }
    squeeze-cloud-providers = @{
        Name = "Short Squeeze Screener (CLOUD + local .private/providers.env)"
        Port = 8787
        Health = "http://127.0.0.1:8787/health"
        Manifest = "http://127.0.0.1:8787/api/v1/integration/manifest"
        Dir = Join-Path $Root "short-squeeze-project\short-squeeze-core"
        Command = @(
            ".\.venv\Scripts\python.exe", "start_cloud.py", "--load-local-providers", "--no-browser", "--port", "8787"
        )
        Env = @{
            SQUEEZE_APP_MODE = "CLOUD_PROVIDER_MODE"
            CLOUD_BOOTSTRAP_SYMBOLS = "AVTX,GME,BIYA"
            FINVIZ_AUTO_REFRESH = "true"
            IBKR_ENABLED = "true"
            IBKR_HOST = "127.0.0.1"
            IBKR_PORT = "4001"
            IBKR_CLIENT_ID = "124"
        }
        Prereq = "Requires .private/providers.env + IB Gateway on 127.0.0.1:4001 for full Adam scoring"
    }
    cvd = @{
        Name = "CVD Bubble Dashboard (demo data)"
        Port = 8050
        Health = "http://127.0.0.1:8050"
        Manifest = $null
        Dir = Join-Path $Root "tradingCVDBubble-main (1)\tradingCVDBubble-main"
        Command = @(".\.venv\Scripts\python.exe", "-m", "app")
        Env = @{}
        Prereq = "MongoDB on localhost:27017 with demo dataset loaded"
    }
    internship = @{
        Name = "Internship News/Options Dashboard (demo state)"
        Port = 8501
        Health = "http://127.0.0.1:8501"
        Manifest = $null
        Dir = Join-Path $Root "internship-project-main\internship-project-main\news_momentum_agent"
        Command = @(
            ".\.venv\Scripts\python.exe", "-m", "streamlit", "run", "dashboard\app.py",
            "--server.headless", "true", "--server.port", "8501"
        )
        Env = @{ STREAMLIT_BROWSER_GATHER_USAGE_STATS = "false" }
        Prereq = "Run scripts/seed_demo_state.py first; do NOT run main.py"
    }
    futures = @{
        Name = "FuturesX ES depth bridge (read-only)"
        Port = 8788
        Health = "http://127.0.0.1:8788/health"
        Manifest = $null
        Dir = Join-Path $Root "Eric_futuresX-main\futuresX-main"
        Command = @(
            ".\venv\Scripts\python.exe", "scripts\bridge_server.py", "--port", "8788"
        )
        Env = @{}
        Prereq = "Read-only HTTP bridge; does NOT start live_trader.py"
    }
}

function Test-Endpoint {
    param([string] $Url)
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
        return "UP ($($r.StatusCode))"
    } catch {
        return "DOWN"
    }
}

function Show-Status {
    Write-Host "Donor demo status (read-only surfaces only):"
    foreach ($key in $Donors.Keys) {
        $d = $Donors[$key]
        $status = Test-Endpoint $d.Health
        Write-Host ("  [{0}] port {1} -> {2}" -f $key, $d.Port, $status)
        Write-Host ("           {0}" -f $d.Name)
        if ($d.Manifest) { Write-Host ("           manifest: {0}" -f $d.Manifest) }
        if ($d.Prereq) { Write-Host ("           prereq: {0}" -f $d.Prereq) }
    }
    Write-Host ""
    Write-Host "FuturesX: offline smoke only - python Eric_futuresX-main/futuresX-main/scripts/smoke_offline_backtest.py"
    Write-Host "IMP UI-001: python integrated-market-platform/tools/ui1/run_ui_api.py --serve --port 8766"
    Write-Host "IMP explore bridge: http://127.0.0.1:8766/explore/squeeze (requires squeeze server)"
    Write-Host "IMP futures bridge: http://127.0.0.1:8766/explore/futures (requires futures bridge on :8788)"
    Write-Host "IMP scanner bridge: http://127.0.0.1:8766/explore/squeeze/scanner (live CLOUD_PROVIDER_MODE)"
    Write-Host "IMP catalyst bridge: http://127.0.0.1:8766/explore/catalyst (requires internship demo state)"
    Write-Host "IMP workspace squeeze: http://127.0.0.1:8766/workspace/BIYA/squeeze (requires squeeze server)"
    Write-Host "IMP lane acceptance (squeeze): python integrated-market-platform/tools/integration/squeeze_lane_acceptance.py --require-donor --require-imp"
    Write-Host "IMP live lane acceptance (squeeze): python integrated-market-platform/tools/integration/squeeze_lane_acceptance.py --require-donor --require-imp --require-scanner-rows --output integrated-market-platform/evidence/integration/squeeze-lane-acceptance.json"
    Write-Host "IMP lane acceptance (futures): python integrated-market-platform/tools/integration/futures_lane_acceptance.py --require-donor --require-imp --output integrated-market-platform/evidence/integration/futures-lane-acceptance.json"
    Write-Host "IMP lane acceptance (catalyst): python integrated-market-platform/tools/integration/catalyst_lane_acceptance.py --require-imp --output integrated-market-platform/evidence/integration/catalyst-lane-acceptance.json"
    $bridgeStatus = Test-Endpoint "http://127.0.0.1:8766/explore/squeeze"
    Write-Host ("IMP squeeze bridge status: {0}" -f $bridgeStatus)
    if ($bridgeStatus -like "UP*") {
        try {
            $payload = Invoke-RestMethod -Uri "http://127.0.0.1:8766/explore/squeeze" -UseBasicParsing -TimeoutSec 3
            Write-Host ("  available={0} row_count={1}" -f $payload.available, $payload.row_count)
        } catch {
            Write-Host "  (could not parse explore/squeeze payload)"
        }
    }
    $catalystStatus = Test-Endpoint "http://127.0.0.1:8766/explore/catalyst"
    Write-Host ("IMP catalyst bridge status: {0}" -f $catalystStatus)
    if ($catalystStatus -like "UP*") {
        try {
            $payload = Invoke-RestMethod -Uri "http://127.0.0.1:8766/explore/catalyst" -UseBasicParsing -TimeoutSec 3
            Write-Host ("  available={0} row_count={1}" -f $payload.available, $payload.row_count)
        } catch {
            Write-Host "  (could not parse explore/catalyst payload)"
        }
    }
    $futuresDonorStatus = Test-Endpoint "http://127.0.0.1:8788/health"
    Write-Host ("FuturesX donor bridge status: {0}" -f $futuresDonorStatus)
    $futuresBridgeStatus = Test-Endpoint "http://127.0.0.1:8766/explore/futures"
    Write-Host ("IMP futures bridge status: {0}" -f $futuresBridgeStatus)
    if ($futuresBridgeStatus -like "UP*") {
        try {
            $payload = Invoke-RestMethod -Uri "http://127.0.0.1:8766/explore/futures" -UseBasicParsing -TimeoutSec 3
            Write-Host ("  available={0} symbol={1}" -f $payload.available, $payload.symbol)
        } catch {
            Write-Host "  (could not parse explore/futures payload)"
        }
    }
}

function Start-Donor {
    param([string] $Key)
    $d = $Donors[$Key]
    if (-not (Test-Path $d.Dir)) {
        Write-Error "Missing donor directory: $($d.Dir)"
        return
    }
    if ($Key -in @("squeeze-cloud-providers", "squeeze-cloud")) {
        $refreshScript = Join-Path $d.Dir "refresh_finviz_token.ps1"
        if (Test-Path $refreshScript) {
            Write-Host "Preflight: automatic Finviz token refresh..."
            & $refreshScript
            if ($LASTEXITCODE -ne 0) {
                Write-Host "Preflight: Finviz refresh did not complete (runtime will retry on 401)." -ForegroundColor Yellow
            }
        }
    }
    Write-Host "Starting $($d.Name) in new window..."
    $commandParts = @("Set-Location '$($d.Dir)'")
    foreach ($pair in $d.Env.GetEnumerator()) {
        $commandParts += "`$env:$($pair.Key)='$($pair.Value)'"
    }
    $commandParts += ($d.Command -join " ")
    $cmd = $commandParts -join "; "
    Start-Process powershell -ArgumentList @("-NoExit", "-Command", $cmd)
}

if ($Start -contains "status" -or $Start.Count -eq 0) {
    Show-Status
}

$toStart = $Start | Where-Object { $_ -ne "status" }
if ($toStart -contains "lanes") {
    Write-Host "Starting integration lanes: squeeze-cloud + futures."
    Write-Host "Catalyst prereq: seed internship demo state once:"
    Write-Host "  cd internship-project-main\internship-project-main\news_momentum_agent"
    Write-Host "  python scripts/seed_demo_state.py"
    $toStart = @("squeeze-cloud", "futures")
}
if ($toStart -contains "all") {
    $toStart = @("squeeze", "futures", "cvd", "internship")
}
foreach ($key in $toStart) {
    if ($Donors.ContainsKey($key)) {
        Start-Donor $key
    }
}
