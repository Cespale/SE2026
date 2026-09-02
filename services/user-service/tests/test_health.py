def test_health_ready_version_and_request_id(client):
    health = client.get("/health", headers={"X-Request-ID": "health-1"})
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "service": "user"}
    assert health.headers["X-Request-ID"] == "health-1"

    assert client.get("/ready").status_code == 200
    version = client.get("/version").json()
    assert version == {"service": "user", "version": "test-version"}
