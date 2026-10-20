$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not $env:DATABRICKS_CONFIG_PROFILE) {
    $env:DATABRICKS_CONFIG_PROFILE = "dbc-b5503989-0919"
}

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    py -3.12 -m venv (Join-Path $PSScriptRoot ".venv")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

& $python -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $python -m streamlit run (Join-Path $PSScriptRoot "app.py")
exit $LASTEXITCODE