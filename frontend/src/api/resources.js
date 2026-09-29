import client from "./client"

// FastAPI's 422 `detail` is an array of {loc, msg}; other errors use a string.
export function errorMessage(err, fallback = "Something went wrong. Please try again.") {
    const detail = err?.response?.data?.detail
    if (typeof detail === "string") return detail
    if (Array.isArray(detail)) {
        return detail
            .map((d) => {
                const field = Array.isArray(d.loc) ? d.loc.filter((p) => p !== "body" && p !== "query").join(".") : ""
                const msg = String(d.msg || "").replace(/^Value error, /, "")
                return field ? `${field}: ${msg}` : msg
            })
            .join(" · ")
    }
    if (!err?.response) return "Can't reach the server. Check your connection."
    return fallback
}

// Drop empty params so FastAPI doesn't try to parse "" as a bool/date.
function cleanParams(params = {}) {
    return Object.fromEntries(Object.entries(params).filter(([, v]) => v !== "" && v != null))
}

export function createResource(path) {
    return {
        list: async (params) => (await client.get(path, { params: cleanParams(params) })).data,
        get: async (id) => (await client.get(`${path}/${id}`)).data,
        products: async (id) => (await client.get(`${path}/${id}/products`)).data,
        create: async (body) => (await client.post(path, body)).data,
        update: async (id, body) => (await client.put(`${path}/${id}`, body)).data,
        remove: async (id) => {
            await client.delete(`${path}/${id}`)
        },
    }
}

export const categoriesApi = createResource("/categories")
export const suppliersApi = createResource("/suppliers")
export const locationsApi = {
    ...createResource("/locations"),
    warehouses: async () => (await client.get("/locations/warehouses")).data,
}

export const productsApi = {
    list: async (params) => (await client.get("/products", { params: cleanParams(params) })).data,
    create: async (body) => (await client.post("/products", body)).data,
    update: async (id, body) => (await client.patch(`/products/${id}`, body)).data,
    remove: async (id) => {
        await client.delete(`/products/${id}`)
    },
}