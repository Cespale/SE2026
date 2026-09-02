param(
    [int]$Concurrency = 4,
    [int]$LoadDurationSeconds = 120,
    [int]$ScaleDownTimeoutSeconds = 240
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv-ms\Scripts\python.exe'
$kubeconfig = Join-Path $root '.ci-results/cloud-native/kind-lab-kubeconfig'
$namespace = 'streamhub-ms'
$gatewayBase = 'http://127.0.0.1:18100'
$runId = Get-Date -Format 'yyyyMMdd-HHmmssfff'
$resultDir = Join-Path $root ".ci-results/cloud-native/$runId"
$timelinePath = Join-Path $resultDir 'hpa-timeline.csv'
$topPath = Join-Path $resultDir 'user-service-top.txt'
$loadJson = Join-Path $resultDir 'load-results.json'
$loadStdout = Join-Path $resultDir 'load.stdout.log'
$loadStderr = Join-Path $resultDir 'load.stderr.log'
$portForwardStdout = Join-Path $resultDir 'port-forward.stdout.log'
$portForwardStderr = Join-Path $resultDir 'port-forward.stderr.log'
$portForward = $null
$loadProcess = $null
$contentStopped = $false
$timeline = [System.Collections.Generic.List[object]]::new()

function Invoke-Kubectl([string[]]$Arguments, [switch]$AllowFailure) {
    $output = & kubectl --kubeconfig $kubeconfig @Arguments 2>&1
    $code = $LASTEXITCODE
    if ($code -ne 0 -and -not $AllowFailure) {
        throw "kubectl $($Arguments -join ' ') failed: $output"
    }
    return $output
}

function Write-Utf8NoBom([string]$Path, [string]$Content) {
    [System.IO.File]::WriteAllText($Path, $Content, [System.Text.UTF8Encoding]::new($false))
}

function Get-DeploymentState([string]$Name) {
    $raw = Invoke-Kubectl -Arguments @('get', 'deployment', $Name, '-n', $namespace, '-o', 'json')
    $item = ($raw -join "`n") | ConvertFrom-Json
    return [pscustomobject]@{
        Desired = [int]($item.spec.replicas)
        Current = [int]($item.status.replicas)
        Ready = [int]($item.status.readyReplicas)
    }
}

function Get-HpaCpu {
    $raw = Invoke-Kubectl -Arguments @('get', 'hpa', 'user-service', '-n', $namespace, '-o', 'json')
    $item = ($raw -join "`n") | ConvertFrom-Json
    $value = $item.status.currentMetrics[0].resource.current.averageUtilization
    if ($null -eq $value) { return $null }
    return [int]$value
}

function Add-Timeline([string]$Phase) {
    $state = Get-DeploymentState 'user-service'
    $cpu = Get-HpaCpu
    $timeline.Add([pscustomobject]@{
        timestamp = (Get-Date).ToUniversalTime().ToString('o')
        phase = $Phase
        desired_replicas = $state.Desired
        current_replicas = $state.Current
        ready_replicas = $state.Ready
        cpu_average_utilization_percent = $cpu
    })
    $top = Invoke-Kubectl -Arguments @('top', 'pods', '-n', $namespace, '-l', 'app=user-service', '--no-headers') -AllowFailure
    Add-Content -LiteralPath $topPath -Value "[$((Get-Date).ToUniversalTime().ToString('o'))] $Phase`n$($top -join "`n")"
    return $state
}

function Invoke-Probe([string]$Uri) {
    $request = [System.Net.HttpWebRequest]::Create($Uri)
    $request.Method = 'GET'
    $request.Timeout = 5000
    $request.ReadWriteTimeout = 5000
    $response = $null
    try {
        $response = $request.GetResponse()
    } catch [System.Net.WebException] {
        $response = $_.Exception.Response
        if ($null -eq $response) {
            return [pscustomobject]@{ status = 0; body = $_.Exception.Message }
        }
    }
    try {
        $reader = [System.IO.StreamReader]::new(
            $response.GetResponseStream(),
            [System.Text.Encoding]::UTF8,
            $true
        )
        try {
            $body = $reader.ReadToEnd()
        } finally {
            $reader.Dispose()
        }
        return [pscustomobject]@{ status = [int]$response.StatusCode; body = $body }
    } finally {
        if ($null -ne $response) { $response.Close() }
    }
}

function Wait-Http([string]$Uri, [int]$TimeoutSeconds = 60) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $probe = Invoke-Probe $Uri
        if ($probe.status -gt 0 -and $probe.status -lt 500) { return }
        Start-Sleep -Seconds 2
    }
    throw "HTTP endpoint not ready: $Uri"
}

function Wait-HttpStatus([string]$Uri, [int]$ExpectedStatus, [int]$TimeoutSeconds = 60) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $lastProbe = $null
    while ((Get-Date) -lt $deadline) {
        $lastProbe = Invoke-Probe $Uri
        if ($lastProbe.status -eq $ExpectedStatus) { return $lastProbe }
        Start-Sleep -Seconds 2
    }
    if ($null -eq $lastProbe) {
        throw "HTTP endpoint returned no result: $Uri"
    }
    throw "HTTP endpoint expected $ExpectedStatus but got $($lastProbe.status): $Uri"
}

Set-Location $root
& $python scripts/check_microservices_workspace.py
if ($LASTEXITCODE -ne 0) { throw 'workspace guard failed' }
if (-not (Test-Path -LiteralPath $kubeconfig)) { throw "Missing Kind kubeconfig: $kubeconfig" }
New-Item -ItemType Directory -Force -Path $resultDir | Out-Null

try {
    Invoke-Kubectl -Arguments @('apply', '-f', (Join-Path $root 'k8s\microservices\user-service-hpa.yaml')) | Out-File (Join-Path $resultDir 'hpa-apply.log')
    Invoke-Kubectl -Arguments @('scale', 'deployment/user-service', '-n', $namespace, '--replicas=1') | Out-Null
    Invoke-Kubectl -Arguments @('rollout', 'status', 'deployment/user-service', '-n', $namespace, '--timeout=180s') | Out-Null

    $portForward = Start-Process kubectl -ArgumentList @(
        '--kubeconfig', $kubeconfig, 'port-forward', '-n', $namespace,
        'service/gateway', '18100:80'
    ) -RedirectStandardOutput $portForwardStdout -RedirectStandardError $portForwardStderr -WindowStyle Hidden -PassThru
    Wait-Http "$gatewayBase/health"

    $metricDeadline = (Get-Date).AddSeconds(120)
    do {
        $cpu = Get-HpaCpu
        if ($null -ne $cpu) { break }
        Start-Sleep -Seconds 5
    } while ((Get-Date) -lt $metricDeadline)
    if ($null -eq $cpu) { throw 'HPA CPU metric remained unknown' }

    $baselineDeadline = (Get-Date).AddSeconds($ScaleDownTimeoutSeconds)
    do {
        $baseline = Add-Timeline 'baseline'
        if ($baseline.Ready -eq 1) { break }
        Start-Sleep -Seconds 5
    } while ((Get-Date) -lt $baselineDeadline)
    if ($baseline.Ready -ne 1) { throw "Baseline expected 1 ready Pod, got $($baseline.Ready)" }

    $username = "hpa-$runId"
    $password = "Lab-$([guid]::NewGuid().ToString('N'))"
    $registerBody = @{ account = $username; password = $password; nickname = 'HPA Lab' } | ConvertTo-Json
    $register = Invoke-WebRequest -Uri "$gatewayBase/api/auth/register" -Method Post -ContentType 'application/json' -Body $registerBody -TimeoutSec 30 -UseBasicParsing
    if ($register.StatusCode -ne 200) { throw "Lab user registration failed: $($register.StatusCode)" }

    $loadStartInfo = New-Object System.Diagnostics.ProcessStartInfo
    $loadStartInfo.FileName = $python
    $loadStartInfo.Arguments = ('"scripts/cloud_native_load.py" --url "{0}/api/auth/login" --username "{1}" --password "{2}" --concurrency {3} --duration {4} --json "{5}"' -f $gatewayBase, $username, $password, $Concurrency, $LoadDurationSeconds, $loadJson)
    $loadStartInfo.WorkingDirectory = $root
    $loadStartInfo.UseShellExecute = $false
    $loadStartInfo.CreateNoWindow = $true
    $loadStartInfo.RedirectStandardOutput = $true
    $loadStartInfo.RedirectStandardError = $true
    $loadProcess = New-Object System.Diagnostics.Process
    $loadProcess.StartInfo = $loadStartInfo
    $loadProcess.Start() | Out-Null

    $scaledUp = $false
    while (-not $loadProcess.HasExited) {
        $state = Add-Timeline 'load'
        if ($state.Ready -ge 2) { $scaledUp = $true }
        Start-Sleep -Seconds 5
        $loadProcess.Refresh()
    }
    $loadProcess.WaitForExit()
    Write-Utf8NoBom $loadStdout $loadProcess.StandardOutput.ReadToEnd()
    Write-Utf8NoBom $loadStderr $loadProcess.StandardError.ReadToEnd()
    $loadProcess.Refresh()
    if ($loadProcess.ExitCode -ne 0) { throw "Load generator failed: $($loadProcess.ExitCode)" }
    if (-not $scaledUp) { throw 'HPA did not reach the scaled-up state' }

    $scaledDown = $false
    $downDeadline = (Get-Date).AddSeconds($ScaleDownTimeoutSeconds)
    do {
        $state = Add-Timeline 'cooldown'
        if ($state.Ready -eq 1) {
            $scaledDown = $true
            break
        }
        Start-Sleep -Seconds 5
    } while ((Get-Date) -lt $downDeadline)
    if (-not $scaledDown) { throw 'HPA did not reach the scaled-down state' }

    Invoke-Kubectl -Arguments @('scale', 'deployment/content-service', '-n', $namespace, '--replicas=0') | Out-Null
    $contentStopped = $true
    $faultDeadline = (Get-Date).AddSeconds(90)
    do {
        $contentState = Get-DeploymentState 'content-service'
        if ($contentState.Ready -eq 0) { break }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $faultDeadline)
    if ($contentState.Ready -ne 0) { throw 'content-service did not stop' }

    # After scaling to 0 there is a lag between readyReplicas=0 and kube-proxy/EndpointSlice removal;
    # a single probe can occasionally hit the window where requests are still routed to a
    # terminating Pod and return 200. Poll for the 503 degradation instead.
    $contentProbe = Wait-HttpStatus "$gatewayBase/api/videos" 503 90
    $userProbe = Invoke-Probe "$gatewayBase/_services/user/health"
    $socialProbe = Invoke-Probe "$gatewayBase/_services/social/health"
    $faultResult = [ordered]@{
        stopped_service = 'content-service'
        content_status = $contentProbe.status
        content_body = $contentProbe.body
        user_health_status = $userProbe.status
        social_health_status = $socialProbe.status
    }
    Write-Utf8NoBom (Join-Path $resultDir 'fault-results.json') ($faultResult | ConvertTo-Json)
    $designedFallback = -join (0x4E0A, 0x6E38, 0x670D, 0x52A1, 0x6682, 0x4E0D, 0x53EF, 0x7528 | ForEach-Object { [char]$_ })
    if ($contentProbe.status -ne 503 -or $contentProbe.body -notmatch $designedFallback) {
        throw "Designed fallback missing: status=$($contentProbe.status) body=$($contentProbe.body)"
    }
    if ($userProbe.status -ne 200 -or $socialProbe.status -ne 200) {
        throw "Fault isolation failed: user=$($userProbe.status) social=$($socialProbe.status)"
    }

    $contentRecoveryScale = Invoke-Kubectl -Arguments @('scale', 'deployment/content-service', '-n', $namespace, '--replicas=1')
    $contentRecoveryScale | Out-File (Join-Path $resultDir 'content-recovery-scale.log')
    $contentRecoveryRollout = Invoke-Kubectl -Arguments @('rollout', 'status', 'deployment/content-service', '-n', $namespace, '--timeout=180s')
    $contentRecoveryRollout | Out-File (Join-Path $resultDir 'content-recovery.log')
    $contentRecoveryProbe = Wait-HttpStatus "$gatewayBase/api/live/rooms" 200 90
    $contentStopped = $false
    $contentRecoveryResult = [ordered]@{
        service = 'content-service'
        cross_service_endpoint = '/api/live/rooms'
        status = $contentRecoveryProbe.status
        body = $contentRecoveryProbe.body
    }
    Write-Utf8NoBom (Join-Path $resultDir 'content-recovery-results.json') ($contentRecoveryResult | ConvertTo-Json)

    $timeline | Export-Csv -LiteralPath $timelinePath -NoTypeInformation -Encoding utf8
    Invoke-Kubectl -Arguments @('get', 'hpa', 'user-service', '-n', $namespace, '-o', 'yaml') | Out-File (Join-Path $resultDir 'hpa-final.yaml')
    Invoke-Kubectl -Arguments @('describe', 'hpa', 'user-service', '-n', $namespace) | Out-File (Join-Path $resultDir 'hpa-describe.txt')
    Invoke-Kubectl -Arguments @('get', 'pods', '-n', $namespace, '-o', 'wide') | Out-File (Join-Path $resultDir 'pods-final.txt')
    Invoke-Kubectl -Arguments @('get', 'events', '-n', $namespace, '--sort-by=.metadata.creationTimestamp') | Out-File (Join-Path $resultDir 'events.txt')
    Invoke-Kubectl -Arguments @('logs', 'deployment/gateway', '-n', $namespace, '--tail=200') -AllowFailure | Out-File (Join-Path $resultDir 'gateway.log')

    $loadResult = Get-Content -LiteralPath $loadJson -Raw | ConvertFrom-Json
    $maxPods = ($timeline | Measure-Object -Property ready_replicas -Maximum).Maximum
    $summary = [ordered]@{
        result = 'PASS'
        hpa = [ordered]@{ baseline_pods = 1; maximum_ready_pods = $maxPods; final_pods = 1; states = @('scaled-up', 'scaled-down') }
        load = $loadResult
        fault = $faultResult
        recovery = $contentRecoveryResult
        evidence_directory = $resultDir
    }
    Write-Utf8NoBom (Join-Path $resultDir 'experiment-summary.json') ($summary | ConvertTo-Json -Depth 8)
    Write-Output "CLOUD_NATIVE_EXPERIMENTS=PASS evidence=$resultDir"
} finally {
    if ($loadProcess -and -not $loadProcess.HasExited) {
        Stop-Process -Id $loadProcess.Id -Force -ErrorAction SilentlyContinue
    }
    if ($contentStopped) {
        Invoke-Kubectl -Arguments @('scale', 'deployment/content-service', '-n', $namespace, '--replicas=1') -AllowFailure | Out-Null
        Invoke-Kubectl -Arguments @('rollout', 'status', 'deployment/content-service', '-n', $namespace, '--timeout=180s') -AllowFailure | Out-File (Join-Path $resultDir 'content-recovery.log')
    }
    if ($timeline.Count) {
        $timeline | Export-Csv -LiteralPath $timelinePath -NoTypeInformation -Encoding utf8
    }
    if ($portForward -and -not $portForward.HasExited) {
        Stop-Process -Id $portForward.Id -Force -ErrorAction SilentlyContinue
    }
}
