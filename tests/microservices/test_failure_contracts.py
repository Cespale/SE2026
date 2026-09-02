from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_timeout_and_read_fallback_contracts_have_behavioral_tests():
    user_tests = read("services/user-service/tests/test_user_social_api.py")
    content_tests = read("services/content-service/tests/test_video_api.py")
    social_tests = read("services/social-service/tests/test_interaction_api.py")
    assert "test_user_stats_uses_content_api_and_degrades_safely" in user_tests
    assert "test_public_read_degrades_when_user_batch_fails" in content_tests
    assert "test_auth_timeout_prevents_create_write" in content_tests
    assert "test_content_missing_or_timeout_prevents_local_write" in social_tests
    assert "test_comment_reply_danmaku_enrichment_and_degraded_read" in social_tests


def test_outbox_retry_dead_visibility_and_idempotency_are_implemented():
    for service in ("content-service", "social-service"):
        outbox = read(f"services/{service}/app/outbox.py")
        main = read(f"services/{service}/app/main.py")
        tests = read(f"services/{service}/tests/test_outbox.py")
        assert "MAX_ATTEMPTS = 10" in outbox
        assert 'event.status = "pending"' in outbox
        assert 'event.status = "dead"' in outbox
        assert 'event.status = "sent"' in outbox
        assert '@app.get("/internal/outbox/dead")' in main
        assert "test_dead_outbox_event_is_visible_through_internal_diagnostics" in tests

    content_api_tests = read("services/content-service/tests/test_video_api.py")
    social_api_tests = read("services/social-service/tests/test_interaction_api.py")
    assert "db.query(ProcessedEvent).count() == 1" in content_api_tests
    assert "test_video_deleted_event_is_idempotent" in social_api_tests


def test_internal_diagnostics_remain_private_at_gateway():
    gateway = read("gateway/nginx.conf")
    assert "location = /internal" in gateway
    assert "location ^~ /internal/" in gateway
    assert gateway.count("return 404") >= 2

