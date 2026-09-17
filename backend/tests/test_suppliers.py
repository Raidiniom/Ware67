def test_list_suppliers_requires_auth(client):
    response = client.get("/api/v1/suppliers")
    assert response.status_code == 401


def test_create_and_list_supplier_as_admin(admin_client):
    create_resp = admin_client.post(
        "/api/v1/suppliers",
        json={"name": "Acme Corp", "contact_person": "Jane Doe", "email": "jane@acmecorp.com"},
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["name"] == "Acme Corp"
    supplier_id = body["id"]

    list_resp = admin_client.get("/api/v1/suppliers")
    assert list_resp.status_code == 200
    assert any(s["id"] == supplier_id for s in list_resp.json())


def test_staff_cannot_create_supplier(staff_client):
    response = staff_client.post("/api/v1/suppliers", json={"name": "Blocked Co"})
    assert response.status_code == 403


def test_update_and_delete_supplier(admin_client):
    create_resp = admin_client.post("/api/v1/suppliers", json={"name": "Temp Supplier"})
    supplier_id = create_resp.json()["id"]

    update_resp = admin_client.put(
        f"/api/v1/suppliers/{supplier_id}", json={"contact_number": "123-456"}
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["contact_number"] == "123-456"

    delete_resp = admin_client.delete(f"/api/v1/suppliers/{supplier_id}")
    assert delete_resp.status_code == 204

    get_resp = admin_client.get(f"/api/v1/suppliers/{supplier_id}")
    assert get_resp.status_code == 404
