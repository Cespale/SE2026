[CmdletBinding()]
param(
    [string]$Version = "kind-cicd-$(Get-Date -Format 'yyyyMMddHHmmss')",
    [string]$ClusterName = 'streamhub-cicd',
    [string]$ResultsRoot = '.ci-results/kind-cicd'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot '.venv-ms\Scripts\python.exe'
$localGate = Join-Path $PSScriptRoot 'run-local-microservices-gate.ps1'
$kindSetup = Join-Path $PSScriptRoot 'setup-kind-lab.ps1'
$gitBash = 'C:\Program Files\Git\bin\bash.exe'
$kubeconfig = Join-Path $projectRoot '.ci-results\cloud-native\kind-lab-kubeconfig'
$resultDir = Join-Path $projectRoot "$ResultsRoot\$Version"
$diagnosticsRelative = "$ResultsRoot/$Version/kind-diagnostics" -replace '\\', '/'
$compose = @('-f', 'docker-compose.microservices.yml', '--env-file', '.env.microservices')

if ($Version -eq 'latest' -or $Version -notmatch '^[A-Za-z0-9._-]+$') {
    throw 'Version must be an immutable URL-safe tag and cannot be latest'
}
foreach ($required in @($python, $localGate, $kindSetup, $gitBash)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required CI/CD dependency is missing: $required"
    }
}

function Invoke-Checked([string]$Label, [scriptblock]$Command) {
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

function Write-Utf8NoBom([string]$Path, [string]$Value) {
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Value, $encoding)
}

function Invoke-BestEffort([scriptblock]$Command) {
    $savedErrorActionPreference = $ErrorActionPreference
    $savedLastExitCode = $global:LASTEXITCODE
    try {
        $ErrorActionPreference = 'SilentlyContinue'
        & $Command | Out-Null
    }
    catch {
        # Cleanup and diagnostics must not hide the original pipeline result.
    }
    finally {
        $ErrorActionPreference = $savedErrorActionPreference
        $global:LASTEXITCODE = $savedLastExitCode
    }
}

function Test-DockerContainerRunning([string]$Name) {
    $savedErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'
    try {
        $status = docker inspect --format '{{.State.Status}}' $Name 2>$null
        return $LASTEXITCODE -eq 0 -and (($status | Out-String).Trim() -eq 'running')
    } finally {
        $ErrorActionPreference = $savedErrorActionPreference
    }
}

function Get-RunningKindControlPlanes {
    $names = @(docker ps `
        --filter 'label=io.x-k8s.kind.role=control-plane' `
        --format '{{.Names}}' 2>$null)
    if ($LASTEXITCODE -ne 0) {
        throw 'Unable to list running Kind control-plane containers'
    }
    return @($names | ForEach-Object { $_.Trim() } | Where-Object { $_ })
}

$oldKubeconfig = $env:KUBECONFIG
$oldImageTag = $env:IMAGE_TAG
$oldExpectedVersion = $env:EXPECTED_VERSION
$oldAppVersion = $env:APP_VERSION
$oldNamespace = $env:NAMESPACE
$kindAttempted = $false
$kindNodesStoppedForLocalGate = @()

try {
    Set-Location -LiteralPath $projectRoot
    New-Item -ItemType Directory -Force -Path $resultDir | Out-Null
    $env:IMAGE_TAG = $Version

    Invoke-Checked 'workspace guard' {
        & $python scripts/check_microservices_workspace.py
    }

    foreach ($runningKindNode in @(Get-RunningKindControlPlanes)) {
        Invoke-Checked "stop Kind control-plane $runningKindNode before local regression" {
            docker stop --time 30 $runningKindNode | Out-Null
        }
        $kindNodesStoppedForLocalGate += $runningKindNode
    }

    & $localGate -Version $Version -ResultsRoot $ResultsRoot

    Invoke-Checked 'stop Docker Compose regression stack' {
        docker compose @compose down
    }

    $kindAttempted = $true
    & $kindSetup -Version $Version -ClusterName $ClusterName

    if (-not (Test-Path -LiteralPath $kubeconfig)) {
        throw "Kind kubeconfig was not created: $kubeconfig"
    }
    $env:KUBECONFIG = $kubeconfig
    $env:EXPECTED_VERSION = $Version
    $env:APP_VERSION = $Version
    $env:NAMESPACE = 'streamhub-ms'

    Invoke-Checked 'Kubernetes health, readiness, and version checks' {
        & $gitBash scripts/health-check-microservices.sh
    }

    $resources = & kubectl --kubeconfig $kubeconfig get deployment,pods,services,hpa `
        -n streamhub-ms -o wide 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
        throw "kubectl resource snapshot failed with exit code $LASTEXITCODE"
    }
    Write-Utf8NoBom (Join-Path $resultDir 'kind-resources.txt') $resources
    Write-Utf8NoBom (Join-Path $resultDir 'kind-result.txt') `
        "KIND_CICD_GATE=PASS version=$Version cluster=$ClusterName`n"
    Write-Output "KIND_CICD_GATE=PASS version=$Version cluster=$ClusterName evidence=$resultDir"
}
catch {
    $reason = $_.Exception.Message -replace '[\r\n]+', ' '
    Write-Utf8NoBom (Join-Path $resultDir 'kind-result.txt') `
        "KIND_CICD_GATE=FAIL version=$Version cluster=$ClusterName reason=$reason`n"
    throw
}
finally {
    Set-Location -LiteralPath $projectRoot
    foreach ($stoppedKindNode in $kindNodesStoppedForLocalGate) {
        if (-not (Test-DockerContainerRunning $stoppedKindNode)) {
            Invoke-BestEffort {
                docker start $stoppedKindNode | Out-Null
            }
        }
    }
    if ($kindAttempted -and (Test-Path -LiteralPath $kubeconfig)) {
        $env:KUBECONFIG = $kubeconfig
        Invoke-BestEffort {
            & $gitBash scripts/collect-deployment-diagnostics.sh $diagnosticsRelative
        }
    }
    Invoke-BestEffort {
        docker compose @compose down *> $null
    }
    $env:KUBECONFIG = $oldKubeconfig
    $env:IMAGE_TAG = $oldImageTag
    $env:EXPECTED_VERSION = $oldExpectedVersion
    $env:APP_VERSION = $oldAppVersion
    $env:NAMESPACE = $oldNamespace
}
