param(
    [Parameter(Mandatory = $true)]
    [string]$Python,

    [Parameter(Mandatory = $true)]
    [string]$TestPath
)

$ErrorActionPreference = 'Stop'

& $Python -m pytest $TestPath -q
$testExitCode = $LASTEXITCODE

if ($testExitCode -ne 0) {
    'API_TEST=FAILED'
    'PUBLISH_IMAGE=SKIPPED'
    'DEPLOY=SKIPPED'
    exit $testExitCode
}

'API_TEST=PASSED'
'PUBLISH_IMAGE=NOT_RUN'
'DEPLOY=NOT_RUN'
