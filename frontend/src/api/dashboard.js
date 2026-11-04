import client from "./client"

export async function getDashboardSummary() {
    const { data } = await client.get("/dashboard/summary")
    return data
}
