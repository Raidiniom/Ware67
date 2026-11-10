import client from "./client"

export async function getInbound(days = 7) {
    const { data } = await client.get("/dashboard/inbound", { params: { days } })
    return data
}
