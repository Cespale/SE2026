[CmdletBinding()]
param(
    [string]$Version = "local-$(Get-Date -Format 'yyyyMMddHHmmss')",
    [string]$ResultsRoot = ".ci-results/microservices-local"
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot '.venv-ms/Scripts/python.exe'
$compose = @('-f', 'docker-compose.microservices.yml', '--env-file', '.env.microservices')
$resultDir = Join-Path $projectRoot "$ResultsRoot/$Version"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Missing microservices test Python: $python"
}
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot '.env.microservices'))) {
    throw 'Missing .env.microservices'
}

New-Item -ItemType Directory -Force -Path $resultDir | Out-Null
$oldImageTag = $env:IMAGE_TAG
$oldAppVersion = $env:APP_VERSION
$env:IMAGE_TAG = $Version
$env:APP_VERSION = $Version

function Invoke-Native([string]$Label, [scriptblock]$Command) {
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

function Invoke-BestEffort([scriptblock]$Command) {
    $savedErrorActionPreference = $ErrorActionPreference
    $savedLastExitCode = $global:LASTEXITCODE
    try {
        $ErrorActionPreference = 'SilentlyContinue'
        & $Command | Out-Null
    }
    catch {
        # Diagnostics must not replace the original gate result.
    }
    finally {
        $ErrorActionPreference = $savedErrorActionPreference
        $global:LASTEXITCODE = $savedLastExitCode
    }
}

try {
    Set-Location -LiteralPath $projectRoot
    Invoke-Native 'workspace guard' { & $python scripts/check_microservices_workspace.py }
    Invoke-Native 'contract tests' {
        & $python -m pytest -q tests/microservices shared/tests --junitxml="$resultDir/contracts.xml"
    }
    foreach ($service in @('user-service', 'content-service', 'social-service')) {
        Invoke-Native "$service pytest" {
            & $python -m pytest -q "services/$service/tests" --junitxml="$resultDir/$service.xml"
        }
    }
    Invoke-Native 'frontend typecheck' { npm run typecheck }
    Invoke-Native 'microservice image build and local deployment' {
        docker compose @compose up -d --build --wait --wait-timeout 240
    }

    # A freshly created database volume only holds the monolith backup in schema
    # public; the per-service schemas (user_service/content_service/social_service)
    # start empty.  Seed them from that backup so the public API and E2E steps can
    # log in and find content on a new machine without a manual data step.  Both
    # steps are idempotent (ON CONFLICT DO NOTHING / WHERE stream_key IS NULL) and
    # become no-ops once data is present, so repeated gate runs are safe.
    $postgresPassword = $null
    $postgresDb = 'streamhub'
    foreach ($envLine in (Get-Content -LiteralPath (Join-Path $projectRoot '.env.microservices'))) {
        if ($envLine -match '^POSTGRES_PASSWORD=(.*)$') {
            $postgresPassword = $Matches[1].Trim().Trim('"').Trim("'")
        }
        elseif ($envLine -match '^POSTGRES_DB=(.*)$') {
            $postgresDb = $Matches[1].Trim().Trim('"').Trim("'")
        }
    }
    if (-not $postgresPassword) {
        throw 'POSTGRES_PASSWORD is required in .env.microservices to seed the service schemas'
    }
    # Host port 5434 is the fixed postgres-ms mapping in docker-compose.microservices.yml.
    $databaseUrl = "postgresql://postgres:$postgresPassword@127.0.0.1:5434/$postgresDb"
    $env:SOURCE_DATABASE_URL = $databaseUrl
    $env:DESTINATION_DATABASE_URL = $databaseUrl
    Invoke-Native 'seed service schemas from monolith backup' {
        & $python scripts/migrate_monolith_data.py
    }
    Invoke-Native 'backfill creator stream keys' {
        docker compose @compose exec -T postgres-ms psql -v ON_ERROR_STOP=1 `
            -U postgres -d $postgresDb `
            -c "UPDATE user_service.users SET stream_key = substr(md5(id::text), 1, 20) WHERE stream_key IS NULL;"
    }

    Invoke-Native 'public API smoke' {
        & $python scripts/public_api_smoke.py --base-url http://127.0.0.1:8100 `
            --junit "$resultDir/public-api.xml" --json "$resultDir/public-api.json"
    }
    $env:E2E_USE_MICROSERVICES = 'true'
    $env:E2E_BASE_URL = 'http://127.0.0.1:5273'
    $env:E2E_BACKEND_URL = 'http://127.0.0.1:8100'
    $env:E2E_JUNIT_OUTPUT = "$resultDir/e2e.xml"
    $env:E2E_ARTIFACT_DIR = "$resultDir/playwright-artifacts"
    Invoke-Native 'UC01-UC08 playwright test' { npx playwright test e2e/streamhub.spec.ts }

    $paths = @(
        '/health', '/ready', '/version',
        '/_services/user/health', '/_services/user/ready', '/_services/user/version',
        '/_services/content/health', '/_services/content/ready', '/_services/content/version',
        '/_services/social/health', '/_services/social/ready', '/_services/social/version'
    )
    $observed = foreach ($path in $paths) {
        $body = Invoke-RestMethod -Uri "http://127.0.0.1:8100$path" -TimeoutSec 5
        [pscustomobject]@{ path = $path; response = $body }
    }
    $observed | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath "$resultDir/observability.json" -Encoding utf8
    "LOCAL_MICROSERVICES_GATE=PASS version=$Version" | Set-Content -LiteralPath "$resultDir/result.txt" -Encoding utf8
    Write-Output "LOCAL_MICROSERVICES_GATE=PASS version=$Version evidence=$resultDir"
}
catch {
    $reason = $_.Exception.Message -replace '[\r\n]+', ' '
    "LOCAL_MICROSERVICES_GATE=FAIL version=$Version reason=$reason" | `
        Set-Content -LiteralPath "$resultDir/result.txt" -Encoding utf8
    throw
}
finally {
    Set-Location -LiteralPath $projectRoot
    Invoke-BestEffort {
        docker compose @compose ps | `
            Set-Content -LiteralPath "$resultDir/compose-ps.txt" -Encoding utf8
    }
    Invoke-BestEffort {
        docker compose @compose logs --no-color --tail 200 | `
            Set-Content -LiteralPath "$resultDir/service-logs.txt" -Encoding utf8
    }
    $env:IMAGE_TAG = $oldImageTag
    $env:APP_VERSION = $oldAppVersion
    Remove-Item Env:E2E_USE_MICROSERVICES -ErrorAction SilentlyContinue
    Remove-Item Env:E2E_BASE_URL -ErrorAction SilentlyContinue
    Remove-Item Env:E2E_BACKEND_URL -ErrorAction SilentlyContinue
    Remove-Item Env:E2E_JUNIT_OUTPUT -ErrorAction SilentlyContinue
    Remove-Item Env:E2E_ARTIFACT_DIR -ErrorAction SilentlyContinue
}
