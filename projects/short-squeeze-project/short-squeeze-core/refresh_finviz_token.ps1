$ErrorActionPreference = "Stop"

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$providers = Join-Path $PSScriptRoot ".private\providers.env"

& $python -m tools.provider_auth.finviz_token_refresh --providers-env $providers
exit $LASTEXITCODE
