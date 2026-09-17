def _seed_product(client, sku="TXN-SKU"):
    return client.post("/api/v1/products", json={"sku": sku, "name": "Widget"}).json()


def test_list_transactions_requires_auth(client):
    response = client.get("/api/v1/transactions")
    assert response.status_code == 401


def test_create_transaction_rejects_unknown_product(admin_client):
    response = admin_client.post(
        "/api/v1/transactions",
        json={"product_id": "missing", "type": "STOCK_IN", "quantity": 5},
    )
    assert response.status_code == 400


def test_create_transaction_quantity_must_be_positive(admin_client):
    product = _seed_product(admin_client)
    response = admin_client.post(
        "/api/v1/transactions",
        json={"product_id": product["id"], "type": "STOCK_IN", "quantity": 0},
    )
    assert response.status_code == 422


def test_any_authenticated_role_can_create_transaction(client, admin_user, staff_user, login_as):
    with login_as(admin_user):
        product = _seed_product(client)

    with login_as(staff_user):
        response = client.post(
            "/api/v1/transactions",
            json={
                "product_id": product["id"],
                "type": "STOCK_OUT",
                "quantity": 3,
                "reference_type": "SO",
                "reference_id": "SO-001",
            },
        )

    assert response.status_code == 201
    body = response.json()
    # user_id must come from the authenticated token, never the client
    assert body["user_id"] == staff_user.id
    assert body["type"] == "STOCK_OUT"
    assert body["quantity"] == 3


def test_user_id_cannot_be_spoofed_by_client(admin_client, admin_user):
    product = _seed_product(admin_client)
    response = admin_client.post(
        "/api/v1/transactions",
        json={
            "product_id": product["id"],
            "type": "STOCK_IN",
            "quantity": 1,
            "user_id": "someone-elses-id",
        },
    )
    assert response.status_code == 201
    assert response.json()["user_id"] == admin_user.id


def test_list_filters_by_product_id(admin_client):
    product_a = _seed_product(admin_client, sku="A")
    product_b = _seed_product(admin_client, sku="B")
    admin_client.post("/api/v1/transactions", json={"product_id": product_a["id"], "type": "STOCK_IN", "quantity": 10})
    admin_client.post("/api/v1/transactions", json={"product_id": product_b["id"], "type": "STOCK_IN", "quantity": 20})

    response = admin_client.get(f"/api/v1/transactions?product_id={product_a['id']}")
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["product_id"] == product_a["id"]


def test_only_admin_can_delete_transaction(client, admin_user, manager_user, staff_user, login_as):
    with login_as(admin_user):
        product = _seed_product(client)
        create_resp = client.post(
            "/api/v1/transactions", json={"product_id": product["id"], "type": "STOCK_IN", "quantity": 1}
        )
        txn_id = create_resp.json()["id"]

    with login_as(manager_user):
        forbidden = client.delete(f"/api/v1/transactions/{txn_id}")
        assert forbidden.status_code == 403

    with login_as(staff_user):
        forbidden_staff = client.delete(f"/api/v1/transactions/{txn_id}")
        assert forbidden_staff.status_code == 403

    with login_as(admin_user):
        allowed = client.delete(f"/api/v1/transactions/{txn_id}")
        assert allowed.status_code == 204

        missing = client.get(f"/api/v1/transactions/{txn_id}")
        assert missing.status_code == 404


def test_get_missing_transaction_returns_404(admin_client):
    response = admin_client.get("/api/v1/transactions/does-not-exist")
    assert response.status_code == 404
