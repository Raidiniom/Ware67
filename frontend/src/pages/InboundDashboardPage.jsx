import { useCallback, useEffect, useState } from "react"
import PageShell from "../components/PageShell"
import { getInbound } from "../api/dashboard"
import { errorMessage } from "../api/resources"
import { formatDateTime } from "../utils/format"
import "./styles/common.css"
import "../components/styles/Resource.css"
import "./styles/Inbound.css"

const POLL_MS = 5000

// Re-runs `fetcher` every `ms`, pausing while the tab is hidden.
function usePolling(fetcher, ms) {
    const [state, setState] = useState({ data: null, error: "", updatedAt: null })

    useEffect(() => {
        let ignore = false
        let timer
        async function tick() {
            if (!document.hidden) {
                try {
                    const data = await fetcher()
                    if (!ignore) setState({ data, error: "", updatedAt: new Date() })
                } catch (err) {
                    if (!ignore) setState((s) => ({ ...s, error: errorMessage(err, "Couldn't refresh.") }))
                }
            }
            if (!ignore) timer = setTimeout(tick, ms)
        }
        timer = setTimeout(tick, 0)
        return () => {
            ignore = true
            clearTimeout(timer)
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
                    <div className="inbound-bar-fill" style={{ height: `${(p.units / max) * 100}%` }} />
                    <small>{p.date.slice(5)}</small>
                </div>
            ))}
        </div>
    )
}

export default function InboundDashboardPage() {
    const [days, setDays] = useState(7)
    const load = useCallback(() => getInbound(days), [days])
    const { data, error, updatedAt } = usePolling(load, POLL_MS)

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
            {error && <div className="page-alert" role="alert">{error}</div>}
            {!data ? (
                <div className="table-wrap"><div className="table-state">Loading…</div></div>
            ) : (
                <>
                    <p className="muted"><span className="live-dot" /> Live · updated {formatDateTime(updatedAt)}</p>

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
            )}
        </PageShell>
    )
}