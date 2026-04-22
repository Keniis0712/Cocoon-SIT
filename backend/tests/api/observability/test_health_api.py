def test_health_route_returns_version_and_timestamp(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "ok"
    assert "version" in payload
    assert "now" in payload
