import client from "./client"

// Partner API keys: a company requests, the platform team approves or
// rejects, the company reveals the key once. See backend/app/api/v1/endpoints/api_keys.py.

export const SCOPES = [
    { value: "products:read", label: "Read products", hint: "List and view products, categories, suppliers and locations" },
    { value: "products:create", label: "Create products", hint: "Add new products, with opening stock" },
    { value: "products:update", label: "Update products", hint: "Change product details (not stock)" },
    { value: "products:delete", label: "Delete products", hint: "Remove products with no stock history" },
]

// --- company side (owners and admins) -------------------------------------

export async function listCompanyKeys() {
    const { data } = await client.get("/company/api-keys", { params: { limit: 200 } })
    return data
}

export async function requestKey(payload) {
    const { data } = await client.post("/company/api-keys", payload)
    return data
}

// Returns the key metadata plus `api_key`, the raw key, exactly once.
export async function revealKey(id) {
    const { data } = await client.post(`/company/api-keys/${id}/reveal`)
    return data
}

export async function revokeCompanyKey(id) {
    await client.delete(`/company/api-keys/${id}`)
}

// --- platform side (WARE67 team) ------------------------------------------

export async function listAllKeys({ status, skip = 0, limit = 50 } = {}) {
    const { data } = await client.get("/platform/api-keys", {
        params: { status: status || undefined, skip, limit },
    })
    return data
}

export async function listExpiringKeys(days = 14) {
    const { data } = await client.get("/platform/api-keys/expiring", { params: { days } })
    return data
}

// Leave scopes out to grant everything that was requested.
export async function approveKey(id, scopes) {
    const { data } = await client.post(`/platform/api-keys/${id}/approve`, scopes ? { scopes } : {})
    return data
}

export async function rejectKey(id, reason) {
    const { data } = await client.post(`/platform/api-keys/${id}/reject`, { reason })
    return data
}

export async function revokeAnyKey(id) {
    await client.delete(`/platform/api-keys/${id}`)
}
