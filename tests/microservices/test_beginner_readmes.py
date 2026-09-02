from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "getting-started"
ENV_INIT = ROOT / "scripts" / "init-microservices-env.ps1"


def read(name: str) -> str:
    return (DOCS / name).read_text(encoding="utf-8")


def test_beginner_index_routes_readers_by_goal_without_hidden_context():
    index = read("README.md")
    for required in (
        "README-Docker-Compose.md",
        "README-Kind-CICD.md",
        "README-Testing-Troubleshooting.md",
        "完全不了解本项目",
        "Docker Desktop",
    ):
        assert required in index


def test_compose_readme_has_copy_start_verify_open_and_safe_stop():
    guide = read("README-Docker-Compose.md")
    for required in (
        ".env.microservices.example",
        "init-microservices-env.ps1",
        "Copy-Item",
        "up -d --build --wait",
        "http://127.0.0.1:5273",
        "http://127.0.0.1:8100/health",
        "docker compose",
        "down",
        "不要使用 `down -v`",
    ):
        assert required in guide


def test_env_initializer_generates_consistent_secrets_without_overwriting_by_default():
    script = ENV_INIT.read_text(encoding="ascii")
    for required in (
        "[switch]$Force",
        "NewGuid",
        "USER_SERVICE_DB_PASSWORD",
        "CONTENT_SERVICE_DB_PASSWORD",
        "SOCIAL_SERVICE_DB_PASSWORD",
        "USER_DATABASE_URL",
        "CONTENT_DATABASE_URL",
        "SOCIAL_DATABASE_URL",
        "UTF8Encoding($false)",
        "already exists",
    ):
        assert required in script
    assert "Write-Output $content" not in script


def test_kind_cicd_readme_has_dependencies_one_command_success_and_inspection():
    guide = read("README-Kind-CICD.md")
    for required in (
        "python -m venv .venv-ms",
        "requirements-microservices-test.txt",
        "npm ci",
        "npx playwright install chromium",
        "run-kind-cicd-gate.ps1",
        "KIND_CICD_GATE=PASS",
        "MICROSERVICES_HEALTH_CHECK=PASS",
        "kind-lab-kubeconfig",
        "kubectl",
        "不要使用 `latest`",
    ):
        assert required in guide


def test_kind_cicd_readme_explains_teammate_self_hosted_runner_integration():
    guide = read("README-Kind-CICD.md")
    for required in (
        "76b18e947342fcb459e3ef7c008e4c0f53aa108b",
        "self-hosted",
        "pull_request",
        "ubuntu-latest",
        "Linux x64",
        "远程未实跑",
        "8 GiB",
        "不要同时运行多个 Kind",
        "IMAGE_TAG",
    ):
        assert required in guide


def test_troubleshooting_readme_explains_evidence_and_common_failures():
    guide = read("README-Testing-Troubleshooting.md")
    for required in (
        "PUBLIC_API_SMOKE=PASS total=85",
        "3 passed",
        "KIND_CICD_GATE=FAIL",
        "ImagePullBackOff",
        "kubectl describe",
        "kubectl logs",
        "get events",
        "kind-diagnostics",
        "不要把 `.env.microservices`",
    ):
        assert required in guide
