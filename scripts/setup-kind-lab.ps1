param(
    [string]$Version = 'local-ci-20260830-fix1',
    [string]$ClusterName = 'streamhub-lab'
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv-ms\Scripts\python.exe'
$toolsDir = Join-Path $root '.tools'
$kind = Join-Path $toolsDir 'kind.exe'
$resultRoot = Join-Path $root '.ci-results\cloud-native'
$kubeconfig = Join-Path $resultRoot 'kind-lab-kubeconfig'
$gitBash = 'C:\Program Files\Git\bin\bash.exe'
$kindVersion = 'v0.33.0'
$kindSha256 = '4b22adaa135368c5a465d56bbd8e520cbea87272a06ca00b6078e7b81515c9fc'
$nodeImage = 'kindest/node:v1.37.0'
$nodeDigest = 'sha256:a1ed56cfb0e7b93589bdf97c8cd566405a265939e3620fc4f5de89adff580ae5'
$nodeMirror = "docker.m.daocloud.io/kindest/node@$nodeDigest"
$metricsServerVersion = 'v0.8.0'
$metricsManifestSha256 = 'ff64d1a13b9ac3b0635f0dd985815fb44c23eed4706c04e5db1daadf6bc0a83b'
$metricsServerImage = 'registry.k8s.io/metrics-server/metrics-server:v0.8.0'
$metricsServerDigest = 'sha256:89258156d0e9af60403eafd44da9676fd66f600c7934d468ccc17e42b199aee2'
$metricsServerMirror = "k8s.m.daocloud.io/metrics-server/metrics-server@$metricsServerDigest"
$namespace = 'streamhub-ms'

function Invoke-Checked([string]$Label, [scriptblock]$Command) {
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

function Get-Sha256Hex([string]$Path) {
    $resolvedPath = (Resolve-Path -LiteralPath $Path -ErrorAction Stop).ProviderPath
    $stream = [System.IO.File]::OpenRead($resolvedPath)
    try {
        $sha256 = [System.Security.Cryptography.SHA256]::Create()
        try {
            $hashBytes = $sha256.ComputeHash($stream)
            return ([System.BitConverter]::ToString($hashBytes)).Replace('-', '').ToLowerInvariant()
        } finally {
            $sha256.Dispose()
        }
    } finally {
        $stream.Dispose()
    }
}

function Get-ExistingSecretValue([string]$Key) {
    $encoded = & kubectl --kubeconfig $kubeconfig get secret streamhub-ms-secrets `
        -n $namespace -o "jsonpath={.data.$Key}" 2>$null
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($encoded)) {
        throw "Existing streamhub-ms-secrets is missing $Key"
    }
    return [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($encoded))
}

function Test-DockerImage([string]$Image) {
    $savedErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'
    try {
        docker image inspect $Image *> $null
        return $LASTEXITCODE -eq 0
    } finally {
        $ErrorActionPreference = $savedErrorActionPreference
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

function Test-KubernetesSecret {
    $savedErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'
    try {
        kubectl --kubeconfig $kubeconfig get secret streamhub-ms-secrets `
            -n $namespace *> $null
        return $LASTEXITCODE -eq 0
    } finally {
        $ErrorActionPreference = $savedErrorActionPreference
    }
}

function Test-KubernetesDeployment([string]$Name) {
    $savedErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'
    try {
        kubectl --kubeconfig $kubeconfig get deployment $Name `
            -n $namespace *> $null
        return $LASTEXITCODE -eq 0
    } finally {
        $ErrorActionPreference = $savedErrorActionPreference
    }
}

function Test-MetricsReady {
    $savedErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'
    try {
        kubectl --kubeconfig $kubeconfig top pods -n $namespace *> $null
        return $LASTEXITCODE -eq 0
    } finally {
        $ErrorActionPreference = $savedErrorActionPreference
    }
}

Set-Location $root
Invoke-Checked 'workspace guard' { & $python scripts/check_microservices_workspace.py }
New-Item -ItemType Directory -Force -Path $toolsDir, $resultRoot | Out-Null

if (-not (Test-Path -LiteralPath $kind)) {
    $download = "$kind.download"
    Invoke-WebRequest -Uri "https://kind.sigs.k8s.io/dl/$kindVersion/kind-windows-amd64" -OutFile $download
    $actual = Get-Sha256Hex $download
    if ($actual -ne $kindSha256) {
        throw "Kind SHA-256 mismatch: $actual"
    }
    Move-Item -LiteralPath $download -Destination $kind
}
if ((Get-Sha256Hex $kind) -ne $kindSha256) {
    throw 'Existing Kind binary failed SHA-256 verification'
}
if (-not (Test-Path -LiteralPath $gitBash)) {
    throw 'Git Bash is required to run the existing deployment script'
}

$nodeContainer = "$ClusterName-control-plane"
$clusters = @(& $kind get clusters)
if ($clusters -notcontains $ClusterName) {
    if (-not (Test-DockerImage $nodeImage)) {
        if (-not (Test-DockerImage $nodeMirror)) {
            Invoke-Checked 'pull digest-pinned Kind node through mirror' { docker pull $nodeMirror }
        }
        Invoke-Checked 'docker tag Kind node image' { docker tag $nodeMirror $nodeImage }
    }
    Invoke-Checked 'kind create cluster' {
        & $kind create cluster --name $ClusterName --kubeconfig $kubeconfig --image $nodeImage --wait 180s
    }
} else {
    if (-not (Test-DockerContainerRunning $nodeContainer)) {
        Invoke-Checked 'start stopped Kind control-plane' {
            docker start $nodeContainer | Out-Null
        }
    }
    Invoke-Checked 'kind export kubeconfig' {
        & $kind export kubeconfig --name $ClusterName --kubeconfig $kubeconfig
    }
}

$images = @(
    "streamhub-user-service:$Version",
    "streamhub-content-service:$Version",
    "streamhub-social-service:$Version",
    "streamhub-gateway:$Version",
    "streamhub-frontend:$Version"
)
$archiveImages = @(
    'postgres:16',
    'ossrs/srs:5',
    'quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z'
)
function Test-NodeImage([string]$Image) {
    $savedErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'
    try {
        docker exec $nodeContainer crictl inspecti $Image *> $null
        return $LASTEXITCODE -eq 0
    } finally {
        $ErrorActionPreference = $savedErrorActionPreference
    }
}

foreach ($image in $images) {
    Invoke-Checked "inspect $image" { docker image inspect $image | Out-Null }
    if (-not (Test-NodeImage $image)) {
        Invoke-Checked "kind load docker-image $image" {
            & $kind load docker-image $image --name $ClusterName
        }
    }
}
foreach ($image in $archiveImages) {
    Invoke-Checked "inspect $image" { docker image inspect $image | Out-Null }
    if (-not (Test-NodeImage $image)) {
        $archiveDir = Join-Path $resultRoot 'image-archives'
        New-Item -ItemType Directory -Force -Path $archiveDir | Out-Null
        $archive = Join-Path $archiveDir (($image -replace '[/.:]', '-') + '-amd64.tar')
        Invoke-Checked "save linux/amd64 archive $image" {
            docker image save --platform linux/amd64 -o $archive $image
        }
        Invoke-Checked "kind load image-archive $image" {
            & $kind load image-archive $archive --name $ClusterName
        }
    }
}

$oldKubeconfig = $env:KUBECONFIG
$secretNames = @(
    'IMAGE_TAG', 'APP_VERSION', 'POSTGRES_PASSWORD', 'USER_SERVICE_DB_PASSWORD',
    'CONTENT_SERVICE_DB_PASSWORD', 'SOCIAL_SERVICE_DB_PASSWORD', 'SECRET_KEY',
    'MINIO_ROOT_USER', 'MINIO_ROOT_PASSWORD', 'PUBLIC_GATEWAY_URL', 'BACKEND_ONLY'
)
try {
    $env:KUBECONFIG = $kubeconfig
    $env:IMAGE_TAG = $Version
    $env:APP_VERSION = $Version
    $env:BACKEND_ONLY = 'true'
    if (Test-KubernetesSecret) {
        $env:POSTGRES_PASSWORD = Get-ExistingSecretValue 'POSTGRES_PASSWORD'
        $env:USER_SERVICE_DB_PASSWORD = Get-ExistingSecretValue 'USER_SERVICE_DB_PASSWORD'
        $env:CONTENT_SERVICE_DB_PASSWORD = Get-ExistingSecretValue 'CONTENT_SERVICE_DB_PASSWORD'
        $env:SOCIAL_SERVICE_DB_PASSWORD = Get-ExistingSecretValue 'SOCIAL_SERVICE_DB_PASSWORD'
        $env:SECRET_KEY = Get-ExistingSecretValue 'SECRET_KEY'
        $env:MINIO_ROOT_USER = Get-ExistingSecretValue 'MINIO_ROOT_USER'
        $env:MINIO_ROOT_PASSWORD = Get-ExistingSecretValue 'MINIO_ROOT_PASSWORD'
    } else {
        $env:POSTGRES_PASSWORD = "Pg-$([guid]::NewGuid().ToString('N'))"
        $env:USER_SERVICE_DB_PASSWORD = "Usr-$([guid]::NewGuid().ToString('N'))"
        $env:CONTENT_SERVICE_DB_PASSWORD = "Cnt-$([guid]::NewGuid().ToString('N'))"
        $env:SOCIAL_SERVICE_DB_PASSWORD = "Soc-$([guid]::NewGuid().ToString('N'))"
        $env:SECRET_KEY = "$([guid]::NewGuid().ToString('N'))$([guid]::NewGuid().ToString('N'))"
        $env:MINIO_ROOT_USER = 'streamhub-lab'
        $env:MINIO_ROOT_PASSWORD = "Min-$([guid]::NewGuid().ToString('N'))"
    }
    $env:PUBLIC_GATEWAY_URL = 'http://127.0.0.1:18100'
    Invoke-Checked 'deploy microservices' { & $gitBash scripts/deploy-microservices.sh }
    foreach ($optionalDeployment in @('frontend-ms', 'srs-ms')) {
        if (Test-KubernetesDeployment $optionalDeployment) {
            Invoke-Checked "scale optional deployment $optionalDeployment" {
                kubectl --kubeconfig $kubeconfig scale deployment/$optionalDeployment `
                    -n $namespace --replicas=0
            }
        }
    }
} finally {
    $env:KUBECONFIG = $oldKubeconfig
    foreach ($name in $secretNames) {
        Remove-Item "Env:$name" -ErrorAction SilentlyContinue
    }
}

$metricsManifest = Join-Path $resultRoot 'metrics-server-components.yaml'
$metricsPatchFile = Join-Path $resultRoot 'metrics-server-kind-patch.json'
Invoke-WebRequest `
    -Uri "https://github.com/kubernetes-sigs/metrics-server/releases/download/$metricsServerVersion/components.yaml" `
    -OutFile $metricsManifest
if ((Get-Sha256Hex $metricsManifest) -ne $metricsManifestSha256) {
    throw 'Metrics Server manifest failed SHA-256 verification'
}
if (-not (Test-NodeImage $metricsServerImage)) {
    if (-not (Test-DockerImage $metricsServerImage)) {
        if (-not (Test-DockerImage $metricsServerMirror)) {
            Invoke-Checked 'pull digest-pinned Metrics Server image through mirror' {
                docker pull $metricsServerMirror
            }
        }
        Invoke-Checked 'tag Metrics Server image' {
            docker tag $metricsServerMirror $metricsServerImage
        }
    }
    $metricsArchiveDir = Join-Path $resultRoot 'image-archives'
    New-Item -ItemType Directory -Force -Path $metricsArchiveDir | Out-Null
    $metricsArchive = Join-Path $metricsArchiveDir 'metrics-server-amd64.tar'
    Invoke-Checked 'save Metrics Server linux/amd64 archive' {
        docker image save --platform linux/amd64 -o $metricsArchive $metricsServerImage
    }
    Invoke-Checked 'load Metrics Server image archive' {
        & $kind load image-archive $metricsArchive --name $ClusterName
    }
}
Invoke-Checked 'install metrics-server' {
    kubectl --kubeconfig $kubeconfig apply -f $metricsManifest
}
$metricArgs = kubectl --kubeconfig $kubeconfig get deployment metrics-server -n kube-system -o jsonpath='{.spec.template.spec.containers[0].args}'
if ($metricArgs -notmatch '--kubelet-insecure-tls') {
    $patch = '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
    $utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($metricsPatchFile, $patch, $utf8WithoutBom)
    Invoke-Checked 'patch metrics-server for local Kind TLS' {
        kubectl --kubeconfig $kubeconfig patch deployment metrics-server -n kube-system `
            --type=json --patch-file $metricsPatchFile
    }
}
Invoke-Checked 'metrics-server rollout' {
    kubectl --kubeconfig $kubeconfig rollout status deployment/metrics-server -n kube-system --timeout=180s
}

$metricsReady = $false
for ($attempt = 1; $attempt -le 30; $attempt++) {
    if (Test-MetricsReady) {
        $metricsReady = $true
        break
    }
    Start-Sleep -Seconds 5
}
if (-not $metricsReady) {
    kubectl --kubeconfig $kubeconfig describe apiservice v1beta1.metrics.k8s.io
    kubectl --kubeconfig $kubeconfig logs deployment/metrics-server -n kube-system --tail=200
    throw 'kubectl top pods did not become ready'
}

kubectl --kubeconfig $kubeconfig get nodes -o wide
kubectl --kubeconfig $kubeconfig get pods -n $namespace -o wide
kubectl --kubeconfig $kubeconfig top pods -n $namespace
Write-Output "KIND_LAB=PASS cluster=$ClusterName version=$Version kubeconfig=$kubeconfig"
