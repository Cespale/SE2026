param(
    [string]$BackendUrl = '',

    [string]$ArtifactDir = (Join-Path $PSScriptRoot '证据\playwright-artifacts'),

    [string]$JunitOutput = (Join-Path $PSScriptRoot '证据\e2e-tests.xml'),

    [string[]]$TestArgs = @()
)

$ErrorActionPreference = 'Stop'
$env:E2E_ARTIFACT_DIR = $ArtifactDir
$env:E2E_JUNIT_OUTPUT = $JunitOutput

if ($BackendUrl) {
    $env:E2E_BACKEND_URL = $BackendUrl
} else {
    Remove-Item Env:E2E_BACKEND_URL -ErrorAction SilentlyContinue
}

& npx playwright test @TestArgs
$testExitCode = $LASTEXITCODE

if ($testExitCode -ne 0) {
    'E2E_TEST=FAILED'
    'PUBLISH_IMAGE=SKIPPED'
    'DEPLOY=SKIPPED'
    exit $testExitCode
}

'E2E_TEST=PASSED'
'PUBLISH_IMAGE=NOT_RUN'
'DEPLOY=NOT_RUN'
