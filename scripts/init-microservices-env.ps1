[CmdletBinding()]
param(
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$target = Join-Path $projectRoot '.env.microservices'

if ((Test-Path -LiteralPath $target) -and -not $Force) {
    throw '.env.microservices already exists; use -Force only when replacement is intended'
}

function New-LocalSecret([string]$Prefix) {
    return "$Prefix-$([guid]::NewGuid().ToString('N'))"
}

$postgresPassword = New-LocalSecret 'Pg'
$userPassword = New-LocalSecret 'Usr'
$contentPassword = New-LocalSecret 'Cnt'
$socialPassword = New-LocalSecret 'Soc'
$minioPassword = New-LocalSecret 'Min'
$secretKey = "Key-$([guid]::NewGuid().ToString('N'))$([guid]::NewGuid().ToString('N'))"

$content = @"
POSTGRES_PASSWORD=$postgresPassword
POSTGRES_DB=streamhub
USER_SERVICE_DB_PASSWORD=$userPassword
CONTENT_SERVICE_DB_PASSWORD=$contentPassword
SOCIAL_SERVICE_DB_PASSWORD=$socialPassword
USER_DATABASE_URL=postgresql://streamhub_user_service:$userPassword@postgres-ms:5432/streamhub
CONTENT_DATABASE_URL=postgresql://streamhub_content_service:$contentPassword@postgres-ms:5432/streamhub
SOCIAL_DATABASE_URL=postgresql://streamhub_social_service:$socialPassword@postgres-ms:5432/streamhub
SECRET_KEY=$secretKey
APP_VERSION=local
MINIO_ROOT_USER=streamhub-ms
MINIO_ROOT_PASSWORD=$minioPassword
MINIO_BUCKET=streamhub-media
SERVICE_CONNECT_TIMEOUT_SECONDS=0.5
SERVICE_TOTAL_TIMEOUT_SECONDS=1.5
USER_SERVICE_URL=http://user-service:8000
CONTENT_SERVICE_URL=http://content-service:8000
SOCIAL_SERVICE_URL=http://social-service:8000
SRS_PUBLIC_RTMP_BASE=rtmp://localhost:1936/live
SRS_PUBLIC_HTTP_BASE=http://localhost:8081/live
"@

$utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($target, $content, $utf8WithoutBom)
Write-Output "MICROSERVICES_ENV=CREATED path=$target"
