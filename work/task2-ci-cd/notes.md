# Notes: 微服务 CI/CD 与可观测性

## Confirmed Constraints
- Source project is read-only: `C:\Users\lausu\Desktop\SE2026`.
- Working copy: `C:\Users\lausu\Desktop\SE2026-microservices`.
- Local only; no commit, push, or remote workflow run.
- Official business scope remains UC01–UC08.
- Keep databases, object storage, media, volumes, and historical evidence.

## Findings
- Existing `.github/workflows/ci.yml` tests/builds the monolith backend and frontend; it does not independently test or image user/content/social services.
- Existing service pytest suites already exercise business behavior, including protected and failure paths; the generated catalog contains 85 public interfaces (83 HTTP + 2 WebSocket).
- Existing K8s manifests already define liveness/readiness and per-service version environment values, but the gateway version is static.
- Docker Compose stack is currently running and healthy. Docker is available; kubectl has no current context; Kind and Minikube CLIs are absent.
- Therefore local Compose can provide fresh runtime proof. Kubernetes/remote Actions can only be configured and statically checked in this environment.

## Source Verification
- GitHub Actions official workflow syntax: `needs` blocks downstream jobs after a failure unless an `always()` condition overrides it.
- GitHub official artifact guidance: logs and test outputs should be retained as workflow artifacts for debugging.
- Kubernetes official docs: readiness removes an unready Pod from service endpoints; rollout status returns non-zero on a failed rollout; diagnose with get/describe/events/logs.

## Evidence
- RED contract run: 7 expected failures in `tests/microservices/test_ci_cd_contract.py`.
- CI/CD contracts: new pytest contract 9/9; compatibility unittest entry 12/12.
- Final local gate version `local-ci-20260830-fix1`: contracts 33, user 12, content 14, social 13; 72 backend/contract tests passed. Public catalog smoke passed 85/85 (83 HTTP runtime + 2 WebSocket behavior-suite references).
- Five immutable local images built: user/content/social/gateway/frontend tagged `local-ci-20260830-fix1`.
- Runtime Compose shows all eight services running; database, MinIO, three business services, and gateway are healthy.
- All three business services reported `ready` and version `local-ci-20260830-fix1`; logs saved under `.ci-results/microservices-local/local-ci-20260830-fix1`.
- Controlled missing-image deployment returned exit 125; image inspect returned 1; verified recovery image and running service version remained intact. No container or volume was changed.
- Cost/size observation: frontend image is about 1.7 GB; content image about 594 MB. This is non-blocking for item 2 but increases CI time/storage.
- A later final rerun found a real readiness race: `page.goto('/#/')` took 34.96 seconds immediately after frontend recreation. Root cause was missing Compose frontend healthcheck, not API failure; login/comment/danmaku requests were HTTP 200. Added an HTTP healthcheck on port 3266 so `docker compose up --wait` blocks until Webpack is serving.
- Post-fix E2E passed three times consecutively with independent reports: 3/3 in 41.8 seconds, 3/3 in 34.3 seconds, and final 3/3 in 29.8 seconds. The original failed Trace remains preserved.
- Fresh final JUnit audit: contracts 33/0, user 12/0, content 14/0, social 13/0, public API 85/0, E2E 3/0. TypeScript, Compose config, PowerShell/Bash syntax, and Python compilation checks passed.
- Latest safe failure drill: `.ci-results/deployment-failure-drill/20260830221958592`; expected deploy exit 125, missing-image inspect exit 1, and running user service stayed on `local-ci-20260830-fix1`.
