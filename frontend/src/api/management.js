import client from "./client"

export async function listManagedUsers() {
    const { data } = await client.get("/users")
    return data
}

export async function createManagedUser(payload) {
    const { data } = await client.post("/users", payload)
    return data
}

export async function updateManagedUser(userId, payload) {
    const { data } = await client.patch(`/users/${userId}`, payload)
    return data
}

export async function listRoles() {
    const { data } = await client.get("/roles")
    return data
}

export async function updateRoleDescription(roleName, description) {
    const { data } = await client.patch(`/roles/${roleName}`, { description })
    return data
}