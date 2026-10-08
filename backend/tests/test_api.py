def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ok", "degraded"}
    assert "version" in body
    assert body["database"]["ok"] is True


def test_score_endpoint_with_inline_rules(client):
    response = client.post(
        "/api/rules/score",
        json={
            "input": {"age": 70},
            "rules": [
                {
                    "id": "senior",
                    "condition": {"field": "age", "op": "gte", "value": 65},
                    "weight": 5,
                    "explanation": "Senior.",
                }
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_score"] == 5
    assert body["triggered"] == ["senior"]
    assert body["explanations"]


def test_score_endpoint_rejects_bad_rules(client):
    response = client.post(
        "/api/rules/score",
        json={"input": {}, "rules": [{"id": "broken"}]},
    )
    assert response.status_code == 422


def test_maps_config_hides_secrets(client):
    response = client.get("/api/maps/config")
    assert response.status_code == 200
    body = response.json()
    assert "tile_url" in body and "router_url" in body
    assert "key" not in str(body).lower()


def test_locations_crud_via_api(client):
    created = client.post(
        "/api/locations",
        json={"name": "Test Point", "latitude": 1.0, "longitude": 2.0},
    )
    assert created.status_code == 201
    location_id = created.json()["id"]

    listed = client.get("/api/locations")
    assert listed.status_code == 200
    assert any(loc["id"] == location_id for loc in listed.json())

    deleted = client.delete(f"/api/locations/{location_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/locations/{location_id}").status_code == 404
