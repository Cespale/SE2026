import importlib.util
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
SMOKE_SCRIPT = ROOT / "scripts" / "public_api_smoke.py"
KIND_CICD_SCRIPT = ROOT / "scripts" / "run-kind-cicd-gate.ps1"
KIND_SETUP_SCRIPT = ROOT / "scripts" / "setup-kind-lab.ps1"


def load_workflow():
    return yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def load_smoke_module():
    spec = importlib.util.spec_from_file_location("public_api_smoke", SMOKE_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_workflow_tests_each_business_service_independently():
    workflow = load_workflow()
    paths = set(workflow["on"]["push"]["paths"])
    assert {"services/**", "shared/**", "gateway/**", "k8s/microservices/**"}.issubset(paths)
    assert "docs/**" not in paths
    jobs = workflow["jobs"]
    matrix = jobs["service-tests"]["strategy"]["matrix"]["include"]
    assert {item["service"] for item in matrix} == {
        "user-service",
        "content-service",
        "social-service",
    }
    for item in matrix:
        assert item["test_path"].startswith("services/")
        assert item["requirements"].startswith("services/")
    commands = "\n".join(
        step.get("run", "") for step in jobs["service-tests"]["steps"]
    )
    assert "pytest" in commands
    assert "--junitxml" in commands


def test_upstream_self_hosted_runner_is_used_only_for_trusted_main_pushes():
    workflow = load_workflow()
    expected_runner = "${{ github.event_name == 'push' && 'self-hosted' || 'ubuntu-latest' }}"
    for job_name in (
        "contract-tests",
        "service-tests",
        "microservices-regression",
        "build-deploy",
    ):
        assert workflow["jobs"][job_name]["runs-on"] == expected_runner
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "76b18e947342fcb459e3ef7c008e4c0f53aa108b" in source


def test_workflow_runs_public_api_and_uc01_to_uc08_regression_before_deploy():
    jobs = load_workflow()["jobs"]
    regression = jobs["microservices-regression"]
    assert set(regression["needs"]) == {"contract-tests", "service-tests"}
    commands = "\n".join(step.get("run", "") for step in regression["steps"])
    assert "docker-compose.microservices.yml" in commands
    assert "scripts/public_api_smoke.py" in commands
    assert "playwright" in commands
    assert ".ci-results/microservices-regression" in commands
    e2e_step = next(
        step for step in regression["steps"] if "Playwright" in step.get("name", "")
    )
    assert e2e_step["env"]["E2E_USE_MICROSERVICES"] == "true"


def test_versioned_microservice_images_and_deploy_are_blocked_by_tests():
    jobs = load_workflow()["jobs"]
    deploy = jobs["build-deploy"]
    assert set(deploy["needs"]) == {"contract-tests", "service-tests", "microservices-regression"}
    assert "always()" not in deploy.get("if", "")
    commands = "\n".join(step.get("run", "") for step in deploy["steps"])
    assert "GITHUB_SHA" in commands
    for image in (
        "streamhub-user-service:${VERSION}",
        "streamhub-content-service:${VERSION}",
        "streamhub-social-service:${VERSION}",
    ):
        assert image in commands
    assert "scripts/deploy-microservices.sh" in commands
    assert "scripts/health-check-microservices.sh" in commands
    assert ":latest" not in commands


def test_success_and_failure_evidence_is_always_retained():
    jobs = load_workflow()["jobs"]
    for job_name in (
        "contract-tests",
        "service-tests",
        "microservices-regression",
        "build-deploy",
    ):
        uploads = [
            step
            for step in jobs[job_name]["steps"]
            if str(step.get("uses", "")).startswith("actions/upload-artifact@")
        ]
        assert len(uploads) == 1, job_name
        assert "always()" in uploads[0].get("if", ""), job_name
        assert uploads[0]["with"]["path"].startswith(".ci-results/"), job_name


def test_compose_and_gateway_expose_the_deployed_version():
    compose = yaml.safe_load(
        (ROOT / "docker-compose.microservices.yml").read_text(encoding="utf-8")
    )["services"]
    for service in ("user-service", "content-service", "social-service"):
        assert compose[service]["image"].endswith(":${IMAGE_TAG:-local-ms}")
    frontend_health = compose["frontend-ms"]["healthcheck"]
    assert "3266" in " ".join(frontend_health["test"])
    assert frontend_health["retries"] >= 20
    gateway_config = (ROOT / "gateway" / "nginx.conf").read_text(encoding="utf-8")
    gateway_entrypoint = (
        ROOT / "gateway" / "streamhub-entrypoint.sh"
    ).read_text(encoding="utf-8")
    assert "__APP_VERSION__" in gateway_config
    assert "APP_VERSION" in gateway_entrypoint
    assert "__APP_VERSION__" in gateway_entrypoint


def test_public_api_smoke_catalog_covers_all_85_public_interfaces():
    generator = (ROOT / "scripts" / "generate_api_catalog.py").read_text(
        encoding="utf-8"
    )
    assert "public_api_smoke.py" in generator
    smoke = load_smoke_module()
    entries = smoke.parse_catalog(ROOT / "docs" / "microservices" / "service-api-catalog.md")
    assert len(entries) == 85
    assert len({entry.test_id for entry in entries}) == 85
    assert sum(entry.method == "WEBSOCKET" for entry in entries) == 2
    assert smoke.materialize_path("/api/videos/{video_id}/related") == (
        "/api/videos/00000000-0000-0000-0000-000000000000/related"
    )
    assert smoke.materialize_path("/uploads/{media_path:path}") == (
        "/uploads/api-smoke-missing.bin"
    )
    assert smoke.is_acceptable_response(401, b'{"detail":"Not authenticated"}')
    assert smoke.is_acceptable_response(404, b'{"detail":"resource missing"}')
    assert not smoke.is_acceptable_response(404, "接口不存在".encode("utf-8"))
    assert not smoke.is_acceptable_response(405, b"")
    assert not smoke.is_acceptable_response(503, b"")


def test_deployment_diagnostics_collect_rollout_pods_events_and_logs():
    script = (ROOT / "scripts" / "collect-deployment-diagnostics.sh").read_text(
        encoding="utf-8"
    )
    assert "kubectl rollout status" in script
    assert "kubectl get pods" in script
    assert "kubectl describe" in script
    assert "kubectl get events" in script
    assert "kubectl logs" in script


def test_local_gate_runs_tests_build_deploy_api_e2e_and_observability():
    script = (ROOT / "scripts" / "run-local-microservices-gate.ps1").read_text(
        encoding="utf-8"
    )
    for required in (
        "pytest",
        "docker compose",
        "--build",
        "public_api_smoke.py",
        "playwright test",
        "logs --no-color",
        "/ready",
        "/version",
        "'/_services/user/health'",
        "'/health'",
    ):
        assert required in script


def test_local_gate_records_failure_and_always_collects_compose_diagnostics():
    script = (ROOT / "scripts" / "run-local-microservices-gate.ps1").read_text(
        encoding="utf-8"
    )
    assert "LOCAL_MICROSERVICES_GATE=FAIL" in script
    assert "catch" in script
    finally_block = script[script.index("finally {") :]
    assert "docker compose" in finally_block
    assert "logs --no-color" in finally_block
    assert "compose-ps.txt" in finally_block
    assert "service-logs.txt" in finally_block
    assert "Invoke-BestEffort" in finally_block


def test_failure_drill_is_safe_expected_and_diagnostic():
    script = (ROOT / "scripts" / "run-deployment-failure-drill.ps1").read_text(
        encoding="utf-8"
    )
    assert "--pull=never" in script
    assert "missing-" in script
    assert "docker image inspect" in script
    assert "EXPECTED_FAILURE" in script
    assert "down -v" not in script
    assert "Remove-Item" not in script


def test_local_kind_cicd_gate_runs_regression_docker_build_deploy_and_diagnostics():
    script = KIND_CICD_SCRIPT.read_text(encoding="ascii")
    for required in (
        "run-local-microservices-gate.ps1",
        "docker-compose.microservices.yml",
        "docker compose",
        "setup-kind-lab.ps1",
        "health-check-microservices.sh",
        "collect-deployment-diagnostics.sh",
        "KIND_CICD_GATE=PASS",
        "kind-lab-kubeconfig",
    ):
        assert required in script
    assert "down -v" not in script
    assert "delete cluster" not in script
    assert "latest" in script
    assert "IMAGE_TAG" in script


def test_local_kind_cicd_gate_records_failures_and_cleanup_is_best_effort():
    script = KIND_CICD_SCRIPT.read_text(encoding="ascii")
    assert "KIND_CICD_GATE=FAIL" in script
    assert "catch" in script
    assert "Invoke-BestEffort" in script
    finally_block = script[script.index("finally {") :]
    assert "Invoke-BestEffort" in finally_block
    assert "docker compose" in finally_block


def test_local_kind_gate_stops_all_running_control_planes_before_local_regression():
    script = KIND_CICD_SCRIPT.read_text(encoding="ascii")
    assert "Test-DockerContainerRunning" in script
    assert "label=io.x-k8s.kind.role=control-plane" in script
    assert "docker stop --time 30 $runningKindNode" in script
    assert script.index("docker stop --time 30 $runningKindNode") < script.index(
        "& $localGate"
    )
    finally_block = script[script.index("finally {") :]
    assert "foreach ($stoppedKindNode in $kindNodesStoppedForLocalGate)" in finally_block
    assert "docker start $stoppedKindNode" in finally_block
    assert "docker rm $runningKindNode" not in script


def test_kind_setup_hash_verification_does_not_require_get_file_hash_cmdlet():
    script = KIND_SETUP_SCRIPT.read_text(encoding="ascii")
    assert "Get-FileHash" not in script
    assert "function Get-Sha256Hex" in script
    assert "[System.Security.Cryptography.SHA256]::Create()" in script
    assert ".ComputeHash(" in script


def test_kind_setup_restarts_a_stopped_existing_control_plane_before_reuse():
    script = KIND_SETUP_SCRIPT.read_text(encoding="ascii")
    reuse_block = script[script.index("$clusters =") : script.index("$images =")]
    assert "Test-DockerContainerRunning" in reuse_block
    assert "docker start $nodeContainer" in reuse_block
    assert reuse_block.index("docker start $nodeContainer") < reuse_block.index(
        "kind export kubeconfig"
    )


def test_kind_health_check_covers_gateway_services_and_exact_version():
    script = (ROOT / "scripts" / "health-check-microservices.sh").read_text(
        encoding="utf-8"
    )
    for path in (
        "/health",
        "/ready",
        "/version",
        "/_services/user/health",
        "/_services/content/ready",
        "/_services/social/version",
    ):
        assert path in script
    assert "EXPECTED_VERSION" in script
    assert "version mismatch" in script
