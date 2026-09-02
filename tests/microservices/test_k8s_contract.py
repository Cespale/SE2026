from pathlib import Path

import yaml


ROOT = Path("k8s/microservices")
DEPLOY_SCRIPT = Path("scripts/deploy-microservices.sh")
HEALTH_SCRIPT = Path("scripts/health-check-microservices.sh")
GATEWAY_ENTRYPOINT = Path("gateway/streamhub-entrypoint.sh")
BUSINESS_SERVICES = ("user-service", "content-service", "social-service")


def resources():
    result = []
    for path in sorted(ROOT.glob("*.yaml")):
        for document in yaml.safe_load_all(path.read_text(encoding="utf-8")):
            if document:
                result.append(document)
    return result


def by_kind_name(kind: str, name: str):
    for item in resources():
        if item.get("kind") == kind and item.get("metadata", {}).get("name") == name:
            return item
    raise AssertionError(f"missing {kind}/{name}")


def test_each_business_service_is_independent_and_probeable():
    images = set()
    for name in BUSINESS_SERVICES:
        deployment = by_kind_name("Deployment", name)
        pod = deployment["spec"]["template"]["spec"]
        assert len(pod["containers"]) == 1
        container = pod["containers"][0]
        images.add(container["image"])
        assert container["image"].endswith(":replace-me")
        env = {entry["name"]: entry for entry in container["env"]}
        assert env["APP_VERSION"]["valueFrom"]["configMapKeyRef"]["name"] == "streamhub-ms-config"
        assert container["livenessProbe"]["httpGet"] == {"path": "/health", "port": 8000}
        assert container["readinessProbe"]["httpGet"] == {"path": "/ready", "port": 8000}
        assert container["resources"] == {
            "requests": {"cpu": "100m", "memory": "128Mi"},
            "limits": {"cpu": "500m", "memory": "512Mi"},
        }
        service = by_kind_name("Service", name)
        assert service["spec"].get("type", "ClusterIP") == "ClusterIP"
        assert service["spec"]["ports"][0]["port"] == 8000
    assert len(images) == 3


def test_supporting_stack_and_schema_job_are_present_without_host_coupling():
    for name in ("postgres-ms", "minio-ms", "gateway", "frontend-ms", "srs-ms"):
        by_kind_name("Deployment", name)
        by_kind_name("Service", name)
    job = by_kind_name("Job", "schema-migration")
    volumes = job["spec"]["template"]["spec"]["volumes"]
    assert any(
        item.get("configMap", {}).get("name") == "streamhub-schema-files"
        for item in volumes
    )
    seed_job = by_kind_name("Job", "data-seed")
    seed_volumes = seed_job["spec"]["template"]["spec"]["volumes"]
    assert any(
        item.get("configMap", {}).get("name") == "streamhub-schema-files"
        for item in seed_volumes
    )
    rendered = "\n".join(
        path.read_text(encoding="utf-8") for path in ROOT.glob("*.yaml")
    )
    assert "nodePort:" not in rendered
    assert "hostNetwork: true" not in rendered
    assert "hostPath:" not in rendered
    assert "container_name" not in rendered
    assert "kind: Secret" not in rendered
    gateway = by_kind_name("Deployment", "gateway")
    gateway_env = gateway["spec"]["template"]["spec"]["containers"][0]["env"]
    assert {item["name"]: item.get("value") for item in gateway_env}[
        "NGINX_STATIC_UPSTREAMS"
    ] == "true"
    entrypoint = GATEWAY_ENTRYPOINT.read_text(encoding="utf-8")
    assert "NGINX_STATIC_UPSTREAMS" in entrypoint
    assert "s/ resolve;/;/" in entrypoint


def test_deploy_and_health_scripts_enforce_versioned_rollouts():
    deploy = DEPLOY_SCRIPT.read_text(encoding="utf-8")
    assert '"${IMAGE_TAG:?IMAGE_TAG is required}"' in deploy
    assert '"${APP_VERSION:?APP_VERSION is required}"' in deploy
    assert 'CI' in deploy and 'latest' in deploy
    assert "kubectl create secret generic streamhub-ms-secrets" in deploy
    assert "kubectl create configmap streamhub-schema-files" in deploy
    assert "kubectl wait --for=condition=complete job/schema-migration" in deploy
    assert "kubectl wait --for=condition=complete job/data-seed" in deploy
    assert "00_monolith_backup.sql" in deploy
    assert "02-service-seed.sql" in deploy
    for name in BUSINESS_SERVICES:
        assert f"kubectl rollout status deployment/{name}" in deploy

    health = HEALTH_SCRIPT.read_text(encoding="utf-8")
    for service in BUSINESS_SERVICES:
        short = service.removesuffix("-service")
        for endpoint in ("health", "ready", "version"):
            assert f"/_services/{short}/{endpoint}" in health
    assert "port-forward service/gateway 8100:80" in health
