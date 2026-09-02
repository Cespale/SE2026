param(
    [int]$Runs = 3,
    [int]$ReadConcurrency = 16,
    [int]$ReadDurationSeconds = 20,
    [int]$LoginConcurrency = 4,
    [int]$LoginDurationSeconds = 30,
    [int]$WarmupSeconds = 5
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv-ms\Scripts\python.exe'
$composeFile = Join-Path $root 'docker-compose.performance.yml'
$runId = Get-Date -Format 'yyyyMMdd-HHmmssfff'
$resultDir = Join-Path $root ".ci-results/performance/$runId"
$rawDir = Join-Path $resultDir 'raw'
$envKeys = @(
    'PERF_POSTGRES_PASSWORD', 'PERF_USER_DB_PASSWORD',
    'PERF_CONTENT_DB_PASSWORD', 'PERF_SOCIAL_DB_PASSWORD',
    'PERF_MINIO_USER', 'PERF_MINIO_PASSWORD', 'PERF_SECRET_KEY',
    'SOURCE_DATABASE_URL', 'DESTINATION_DATABASE_URL'
)
$oldEnvironment = @{}
foreach ($key in $envKeys) {
    $oldEnvironment[$key] = [Environment]::GetEnvironmentVariable($key, 'Process')
}

function Invoke-Compose([string[]]$Arguments, [switch]$AllowFailure) {
    $output = & docker compose --project-name streamhub-perf -f $composeFile @Arguments 2>&1
    $code = $LASTEXITCODE
    if ($code -ne 0 -and -not $AllowFailure) {
        throw "docker compose $($Arguments -join ' ') failed: $output"
    }
    return $output
}

function Stop-Applications {
    Invoke-Compose -Arguments @(
        'stop', '-t', '20', 'gateway', 'social-service', 'content-service',
        'user-service', 'monolith'
    ) -AllowFailure | Out-Null
}

function Start-Version([string]$Version) {
    Stop-Applications
    if ($Version -eq 'monolith') {
        Invoke-Compose -Arguments @('up', '-d', '--wait', '--wait-timeout', '180', 'monolith') | Out-Null
        return
    }
    if ($Version -eq 'microservices') {
        Invoke-Compose -Arguments @('up', '-d', '--wait', '--wait-timeout', '180', 'gateway') | Out-Null
        return
    }
    throw "Unknown version: $Version"
}

function Assert-Probe([string]$Version, [string]$BaseUrl) {
    foreach ($path in @('/api/categories', '/api/videos?sort=latest&page=1&page_size=20')) {
        $response = Invoke-WebRequest -Uri "$BaseUrl$path" -TimeoutSec 15 -SkipHttpErrorCheck
        if ($response.StatusCode -ne 200) {
            throw "$Version probe failed: $path -> $($response.StatusCode)"
        }
    }
    $loginBody = @{ account = 'user'; password = 'user123' } | ConvertTo-Json -Compress
    $login = Invoke-WebRequest -Uri "$BaseUrl/api/auth/login" -Method Post `
        -ContentType 'application/json' -Body $loginBody -TimeoutSec 30 -SkipHttpErrorCheck
    if ($login.StatusCode -ne 200) {
        throw "$Version login probe failed: $($login.StatusCode)"
    }
}

function Get-Average($Values) {
    return [math]::Round(($Values | Measure-Object -Average).Average, 3)
}

function Get-RangeSummary($Values) {
    $measure = $Values | Measure-Object -Minimum -Maximum -Average
    return [ordered]@{
        mean = [math]::Round($measure.Average, 3)
        min = [math]::Round($measure.Minimum, 3)
        max = [math]::Round($measure.Maximum, 3)
    }
}

if ($Runs -lt 3) { throw 'Runs must be at least 3' }
Set-Location $root
& $python scripts/check_microservices_workspace.py
if ($LASTEXITCODE -ne 0) { throw 'workspace guard failed' }
New-Item -ItemType Directory -Force -Path $rawDir | Out-Null

$env:PERF_POSTGRES_PASSWORD = "pg-$([guid]::NewGuid().ToString('N'))"
$env:PERF_USER_DB_PASSWORD = "usr-$([guid]::NewGuid().ToString('N'))"
$env:PERF_CONTENT_DB_PASSWORD = "cnt-$([guid]::NewGuid().ToString('N'))"
$env:PERF_SOCIAL_DB_PASSWORD = "soc-$([guid]::NewGuid().ToString('N'))"
$env:PERF_MINIO_USER = 'streamhub-perf'
$env:PERF_MINIO_PASSWORD = "minio-$([guid]::NewGuid().ToString('N'))"
$env:PERF_SECRET_KEY = "secret-$([guid]::NewGuid().ToString('N'))"

$allResults = [System.Collections.Generic.List[object]]::new()
$completed = $false

try {
    docker version | Out-File (Join-Path $resultDir 'docker-version.txt')
    docker info | Out-File (Join-Path $resultDir 'docker-info.txt')
    Invoke-Compose -Arguments @('config', '--no-interpolate') | Out-File (Join-Path $resultDir 'compose-config.yaml')
    Invoke-Compose -Arguments @('build', 'monolith', 'user-service', 'content-service', 'social-service', 'gateway') | Out-File (Join-Path $resultDir 'build.log')

    # Remove only prior generated streamhub-perf containers; no named volume exists or is removed.
    Invoke-Compose -Arguments @('rm', '-s', '-f') -AllowFailure | Out-File (Join-Path $resultDir 'prior-container-cleanup.log')
    Invoke-Compose -Arguments @('up', '-d', '--wait', '--wait-timeout', '180', 'postgres-perf', 'minio-perf') | Out-File (Join-Path $resultDir 'infra-start.log')

    $streamKeySql = "UPDATE public.users SET stream_key = substr(md5(id::text), 1, 20) WHERE stream_key IS NULL;"
    Invoke-Compose -Arguments @('exec', '-T', 'postgres-perf', 'psql', '-v', 'ON_ERROR_STOP=1', '-U', 'postgres', '-d', 'streamhub', '-c', $streamKeySql) | Out-File (Join-Path $resultDir 'stream-key-normalization.log')

    $databaseUrl = "postgresql://postgres:$($env:PERF_POSTGRES_PASSWORD)@127.0.0.1:55435/streamhub"
    $env:SOURCE_DATABASE_URL = $databaseUrl
    $env:DESTINATION_DATABASE_URL = $databaseUrl
    & $python scripts/migrate_monolith_data.py | Out-File (Join-Path $resultDir 'data-migration.log')
    if ($LASTEXITCODE -ne 0) { throw 'controlled data migration failed' }

    $datasetSql = @'
WITH
pu AS (
  SELECT count(*) AS n, md5(COALESCE(string_agg(to_jsonb(t)::text, E'\n' ORDER BY id::text), '')) AS digest
  FROM (SELECT id, account, password_hash, nickname, avatar, bio, user_type, status, stream_key FROM public.users) t
),
mu AS (
  SELECT count(*) AS n, md5(COALESCE(string_agg(to_jsonb(t)::text, E'\n' ORDER BY id::text), '')) AS digest
  FROM (SELECT id, account, password_hash, nickname, avatar, bio, user_type, status, stream_key FROM user_service.users) t
),
pc AS (
  SELECT count(*) AS n, md5(COALESCE(string_agg(to_jsonb(t)::text, E'\n' ORDER BY id::text), '')) AS digest
  FROM (SELECT id, name, type, sort_order FROM public.categories) t
),
mc AS (
  SELECT count(*) AS n, md5(COALESCE(string_agg(to_jsonb(t)::text, E'\n' ORDER BY id::text), '')) AS digest
  FROM (SELECT id, name, type, sort_order FROM content_service.categories) t
),
pv AS (
  SELECT count(*) AS n, md5(COALESCE(string_agg(to_jsonb(t)::text, E'\n' ORDER BY id::text), '')) AS digest
  FROM (SELECT id, title, description, tags, cover_url, video_url, duration, category_id, view_count, like_count, comment_count, favorite_count, uploader_id, audit_status, status, reject_reason FROM public.videos) t
),
mv AS (
  SELECT count(*) AS n, md5(COALESCE(string_agg(to_jsonb(t)::text, E'\n' ORDER BY id::text), '')) AS digest
  FROM (SELECT id, title, description, tags, cover_url, video_url, duration, category_id, view_count, like_count, comment_count, favorite_count, uploader_id, audit_status, status, reject_reason FROM content_service.videos) t
)
SELECT json_build_object(
  'users', json_build_object('source_count', pu.n, 'target_count', mu.n, 'source_sha', pu.digest, 'target_sha', mu.digest, 'equal', pu.n = mu.n AND pu.digest = mu.digest),
  'categories', json_build_object('source_count', pc.n, 'target_count', mc.n, 'source_sha', pc.digest, 'target_sha', mc.digest, 'equal', pc.n = mc.n AND pc.digest = mc.digest),
  'videos', json_build_object('source_count', pv.n, 'target_count', mv.n, 'source_sha', pv.digest, 'target_sha', mv.digest, 'equal', pv.n = mv.n AND pv.digest = mv.digest)
)::text
FROM pu, mu, pc, mc, pv, mv;
'@
    $datasetOutput = Invoke-Compose -Arguments @('exec', '-T', 'postgres-perf', 'psql', '-tA', '-v', 'ON_ERROR_STOP=1', '-U', 'postgres', '-d', 'streamhub', '-c', $datasetSql)
    $datasetLine = $datasetOutput | Where-Object { $_ -match '^\{' } | Select-Object -Last 1
    if (-not $datasetLine) { throw 'dataset manifest query returned no JSON' }
    $dataset = $datasetLine | ConvertFrom-Json
    foreach ($table in @('users', 'categories', 'videos')) {
        if (-not $dataset.$table.equal) { throw "dataset mismatch: $table" }
    }
    [ordered]@{
        database_container = 'streamhub-perf-postgres'
        source_schema = 'public'
        target_schemas = @('user_service', 'content_service', 'social_service')
        tables = $dataset
    } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $resultDir 'dataset-manifest.json') -Encoding utf8

    $endpoints = @(
        [pscustomobject]@{ Name = 'categories'; Path = '/api/categories'; Method = 'GET'; Concurrency = $ReadConcurrency; Duration = $ReadDurationSeconds; Body = $null },
        [pscustomobject]@{ Name = 'videos-latest'; Path = '/api/videos?sort=latest&page=1&page_size=20'; Method = 'GET'; Concurrency = $ReadConcurrency; Duration = $ReadDurationSeconds; Body = $null },
        [pscustomobject]@{ Name = 'login'; Path = '/api/auth/login'; Method = 'POST'; Concurrency = $LoginConcurrency; Duration = $LoginDurationSeconds; Body = (@{ account = 'user'; password = 'user123' } | ConvertTo-Json -Compress) }
    )

    for ($run = 1; $run -le $Runs; $run++) {
        $versions = if ($run % 2 -eq 1) { @('monolith', 'microservices') } else { @('microservices', 'monolith') }
        foreach ($version in $versions) {
            Start-Version $version
            $baseUrl = if ($version -eq 'monolith') { 'http://127.0.0.1:18200' } else { 'http://127.0.0.1:18210' }
            Assert-Probe $version $baseUrl
            $appContainers = if ($version -eq 'monolith') {
                @('streamhub-perf-monolith')
            } else {
                @('streamhub-perf-gateway', 'streamhub-perf-user', 'streamhub-perf-content', 'streamhub-perf-social')
            }

            foreach ($endpoint in $endpoints) {
                $stem = "$version-$($endpoint.Name)-run$run"
                $jsonPath = Join-Path $rawDir "$stem.json"
                $csvPath = Join-Path $rawDir "$stem-stats.csv"
                $arguments = @(
                    'scripts/performance_load.py', '--url', "$baseUrl$($endpoint.Path)",
                    '--method', $endpoint.Method, '--concurrency', $endpoint.Concurrency,
                    '--duration', $endpoint.Duration, '--warmup', $WarmupSeconds,
                    '--timeout', '10', '--version', $version, '--endpoint', $endpoint.Name,
                    '--run', $run, '--json', $jsonPath, '--csv', $csvPath
                )
                if ($endpoint.Body) { $arguments += @('--body-json', $endpoint.Body) }
                foreach ($container in $appContainers) { $arguments += @('--app-container', $container) }
                $arguments += @('--infra-container', 'streamhub-perf-postgres')

                # performance_load.py runs docker stats once per sample and writes raw CSV.
                & $python @arguments
                if ($LASTEXITCODE -ne 0) { throw "benchmark failed: $stem" }
                $result = Get-Content -LiteralPath $jsonPath -Raw | ConvertFrom-Json
                $allResults.Add($result)
            }
        }
    }

    $aggregates = foreach ($group in ($allResults | Group-Object endpoint, version)) {
        $items = @($group.Group)
        [ordered]@{
            endpoint = $items[0].endpoint
            version = $items[0].version
            runs = $items.Count
            concurrency = $items[0].http.concurrency
            throughput_rps = Get-RangeSummary @($items.http.throughput_rps)
            average_ms = Get-RangeSummary @($items.http.average_ms)
            p95_ms = Get-RangeSummary @($items.http.p95_ms)
            error_rate_percent = Get-RangeSummary @($items.http.error_rate_percent)
            app_cpu_mean_percent = Get-RangeSummary @($items.resources.app_cpu_mean_percent)
            app_cpu_peak_percent = Get-RangeSummary @($items.resources.app_cpu_peak_percent)
            app_memory_mean_bytes = Get-RangeSummary @($items.resources.app_memory_mean_bytes)
            app_memory_peak_bytes = Get-RangeSummary @($items.resources.app_memory_peak_bytes)
            postgres_cpu_mean_percent = Get-RangeSummary @($items.resources.infra_cpu_mean_percent)
            postgres_memory_mean_bytes = Get-RangeSummary @($items.resources.infra_memory_mean_bytes)
        }
    }

    $summary = [ordered]@{
        result = 'PASS'
        generated_at = (Get-Date).ToUniversalTime().ToString('o')
        machine = [ordered]@{ docker_host = 'same-local-docker-desktop'; sequential_versions = $true }
        controls = [ordered]@{
            runs_per_endpoint_version = $Runs
            warmup_seconds = $WarmupSeconds
            read_concurrency = $ReadConcurrency
            read_duration_seconds = $ReadDurationSeconds
            login_concurrency = $LoginConcurrency
            login_duration_seconds = $LoginDurationSeconds
            monolith_cpu_limit = 0.5
            active_business_service_cpu_limit = 0.5
            same_postgres_container = $true
        }
        aggregates = @($aggregates)
        raw_runs = @($allResults)
        evidence_directory = $resultDir
    }
    $summary | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $resultDir 'summary.json') -Encoding utf8
    $completed = $true
    Write-Output "PERFORMANCE_COMPARISON=PASS evidence=$resultDir"
}
finally {
    Invoke-Compose -Arguments @('ps', '-a') -AllowFailure | Out-File (Join-Path $resultDir 'compose-ps-final.txt')
    Invoke-Compose -Arguments @('logs', '--no-color', '--tail', '500') -AllowFailure | Out-File (Join-Path $resultDir 'compose.log')
    Stop-Applications
    Invoke-Compose -Arguments @('stop', '-t', '20', 'postgres-perf', 'minio-perf') -AllowFailure | Out-Null
    foreach ($key in $envKeys) {
        if ($null -eq $oldEnvironment[$key]) {
            [Environment]::SetEnvironmentVariable($key, $null, 'Process')
        } else {
            [Environment]::SetEnvironmentVariable($key, $oldEnvironment[$key], 'Process')
        }
    }
    if (-not $completed) {
        Write-Error "PERFORMANCE_COMPARISON=FAIL evidence=$resultDir"
    }
}
