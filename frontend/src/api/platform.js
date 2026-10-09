import client from "./client"

// WARE67 platform team routes: companies. API key review lives in apiKeys.js.

export async function listCompanies({ search, skip = 0, limit = 50 } = {}) {
    const { data } = await client.get("/platform/companies", {
        params: { search: search || undefined, skip, limit },
    })
    return data
}

export async function setCompanyActive(id, isActive) {
    const { data } = await client.patch(`/platform/companies/${id}`, { is_active: isActive })
    return data
}
