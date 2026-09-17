def _seed_product(client, sku="ADJ-SKU"):
    return client.post("/api/v1/products", json={"sku": sku, "name": "Widget"}).json()


def test_list_requires_auth(client):
    response = client.get("/api/v1/inventory-adjustments")
    assert response.status_code == 401


def test_staff_cannot_create_adjustment(client, admin_user, staff_user, login_as):
    with login_as(admin_user):
        product = _seed_product(client)

    with login_as(staff_user):
        response = client.post(
            "/api/v1/inventory-adjustments",
            json={"product_id": product["id"], "quantity_change": -2, "reason": "Damaged"},
        )

    assert response.status_code == 403


def test_manager_can_create_adjustment(client, admin_user, manager_user, login_as):
    with login_as(admin_user):
        product = _seed_product(client)

    with login_as(manager_user):
        response = client.post(
            "/api/v1/inventory-adjustments",
            json={"product_id": product["id"], "quantity_change": 5, "reason": "Recount"},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["quantity_change"] == 5
    assert body["user_id"] == manager_user.id


def test_zero_quantity_change_rejected(admin_client):
    product = _seed_product(admin_client)
    response = admin_client.post(
        "/api/v1/inventory-adjustments",
        json={"product_id": product["id"], "quantity_change": 0},
    )
    assert response.status_code == 422


def test_create_rejects_unknown_product(admin_client):
    response = admin_client.post(
        "/api/v1/inventory-adjustments",
        json={"product_id": "missing", "quantity_change": 1},
    )
    assert response.status_code == 400


def test_list_filters_by_product_id(admin_client):
    product_a = _seed_product(admin_client, sku="A")
    product_b = _seed_product(admin_client, sku="B")
    admin_client.post("/api/v1/inventory-adjustments", json={"product_id": product_a["id"], "quantity_change": 3})
    admin_client.post("/api/v1/inventory-adjustments", json={"product_id": product_b["id"], "quantity_change": -1})

    response = admin_client.get(f"/api/v1/inventory-adjustments?product_id={product_a['id']}")
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["product_id"] == product_a["id"]


def test_only_admin_can_delete_adjustment(client, admin_user, manager_user, login_as):
    with login_as(admin_user):
        product = _seed_product(client)
        create_resp = client.post(
            "/api/v1/inventory-adjustments", json={"product_id": product["id"], "quantity_change": 4}
        )
        adjustment_id = create_resp.json()["id"]

    with login_as(manager_user):
        forbidden = client.delete(f"/api/v1/inventory-adjustments/{adjustment_id}")
        assert forbidden.status_code == 403

    with login_as(admin_user):
        allowed = client.delete(f"/api/v1/inventory-adjustments/{adjustment_id}")
        assert allowed.status_code == 204

        missing = client.get(f"/api/v1/inventory-adjustments/{adjustment_id}")
        assert missing.status_code == 404


def test_get_missing_adjustment_returns_404(admin_client):
    response = admin_client.get("/api/v1/inventory-adjustments/does-not-exist")
    assert response.status_code == 404
