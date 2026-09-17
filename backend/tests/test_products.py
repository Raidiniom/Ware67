def _create_category(admin_client, name="Cat"):
    return admin_client.post("/api/v1/categories", json={"name": name}).json()


def _create_supplier(admin_client, name="Sup"):
    return admin_client.post("/api/v1/suppliers", json={"name": name}).json()


def _create_location(admin_client, name="Loc"):
    return admin_client.post("/api/v1/locations", json={"name": name}).json()


def test_list_products_requires_auth(client):
    response = client.get("/api/v1/products")
    assert response.status_code == 401


def test_create_product_rejects_unknown_refs(admin_client):
    response = admin_client.post(
        "/api/v1/products",
        json={"sku": "SKU-1", "name": "Widget", "category_id": "does-not-exist"},
    )
    assert response.status_code == 400


def test_create_and_fetch_product(admin_client):
    category = _create_category(admin_client)
    supplier = _create_supplier(admin_client)
    location = _create_location(admin_client)

    response = admin_client.post(
        "/api/v1/products",
        json={
            "sku": "SKU-100",
            "name": "Widget",
            "category_id": category["id"],
            "supplier_id": supplier["id"],
            "location_id": location["id"],
            "unit": "pcs",
            "price": 12.5,
            "reorder_level": 5,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["sku"] == "SKU-100"
    assert body["price"] == 12.5

    get_resp = admin_client.get(f"/api/v1/products/{body['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["category_id"] == category["id"]


def test_duplicate_sku_rejected(admin_client):
    admin_client.post("/api/v1/products", json={"sku": "DUPE", "name": "One"})
    response = admin_client.post("/api/v1/products", json={"sku": "DUPE", "name": "Two"})
    assert response.status_code == 400


def test_staff_can_list_products(staff_client, db_session):
    from app.models.product import Product

    db_session.add(Product(sku="SEED-1", name="Seed widget"))
    db_session.commit()

    response = staff_client.get("/api/v1/products")
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_staff_cannot_create_product(staff_client):
    response = staff_client.post("/api/v1/products", json={"sku": "BLOCKED", "name": "Nope"})
    assert response.status_code == 403


def test_update_product(admin_client):
    create_resp = admin_client.post("/api/v1/products", json={"sku": "UPD-1", "name": "Before"})
    product_id = create_resp.json()["id"]

    update_resp = admin_client.put(
        f"/api/v1/products/{product_id}", json={"name": "After", "price": 99.99}
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "After"
    assert update_resp.json()["price"] == 99.99


def test_update_product_rejects_duplicate_sku(admin_client):
    admin_client.post("/api/v1/products", json={"sku": "SKU-A", "name": "A"})
    create_b = admin_client.post("/api/v1/products", json={"sku": "SKU-B", "name": "B"})
    product_b_id = create_b.json()["id"]

    response = admin_client.put(f"/api/v1/products/{product_b_id}", json={"sku": "SKU-A"})
    assert response.status_code == 400


def test_delete_product(admin_client):
    create_resp = admin_client.post("/api/v1/products", json={"sku": "DEL-1", "name": "Delete me"})
    product_id = create_resp.json()["id"]

    delete_resp = admin_client.delete(f"/api/v1/products/{product_id}")
    assert delete_resp.status_code == 204

    get_resp = admin_client.get(f"/api/v1/products/{product_id}")
    assert get_resp.status_code == 404


def test_get_missing_product_returns_404(admin_client):
    response = admin_client.get("/api/v1/products/does-not-exist")
    assert response.status_code == 404
