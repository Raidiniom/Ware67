import { useCallback, useEffect, useState } from "react"
import PageShell from "../components/PageShell"
import { getInbound, TIME_ZONE } from "../api/dashboard"
import { errorMessage } from "../api/resources"
import { formatDateTime } from "../utils/format"
import "./styles/common.css"
import "../components/styles/Resource.css"
import "./styles/Inbound.css"

const POLL_MS = 5000
const STOP_ON = [403, 404, 422] // permanent errors: don't keep hammering

// Polls while the tab is visible. Hidden tabs don't poll at all; coming back
// fetches straight away so stale data isn't shown as live.
function usePolling(fetcher, ms) {
    const [state, setState] = useState({ data: null, error: "", updatedAt: null })

    useEffect(() => {
        let ignore = false
        let stopped = false
        let inFlight = false
        let timer = null

        function schedule(delay) {
            clearTimeout(timer)
            timer = null
            if (!ignore && !stopped && !document.hidden) timer = setTimeout(tick, delay)
        }

        async function tick() {
            timer = null
            if (inFlight) return // the running request schedules the next one
            inFlight = true
            try {
                const data = await fetcher()
                if (!ignore) setState({ data, error: "", updatedAt: new Date() })
            } catch (err) {
                if (STOP_ON.includes(err.response?.status)) stopped = true
                if (!ignore) setState((s) => ({ ...s, error: errorMessage(err, "Couldn't refresh.") }))
            } finally {
                inFlight = false
            }
            schedule(ms)
        }

        function onVisibilityChange() {
            if (document.hidden) {
                clearTimeout(timer)
                timer = null
            } else {
                schedule(0)
            }
        }

        document.addEventListener("visibilitychange", onVisibilityChange)
        schedule(0)
        return () => {
            ignore = true
            clearTimeout(timer)
            document.removeEventListener("visibilitychange", onVisibilityChange)
        }
    }, [fetcher, ms])

    return state
}

function Bars({ series }) {
    const max = Math.max(1, ...series.map((p) => p.units))
    return (
        <div className="inbound-bars" role="img" aria-label="Units received per day">
            {series.map((p) => (
                <div key={p.date} className="inbound-bar" title={`${p.date}: ${p.units} units`}>
                    <div className="inbound-bar-track">
                        <div className="inbound-bar-fill" style={{ height: `${(p.units / max) * 100}%` }} />
                    </div>
                    <small>{p.date.slice(5)}</small>
                </div>
            ))}
        </div>
    )
}

function InboundBoard({ days }) {
    const load = useCallback(() => getInbound(days), [days])
    const { data, error, updatedAt } = usePolling(load, POLL_MS)

    if (!data) {
        return error
            ? <div className="page-alert" role="alert">{error}</div>
            : <div className="table-wrap"><div className="table-state">Loading…</div></div>
    }

    return (
        <>
            {error && <div className="page-alert" role="alert">{error}</div>}
            <p className="muted">
                {error
                    ? <>Not live · last updated {formatDateTime(updatedAt)}</>
                    : <><span className="live-dot" /> Live · updated {formatDateTime(updatedAt)}</>}
                {data.tz !== TIME_ZONE && <> · days counted in {data.tz}</>}
            </p>

            <div className="inbound-stats">
                <div><span>Units received</span><strong>{data.units_in}</strong></div>
                <div><span>Stock-in transactions</span><strong>{data.transactions}</strong></div>
            </div>

            <Bars series={data.series} />

            <h2 className="inbound-h">Top received products</h2>
            <ul className="inbound-list">
                {data.top_products.length === 0 && <li>No stock received in this period.</li>}
                {data.top_products.map((p) => (
                    <li key={p.product_id}><span>{p.sku} — {p.name}</span><strong>+{p.units}</strong></li>
                ))}
            </ul>

            <h2 className="inbound-h">Latest arrivals</h2>
            <ul className="inbound-list">
                {data.recent.length === 0 && <li>No stock received in this period.</li>}
                {data.recent.map((e) => (
                    <li key={e.id}>
                        <span>
                            <strong>{e.product_name}</strong> <small>{e.product_sku}</small><br />
                            <small>
                                {formatDateTime(e.created_at)} · {e.source}
                                {e.reference_id ? ` · ${e.reference_type ?? ""} ${e.reference_id}` : ""}
                            </small>
                        </span>
                        <strong>+{e.quantity}</strong>
                    </li>
                ))}
            </ul>
        </>
    )
}

export default function InboundDashboardPage() {
    const [days, setDays] = useState(7)
    return (
        <PageShell
            title="Inbound movement"
            subtitle="Stock received into the warehouse, refreshed every few seconds."
            actions={
                <select value={days} onChange={(e) => setDays(Number(e.target.value))} aria-label="Period">
                    {[7, 14, 30].map((d) => <option key={d} value={d}>Last {d} days</option>)}
                </select>
            }
        >
            <InboundBoard key={days} days={days} />
        </PageShell>
    )
}
