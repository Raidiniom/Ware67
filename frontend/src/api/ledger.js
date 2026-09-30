import client from "./client"

// Drop empty params so FastAPI doesn't try to parse "" as a date/enum.
function cleanParams(params = {}) {
    return Object.fromEntries(Object.entries(params).filter(([, v]) => v !== "" && v != null))
}

// Transactions: anyone signed in can read; create is open to any authenticated user.
export const transactionsApi = {
    list: async (params) => (await client.get("/transactions", { params: cleanParams(params) })).data,
    get: async (id) => (await client.get(`/transactions/${id}`)).data,
    create: async (body) => (await client.post("/transactions", body)).data,
}

// Adjustments: read for everyone, create for ADMIN / MANAGER.
export const adjustmentsApi = {
    list: async (params) => (await client.get("/adjustments", { params: cleanParams(params) })).data,
    get: async (id) => (await client.get(`/adjustments/${id}`)).data,
    create: async (body) => (await client.post("/adjustments", body)).data,
}

// Audit logs: ADMIN only, read only.
export const auditLogsApi = {
    list: async (params) => (await client.get("/audit-logs", { params: cleanParams(params) })).data,
    get: async (id) => (await client.get(`/audit-logs/${id}`)).data,
}