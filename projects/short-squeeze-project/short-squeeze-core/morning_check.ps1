[CmdletBinding()]
param(
    [string]$RailwayUrl = ""
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root '.venv\Scripts\python.exe'
$expectedBranch = 'main'
$releaseVersion = '0.16.0'
$releaseName = "short-squeeze-research-screener-$releaseVersion"
$releaseDir = Join-Path $root "dist\$releaseName"
$zipPath = Join-Path $root "dist\$releaseName.zip"
$zipChecksumPath = "$zipPath.sha256"
$releaseManifestPath = Join-Path $releaseDir 'RELEASE_MANIFEST.json'
$finalTestReportPath = Join-Path $root 'dist\batch15-final.xml'
$results = [System.Collections.Generic.List[object]]::new()

function Add-Check {
    param([string]$Name, [bool]$Passed, [string]$Detail)
    $results.Add([pscustomobject]@{
        Name = $Name
        Passed = $Passed
        Detail = $Detail
    })
}

if (-not (Test-Path -LiteralPath $python)) {
    Add-Check 'Python environment' $false 'Create .venv and install the project.'
} else {
    Add-Check 'Python environment' $true 'Available'
}

Push-Location $root
try {
    $branch = (& git branch --show-current).Trim()
    Add-Check 'Expected branch' ($branch -eq $expectedBranch) $branch
    $head = (& git rev-parse HEAD).Trim()
    $workingTree = @(& git status --short 2>$null)
    Add-Check 'Working tree' ($workingTree.Count -eq 0) 'No uncommitted files'

    if (Test-Path -LiteralPath $python) {
        & $python -m apps.research_screener.config doctor --mode FROZEN_DEMO --no-ibkr-probe *> $null
        Add-Check 'Configuration doctor' ($LASTEXITCODE -eq 0) 'FROZEN_DEMO'

        & $python tools/integration_acceptance.py --mode frozen --json *> $null
        Add-Check 'Integration acceptance' ($LASTEXITCODE -eq 0) 'Frozen HTTP checks'
    }

    Add-Check 'Release directory' (Test-Path -LiteralPath $releaseDir) $releaseName
    Add-Check 'Release ZIP' (Test-Path -LiteralPath $zipPath) "$releaseName.zip"
    $releaseSourceMatches = $false
    if (Test-Path -LiteralPath $releaseManifestPath) {
        $releaseManifest = Get-Content -LiteralPath $releaseManifestPath -Raw |
            ConvertFrom-Json
        $releaseSourceMatches = $releaseManifest.git_source_commit -eq $head
    }
    Add-Check 'Release source commit' $releaseSourceMatches $head
    Add-Check 'Final test report' (Test-Path -LiteralPath $finalTestReportPath) 'batch15-final.xml'

    $checksumOk = $false
    if ((Test-Path -LiteralPath $zipPath) -and (Test-Path -LiteralPath $zipChecksumPath)) {
        $expected = ((Get-Content -LiteralPath $zipChecksumPath -Raw).Split(' ')[0]).Trim()
        $actual = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
        $checksumOk = $expected -eq $actual
    }
    Add-Check 'ZIP checksum' $checksumOk 'SHA-256'

    if ((Test-Path -LiteralPath $python) -and (Test-Path -LiteralPath $releaseDir)) {
        & $python tools/release_audit.py $releaseDir --allowlist release-audit-allowlist.json --json *> $null
        Add-Check 'Release privacy audit' ($LASTEXITCODE -eq 0) 'No prohibited findings'
    }

    if ($RailwayUrl -and (Test-Path -LiteralPath $python)) {
        & $python tools/integration_acceptance.py --url $RailwayUrl --json *> $null
        Add-Check 'Railway acceptance' ($LASTEXITCODE -eq 0) 'Public URL'
    }
}
finally {
    Pop-Location
}

foreach ($result in $results) {
    $state = if ($result.Passed) { 'PASS' } else { 'FAIL' }
    Write-Host ("{0,-4} {1,-24} {2}" -f $state, $result.Name, $result.Detail)
}

$failures = @($results | Where-Object { -not $_.Passed }).Count
Write-Host ("SUMMARY: {0} passed, {1} failed" -f ($results.Count - $failures), $failures)
exit $(if ($failures -eq 0) { 0 } else { 1 })
