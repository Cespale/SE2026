[CmdletBinding()]
param(
    [string]$GoodVersion = 'local-ci-20260830',
    [string]$ResultsRoot = '.ci-results/deployment-failure-drill'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runId = Get-Date -Format 'yyyyMMddHHmmssfff'
$resultDir = Join-Path $projectRoot "$ResultsRoot/$runId"
$missingImage = "streamhub-user-service:missing-$runId"
$goodImage = "streamhub-user-service:$GoodVersion"
New-Item -ItemType Directory -Force -Path $resultDir | Out-Null

Set-Location -LiteralPath $projectRoot

$oldPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
& docker image inspect $missingImage *> "$resultDir/missing-image-inspect.txt"
$missingInspectExit = $LASTEXITCODE
& docker run --rm --pull=never $missingImage *> "$resultDir/deploy-attempt.txt"
$deployExit = $LASTEXITCODE
& docker image inspect $goodImage *> "$resultDir/good-image-inspect.txt"
$goodInspectExit = $LASTEXITCODE
$ErrorActionPreference = $oldPreference

if ($missingInspectExit -eq 0) {
    throw "Failure drill invalid: generated missing image unexpectedly exists: $missingImage"
}
if ($deployExit -eq 0) {
    throw 'Failure drill invalid: deployment unexpectedly succeeded'
}
if ($goodInspectExit -ne 0) {
    throw "Recovery image is unavailable: $goodImage"
}

$runningVersion = Invoke-RestMethod -Uri 'http://127.0.0.1:8100/_services/user/version' -TimeoutSec 5
$evidence = [ordered]@{
    drill = 'EXPECTED_FAILURE'
    failed_image = $missingImage
    deployment_exit_code = $deployExit
    missing_image_inspect_exit_code = $missingInspectExit
    recovery_image = $goodImage
    recovery_image_present = $true
    running_service_version = $runningVersion.version
    root_cause = 'The requested immutable image tag does not exist locally; --pull=never proves this before any container or volume is changed.'
    resolution = 'Deploy the verified existing immutable image tag, then re-run readiness and version checks.'
}
$evidence | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath "$resultDir/result.json" -Encoding utf8

@"
# 受控部署失败排查

- 结果：EXPECTED_FAILURE（预期失败，不计入最终版本失败数）
- 失败镜像：`$missingImage`
- 部署退出码：`$deployExit`
- 第一证据：`deploy-attempt.txt` 显示本地不存在该不可变标签。
- 第二证据：`missing-image-inspect.txt` 再次确认镜像不存在。
- 对照证据：`good-image-inspect.txt` 确认恢复版本 `$goodImage` 存在。
- 服务未受影响：当前 user-service 仍报告版本 `$($runningVersion.version)`。
- 根因：部署引用了不存在的镜像标签；不是数据库、业务代码或健康检查故障。
- 处理：改回已构建并验证的不可变版本，重新检查 `/ready` 和 `/version`。Kubernetes 现场再查看 rollout、Pod、Events、describe 与 logs。
"@ | Set-Content -LiteralPath "$resultDir/diagnosis.md" -Encoding utf8

Write-Output "DEPLOYMENT_FAILURE_DRILL=EXPECTED_FAILURE evidence=$resultDir"
