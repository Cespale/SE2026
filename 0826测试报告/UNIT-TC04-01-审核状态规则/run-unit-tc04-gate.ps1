param(
    [Parameter(Mandatory = $true)]
    [string]$Python,
    [Parameter(Mandatory = $true)]
    [string]$TestPath
)

$ErrorActionPreference = 'Stop'

& $Python -m pytest --noconftest $TestPath -q
$testExitCode = $LASTEXITCODE

if ($testExitCode -ne 0) {
    'UNIT_TEST=FAILED'
    'PUBLISH_IMAGE=SKIPPED'
    'DEPLOY=SKIPPED'
    exit $testExitCode
}

'UNIT_TEST=PASSED'
'PUBLISH_IMAGE=NOT_RUN'
'DEPLOY=NOT_RUN'
