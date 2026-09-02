$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv-ms\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $python)) {
    throw "Missing copy-local Python environment: $python"
}

& $python @args
exit $LASTEXITCODE
