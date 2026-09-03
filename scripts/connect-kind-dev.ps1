[CmdletBinding()]
param(
    [string]$ClusterName = 'streamhub-cicd',
    [string]$Namespace = 'streamhub-ms',
    [int]$ApiPort = 8099,        # 到 Kind 网关 (service/gateway:80) 的 REST 隧道
    [int]$RtmpPort = 1936,       # 到 SRS (service/srs-ms:1935) 的 RTMP 推流隧道，前端推流地址写死 1936
    [int]$HttpFlvPort = 8081,    # 到 SRS (service/srs-ms:8080) 的 HTTP-FLV 播放隧道
    [switch]$SkipLiveSrs,        # 不检查/部署 SRS 与 social 的 SRS 环境变量（只连 API + 前端）
    [switch]$NoFrontend,         # 不启动本地前端 dev server（只连隧道）
    [switch]$NoBrowser,          # 不自动打开浏览器
    [switch]$Teardown            # 停止本次脚本管理的隧道/前端进程（按端口清理）
)

# ---------------------------------------------------------------------------
# 一键把本地浏览器前端 + OBS 接到 Kind 后端（无需改任何代码/路径）。
# 前置条件（README 已覆盖）：已跑过一次 run-kind-cicd-gate 部署集群；
# node_modules 已装（npm ci）；kubectl、npm、node 在 PATH。
# 运行：powershell -ExecutionPolicy Bypass -File scripts\connect-kind-dev.ps1
# 结束：在该窗口按 Ctrl+C，或用同脚本加 -Teardown 清理。
# ---------------------------------------------------------------------------

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$kubeconfig = Join-Path $projectRoot '.ci-results\cloud-native\kind-lab-kubeconfig'
$srsManifest = Join-Path $projectRoot 'k8s\microservices\srs.yaml'
$webpackCli = Join-Path $projectRoot 'node_modules\.bin\webpack-dev-server.cmd'
$frontendPort = 3266            # webpack.config.js 写死的端口，勿改
$apiBase = "http://127.0.0.1:$ApiPort"
$rtmpBase = "rtmp://127.0.0.1:$RtmpPort/live"
$flvBase = "http://127.0.0.1:$HttpFlvPort/live"

function Write-Step([string]$m) { Write-Host "[kind-dev] $m" }

function Test-PortOpen([int]$port, [int]$timeoutSec = 3) {
    try {
        $c = New-Object System.Net.Sockets.TcpClient
        $iar = $c.BeginConnect('127.0.0.1', $port, $null, $null)
        if (-not $iar.AsyncWaitHandle.WaitOne($timeoutSec * 1000)) { $c.Close(); return $false }
        $c.EndConnect($iar); $c.Close(); return $true
    } catch { return $false }
}

function Test-Http([string]$url) {
    try {
        $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        return ($r.StatusCode -eq 200)
    } catch { return $false }
}

function Stop-ListenerOnPort([int]$port) {
    try {
        $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        foreach ($cn in $conns) {
            $proc = Get-Process -Id $cn.OwningProcess -ErrorAction SilentlyContinue
            Write-Step "端口 $port 被 PID $($cn.OwningProcess) ($($proc.ProcessName)) 占用，停止它"
            Stop-Process -Id $cn.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    } catch { }
}

function Get-DeployEnv([string]$deploy, [string]$key) {
    $q = "{.spec.template.spec.containers[0].env[?(@.name=='$key')].value}"
    $o = & kubectl --kubeconfig $kubeconfig -n $Namespace get deployment $deploy -o jsonpath="$q" 2>$null
    return ($o | Out-String).Trim()
}

function Invoke-Apply([string]$file) {
    & kubectl --kubeconfig $kubeconfig apply -f $file | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "kubectl apply 失败: $file" }
}

function Wait-Rollout([string]$deploy) {
    & kubectl --kubeconfig $kubeconfig -n $Namespace rollout status deployment/$deploy --timeout=240s | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "deployment/$deploy 未就绪" }
}

function Ensure-DeployEnv([string]$deploy, [string]$key, [string]$value) {
    $cur = Get-DeployEnv $deploy $key
    if ($cur -ne $value) {
        Write-Step "设置 $deploy 的 $key = $value"
        & kubectl --kubeconfig $kubeconfig -n $Namespace set env deployment/$deploy "$key=$value" | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "设置 $key 失败" }
        Wait-Rollout $deploy
    }
}

# ---------- 清理模式 ----------
if ($Teardown) {
    foreach ($p in @($ApiPort, $RtmpPort, $HttpFlvPort, $frontendPort)) { Stop-ListenerOnPort $p }
    Write-Step "清理完成。端口 ${ApiPort}/${RtmpPort}/${HttpFlvPort}/${frontendPort} 的监听进程已停止（如曾被占用）。"
    exit 0
}

# ---------- 预检 ----------
foreach ($tool in @('kubectl', 'npm', 'node')) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        Write-Host "[kind-dev] 缺少 $tool，请先安装并加入 PATH（见 README 第 1 节）" -ForegroundColor Red
        exit 1
    }
}
if (-not (Test-Path -LiteralPath $kubeconfig)) {
    Write-Host "[kind-dev] 找不到 kubeconfig：$kubeconfig" -ForegroundColor Red
    Write-Host "[kind-dev] 请先在本机跑一次完整门禁部署 Kind 集群：" -ForegroundColor Yellow
    Write-Host "        .\scripts\run-kind-cicd-gate.ps1 -Version `"dev-$(Get-Date -Format 'yyyyMMddHHmmss')`"" -ForegroundColor Yellow
    exit 2
}
$nsOk = & kubectl --kubeconfig $kubeconfig get ns $Namespace 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[kind-dev] Kind 集群里没有命名空间 $Namespace（后端未部署）。请先运行上面的 run-kind-cicd-gate.ps1。" -ForegroundColor Red
    exit 2
}
foreach ($open in @($ApiPort, $RtmpPort, $HttpFlvPort, $frontendPort)) {
    if (Test-PortOpen $open) {
        Write-Host "[kind-dev] 端口 $open 已被占用。可能是上次运行残留，先执行一次：-Teardown" -ForegroundColor Yellow
        exit 3
    }
}

# ---------- 确保直播后端（SRS + social 的 SRS 地址），Kind 门禁默认不部署 ----------
if (-not $SkipLiveSrs) {
    if (Test-Path -LiteralPath $srsManifest) {
        $hasSrs = & kubectl --kubeconfig $kubeconfig -n $Namespace get deployment srs-ms 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Step "未部署 srs-ms，正在部署（首次会拉镜像，需一会）"
            Invoke-Apply $srsManifest
            Wait-Rollout 'srs-ms'
        } else {
            Write-Step "srs-ms 已存在"
        }
        # 尽力开启 SRS 的 HTTP CORS，供浏览器跨端口拉 FLV
        Ensure-DeployEnv 'srs-ms' 'SRS_HTTP_SERVER_CROSSDOMAIN' 'on'
        # social-service 用它生成直播间 push/pull URL；Kind 门禁写的是空/ConfigMap，需与本机隧道端口一致
        Ensure-DeployEnv 'social-service' 'SRS_PUBLIC_RTMP_BASE' "rtmp://localhost:$RtmpPort/live"
        Ensure-DeployEnv 'social-service' 'SRS_PUBLIC_HTTP_BASE' "http://localhost:$HttpFlvPort/live"
    } else {
        Write-Step "未找到 $srsManifest，跳过 SRS 相关配置（直播不可用）"
    }
} else {
    Write-Step "已跳过 SRS/直播配置（-SkipLiveSrs）"
}

# ---------- 启动隧道（后台 Job）----------
$jobs = New-Object System.Collections.ArrayList

$gwJob = Start-Job -ScriptBlock {
    param($kc, $ns, $local)
    & kubectl --kubeconfig $kc -n $ns port-forward service/gateway "$local`:80"
} -ArgumentList $kubeconfig, $Namespace, $ApiPort
[void]$jobs.Add($gwJob)

$srsJob = Start-Job -ScriptBlock {
    param($kc, $ns, $rtmpLocal, $flvLocal)
    & kubectl --kubeconfig $kc -n $ns port-forward service/srs-ms "$rtmpLocal`:1935" "$flvLocal`:8080"
} -ArgumentList $kubeconfig, $Namespace, $RtmpPort, $HttpFlvPort
[void]$jobs.Add($srsJob)

Write-Step "等待隧道就绪（网关 $ApiPort、SRS $RtmpPort/$HttpFlvPort）..."
$deadline = (Get-Date).AddSeconds(60)
foreach ($probe in @(
        @{ p = $ApiPort;  what = 'REST 网关' },
        @{ p = $RtmpPort; what = 'RTMP 推流' },
        @{ p = $HttpFlvPort; what = 'HTTP-FLV' }
    )) {
    while (-not (Test-PortOpen $probe.p) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 800 }
    if (-not (Test-PortOpen $probe.p)) {
        Write-Host "[kind-dev] 隧道端口 $($probe.p)（$($probe.what)）未起来" -ForegroundColor Red
        foreach ($j in $jobs) { Receive-Job -Job $j -ErrorAction SilentlyContinue }
        throw "隧道启动失败"
    }
    Write-Step "隧道 OK: $($probe.what) 127.0.0.1:$($probe.p)"
}

# ---------- 本地前端 dev server ----------
if (-not $NoFrontend) {
    if (-not (Test-Path -LiteralPath $webpackCli)) {
        Write-Host "[kind-dev] 缺少 node_modules，请先 npm ci（README 第 4 节）" -ForegroundColor Red
        exit 1
    }
    $npmJob = Start-Job -ScriptBlock {
        param($root, $base, $proxy)
        Set-Location $root
        $env:REACT_APP_API_BASE_URL = $base
        $env:STREAMHUB_BACKEND_PROXY_TARGET = $proxy
        & npm run dev
    } -ArgumentList $projectRoot, $apiBase, $apiBase
    [void]$jobs.Add($npmJob)

    Write-Step "等待前端编译并监听 $frontendPort（首次约 5~15 秒）..."
    $up = $false
    $deadline = (Get-Date).AddSeconds(240)
    while ((Get-Date) -lt $deadline) {
        $st = $npmJob.State
        if ($st -eq 'Failed' -or $st -eq 'Completed') {
            Receive-Job -Job $npmJob
            throw "前端 dev server 异常退出（$st）"
        }
        if (Test-Http "http://127.0.0.1:$frontendPort/") { $up = $true; break }
        Start-Sleep -Milliseconds 1000
    }
    if (-not $up) {
        Write-Host "[kind-dev] 前端 $frontendPort 长时间未就绪，查看上方编译输出" -ForegroundColor Red
        throw '前端未就绪'
    }
    Write-Step "前端 OK: http://127.0.0.1:$frontendPort"
}

# ---------- 汇总 ----------
Write-Host ""
Write-Host "===================================================================" -ForegroundColor Cyan
Write-Host "  Kind 后端已就绪，本地访问入口：" -ForegroundColor Green
Write-Host "   * 网页前端    http://127.0.0.1:$frontendPort" -ForegroundColor White
Write-Host "   * REST 网关    http://127.0.0.1:$ApiPort/health" -ForegroundColor White
if (-not $SkipLiveSrs) {
    Write-Host "   * OBS 推流    服务器 $rtmpBase   （流密钥取网页「开播」页）" -ForegroundColor White
    Write-Host "   * 网页播放     $flvBase/<流密钥>.flv" -ForegroundColor White
}
Write-Host "===================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "此窗口保持打开即可继续使用；按 Ctrl+C 结束并自动清理隧道。" -ForegroundColor Yellow
if (-not $NoBrowser -and -not $NoFrontend) {
    Start-Process "http://127.0.0.1:$frontendPort/"
}

# ---------- 保持运行，Ctrl+C 清理 ----------
try {
    while ($true) { Start-Sleep -Seconds 3600 }
} finally {
    Write-Step "正在清理后台隧道/前端进程..."
    foreach ($j in $jobs) {
        Stop-Job -Job $j -ErrorAction SilentlyContinue
        Remove-Job -Job $j -Force -ErrorAction SilentlyContinue
    }
    foreach ($p in @($ApiPort, $RtmpPort, $HttpFlvPort, $frontendPort)) { Stop-ListenerOnPort $p }
    Write-Step "清理完成。"
}
