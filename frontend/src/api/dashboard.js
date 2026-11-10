import client from "./client"

// Days are counted in the viewer's own time zone.
const TIME_ZONE = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"

export async function getInbound(days = 7) {
    const { data } = await client.get("/dashboard/inbound", { params: { days, tz: TIME_ZONE } })
    return data
}
