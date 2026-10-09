import client from "./client"

export async function login(email, password) {
    const { data } = await client.post("/auth/login", { email, password })
    return data
}

// Signing up creates a new company with this account as its owner.
export async function register({ name, email, password, companyName }) {
    const { data } = await client.post("/auth/register", { name, email, password, company_name: companyName })
    return data
}

export async function getCurrentUser() {
    const { data } = await client.get("/auth/me")
    return data
}
