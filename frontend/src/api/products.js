import client from "./client"

export async function listProducts(search = "") {
    const { data } = await client.get("/products", {
        params: search ? { search } : undefined,
    })
    return data
}

export async function createProduct(payload) {
    const { data } = await client.post("/products", payload)
    return data
}

export async function updateProduct(productId, payload) {
    const { data } = await client.patch(`/products/${productId}`, payload)
    return data
}

export async function deleteProduct(productId) {
    await client.delete(`/products/${productId}`)
}
