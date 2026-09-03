<#
.SYNOPSIS
    一键接通「本地前端 / OBS / 浏览器」到 Kind 里的后端与 SRS 直播。
.DESCRIPTION
    为 Kind 集群(默认 streamhub-cicd)打通下列本地链路：
      - 网关隧道  127.0.0.1:8099  -> service/gateway  :80    (REST /api)
      - 直播隧道  127.0.0.1:1936  -> service/srs-ms   :1935  (OBS RTMP 推流)
      - 直播隧道  127.0.0.1:8081  -> service/srs-ms   :8080  (浏览器 HTTP-FLV)
      - 前端      127.0.0.1:3266  (webpack dev server, API 指向 8099 网关)
    默认会幂等“补齐”：若 Kind 里没有 srs-ms 则用 k8s/microservices/srs.yaml 部署，
    若 social-service 的 SRS_PUBLIC_* 不是 rtmp://localhost:1936/live 与
    http://localhost:8081/live 则修正(这决定直播间 pushUrl/pullUrl)。
    所有进程以后台方式启动并写日志到 .ci-results\kind-local\，脚本本身立即返回。
    -Cleanup 会停止本脚本启动(或同 kubeconfig+port-forward 特征)的转发与前端。
.EXAMPLE
    .\scripts\connect-kind-local.ps1
.EXAMPLE
    .\scripts\connect-kind-local.ps1 -SkipEnsure -NoBrowser
.EXAMPLE
    .\scripts\connect-kind-local.ps1 -Cleanup
#>
[CmdletBinding()]
param(
    [string]$ClusterName = 'streamhub-cicd',
    [string]$Namespace = 'streamhub-ms',
    [int]$GatewayPort = 8099,
    [int]$SrsRtmpPort = 1936,
    [int]$SrsHttpPort = 8081,
    [int]$FrontendPort = 3266,
    [switch]$SkipEnsure,      # 跳过 srs 部署与 social env 补齐
    [switch]$SkipFrontend,    # 不启动 webpack dev server
    [switch]$NoBrowser,       # 启动后不自动打开浏览器
    [switch]$Cleanup          # 停止相关转发/前端进程后退出
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$kubeconfig = Join-Path $root '.ci-results\cloud-native\kind-lab-kubeconfig'
$srsManifest = Join-Path $root 'k8s\microservices\srs.yaml'
$logDir = Join-Path $root '.ci-results\kind-local'
$namespaceArg = @('-n', $Namespace)

function Get-KubectlPath {
    $cmd = Get-Command kubectl -ErrorAction SilentlyContinue
    if (-not $cmd) { throw 'kubectl 不在 PATH。请先安装并按 README 配置。' }
    return $cmd.Source
}

function Test-TcpPort([int]$Port, [int]$TimeoutMs = 800) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $iar = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        if ($iar.AsyncWaitHandle.WaitOne($TimeoutMs)) {
            $client.EndConnect($iar)
            return $true
        }
    }
    catch { }
    finally { $client.Close() }
    return $false
}

function Test-HttpOk([string]$Url, [int]$TimeoutSec = 3) {
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec -ErrorAction Stop
        return $r.StatusCode -eq 200
    }
    catch { return $false }
}

function Start-Detached([string]$FilePath, [string]$ArgumentList, [string]$OutLog, [string]$ErrLog) {
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    if (Test-Path -LiteralPath $OutLog) { Remove-Item -LiteralPath $OutLog -Force }
    if (Test-Path -LiteralPath $ErrLog) { Remove-Item -LiteralPath $ErrLog -Force }
    return Start-Process -FilePath $FilePath -ArgumentList $ArgumentList -WindowStyle Hidden `
        -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog -PassThru
}

function Wait-Port([int]$Port, [int]$TimeoutSec) {
    for ($i = 0; $i -lt $TimeoutSec; $i++) {
        if (Test-TcpPort $Port) { return $true }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Wait-Http([string]$Url, [int]$TimeoutSec) {
    for ($i = 0; $i -lt $TimeoutSec; $i++) {
        if (Test-HttpOk $Url) { return $true }
        Start-Sleep -Seconds 1
    }
    return $false
}

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
if ($Cleanup) {
    $stopped = @()
    foreach ($p in @(Get-CimInstance Win32_Process -Filter "Name = 'kubectl.exe'" -ErrorAction SilentlyContinue)) {
        if ($p.CommandLine -and $p.CommandLine -like "*$kubeconfig*" -and $p.CommandLine -like '*port-forward*') {
            Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
            $stopped += "kubectl pid $($p.ProcessId)"
        }
    }
    foreach ($p in @(Get-CimInstance Win32_Process -Filter "Name = 'node.exe'" -ErrorAction SilentlyContinue)) {
        if ($p.CommandLine -and $p.CommandLine -like "*$root*" -and $p.CommandLine -like '*webpack*') {
            Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
            $stopped += "node pid $($p.ProcessId)"
        }
    }
    if ($stopped.Count -eq 0) { Write-Host '没有找到本脚本启动的转发/前端进程(或已停止)。' }
    else { Write-Host ('已停止：' + ($stopped -join '; ')) }
    exit 0
}

# ---------------------------------------------------------------------------
# 前置校验
# ---------------------------------------------------------------------------
$kubectl = Get-KubectlPath
if (-not (Test-Path -LiteralPath $kubeconfig)) {
    throw "未找到 kubeconfig：$kubeconfig 。请先运行 run-kind-cicd-gate.ps1 部署 Kind。"
}
& $kubectl --kubeconfig $kubeconfig get namespace $Namespace *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Kind 集群 $ClusterName 中没有命名空间 $Namespace 。请先运行门禁完成部署。"
}

# ---------------------------------------------------------------------------
# 幂等补齐 srs-ms 与 social-service 的 SRS 地址(可 -SkipEnsure 跳过)
# ---------------------------------------------------------------------------
if (-not $SkipEnsure) {
    $srsExists = $true
    & $kubectl --kubeconfig $kubeconfig @namespaceArg get deployment srs-ms *> $null
    if ($LASTEXITCODE -ne 0) { $srsExists = $false }

    if (-not $srsExists) {
        if (-not (Test-Path -LiteralPath $srsManifest)) { throw "缺少 SRS 清单：$srsManifest" }
        Write-Host '部署 srs-ms 到 Kind...' -ForegroundColor Cyan
        & $kubectl --kubeconfig $kubeconfig apply -f $srsManifest
        if ($LASTEXITCODE -ne 0) { throw 'kubectl apply srs.yaml 失败' }
        & $kubectl --kubeconfig $kubeconfig @namespaceArg rollout status deployment/srs-ms --timeout=180s
        if ($LASTEXITCODE -ne 0) { throw 'srs-ms 未就绪' }
    }

    # 读取 social-service 运行 Pod 里当前 SRS 地址；不一致则修正(幂等)。
    $socialPod = (& $kubectl --kubeconfig $kubeconfig @namespaceArg get pod `
        -l app=social-service -o jsonpath='{.items[0].metadata.name}' 2>$null)
    $wantRtmp = "rtmp://localhost:$SrsRtmpPort/live"
    $wantHttp = "http://localhost:$SrsHttpPort/live"
    $needSet = -not $socialPod
    if ($socialPod) {
        $curRtmp = (& $kubectl --kubeconfig $kubeconfig @namespaceArg exec $socialPod -- `
            sh -c 'echo ${SRS_PUBLIC_RTMP_BASE}' 2>$null).Trim()
        $curHttp = (& $kubectl --kubeconfig $kubeconfig @namespaceArg exec $socialPod -- `
            sh -c 'echo ${SRS_PUBLIC_HTTP_BASE}' 2>$null).Trim()
        if ($curRtmp -ne $wantRtmp -or $curHttp -ne $wantHttp) { $needSet = $true }
    }
    if ($needSet) {
        Write-Host "设置 social-service 的 SRS_PUBLIC_*(=$wantRtmp / $wantHttp)..." -ForegroundColor Cyan
        & $kubectl --kubeconfig $kubeconfig @namespaceArg set env deployment/social-service `
            "SRS_PUBLIC_RTMP_BASE=$wantRtmp" "SRS_PUBLIC_HTTP_BASE=$wantHttp"
        if ($LASTEXITCODE -ne 0) { throw 'kubectl set env social-service 失败' }
        & $kubectl --kubeconfig $kubeconfig @namespaceArg rollout status deployment/social-service --timeout=180s
        if ($LASTEXITCODE -ne 0) { throw 'social-service 未就绪' }
    }
}

# ---------------------------------------------------------------------------
# 网关隧道 8099 -> service/gateway:80
# ---------------------------------------------------------------------------
if (-not (Test-TcpPort $GatewayPort)) {
    Write-Host "启动网关隧道 $GatewayPort -> service/gateway:80 ..." -ForegroundColor Cyan
    $proc = Start-Detached $kubectl `
        "--kubeconfig=$kubeconfig -n $Namespace port-forward service/gateway $($GatewayPort):80" `
        (Join-Path $logDir 'gateway.stdout.log') (Join-Path $logDir 'gateway.stderr.log')
    if (-not (Wait-Http "http://127.0.0.1:$GatewayPort/health" 25)) {
        if ($proc.HasExited) {
            $err = if (Test-Path (Join-Path $logDir 'gateway.stderr.log')) {
                (Get-Content (Join-Path $logDir 'gateway.stderr.log') -Raw)
            } else { '(无日志)' }
            throw "网关隧道启动失败(进程退出)：$err"
        }
        throw "网关隧道 $GatewayPort 未能在 25s 内就绪"
    }
    Write-Host "  网关隧道 OK: http://127.0.0.1:$GatewayPort/health" -ForegroundColor Green
} else {
    Write-Host "  端口 $GatewayPort 已在监听，跳过网关转发。" -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------------
# SRS 隧道 1936(RTMP) + 8081(HTTP-FLV) -> service/srs-ms
# ---------------------------------------------------------------------------
$rtmpUp = Test-TcpPort $SrsRtmpPort
$httpUp = Test-HttpOk "http://127.0.0.1:$SrsHttpPort/"
if (-not ($rtmpUp -and $httpUp)) {
    if ($rtmpUp -or $httpUp) {
        Write-Warning "1936/8081 只起来一半($rtmpUp/$httpUp)，可能被其他进程占用；仍尝试补全 SRS 转发。"
    }
    Write-Host "启动直播隧道 $SrsRtmpPort->1935, $SrsHttpPort->8080 ..." -ForegroundColor Cyan
    $proc2 = Start-Detached $kubectl `
        "--kubeconfig=$kubeconfig -n $Namespace port-forward service/srs-ms $($SrsRtmpPort):1935 $($SrsHttpPort):8080" `
        (Join-Path $logDir 'srs.stdout.log') (Join-Path $logDir 'srs.stderr.log')
    $okRtmp = Wait-Port $SrsRtmpPort 25
    $okHttp = Wait-Http "http://127.0.0.1:$SrsHttpPort/" 25
    if (-not ($okRtmp -and $okHttp)) {
        if ($proc2.HasExited) {
            $err2 = if (Test-Path (Join-Path $logDir 'srs.stderr.log')) {
                (Get-Content (Join-Path $logDir 'srs.stderr.log') -Raw)
            } else { '(无日志)' }
            throw "SRS 隧道启动失败(进程退出)：$err2"
        }
        throw "SRS 隧道未能在 25s 内就绪(rtmp=$okRtmp http=$okHttp)"
    }
    Write-Host "  直播隧道 OK: RTMP $SrsRtmpPort / HTTP-FLV $SrsHttpPort" -ForegroundColor Green
} else {
    Write-Host "  端口 $SrsRtmpPort/$SrsHttpPort 已在监听，跳过 SRS 转发。" -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------------
# 前端 webpack dev server(指向网关隧道)
# ---------------------------------------------------------------------------
if (-not $SkipFrontend) {
    if (-not (Test-TcpPort $FrontendPort)) {
        Write-Host "启动前端 dev server(端口 $FrontendPort, API->$GatewayPort)..." -ForegroundColor Cyan
        $feOut = Join-Path $logDir 'frontend.stdout.log'
        $feErr = Join-Path $logDir 'frontend.stderr.log'
        New-Item -ItemType Directory -Force -Path $logDir | Out-Null
        if (Test-Path -LiteralPath $feOut) { Remove-Item -LiteralPath $feOut -Force }
        if (Test-Path -LiteralPath $feErr) { Remove-Item -LiteralPath $feErr -Force }
        $cmd = ("`$env:REACT_APP_API_BASE_URL='http://127.0.0.1:{0}'; " +
                "`$env:STREAMHUB_BACKEND_PROXY_TARGET='http://127.0.0.1:{0}'; " +
                '& npm.cmd run dev') -f $GatewayPort
        Start-Process -FilePath 'powershell.exe' `
            -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', $cmd `
            -WorkingDirectory $root -WindowStyle Hidden `
            -RedirectStandardOutput $feOut -RedirectStandardError $feErr | Out-Null
        if (-not (Wait-Http "http://127.0.0.1:$FrontendPort/" 120)) {
            $feLog = if (Test-Path -LiteralPath $feErr) { Get-Content -LiteralPath $feErr -Raw } else { '' }
            Write-Warning "前端未在 120s 内就绪，详见 $feOut / $feErr。$feLog"
        } else {
            Write-Host "  前端 OK: http://127.0.0.1:$FrontendPort" -ForegroundColor Green
        }
    } else {
        Write-Host "  端口 $FrontendPort 已在监听，跳过前端启动。" -ForegroundColor DarkGray
    }
}

# ---------------------------------------------------------------------------
# 汇总
# ---------------------------------------------------------------------------
Write-Host ''
Write-Host '================ Kind 本地接入就绪 ================' -ForegroundColor Green
Write-Host ("  前端页面        http://127.0.0.1:{0}" -f $FrontendPort)
Write-Host ("  REST API 隧道  http://127.0.0.1:{0}/health" -f $GatewayPort)
Write-Host ("  OBS 推流        rtmp://127.0.0.1:{0}/live  (服务器) + 页面里的流密钥" -f $SrsRtmpPort)
Write-Host ("  HTTP-FLV 播放   http://127.0.0.1:{0}/live/<流密钥>.flv" -f $SrsHttpPort)
Write-Host '  日志目录：.ci-results\kind-local\'
Write-Host ('  停止：.\scripts\connect-kind-local.ps1 -Cleanup')
Write-Host '===================================================' -ForegroundColor Green

if (-not $NoBrowser -and -not $SkipFrontend) {
    Start-Process "http://127.0.0.1:$FrontendPort"
}
