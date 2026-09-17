def test_list_locations_requires_auth(client):
    response = client.get("/api/v1/locations")
    assert response.status_code == 401


def test_create_and_list_location_as_admin(admin_client):
    create_resp = admin_client.post(
        "/api/v1/locations",
        json={"name": "Main Warehouse - A1", "warehouse": "Main", "aisle": "A", "shelf": "1", "bin": "B1"},
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["warehouse"] == "Main"
    location_id = body["id"]

    list_resp = admin_client.get("/api/v1/locations")
    assert list_resp.status_code == 200
    assert any(l["id"] == location_id for l in list_resp.json())


def test_staff_cannot_create_location(staff_client):
    response = staff_client.post("/api/v1/locations", json={"name": "Blocked"})
    assert response.status_code == 403


def test_update_and_delete_location(admin_client):
    create_resp = admin_client.post("/api/v1/locations", json={"name": "Temp Bin"})
    location_id = create_resp.json()["id"]

    update_resp = admin_client.put(f"/api/v1/locations/{location_id}", json={"bin": "Z9"})
    assert update_resp.status_code == 200
    assert update_resp.json()["bin"] == "Z9"

    delete_resp = admin_client.delete(f"/api/v1/locations/{location_id}")
    assert delete_resp.status_code == 204

    get_resp = admin_client.get(f"/api/v1/locations/{location_id}")
    assert get_resp.status_code == 404
