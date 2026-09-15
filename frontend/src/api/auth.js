import client from "./client"

export async function login(email, password) {
    const { data } = await client.post("/auth/login", { email, password })
    return data
}

export async function register({ name, email, password }) {
    const { data } = await client.post("/auth/register", { name, email, password })
    return data
}

// No email/SMS provider available, so "forgot password" is a direct,
// one-step change: verify with email + full name, then set the new
// password immediately (see backend/app/api/v1/endpoints/auth.py for the
// trade-off this makes).
export async function forgotPassword({ email, name, newPassword }) {
    const { data } = await client.post("/auth/forgot-password", {
        email,
        name,
        new_password: newPassword,
    })
    return data
}

export async function getCurrentUser() {
    const { data } = await client.get("/auth/me")
    return data
}
