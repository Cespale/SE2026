def test_health_ready_version_and_request_id(client):
    health = client.get("/health", headers={"X-Request-ID": "content-health"})
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "service": "content"}
    assert health.headers["X-Request-ID"] == "content-health"
    assert client.get("/ready").status_code == 200
    assert client.get("/version").json() == {
        "service": "content",
        "version": "test-version",
    }
