# StreamHub Business Microservices Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the copied FastAPI monolith with independently buildable, testable, deployable user, content, and social business services while preserving current public API paths and data.

**Architecture:** Keep a compatibility gateway in front of the copied monolith while extracting one complete service boundary at a time. Each service owns one PostgreSQL Schema and account; cross-service reads use internal HTTP, durable cross-service writes use an Outbox plus idempotent receivers, and no service queries another Schema.

**Tech Stack:** Python 3.11.9, FastAPI 0.115.6, Uvicorn 0.32.1, SQLAlchemy 2.0.36, PostgreSQL 16, httpx 0.28.1, MinIO 7.2.20, Nginx Alpine, Docker Compose v5.4.0, Kubernetes, pytest, Playwright.

**Execution status (2026-08-30):** Tasks 1–9 complete for course item 1. Task 7 used direct final cutover because Tasks 4–6 had already extracted and runtime-tested all three boundaries; the temporary legacy gateway remains a reference artifact but was never added to the final stack. Final regression evidence: 63 backend pytest tests and 3 Playwright E2E scenarios passed; the catalog covers 85 public and 11 internal APIs; 90/90 repeated service probes, the cross-service like/outbox flow, avatar upload/read, Schema isolation, independent image builds, and final health probes passed. Task 8 added 20 Kubernetes resources across 10 YAML files plus deployment/health scripts; Kubernetes API validation remains `UNVERIFIED_NO_KUBE_CONTEXT` because kubectl has no current context. Course items 2–4 (CI/CD, cloud-native experiments, and measured monolith/microservice performance comparison) remain separate follow-up work.

## Global Constraints

- Source `C:\Users\lausu\Desktop\SE2026` is read-only.
- Modify only `C:\Users\lausu\Desktop\SE2026-microservices`.
- Do not commit, push, create remote runs, or add Git metadata.
- Do not delete source PostgreSQL/MinIO data, media files, Volumes, reports, or historical evidence.
- Formal E2E scope is UC01–UC08; preserve all other currently implemented public functions and include their public APIs in Task 9 coverage.
- Use three business services named user, content, and social. Gateway, frontend, PostgreSQL, MinIO, and SRS do not count.
- Use Schemas `user_service`, `content_service`, and `social_service` with restricted accounts.
- Never create cross-Schema foreign keys, ORM relationships, SQL joins, or direct table access.
- Keep external `/api/*`, `/ws/*`, `/uploads/*`, and `/avatars/*` paths compatible.
- Use internal HTTP plus database Outbox; do not add RabbitMQ, Kafka, Redis, or Celery.
- Default service connection timeout is 0.5 seconds; total timeout is 1.5 seconds; idempotent reads retry at most twice.
- Each service must expose `/health`, `/ready`, and `/version`.
- Secrets remain in ignored local environment files and must never appear in logs, reports, commands captured as evidence, or code.
- All PowerShell commands must run under Windows PowerShell 5.1 and PowerShell 7 compatible syntax.
- Every claimed test count must come from newly generated logs or JUnit files.

---

## Locked File Structure

```text
database/
  init/01-service-schemas.sh
  migrations/001-service-tables.sql
gateway/
  Dockerfile
  nginx.conf
services/
  user-service/app/{config,database,main,models,schemas,security,outbox}.py
  user-service/tests/
  user-service/{Dockerfile,requirements.txt}
  content-service/app/{config,database,main,models,schemas,clients,outbox,object_storage}.py
  content-service/tests/
  content-service/{Dockerfile,requirements.txt}
  social-service/app/{config,database,main,models,schemas,clients,outbox}.py
  social-service/tests/
  social-service/{Dockerfile,requirements.txt}
shared/streamhub_common/{auth_context,request_id,service_client}.py
shared/tests/
scripts/{check_microservices_workspace,migrate_monolith_data,verify_schema_isolation}.py
scripts/py-ms.ps1
tests/microservices/
docs/microservices/
docker-compose.microservices.yml
.env.microservices.example
requirements-microservices-test.txt
```

Business models never enter `shared/`. Files change together by service, not by generic controller/repository layers.

---

### Task 1: Workspace guardrail and reproducible baseline

**Files:**
- Create: `.microservices-workspace.json`
- Create: `requirements-microservices-test.txt`
- Create: `scripts/py-ms.ps1`
- Create: `scripts/check_microservices_workspace.py`
- Create: `tests/microservices/test_workspace_guard.py`
- Create: `work/microservices/.gitkeep`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: copied workspace path and read-only source path.
- Produces: `check_workspace(root: Path) -> None`; exit code 0 and `WORKSPACE_GUARD=PASS` only for the copied workspace.

- [ ] **Step 1: Create the copy-local Python environment**

`requirements-microservices-test.txt`:

```text
-r backend/requirements-test.txt
```

`scripts/py-ms.ps1`:

```powershell
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv-ms\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw "Missing copy-local Python environment: $python"
}
& $python @args
exit $LASTEXITCODE
```

Run: `python -m venv .venv-ms`

Run: `& ".\scripts\py-ms.ps1" -m pip install -r requirements-microservices-test.txt`

Expected: pytest 9.1.1 and project dependencies install only under `.venv-ms`.

Add `.venv-ms/`, `.env.microservices`, and `work/microservices/*` with an exception for `.gitkeep` to `.gitignore`. This prevents secrets and generated evidence from accidental packaging even though the copy has no Git metadata.

- [ ] **Step 2: Write the failing guard test**

```python
from pathlib import Path

import pytest

from scripts.check_microservices_workspace import check_workspace


def test_accepts_copy_and_rejects_source():
    copy_root = Path(r"C:\Users\lausu\Desktop\SE2026-microservices")
    source_root = Path(r"C:\Users\lausu\Desktop\SE2026")
    check_workspace(copy_root)
    with pytest.raises(RuntimeError, match="read-only source"):
        check_workspace(source_root)
```

- [ ] **Step 3: Verify the test fails before the module exists**

Run: `& ".\scripts\py-ms.ps1" -m pytest tests/microservices/test_workspace_guard.py -q`

Expected: collection fails with `ModuleNotFoundError: No module named 'scripts.check_microservices_workspace'`.

- [ ] **Step 4: Add the immutable workspace marker**

```json
{
  "source": "C:\\Users\\lausu\\Desktop\\SE2026",
  "target": "C:\\Users\\lausu\\Desktop\\SE2026-microservices",
  "allow_git": false,
  "allow_remote": false
}
```

- [ ] **Step 5: Implement the guard**

```python
import json
from pathlib import Path


def check_workspace(root: Path) -> None:
    resolved = root.resolve()
    source = Path(r"C:\Users\lausu\Desktop\SE2026").resolve()
    target = Path(r"C:\Users\lausu\Desktop\SE2026-microservices").resolve()
    if resolved == source:
        raise RuntimeError("read-only source")
    if resolved != target:
        raise RuntimeError(f"unexpected workspace: {resolved}")
    marker = resolved / ".microservices-workspace.json"
    data = json.loads(marker.read_text(encoding="utf-8"))
    if Path(data["target"]).resolve() != target:
        raise RuntimeError("workspace marker target mismatch")
    if data["allow_git"] or data["allow_remote"]:
        raise RuntimeError("local-only policy mismatch")
    if (resolved / ".git").exists():
        raise RuntimeError("Git metadata is forbidden in the copy")


if __name__ == "__main__":
    check_workspace(Path.cwd())
    print("WORKSPACE_GUARD=PASS")
```

- [ ] **Step 6: Run the guard and preserve the baseline**

Run: `& ".\scripts\py-ms.ps1" -m pytest tests/microservices/test_workspace_guard.py -q`

Expected: `1 passed`.

Run: `& ".\scripts\py-ms.ps1" scripts/check_microservices_workspace.py`

Expected: `WORKSPACE_GUARD=PASS`.

Run: `& ".\scripts\py-ms.ps1" scripts/test_point_report.py | Tee-Object work/microservices/monolith-test-points.log`

Expected: historical baseline contains `POINTS_TOTAL=227`; this is evidence only, not a future microservice result.

- [ ] **Step 7: Local checkpoint**

Run: `Get-FileHash .microservices-workspace.json,scripts/check_microservices_workspace.py,tests/microservices/test_workspace_guard.py | Format-Table`

Expected: three SHA256 hashes. Do not run Git commands.

---

### Task 2: Shared HTTP contracts and request identity

**Files:**
- Create: `shared/__init__.py`
- Create: `shared/streamhub_common/__init__.py`
- Create: `shared/streamhub_common/auth_context.py`
- Create: `shared/streamhub_common/request_id.py`
- Create: `shared/streamhub_common/service_client.py`
- Create: `shared/tests/test_service_client.py`

**Interfaces:**
- Produces: `AuthContext`, `RequestIdMiddleware`, `ServiceClient.request_json(method, path, **kwargs)`, `ServiceUnavailable`.
- Consumes: `SERVICE_CONNECT_TIMEOUT`, `SERVICE_TOTAL_TIMEOUT`, `X-Request-ID`.

- [ ] **Step 1: Write failing tests for retry boundaries and request ID forwarding**

```python
import asyncio

import httpx
import pytest

from shared.streamhub_common.service_client import ServiceClient, ServiceUnavailable


def test_get_retries_twice_and_forwards_request_id():
    async def run():
        attempts = []

        def handler(request: httpx.Request) -> httpx.Response:
            attempts.append(request.headers["X-Request-ID"])
            if len(attempts) < 3:
                return httpx.Response(503, json={"detail": "busy"})
            return httpx.Response(200, json={"ok": True})

        client = ServiceClient(
            "http://user-service:8000",
            transport=httpx.MockTransport(handler),
        )
        result = await client.request_json("GET", "/internal/users", request_id="req-1")
        assert result == {"ok": True}
        assert attempts == ["req-1", "req-1", "req-1"]
        await client.client.aclose()

    asyncio.run(run())


def test_post_is_not_retried():
    async def run():
        attempts = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            return httpx.Response(503, json={"detail": "busy"})

        client = ServiceClient(
            "http://content-service:8000",
            transport=httpx.MockTransport(handler),
        )
        with pytest.raises(ServiceUnavailable):
            await client.request_json("POST", "/internal/events", request_id="req-2")
        assert attempts == 1
        await client.client.aclose()

    asyncio.run(run())
```

- [ ] **Step 2: Verify tests fail**

Run: `& ".\scripts\py-ms.ps1" -m pytest shared/tests/test_service_client.py -q`

Expected: import failure because `service_client.py` does not exist.

- [ ] **Step 3: Implement immutable authentication context**

```python
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AuthContext:
    user_id: UUID
    user_type: int
    status: int

    @property
    def is_creator(self) -> bool:
        return self.user_type >= 1 and self.status == 0

    @property
    def is_admin(self) -> bool:
        return self.user_type >= 2 and self.status == 0
```

- [ ] **Step 4: Implement request ID middleware**

```python
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
```

- [ ] **Step 5: Implement bounded service client**

```python
import asyncio
import os

import httpx


class ServiceUnavailable(RuntimeError):
    pass


class ServiceClient:
    def __init__(self, base_url: str, transport=None):
        connect = float(os.getenv("SERVICE_CONNECT_TIMEOUT", "0.5"))
        total = float(os.getenv("SERVICE_TOTAL_TIMEOUT", "1.5"))
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(total, connect=connect),
            transport=transport,
        )

    async def request_json(self, method: str, path: str, request_id: str, **kwargs):
        method = method.upper()
        max_attempts = 3 if method in {"GET", "HEAD"} else 1
        headers = dict(kwargs.pop("headers", {}))
        headers["X-Request-ID"] = request_id
        last_error = None
        for attempt in range(max_attempts):
            try:
                response = await self.client.request(
                    method,
                    f"{self.base_url}{path}",
                    headers=headers,
                    **kwargs,
                )
                if response.status_code < 500:
                    response.raise_for_status()
                    return response.json()
                last_error = RuntimeError(f"upstream status {response.status_code}")
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
            if attempt + 1 < max_attempts:
                await asyncio.sleep(0.05 * (2**attempt))
        raise ServiceUnavailable(str(last_error))
```

- [ ] **Step 6: Run tests**

Run: `& ".\scripts\py-ms.ps1" -m pytest shared/tests/test_service_client.py -q`

Expected: `2 passed`.

- [ ] **Step 7: Local checkpoint**

Run: `& ".\scripts\py-ms.ps1" -m compileall -q shared`

Expected: exit code 0. Do not commit.

---

### Task 3: PostgreSQL Schema ownership and safe data copier

**Files:**
- Create: `database/init/01-service-schemas.sh`
- Create: `database/migrations/001-service-tables.sql`
- Create: `.env.microservices.example`
- Create: `docker-compose.microservices.yml`
- Create: `scripts/migrate_monolith_data.py`
- Create: `scripts/verify_schema_isolation.py`
- Create: `tests/microservices/test_schema_contract.py`

**Interfaces:**
- Consumes: `POSTGRES_PASSWORD`, three service passwords, source and destination database URLs.
- Produces: three Schemas/roles, owned tables, copied rows, and `SCHEMA_ISOLATION=PASS`.

- [ ] **Step 1: Write the Schema contract test**

```python
from pathlib import Path


def test_schema_sql_has_three_owners_and_no_cross_schema_foreign_keys():
    sql = Path("database/migrations/001-service-tables.sql").read_text(encoding="utf-8")
    assert "user_service.users" in sql
    assert "content_service.videos" in sql
    assert "social_service.comments" in sql
    assert "social_service.video_favorites" in sql
    assert "integration_outbox" in sql
    assert "processed_events" in sql
    assert "REFERENCES user_service." not in sql
    assert "REFERENCES content_service." not in sql
    assert "REFERENCES social_service." not in sql
```

- [ ] **Step 2: Verify it fails because migration SQL is absent**

Run: `& ".\scripts\py-ms.ps1" -m pytest tests/microservices/test_schema_contract.py -q`

Expected: `FileNotFoundError`.

- [ ] **Step 3: Create roles and Schemas without embedding passwords**

`database/init/01-service-schemas.sh` must use `psql --set` variables and execute these exact ownership rules:

```sql
CREATE SCHEMA IF NOT EXISTS user_service AUTHORIZATION streamhub_user_service;
CREATE SCHEMA IF NOT EXISTS content_service AUTHORIZATION streamhub_content_service;
CREATE SCHEMA IF NOT EXISTS social_service AUTHORIZATION streamhub_social_service;
REVOKE ALL ON SCHEMA user_service FROM PUBLIC;
REVOKE ALL ON SCHEMA content_service FROM PUBLIC;
REVOKE ALL ON SCHEMA social_service FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA user_service TO streamhub_user_service;
GRANT USAGE, CREATE ON SCHEMA content_service TO streamhub_content_service;
GRANT USAGE, CREATE ON SCHEMA social_service TO streamhub_social_service;
```

The shell script must create a missing role with `SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', role_name, password) \gexec`, then reset its password idempotently. It must not echo environment values.

- [ ] **Step 4: Create exact table ownership migration**

Create tables in this dependency order:

```text
user_service: users, follows, conversations, messages, notifications, processed_events
content_service: categories, videos, integration_outbox, processed_events
social_service: comments, comment_mentions, video_likes, video_favorites,
                video_interaction_baselines, danmaku, live_rooms, reports, sensitive_words,
                integration_outbox, processed_events
```

Wrap each group with `SET ROLE streamhub_<service>; SET search_path TO <schema>;` and finish with `RESET ROLE;`. This makes tables, sequences, and indexes owned by the correct restricted account instead of `postgres`.

Within-Schema foreign keys are allowed only for:

```text
user_service.messages.conversation_id -> user_service.conversations.id
user_service.notifications recipient/sender -> user_service.users.id
content_service.videos.category_id -> content_service.categories.id
social_service.comment_mentions.comment_id -> social_service.comments.id
```

All user IDs, video IDs, category IDs, reporter IDs, handler IDs, and target IDs owned elsewhere are plain typed columns without foreign keys.

- [ ] **Step 5: Implement an idempotent copier**

`scripts/migrate_monolith_data.py` must:

```python
TABLE_MAP = {
    "users": "user_service",
    "follows": "user_service",
    "conversations": "user_service",
    "messages": "user_service",
    "notifications": "user_service",
    "categories": "content_service",
    "videos": "content_service",
    "comments": "social_service",
    "comment_mentions": "social_service",
    "video_likes": "social_service",
    "danmaku": "social_service",
    "live_rooms": "social_service",
    "reports": "social_service",
    "sensitive_words": "social_service",
}
```

Reflect each source table from `public`, reflect its target table from the assigned Schema, copy rows with PostgreSQL `ON CONFLICT DO NOTHING`, and compare source/target row counts. Never issue DELETE, DROP, TRUNCATE, or UPDATE against the source engine. Exit nonzero when a target count is smaller than its source count.

Seed `social_service.video_interaction_baselines` idempotently from each source video. For likes, comments, and favorites, store `max(source aggregate counter - copied detail row count, 0)`. Social absolute-count events add this residual to current detail counts so legacy aggregate data is not lost.

- [ ] **Step 6: Implement permission verification**

`scripts/verify_schema_isolation.py` must connect as each service account, verify one owned SELECT succeeds, and verify both foreign Schema SELECTs fail with `psycopg2.errors.InsufficientPrivilege`. Print only `SCHEMA_ISOLATION=PASS` on success.

- [ ] **Step 7: Run static contract test**

Run: `& ".\scripts\py-ms.ps1" -m pytest tests/microservices/test_schema_contract.py -q`

Expected: `1 passed`.

- [ ] **Step 8: Create and start the isolated PostgreSQL foundation**

Create `.env.microservices.example` with variable names and safe examples only. Create a local ignored `.env.microservices` with strong values for `POSTGRES_PASSWORD`, `USER_SERVICE_DB_PASSWORD`, `CONTENT_SERVICE_DB_PASSWORD`, and `SOCIAL_SERVICE_DB_PASSWORD`.

The initial `docker-compose.microservices.yml` contains only this foundation; Task 7 adds the remaining services:

```yaml
name: streamhub-ms
services:
  postgres-ms:
    image: postgres:16
    env_file: .env.microservices
    environment:
      POSTGRES_USER: postgres
      POSTGRES_DB: streamhub
    ports:
      - "127.0.0.1:5434:5432"
    volumes:
      - streamhub_ms_pgdata:/var/lib/postgresql/data
      - ./backend/docker-init/01_streamhub_backup.sql:/docker-entrypoint-initdb.d/01-streamhub-backup.sql:ro
      - ./database/init/01-service-schemas.sh:/docker-entrypoint-initdb.d/02-service-schemas.sh:ro
      - ./database/migrations/001-service-tables.sql:/docker-entrypoint-initdb.d/03-service-tables.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d streamhub"]
      interval: 5s
      timeout: 5s
      retries: 20
volumes:
  streamhub_ms_pgdata:
```

Run: `& ".\scripts\py-ms.ps1" scripts/check_microservices_workspace.py`.

Expected: `WORKSPACE_GUARD=PASS`.

Run: `docker compose -f docker-compose.microservices.yml up -d postgres-ms`.

Expected: `postgres-ms` healthy on host port 5434. Never point migration or permission scripts at port 5433.

- [ ] **Step 9: Copy source rows without printing credentials**

Read `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` from `streamhub-postgres` into PowerShell variables, URL-encode the password with `[Uri]::EscapeDataString`, set process-only `SOURCE_DATABASE_URL` and `DESTINATION_DATABASE_URL`, run the copier, then remove both environment variables in a `finally` block. Do not pipe the URLs or Docker environment to a log.

Run:

```powershell
$container = (docker inspect streamhub-postgres | ConvertFrom-Json)[0]
$sourceSettings = @{}
foreach ($entry in $container.Config.Env) {
    $parts = $entry -split '=', 2
    $sourceSettings[$parts[0]] = $parts[1]
}
$copySettings = @{}
foreach ($line in Get-Content -LiteralPath '.env.microservices') {
    if ($line -match '^([^#=]+)=(.*)$') {
        $copySettings[$matches[1].Trim()] = $matches[2].Trim()
    }
}
$sourcePassword = [Uri]::EscapeDataString($sourceSettings['POSTGRES_PASSWORD'])
$copyPassword = [Uri]::EscapeDataString($copySettings['POSTGRES_PASSWORD'])
$sourceDatabase = $sourceSettings['POSTGRES_DB']
if (-not $sourceDatabase) { $sourceDatabase = 'streamhub' }
try {
    $env:SOURCE_DATABASE_URL = "postgresql://$($sourceSettings['POSTGRES_USER']):$sourcePassword@127.0.0.1:5433/$sourceDatabase"
    $env:DESTINATION_DATABASE_URL = "postgresql://postgres:$copyPassword@127.0.0.1:5434/streamhub"
    & ".\scripts\py-ms.ps1" scripts/migrate_monolith_data.py |
        Tee-Object work/microservices/data-migration.log
    if ($LASTEXITCODE -ne 0) { throw "Data migration failed: $LASTEXITCODE" }
}
finally {
    Remove-Item Env:SOURCE_DATABASE_URL -ErrorAction SilentlyContinue
    Remove-Item Env:DESTINATION_DATABASE_URL -ErrorAction SilentlyContinue
}
```

Expected: one source/target count line per existing table and final `DATA_MIGRATION=PASS`; no connection string appears.

Run: `& ".\scripts\py-ms.ps1" scripts/verify_schema_isolation.py`

Expected: `SCHEMA_ISOLATION=PASS`.

- [ ] **Step 10: Local checkpoint**

Run: `rg -n "REFERENCES (user_service|content_service|social_service)" database/migrations/001-service-tables.sql`

Expected: no output. The four approved within-Schema references use unqualified table names under the service `search_path`; every Schema-qualified foreign key is forbidden.

---

### Task 4: User service extraction

**Files:**
- Create: `services/user-service/app/__init__.py`
- Create: `services/user-service/app/config.py`
- Create: `services/user-service/app/database.py`
- Create: `services/user-service/app/models.py`
- Create: `services/user-service/app/schemas.py`
- Create: `services/user-service/app/security.py`
- Create: `services/user-service/app/outbox.py`
- Create: `services/user-service/app/main.py`
- Create: `services/user-service/tests/conftest.py`
- Create: `services/user-service/tests/test_health.py`
- Create: `services/user-service/tests/test_auth_api.py`
- Create: `services/user-service/tests/test_user_social_api.py`
- Create: `services/user-service/tests/test_chat_notification_api.py`
- Create: `services/user-service/requirements.txt`
- Create: `services/user-service/Dockerfile`

**Interfaces:**
- Consumes: `USER_DATABASE_URL`, `SECRET_KEY`, MinIO avatar credentials, shared request ID types.
- Produces: user-facing routes plus `POST /internal/auth/introspect`, `POST /internal/users/batch`, and `POST /internal/notifications`.

- [ ] **Step 1: Write health/readiness/version tests**

```python
def test_health_ready_version(client):
    assert client.get("/health").json() == {"status": "ok", "service": "user"}
    assert client.get("/ready").status_code == 200
    body = client.get("/version").json()
    assert body["service"] == "user"
    assert body["version"]
```

- [ ] **Step 2: Write authorization tests before moving routes**

Cover exact behavior:

```text
login success and wrong password
register duplicate account
GET/PATCH /api/auth/me
change password rejects wrong old password
upgrade requires normal active user
admin cannot ban the admin account
introspect returns user_id, user_type, status
introspect rejects expired, bad-signature, and banned users
```

Run: `& ".\scripts\py-ms.ps1" -m pytest services/user-service/tests/test_health.py services/user-service/tests/test_auth_api.py -q`

Expected: collection fails because the service does not exist.

- [ ] **Step 3: Implement focused models**

Move the existing columns and constraints without cross-service relationships:

```text
User, Follow, Conversation, Message, Notification, ProcessedEvent
```

Keep within-Schema relationships optional; never import content or social models.

- [ ] **Step 4: Implement current auth semantics**

Copy password hashing and HMAC token verification from `backend/app/security.py`. Keep the existing external token format so the frontend does not log out. `get_current_user` must query only `user_service.users` and reject `status != 0`.

Add internal response:

```python
class IntrospectionOut(BaseModel):
    user_id: str
    user_type: int
    status: int
```

- [ ] **Step 5: Extract all user-owned public routes**

Move these exact routes and preserve their request/response contracts:

```text
POST /api/auth/login
POST /api/auth/register
GET/PATCH /api/auth/me
PUT /api/auth/change-password
POST /api/auth/upgrade-to-creator
POST /api/auth/upload-avatar
GET /api/users/{user_id}
GET /api/users/{user_id}/stats
POST/DELETE /api/users/{user_id}/follow
GET /api/users/{user_id}/relation
GET /api/users/{user_id}/followers
GET /api/users/{user_id}/following
GET /api/creator/fans
GET /api/notifications
GET /api/notifications/unread-count
POST /api/notifications/{notif_id}/read
POST /api/notifications/read-all
GET/POST /api/chat/conversations
GET/POST /api/chat/conversations/{conv_id}/messages
POST /api/chat/messages/{msg_id}/recall
POST /api/chat/conversations/{conv_id}/read
WS /ws/chat
GET /api/admin/users
PATCH /api/admin/users/{user_id}/type
PATCH /api/admin/users/{user_id}/ban
```

The route extraction must replace only external enrichment: user service does not query videos, comments, likes, categories, live rooms, reports, or sensitive words. `/api/users/{user_id}/stats` keeps follower/following counts locally and obtains received-like count from `GET /internal/users/{user_id}/received-like-count` on content service; content failure returns `likeCount=0` plus `X-StreamHub-Degraded: content-service`.

- [ ] **Step 6: Implement internal APIs with exact failure rules**

```text
POST /internal/auth/introspect
  input: Authorization header
  200: {user_id,user_type,status}
  401: invalid/expired token or missing/banned user

POST /internal/users/batch
  input: {ids:[UUID], limit <= 200}
  output: [{id,account,nickname,avatar,bio,userType,status}]

GET /internal/users/{user_id}/following-ids
  output: {ids:[UUID]}; used by content feed without exposing the user Schema

POST /internal/notifications
  input: {eventId,recipientId,senderId,notifType,targetType,targetId,content}
  behavior: insert notification and processed_events atomically; duplicate eventId returns 200
```

- [ ] **Step 7: Run user service tests**

Run: `& ".\scripts\py-ms.ps1" -m pytest services/user-service/tests -q --junitxml=work/microservices/user-service.xml`

Expected: all collected user tests pass; XML reports 0 failures and 0 errors.

- [ ] **Step 8: Build service independently**

`requirements.txt` must contain only user runtime dependencies: FastAPI, Uvicorn, SQLAlchemy, psycopg2-binary, Pydantic, python-dotenv, passlib[bcrypt], bcrypt, python-multipart, MinIO, httpx.

Run: `docker build -f services/user-service/Dockerfile -t streamhub-user-service:local .`

Expected: image builds without copying the monolith app.

- [ ] **Step 9: Local checkpoint**

Run: `rg -n "from .*?(Video|Comment|Danmaku|LiveRoom|Report|SensitiveWord)|content_service\.|social_service\." services/user-service/app`

Expected: no output.

---

### Task 5: Content service extraction

**Files:**
- Create: `services/content-service/app/` focused modules listed in Locked File Structure.
- Create: `services/content-service/tests/test_health.py`
- Create: `services/content-service/tests/test_video_api.py`
- Create: `services/content-service/tests/test_admin_creator_api.py`
- Create: `services/content-service/tests/test_outbox.py`
- Create: `services/content-service/requirements.txt`
- Create: `services/content-service/Dockerfile`

**Interfaces:**
- Consumes: user introspection/batch APIs, MinIO `videos/` and `covers/`, content Schema.
- Produces: video/category/media APIs plus video validation, batch summaries, and idempotent statistic update APIs.

- [ ] **Step 1: Write failing API and Outbox tests**

Cover exact route groups:

```text
GET /api/categories
GET /api/videos, /recommended, /{id}, /{id}/related
GET /api/users/{user_id}/videos
POST /api/videos
GET /api/creator/videos
GET/PATCH /api/admin/videos/pending and /api/admin/videos/{id}/audit
POST /api/videos/upload-file and /api/videos/upload-cover
GET /api/feed
GET /api/creator/week-stats
GET/DELETE/PUT /api/creator/videos/{status|video_id}
GET /api/admin/videos
POST /api/admin/videos/{id}/warn and /unapprove
POST /api/admin/local-videos/sync
POST /api/admin/cleanup-uploads
```

Tests must prove auth timeout returns 503 before a protected write and that audit notification creates Outbox state in the same transaction.

- [ ] **Step 2: Verify tests fail**

Run: `& ".\scripts\py-ms.ps1" -m pytest services/content-service/tests -q`

Expected: collection fails because the service app does not exist.

- [ ] **Step 3: Implement models and remove cross-service ORM access**

Models are exactly `Category`, `Video`, `IntegrationOutbox`, and `ProcessedEvent`. `Video.uploader_id` is UUID without a foreign key or relationship. Video response enrichment uses `POST /internal/users/batch`; timeout returns `uploaderName="用户"`, empty avatar, and response header `X-StreamHub-Degraded: user-service`.

- [ ] **Step 4: Extract content-owned routes and MinIO logic**

Move current route behavior from `backend/app/main.py` and `backend/app/object_storage.py`. Keep media validation, file size limits, generated object names, and public URL format. Restrict service credentials to `videos/` and `covers/`; avatar operations remain in user service.

- [ ] **Step 5: Implement internal content APIs**

```text
GET /internal/videos/{video_id}/interaction-target
  200 only when video exists, status=0, audit_status=1

POST /internal/videos/batch
  input {ids:[UUID], limit <= 200}
  output video summaries without user joins

GET /internal/users/{user_id}/received-like-count
  output {likeCount:int}; sum approved, active videos only

PUT /internal/videos/{video_id}/interaction-counts
  input {eventId,likeCount,commentCount,favoriteCount}
  transaction inserts processed_events then stores absolute nonnegative counts
  duplicate eventId returns current counts without another update
```

- [ ] **Step 6: Implement durable content Outbox delivery**

Implement `drain_outbox_once()` using `FOR UPDATE SKIP LOCKED`. Deliver audit notifications to `POST /internal/notifications` and video deletion events to `POST /internal/events/video-deleted`. On success mark `sent`; on failure increment attempts and schedule exponential retry; after 10 attempts mark `dead`. Tests use MockTransport and assert duplicate delivery is harmless.

- [ ] **Step 7: Correct creator cross-service operations**

`/api/feed` obtains followed user IDs from user service, then queries only content videos. `/api/creator/week-stats` remains a zero-valued historical compatibility endpoint and must be documented as simulated; do not claim it measures real playback. Video deletion emits `video.deleted` to content Outbox; it does not delete social tables directly.

- [ ] **Step 8: Run and build independently**

Run: `& ".\scripts\py-ms.ps1" -m pytest services/content-service/tests -q --junitxml=work/microservices/content-service.xml`

Expected: 0 failures and 0 errors.

Run: `docker build -f services/content-service/Dockerfile -t streamhub-content-service:local .`

Expected: successful image build.

- [ ] **Step 9: Local checkpoint**

Run: `rg -n "db\.(get|query)\((User|Follow|Comment|Danmaku|LiveRoom|VideoLike|Report|SensitiveWord)" services/content-service/app`

Expected: no output.

---

### Task 6: Social service extraction and durable interaction consistency

**Files:**
- Create: `services/social-service/app/` focused modules listed in Locked File Structure.
- Create: `services/social-service/tests/test_health.py`
- Create: `services/social-service/tests/test_interaction_api.py`
- Create: `services/social-service/tests/test_live_api.py`
- Create: `services/social-service/tests/test_moderation_api.py`
- Create: `services/social-service/tests/test_outbox.py`
- Create: `services/social-service/requirements.txt`
- Create: `services/social-service/Dockerfile`

**Interfaces:**
- Consumes: user introspection/batch APIs and content video/category APIs.
- Produces: interaction/live/moderation APIs, authoritative counts, and event relay.

- [ ] **Step 1: Write failing interaction, failure, and idempotency tests**

Required assertions:

```text
duplicate like returns 400 and does not increment
unlike without prior like returns 400
duplicate favorite returns 400 and does not increment
unfavorite removes one favorite row
content validation 404 prevents local write
content timeout returns 503 and prevents local write
successful like/comment/favorite writes business row and Outbox atomically
repeated Outbox delivery is accepted by content without double update
comment user enrichment timeout returns placeholder and degraded header
```

- [ ] **Step 2: Verify tests fail**

Run: `& ".\scripts\py-ms.ps1" -m pytest services/social-service/tests -q`

Expected: collection fails because the service app does not exist.

- [ ] **Step 3: Implement owned models**

Create exactly `Comment`, `CommentMention`, `VideoLike`, `VideoFavorite`, `VideoInteractionBaseline`, `Danmaku`, `LiveRoom`, `Report`, `SensitiveWord`, `IntegrationOutbox`, and `ProcessedEvent`. No model imports or relationships to user/content tables.

- [ ] **Step 4: Extract exact public route groups**

```text
POST/DELETE /api/videos/{id}/like
GET /api/videos/{id}/like-status
POST/DELETE /api/videos/{id}/favorite
GET /api/videos/{id}/comments and /danmaku
POST /api/videos/{id}/comments and /danmaku
GET /api/comments/{id}/replies
DELETE /api/comments/{id}
GET/POST /api/live/rooms and GET /api/live/rooms/{id}
POST /api/live/rooms/{id}/end and /stop
WS /ws/live/{room_id}
POST /api/live/{room_id}/danmaku
GET /api/creator/comments
DELETE /api/creator/comments/{comment_id}
GET /api/creator/active-room
POST /api/reports
GET/PATCH /api/admin/reports*
GET/POST/DELETE /api/admin/sensitive-words*
GET /api/admin/live-rooms
POST /api/admin/live-rooms/{id}/warn and /close
GET /api/users/{id}/likes
```

- [ ] **Step 5: Implement absolute count Outbox events**

After each local interaction transaction, calculate counts from owned tables and enqueue:

```json
{
  "eventType": "video.interaction-counts.changed",
  "videoId": "UUID",
  "likeCount": 0,
  "commentCount": 0,
  "favoriteCount": 0
}
```

Outbox attempts use states `pending`, `processing`, `sent`, `dead`; default maximum attempts is 10. A failed HTTP call schedules `next_attempt_at` with exponential delay and never rolls back the already committed interaction.

Comment, mention, and report notifications use a second event type `notification.created` delivered to user service through the same Outbox worker. No notification write occurs through direct access to `user_service.notifications`.

- [ ] **Step 6: Handle content deletion without direct cleanup**

Expose `POST /internal/events/video-deleted`. Consume `video.deleted` idempotently by deleting matching comments, likes, favorites, and video danmaku inside the social transaction, matching the current external deletion behavior. Record `event_id` in `processed_events`. Never query content tables during cleanup.

- [ ] **Step 7: Preserve verified WebSocket behavior**

Port live WebSocket tests that accept the actual initial `online` event order. Preserve the existing disconnect guard so an old socket cannot clear a new connection. Keep the backend regression for disconnect during join acknowledgment.

- [ ] **Step 8: Run and build independently**

Run: `& ".\scripts\py-ms.ps1" -m pytest services/social-service/tests -q --junitxml=work/microservices/social-service.xml`

Expected: 0 failures and 0 errors.

Run: `docker build -f services/social-service/Dockerfile -t streamhub-social-service:local .`

Expected: successful image build.

- [ ] **Step 9: Local checkpoint**

Run: `rg -n "db\.(get|query)\((User|Video|Category)" services/social-service/app`

Expected: no output.

---

### Task 7: Compatibility gateway and isolated local stack

**Files:**
- Create: `gateway/Dockerfile`
- Create: `gateway/nginx.legacy.conf`
- Create: `gateway/nginx.conf`
- Modify: `.env.microservices.example`
- Modify: `docker-compose.microservices.yml`
- Create: `tests/microservices/test_gateway_routes.py`
- Modify: `webpack.config.js`
- Modify: `playwright.config.ts`

**Interfaces:**
- Consumes: three service names and original public paths.
- Produces: one public gateway on 8100 and frontend on 5273; internal service ports are not public.

- [ ] **Step 1: Write route ownership tests**

Parse `gateway/nginx.conf` and assert these ownership rules:

```text
/api/auth, user profile/follow, chat, notifications, admin users -> user-service
video/category/media/admin video/creator video/feed -> content-service
like/favorite/comment/danmaku/live/report/sensitive-word/admin live -> social-service
/ws/chat -> user-service
/ws/live -> social-service
specific interaction routes precede generic /api/videos routes
```

Run: `& ".\scripts\py-ms.ps1" -m pytest tests/microservices/test_gateway_routes.py -q`

Expected: fail because the gateway config does not exist.

- [ ] **Step 2: Start with a temporary legacy gateway**

`gateway/nginx.legacy.conf` proxies every current public HTTP/WebSocket/media path to `legacy-backend:8000`. Add a temporary `legacy-backend` Compose service built from `backend/Dockerfile` and connected only to the copy's PostgreSQL/MinIO. This compatibility service exists only during route cutover and never connects to source ports or Volumes.

- [ ] **Step 3: Implement final Nginx route ordering**

Use exact upstream names:

```nginx
upstream user_service { server user-service:8000; }
upstream content_service { server content-service:8000; }
upstream social_service { server social-service:8000; }
```

Define regex locations for nested interaction paths before `location /api/videos`. Forward `Authorization`, `X-Request-ID`, original host, and WebSocket upgrade headers. Set connect timeout to `500ms`, read timeout to `2s`, and return JSON 502/503 bodies.

Expose read-only operational routes `/_services/user/{health|ready|version}`, `/_services/content/{health|ready|version}`, and `/_services/social/{health|ready|version}` by proxying to the corresponding service. Do not expose `/internal/*` through the gateway.

- [ ] **Step 4: Cut over one service boundary at a time**

Perform three gateway checkpoints in order:

```text
1. Route only user-owned paths to user-service; reload Nginx; run user tests and login/profile/chat smoke.
2. Route content-owned paths to content-service; reload Nginx; run content tests and video/upload/audit smoke.
3. Route social-owned paths to social-service; reload Nginx; run social tests and interaction/live smoke.
```

At every checkpoint, unmatched paths continue through `legacy-backend`. If a checkpoint fails, restore only the previous gateway config; do not alter source or service-owned data.

- [ ] **Step 5: Create the final isolated Compose stack**

Compose project name: `streamhub-ms`. Required services:

```text
postgres-ms, minio-ms, user-service, content-service, social-service,
gateway, frontend-ms, srs-ms
```

Host ports must be exactly 5434, 9100, 9101, 8100, 5273, 1936, and 8081 as specified in the design. Remove every fixed `container_name`. Use distinct named Volumes `streamhub_ms_pgdata` and `streamhub_ms_minio_data`.

After all public route inventory tests pass, remove `legacy-backend` and `gateway/nginx.legacy.conf` from runtime use. Keep the copied monolith code as the before-version reference, but no final container may run `backend/app/main.py`.

- [ ] **Step 6: Create local-only environment template**

`.env.microservices.example` lists variable names and safe non-secret examples. Actual `.env.microservices` is ignored and generated locally with strong passwords. It must contain `APP_VERSION=local-ms`, three service database URLs, MinIO credentials, `SECRET_KEY`, timeout values, and service base URLs.

- [ ] **Step 7: Route the frontend through gateway**

Set copy-only frontend environment `REACT_APP_API_BASE_URL=http://127.0.0.1:8100`. Keep `src/api.ts` path construction unchanged. Configure E2E to use gateway 8100 and frontend 5273 without touching source ports 8000/5173.

- [ ] **Step 8: Run static and runtime route checks**

Run: `& ".\scripts\py-ms.ps1" -m pytest tests/microservices/test_gateway_routes.py -q`

Expected: all route ownership tests pass.

Run: `docker compose -f docker-compose.microservices.yml config -q`

Expected: exit code 0 and no secret value printed.

Run: `docker compose -f docker-compose.microservices.yml up -d --build`

Expected: isolated stack starts without replacing or stopping source containers.

- [ ] **Step 9: Verify public operational endpoints**

Run:

```powershell
Invoke-RestMethod http://127.0.0.1:8100/_services/user/health
Invoke-RestMethod http://127.0.0.1:8100/_services/content/health
Invoke-RestMethod http://127.0.0.1:8100/_services/social/health
```

Expected: each returns its service name and `status=ok`.

- [ ] **Step 10: Local checkpoint**

Run: `docker compose -f docker-compose.microservices.yml ps | Tee-Object work/microservices/compose-ps.log`

Expected: PostgreSQL and MinIO healthy; three services, gateway, frontend, and SRS running.

---

### Task 8: Independent Kubernetes deployment manifests

**Files:**
- Create: `k8s/microservices/user-service.yaml`
- Create: `k8s/microservices/content-service.yaml`
- Create: `k8s/microservices/social-service.yaml`
- Create: `k8s/microservices/gateway.yaml`
- Create: `k8s/microservices/postgres.yaml`
- Create: `k8s/microservices/minio.yaml`
- Create: `k8s/microservices/frontend.yaml`
- Create: `scripts/deploy-microservices.sh`
- Create: `scripts/health-check-microservices.sh`
- Create: `tests/microservices/test_k8s_contract.py`

**Interfaces:**
- Produces: one Deployment and ClusterIP Service per business service; readiness/liveness/version visibility.

- [ ] **Step 1: Write manifest contract tests**

Assert every business Deployment has distinct image, `APP_VERSION`, liveness `/health`, readiness `/ready`, resource requests/limits, and no public NodePort. Assert gateway depends on ClusterIP service names, not IPs.

- [ ] **Step 2: Verify tests fail**

Run: `& ".\scripts\py-ms.ps1" -m pytest tests/microservices/test_k8s_contract.py -q`

Expected: missing manifest failure.

- [ ] **Step 3: Create manifests**

Use initial resources for later HPA experiments:

```yaml
resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 500m
    memory: 512Mi
```

Do not create HPA yet. Images accept `${IMAGE_TAG}` through `scripts/deploy-microservices.sh`; default local tag is forbidden in the script when `CI=true`.

- [ ] **Step 4: Create deployment and health scripts**

Deployment order: namespace, Secrets, PostgreSQL, MinIO, Schema job, user, content, social, gateway, frontend. Wait for rollout after each business service. Health script checks all health, readiness, and version endpoints and exits nonzero on the first failure.

- [ ] **Step 5: Run contract tests and server-side dry run**

Run: `& ".\scripts\py-ms.ps1" -m pytest tests/microservices/test_k8s_contract.py -q`

Expected: all tests pass.

Run: `kubectl apply --dry-run=client -f k8s/microservices/`

Expected: all resources validate locally. If `kubectl` is unavailable, record `UNVERIFIED_TOOL_MISSING`; do not claim Kubernetes validation passed.

- [ ] **Step 6: Local checkpoint**

Run: `rg -n "readinessProbe|livenessProbe|resources:|APP_VERSION" k8s/microservices`

Expected: each of the three business service manifests contains all four items.

---

### Task 9: Full regression, isolation audit, and course deliverables

**Files:**
- Create: `tests/microservices/test_public_api_catalog.py`
- Create: `tests/microservices/test_failure_contracts.py`
- Create: `docs/microservices/service-architecture.md`
- Create: `docs/microservices/service-api-catalog.md`
- Create: `docs/microservices/table-ownership.md`
- Create: `docs/microservices/cross-service-calls.md`
- Create: `docs/microservices/monolith-vs-microservices.md`
- Create: `scripts/hash-version-manifest.py`

**Interfaces:**
- Consumes: completed stack and original route inventory.
- Produces: verified documents, JUnit/log evidence, and version hashes.

- [ ] **Step 1: Generate public API inventory from both applications**

Extract monolith decorators and service OpenAPI documents. Test that every monolith public HTTP/WebSocket path is either present at the gateway or explicitly documented as replaced by an equivalent path. Any missing path fails the test.

- [ ] **Step 2: Run service and shared tests**

Run:

```powershell
& ".\scripts\py-ms.ps1" -m pytest shared/tests services/user-service/tests services/content-service/tests services/social-service/tests tests/microservices -q --junitxml=work/microservices/backend-all.xml
```

Expected: 0 failures and 0 errors. Record actual collected count.

- [ ] **Step 3: Run Schema isolation and forbidden-query audits**

Run: `& ".\scripts\py-ms.ps1" scripts/verify_schema_isolation.py | Tee-Object work/microservices/schema-isolation.log`

Expected: `SCHEMA_ISOLATION=PASS`.

Run: `rg -n "JOIN (user_service|content_service|social_service)|FROM (user_service|content_service|social_service)|db\.(get|query)\((User|Video|Comment|LiveRoom)" services`

Expected: only own-service model uses; manually classify exact results in `table-ownership.md`.

- [ ] **Step 4: Run existing formal E2E through the new gateway**

Run: `npm ci` because the copied workspace intentionally excludes `node_modules` and includes `package-lock.json`.

Run:

```powershell
$env:PLAYWRIGHT_JUNIT_OUTPUT_NAME = 'work/microservices/e2e.xml'
npx playwright test e2e/streamhub.spec.ts --reporter=line,junit
Remove-Item Env:PLAYWRIGHT_JUNIT_OUTPUT_NAME
```

Expected: 3 passed through ports 5273/8100. Preserve JUnit at `work/microservices/e2e.xml`. A failure must remain reported; do not reuse historical XML.

- [ ] **Step 5: Verify failure handling**

Automated tests must cover user-service timeout on protected writes, user enrichment fallback on public reads, content-service timeout before social writes, Outbox retry, duplicate event idempotency, and dead-event visibility. This is contract verification only; the live fault experiment remains Task 3 of the course work.

- [ ] **Step 6: Build all three images independently**

Run:

```powershell
docker build -f services/user-service/Dockerfile -t streamhub-user-service:local-ms .
docker build -f services/content-service/Dockerfile -t streamhub-content-service:local-ms .
docker build -f services/social-service/Dockerfile -t streamhub-social-service:local-ms .
```

Expected: all three exit code 0. Save concise logs under `work/microservices/`.

- [ ] **Step 7: Generate required course documents**

Documents must contain only verified routes, tables, calls, results, and current UC01–UC08 scope. `service-architecture.md` includes Mermaid source for the service diagram. `service-api-catalog.md` lists method, public path, owner, auth, internal dependencies, and API test ID. `table-ownership.md` lists every real and new table, owner, allowed account, external ID fields, and forbidden access. `cross-service-calls.md` lists caller, callee, timeout, retry, fallback, idempotency, and failure response.

- [ ] **Step 8: Generate local before/after version evidence**

`scripts/hash-version-manifest.py` hashes code/config files from source and copy while excluding `.git`, dependencies, caches, `.env`, media binaries, and test artifacts. It writes `docs/microservices/version-manifest.json` and a summarized diff to `monolith-vs-microservices.md`. It never writes under the source path.

- [ ] **Step 9: Final verification**

Run:

```powershell
& ".\scripts\py-ms.ps1" scripts/check_microservices_workspace.py
& ".\scripts\py-ms.ps1" -m pytest shared/tests services/user-service/tests services/content-service/tests services/social-service/tests tests/microservices -q
docker compose -f docker-compose.microservices.yml config -q
docker compose -f docker-compose.microservices.yml ps
```

Expected: guard passes, all tests pass, Compose validates, required services run. Report actual counts and states.

- [ ] **Step 10: Stop at local delivery boundary**

Do not commit, push, trigger Actions, delete Volumes, or stop source containers. Report files changed, tests run, failures, warnings, unverified items, and exact next course item.

---

## Plan Self-Review Checklist

- [ ] Every design section maps to a task: isolation (3), three services (4–6), calls/failures (2, 4–6), gateway (7), deployment (8), tests/docs/version evidence (9).
- [ ] No task modifies `C:\Users\lausu\Desktop\SE2026`.
- [ ] No commit or push step exists.
- [ ] Every table has exactly one owner.
- [ ] All public route families have one owner and gateway order handles nested video interaction routes first.
- [ ] Runtime test numbers are not copied from historical results.
- [ ] Task 2–4 course work remains outside this plan except required foundations.
