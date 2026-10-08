import client from "./client"

export async function login(email, password) {
    const { data } = await client.post("/auth/login", { email, password })
    return data
}

export async function register({ name, email, password }) {
    const { data } = await client.post("/auth/register", { name, email, password })
    return data
}

export async function getCurrentUser() {
    const { data } = await client.get("/auth/me")
    return data
}
