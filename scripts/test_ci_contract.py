from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "ci.yml"
EXPECTED_JOBS = {
    "contract-tests",
    "service-tests",
    "microservices-regression",
    "build-deploy",
}
BUSINESS_SERVICES = {"user-service", "content-service", "social-service"}


class CiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        cls.workflow = yaml.load(cls.workflow_text, Loader=yaml.BaseLoader)
        cls.jobs = cls.workflow["jobs"]

    def job_commands(self, name: str) -> str:
        return "\n".join(
            step.get("run", "") for step in self.jobs[name].get("steps", [])
        )

    def test_push_to_main_runs_the_pipeline(self) -> None:
        self.assertEqual(self.workflow["on"]["push"]["branches"], ["main"])
        paths = set(self.workflow["on"]["push"]["paths"])
        self.assertTrue(
            {"services/**", "shared/**", "gateway/**", "k8s/microservices/**"}.issubset(paths)
        )
        self.assertNotIn("docs/**", paths)

    def test_pipeline_has_four_explicit_gates(self) -> None:
        self.assertEqual(set(self.jobs), EXPECTED_JOBS)

    def test_each_business_service_has_an_independent_test_matrix_entry(self) -> None:
        matrix = self.jobs["service-tests"]["strategy"]["matrix"]["include"]
        self.assertEqual({item["service"] for item in matrix}, BUSINESS_SERVICES)
        for item in matrix:
            self.assertIn(item["service"], item["test_path"])
            self.assertIn(item["service"], item["requirements"])

    def test_service_tests_generate_junit(self) -> None:
        commands = self.job_commands("service-tests")
        self.assertIn("python -m pytest", commands)
        self.assertIn("--junitxml", commands)

    def test_regression_uses_the_microservices_compose_stack(self) -> None:
        commands = self.job_commands("microservices-regression")
        self.assertIn("docker-compose.microservices.yml", commands)
        self.assertIn("up -d --build --wait", commands)

    def test_all_public_apis_and_uc01_to_uc08_are_regressed(self) -> None:
        commands = self.job_commands("microservices-regression")
        self.assertIn("scripts/public_api_smoke.py", commands)
        self.assertIn("e2e/streamhub.spec.ts", commands)
        e2e = next(
            step
            for step in self.jobs["microservices-regression"]["steps"]
            if "Playwright" in step.get("name", "")
        )
        self.assertEqual(e2e["env"]["E2E_USE_MICROSERVICES"], "true")

    def test_deployment_is_blocked_until_every_gate_passes(self) -> None:
        deploy = self.jobs["build-deploy"]
        self.assertEqual(set(deploy["needs"]), EXPECTED_JOBS - {"build-deploy"})
        self.assertNotIn("always()", deploy.get("if", ""))

    def test_three_business_images_use_the_commit_version_and_never_latest(self) -> None:
        commands = self.job_commands("build-deploy")
        self.assertIn("GITHUB_SHA", commands)
        for service in BUSINESS_SERVICES:
            self.assertIn(f"streamhub-{service}:${{VERSION}}", commands)
        self.assertNotIn(":latest", commands)

    def test_versioned_images_are_published_to_ghcr(self) -> None:
        deploy = self.jobs["build-deploy"]
        self.assertEqual(deploy["permissions"]["packages"], "write")
        commands = self.job_commands("build-deploy")
        for service in BUSINESS_SERVICES:
            self.assertIn(f"ghcr.io/${{OWNER}}/streamhub-{service}:${{VERSION}}", commands)
        self.assertIn("docker push", commands)

    def test_kind_uses_microservice_deploy_and_health_scripts(self) -> None:
        commands = self.job_commands("build-deploy")
        self.assertIn("kind load docker-image", commands)
        self.assertIn("scripts/deploy-microservices.sh", commands)
        self.assertIn("scripts/health-check-microservices.sh", commands)

    def test_all_jobs_always_retain_success_or_failure_evidence(self) -> None:
        for name in EXPECTED_JOBS:
            uploads = [
                step
                for step in self.jobs[name]["steps"]
                if str(step.get("uses", "")).startswith("actions/upload-artifact@")
            ]
            self.assertEqual(len(uploads), 1, name)
            self.assertIn("always()", uploads[0].get("if", ""), name)
            self.assertTrue(uploads[0]["with"]["path"].startswith(".ci-results/"))

    def test_diagnostics_and_node24_compatible_actions_are_present(self) -> None:
        commands = self.job_commands("build-deploy")
        self.assertIn("collect-deployment-diagnostics.sh", commands)
        action_uses = {
            step.get("uses", "")
            for job in self.jobs.values()
            for step in job.get("steps", [])
            if step.get("uses")
        }
        self.assertTrue(
            {
                "actions/checkout@v6",
                "actions/setup-node@v6",
                "actions/setup-python@v6",
                "actions/upload-artifact@v6",
                "docker/login-action@v4",
                "helm/kind-action@v1.14.0",
            }.issubset(action_uses)
        )


if __name__ == "__main__":
    unittest.main()
