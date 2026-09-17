def test_list_categories_requires_auth(client):
    response = client.get("/api/v1/categories")
    assert response.status_code == 401


def test_create_and_list_category_as_admin(admin_client):
    create_resp = admin_client.post(
        "/api/v1/categories", json={"name": "Electronics", "description": "Electronic parts"}
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["name"] == "Electronics"
    category_id = body["id"]

    list_resp = admin_client.get("/api/v1/categories")
    assert list_resp.status_code == 200
    assert any(c["id"] == category_id for c in list_resp.json())

    get_resp = admin_client.get(f"/api/v1/categories/{category_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Electronics"


def test_staff_can_read_but_not_create_category(staff_client):
    list_resp = staff_client.get("/api/v1/categories")
    assert list_resp.status_code == 200

    create_resp = staff_client.post("/api/v1/categories", json={"name": "Blocked"})
    assert create_resp.status_code == 403


def test_update_and_delete_category(admin_client):
    create_resp = admin_client.post("/api/v1/categories", json={"name": "Temp"})
    category_id = create_resp.json()["id"]

    update_resp = admin_client.put(f"/api/v1/categories/{category_id}", json={"description": "Updated"})
    assert update_resp.status_code == 200
    assert update_resp.json()["description"] == "Updated"
    assert update_resp.json()["name"] == "Temp"

    delete_resp = admin_client.delete(f"/api/v1/categories/{category_id}")
    assert delete_resp.status_code == 204

    get_resp = admin_client.get(f"/api/v1/categories/{category_id}")
    assert get_resp.status_code == 404


def test_get_missing_category_returns_404(admin_client):
    response = admin_client.get("/api/v1/categories/does-not-exist")
    assert response.status_code == 404
