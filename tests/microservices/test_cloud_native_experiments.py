from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_user_service_hpa_has_bounded_cpu_scaling():
    hpa = yaml.safe_load(read("k8s/microservices/user-service-hpa.yaml"))
    assert hpa["apiVersion"] == "autoscaling/v2"
    assert hpa["kind"] == "HorizontalPodAutoscaler"
    assert hpa["spec"]["scaleTargetRef"] == {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "name": "user-service",
    }
    assert hpa["spec"]["minReplicas"] == 1
    assert hpa["spec"]["maxReplicas"] == 4
    metric = hpa["spec"]["metrics"][0]
    assert metric["resource"]["name"] == "cpu"
    assert metric["resource"]["target"] == {
        "type": "Utilization",
        "averageUtilization": 40,
    }
    assert hpa["spec"]["behavior"]["scaleDown"]["stabilizationWindowSeconds"] == 30


def test_user_service_has_cpu_request_and_limit_for_hpa():
    deployment = yaml.safe_load_all(read("k8s/microservices/user-service.yaml"))
    workload = next(item for item in deployment if item["kind"] == "Deployment")
    resources = workload["spec"]["template"]["spec"]["containers"][0]["resources"]
    assert resources["requests"]["cpu"] == "100m"
    assert resources["limits"]["cpu"] == "500m"


def test_business_services_pin_verified_non_root_uid():
    for service in ("user-service", "content-service", "social-service"):
        documents = yaml.safe_load_all(read(f"k8s/microservices/{service}.yaml"))
        workload = next(item for item in documents if item["kind"] == "Deployment")
        security = workload["spec"]["template"]["spec"]["securityContext"]
        assert security == {"runAsNonRoot": True, "runAsUser": 100, "runAsGroup": 101}


def test_gateway_has_bounded_timeout_and_designed_fallback():
    gateway = read("gateway/nginx.conf")
    assert "proxy_connect_timeout 500ms" in gateway
    assert "proxy_read_timeout 2s" in gateway
    assert "error_page 502 503 504 = @service_unavailable" in gateway
    assert 'return 503 \'{"detail":"上游服务暂不可用"}\'' in gateway
    auth_location = gateway.split("location ^~ /api/auth/ {", 1)[1].split("}", 1)[0]
    assert "proxy_read_timeout 10s" in auth_location


def test_gateway_keeps_only_capabilities_required_by_official_nginx_startup():
    documents = yaml.safe_load_all(read("k8s/microservices/gateway.yaml"))
    workload = next(item for item in documents if item["kind"] == "Deployment")
    security = workload["spec"]["template"]["spec"]["containers"][0]["securityContext"]
    assert security["allowPrivilegeEscalation"] is False
    assert security["capabilities"]["drop"] == ["ALL"]
    assert set(security["capabilities"]["add"]) == {
        "CHOWN",
        "SETGID",
        "SETUID",
        "NET_BIND_SERVICE",
    }


def test_frontend_has_startup_probe_for_first_webpack_compile():
    documents = yaml.safe_load_all(read("k8s/microservices/frontend.yaml"))
    workload = next(item for item in documents if item["kind"] == "Deployment")
    container = workload["spec"]["template"]["spec"]["containers"][0]
    probe = container["startupProbe"]
    assert probe["httpGet"] == {"path": "/", "port": 3266}
    assert probe["periodSeconds"] == 5
    assert probe["failureThreshold"] >= 40


def test_kind_setup_is_pinned_isolated_and_waits_for_metrics():
    script = read("scripts/setup-kind-lab.ps1")
    for required in (
        "v0.33.0",
        "v0.8.0",
        "streamhub-lab",
        "kind-lab-kubeconfig",
        "load docker-image",
        "--kubelet-insecure-tls",
        "kubectl top pods",
    ):
        assert required in script
    assert "Remove-Item Env:KUBECONFIG" not in script
    assert "docker compose down" not in script


def test_metrics_server_manifest_is_downloaded_then_applied_locally():
    script = read("scripts/setup-kind-lab.ps1")
    assert "Invoke-WebRequest" in script
    assert "metrics-server-components.yaml" in script
    assert "releases/download/$metricsServerVersion/components.yaml" in script
    assert 'kubectl --kubeconfig $kubeconfig apply -f $metricsManifest' in script
    assert '$kubectl =' not in script
    assert 'kubectl --kubeconfig $kubeconfig apply -f "https://' not in script


def test_metrics_server_image_and_manifest_are_digest_verified_and_preloaded():
    script = read("scripts/setup-kind-lab.ps1")
    assert "ff64d1a13b9ac3b0635f0dd985815fb44c23eed4706c04e5db1daadf6bc0a83b" in script
    assert "89258156d0e9af60403eafd44da9676fd66f600c7934d468ccc17e42b199aee2" in script
    assert "k8s.m.daocloud.io/metrics-server/metrics-server" in script
    assert "registry.k8s.io/metrics-server/metrics-server:v0.8.0" in script
    assert "metrics-server-amd64.tar" in script


def test_metrics_server_patch_uses_file_to_preserve_json_on_windows_ps51():
    script = read("scripts/setup-kind-lab.ps1")
    assert "metrics-server-kind-patch.json" in script
    assert "WriteAllText($metricsPatchFile" in script
    assert "--patch-file $metricsPatchFile" in script
    assert "-p $patch" not in script


def test_kind_setup_reuses_existing_secret_for_persistent_services():
    script = read("scripts/setup-kind-lab.ps1")
    assert "Get-ExistingSecretValue" in script
    assert "streamhub-ms-secrets" in script
    for key in (
        "POSTGRES_PASSWORD",
        "USER_SERVICE_DB_PASSWORD",
        "CONTENT_SERVICE_DB_PASSWORD",
        "SOCIAL_SERVICE_DB_PASSWORD",
        "SECRET_KEY",
        "MINIO_ROOT_USER",
        "MINIO_ROOT_PASSWORD",
    ):
        assert f"Get-ExistingSecretValue '{key}'" in script


def test_kind_lab_skips_unneeded_frontend_and_srs_workloads():
    setup = read("scripts/setup-kind-lab.ps1")
    deploy = read("scripts/deploy-microservices.sh")
    assert "$env:BACKEND_ONLY = 'true'" in setup
    assert "BACKEND_ONLY" in deploy
    assert 'if [[ "${BACKEND_ONLY:-false}" != "true" ]]' in deploy
    assert "function Test-KubernetesDeployment" in setup
    assert "if (Test-KubernetesDeployment $optionalDeployment)" in setup
    assert "scale deployment/$optionalDeployment" in setup


def test_kind_setup_has_digest_pinned_proxy_fallback():
    script = read("scripts/setup-kind-lab.ps1")
    assert "kindest/node:v1.37.0" in script
    assert "a1ed56cfb0e7b93589bdf97c8cd566405a265939e3620fc4f5de89adff580ae5" in script
    assert "docker.m.daocloud.io/kindest/node" in script
    assert "docker tag" in script


def test_kind_setup_preloads_all_images_used_by_manifests():
    script = read("scripts/setup-kind-lab.ps1")
    for image in (
        "postgres:16",
        "quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z",
        "ossrs/srs:5",
    ):
        assert image in script
    assert "load docker-image $image" in script
    assert "load docker-image $images" not in script
    assert "crictl inspecti" in script


def test_kind_image_existence_probes_tolerate_expected_misses_on_windows_ps51():
    script = read("scripts/setup-kind-lab.ps1")
    assert "function Test-DockerImage" in script
    node_probe = script[script.index("function Test-NodeImage"):script.index("foreach ($image in $images)")]
    docker_probe = script[script.index("function Test-DockerImage"):script.index("function Test-NodeImage")]
    for probe in (docker_probe, node_probe):
        assert "$ErrorActionPreference = 'SilentlyContinue'" in probe
        assert "finally" in probe
        assert "$ErrorActionPreference = $savedErrorActionPreference" in probe
    assert "if (-not (Test-DockerImage $nodeImage))" in script
    assert "if (-not (Test-DockerImage $metricsServerImage))" in script


def test_kind_expected_kubectl_misses_do_not_abort_windows_ps51():
    script = read("scripts/setup-kind-lab.ps1")
    for function_name in ("Test-KubernetesSecret", "Test-MetricsReady"):
        start = script.index(f"function {function_name}")
        end = script.index("\n}", start)
        probe = script[start:end]
        assert "$ErrorActionPreference = 'SilentlyContinue'" in probe
        assert "finally" in probe
    assert "if (Test-KubernetesSecret)" in script
    assert "if (Test-MetricsReady)" in script


def test_postgres_uses_single_platform_archive_for_kind_import():
    script = read("scripts/setup-kind-lab.ps1")
    archive_start = script.index("$archiveImages = @(")
    archive_end = script.index("\n)", archive_start)
    archive_images = script[archive_start:archive_end]
    assert "'postgres:16'" in archive_images
    assert "'ossrs/srs:5'" in archive_images
    assert "docker image save --platform linux/amd64" in script


def test_incomplete_multiplatform_minio_uses_single_platform_kind_archive():
    script = read("scripts/setup-kind-lab.ps1")
    direct_start = script.index("$images = @(")
    archive_start = script.index("$archiveImages = @(", direct_start)
    direct_images = script[direct_start:archive_start]
    archive_end = script.index("\n)", archive_start)
    archive_images = script[archive_start:archive_end]
    minio = "quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z"
    assert minio not in direct_images
    assert minio in archive_images
    assert "load image-archive" in script


def test_existing_deploy_script_can_use_windows_kubectl_from_wsl():
    script = read("scripts/deploy-microservices.sh")
    assert "command -v kubectl.exe" in script
    assert "kubectl()" in script


def test_experiment_script_asserts_scale_fault_isolation_and_recovery():
    script = read("scripts/run-cloud-native-experiments.ps1")
    guide = read("docs/microservices/cloud-native-experiments.md")
    assert "[int]$Concurrency = 4" in script
    for required in (
        "check_microservices_workspace.py",
        "user-service-hpa.yaml",
        "cloud_native_load.py",
        "scaled-up",
        "scaled-down",
        "content-service",
        "0x4E0A",
        "_services/user/health",
        "_services/social/health",
        ".ci-results/cloud-native",
        "finally",
    ):
        assert required in script
    assert "down -v" not in script
    assert "delete cluster" not in script
    pass_index = script.index('Write-Output "CLOUD_NATIVE_EXPERIMENTS=PASS')
    recovery_start = script.index("$contentRecoveryScale = Invoke-Kubectl")
    recovery_ready = script.index("$contentStopped = $false", recovery_start)
    acceptance_recovery = script[recovery_start:recovery_ready]
    recovery_evidence = script[recovery_start:pass_index]
    assert "--replicas=1" in acceptance_recovery
    assert "rollout" in acceptance_recovery
    assert "-AllowFailure" not in acceptance_recovery
    assert 'Wait-HttpStatus "$gatewayBase/api/live/rooms" 200 90' in acceptance_recovery
    assert "content-recovery-results.json" in recovery_evidence
    assert "get hpa,pods" not in guide
    assert "get hpa user-service -n streamhub-ms -w" in guide
    assert "get pods -n streamhub-ms -w" in guide


def test_experiment_script_source_is_windows_powershell_51_safe():
    source = (ROOT / "scripts/run-cloud-native-experiments.ps1").read_bytes()
    assert all(byte < 128 for byte in source), "Windows PowerShell 5.1 needs ASCII or UTF-8 BOM"
    script = source.decode("ascii")
    assert "??" not in script
    assert "-SkipHttpErrorCheck" not in script


def test_experiment_waits_before_reading_child_exit_code():
    script = read("scripts/run-cloud-native-experiments.ps1")
    exit_code_check = script.index("$loadProcess.ExitCode")
    assert "$loadProcess.WaitForExit()" in script[:exit_code_check]


def test_experiment_uses_process_api_when_capturing_load_output():
    script = read("scripts/run-cloud-native-experiments.ps1")
    assert "System.Diagnostics.ProcessStartInfo" in script
    assert "RedirectStandardOutput" in script
    assert "StandardOutput.ReadToEnd()" in script


def test_experiment_writes_machine_readable_json_without_utf8_bom():
    script = read("scripts/run-cloud-native-experiments.ps1")
    assert "Write-Utf8NoBom" in script
    assert "UTF8Encoding]::new($false)" in script
