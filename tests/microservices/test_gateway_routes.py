from pathlib import Path


GATEWAY = Path("gateway/nginx.conf")
COMPOSE = Path("docker-compose.microservices.yml")
MONOLITH_COMPOSE = Path("docker-compose.yml")
WEBPACK = Path("webpack.config.js")
LIVE_START_PAGE = Path("src/pages/LiveStartPage.tsx")
PLAYWRIGHT = Path("playwright.config.ts")
E2E_SPEC = Path("e2e/streamhub.spec.ts")


def test_gateway_declares_three_business_upstreams_and_blocks_internal_api():
    config = GATEWAY.read_text(encoding="utf-8")
    assert "upstream user_service" in config
    assert "server user-service:8000" in config
    assert "upstream content_service" in config
    assert "server content-service:8000" in config
    assert "upstream social_service" in config
    assert "server social-service:8000" in config
    assert "resolver 127.0.0.11 ipv6=off" in config
    assert config.count("resolve;") == 3
    assert "location = /internal" in config
    assert "location ^~ /internal/" in config
    assert config.count("return 404") >= 2


def test_gateway_routes_overlapping_public_paths_to_the_owner():
    config = GATEWAY.read_text(encoding="utf-8")
    expected = {
        "~ ^/api/videos/[^/]+/(like|like-status|favorite|comments|danmaku)": "social_service",
        "~ ^/api/users/[^/]+/videos/?$": "content_service",
        "~ ^/api/users/[^/]+/likes/?$": "social_service",
        "^~ /api/auth/": "user_service",
        "^~ /api/chat/": "user_service",
        "^~ /api/admin/users": "user_service",
        "/api/videos": "content_service",
        "^~ /api/categories": "content_service",
        "^~ /api/live/": "social_service",
        "^~ /api/admin/reports": "social_service",
        "^~ /uploads/": "content_service",
        "^~ /avatars/": "user_service",
    }
    for location, upstream in expected.items():
        start = config.index(f"location {location}")
        end = config.index("\n    }", start)
        assert f"proxy_pass http://{upstream}" in config[start:end]

    assert config.index("location ~ ^/api/videos/") < config.index(
        "location /api/videos"
    )
    assert config.index("location ~ ^/api/users/[^/]+/videos") < config.index(
        "location /api/users/"
    )


def test_gateway_forwards_identity_request_id_websocket_and_has_json_failures():
    config = GATEWAY.read_text(encoding="utf-8")
    for directive in (
        "proxy_set_header Authorization $http_authorization",
        "proxy_set_header X-Request-ID $streamhub_request_id",
        "proxy_hide_header X-Request-ID",
        "proxy_set_header Host $host",
        "proxy_set_header Upgrade $http_upgrade",
        "proxy_connect_timeout 500ms",
        "proxy_read_timeout 2s",
        "error_page 502 503 504 = @service_unavailable",
        'return 503 \'{"detail":"上游服务暂不可用"}\'',
    ):
        assert directive in config
    for service in ("user", "content", "social"):
        assert f"^/_services/{service}/(health|ready|version)$" in config
    upload_start = config.index("location = /api/videos/upload-file")
    upload_end = config.index("\n        }", upload_start)
    upload = config[upload_start:upload_end]
    assert "client_max_body_size 512m" in upload
    assert "proxy_request_buffering off" in upload
    assert "proxy_read_timeout 120s" in upload


def test_isolated_compose_has_only_final_stack_and_exact_host_ports():
    compose = COMPOSE.read_text(encoding="utf-8")
    for service in (
        "postgres-ms:",
        "minio-ms:",
        "user-service:",
        "content-service:",
        "social-service:",
        "gateway:",
        "frontend-ms:",
        "srs-ms:",
    ):
        assert service in compose
    for mapping in (
        '"127.0.0.1:5434:5432"',
        '"127.0.0.1:9100:9000"',
        '"127.0.0.1:9101:9001"',
        '"127.0.0.1:8100:80"',
        '"127.0.0.1:5273:3266"',
        '"127.0.0.1:1936:1935"',
        '"127.0.0.1:8081:8080"',
    ):
        assert mapping in compose
    assert "legacy-backend:" not in compose
    assert "container_name:" not in compose
    assert "streamhub_ms_pgdata:" in compose
    assert "streamhub_ms_minio_data:" in compose

    monolith = MONOLITH_COMPOSE.read_text(encoding="utf-8")
    assert "container_name:" not in monolith
    assert "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}" in monolith
    assert "${SECRET_KEY:?SECRET_KEY is required}" in monolith
    assert "CORS_ORIGINS:" in monolith
    assert "REACT_APP_API_BASE_URL:" in monolith
    for configurable_port in (
        "POSTGRES_HOST_PORT",
        "MINIO_API_HOST_PORT",
        "MINIO_CONSOLE_HOST_PORT",
        "BACKEND_HOST_PORT",
        "FRONTEND_HOST_PORT",
        "SRS_RTMP_HOST_PORT",
        "SRS_HTTP_HOST_PORT",
    ):
        assert configurable_port in monolith


def test_frontend_copy_defaults_to_gateway_not_monolith():
    config = WEBPACK.read_text(encoding="utf-8")
    assert "http://127.0.0.1:8100" in config
    assert "port: 5273" in config
    live_page = LIVE_START_PAGE.read_text(encoding="utf-8")
    assert ":1936/live" in live_page
    assert ":1935/live" not in live_page
    e2e = PLAYWRIGHT.read_text(encoding="utf-8")
    assert "E2E_USE_MICROSERVICES" in e2e
    assert "http://127.0.0.1:5273" in e2e
    assert "http://127.0.0.1:8100" in e2e
    spec = E2E_SPEC.read_text(encoding="utf-8")
    assert "E2E_USE_MICROSERVICES" in spec
    assert "http://127.0.0.1:8100" in spec


def test_long_submission_review_e2e_has_real_upload_timeout_budget():
    spec = E2E_SPEC.read_text(encoding="utf-8")
    start = spec.index("E2E-TC03-05")
    end = spec.index("E2E-TC06-08", start)
    assert "test.setTimeout(120_000)" in spec[start:end]


def test_search_playback_e2e_has_cold_start_timeout_budget():
    spec = E2E_SPEC.read_text(encoding="utf-8")
    start = spec.index("E2E-TC01-02")
    end = spec.index("E2E-TC03-05", start)
    assert "test.setTimeout(60_000)" in spec[start:end]


def test_live_e2e_waits_for_room_readiness_before_viewer_navigation():
    spec = E2E_SPEC.read_text(encoding="utf-8")
    start = spec.index("E2E-TC06-08")
    live_test = spec[start:]
    readiness = live_test.index("expect.poll")
    navigation = live_test.index("await viewer.goto(liveUrl")
    assert readiness < navigation
    assert "`${e2eBackendUrl}/api/live/rooms/${roomId}`" in live_test[:navigation]
    assert ".toBe(200)" in live_test[readiness:navigation]
