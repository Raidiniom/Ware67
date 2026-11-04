import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { getDashboardSummary } from "../api/dashboard"
import { errorMessage } from "../api/resources"
import { formatDateTime } from "../utils/format"

const LOW_STOCK_LINK = "/products?low_stock=true"

const count = (n) => Number(n).toLocaleString()
const money = (n) =>
    Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })

function Stat({ label, value, hint, to, alert }) {
    const body = (
        <>
            <span>{label}</span>
            <strong>{value}</strong>
            {hint && <small>{hint}</small>}
        </>
    )
    const className = `overview-stat${alert ? " overview-stat--alert" : ""}`
    return to ? <Link className={className} to={to}>{body}</Link> : <div className={className}>{body}</div>
}

export default function DashboardOverview() {
    const [summary, setSummary] = useState(null)
    const [error, setError] = useState("")

    useEffect(() => {
        let ignore = false
        getDashboardSummary()
            .then((data) => {
                if (!ignore) setSummary(data)
            })
            .catch((err) => {
                if (!ignore) setError(errorMessage(err, "Couldn't load the overview."))
            })
        return () => {
            ignore = true
        }
    }, [])

    if (error) return <p className="overview-note" role="alert">{error}</p>
    if (!summary) return <p className="overview-note">Loading the overview…</p>

    if (summary.product_count === 0) {
        return (
            <p className="overview-note">
                No products yet. <Link to="/products">Add your first ones</Link>, one at a time or from a CSV file.
            </p>
        )
    }

    return (
        <>
            <div className="overview-stats">
                <Stat label="Products" value={count(summary.product_count)} to="/products" />
                <Stat label="Units in stock" value={count(summary.units_in_stock)} />
                <Stat
                    label="Low stock"
                    value={count(summary.low_stock_count)}
                    hint="At or below reorder level"
                    to={LOW_STOCK_LINK}
                    alert={summary.low_stock_count > 0}
                />
                <Stat
                    label="Out of stock"
                    value={count(summary.out_of_stock_count)}
                    to={LOW_STOCK_LINK}
                    alert={summary.out_of_stock_count > 0}
                />
                <Stat label="Stock value" value={money(summary.stock_value)} hint="At selling price" />
            </div>

            <div className="overview-lists">
                <section className="overview-list">
                    <header>
                        <h3>Needs restocking</h3>
                        {summary.low_stock_count > summary.low_stock_items.length && (
                            <Link to={LOW_STOCK_LINK}>View all {count(summary.low_stock_count)}</Link>
                        )}
                    </header>
                    {summary.low_stock_items.length === 0 ? (
                        <p className="overview-empty">Everything is above its reorder level.</p>
                    ) : (
                        <ul>
                            {summary.low_stock_items.map((p) => (
                                <li key={p.id}>
                                    <div>
                                        <strong>{p.name}</strong>
                                        <small>{p.sku}</small>
                                    </div>
                                    <div className="overview-qty">
                                        <strong className={p.current_stock === 0 ? "qty--neg" : undefined}>
                                            {count(p.current_stock)} {p.unit || ""}
                                        </strong>
                                        <small>Reorder at {count(p.reorder_level)}</small>
                                    </div>
                                </li>
                            ))}
                        </ul>
                    )}
                </section>

                <section className="overview-list">
                    <header>
                        <h3>Recent stock movements</h3>
                        <Link to="/transactions">View all</Link>
                    </header>
                    {summary.recent_movements.length === 0 ? (
                        <p className="overview-empty">No stock movements yet.</p>
                    ) : (
                        <ul>
                            {summary.recent_movements.map((m) => (
                                <li key={m.id}>
                                    <div>
                                        <strong>{m.product_name}</strong>
                                        <small>
                                            {m.label}
                                            {m.actor ? ` · ${m.actor}` : ""} · {formatDateTime(m.created_at)}
                                        </small>
                                    </div>
                                    <div className="overview-qty">
                                        <strong className={m.quantity_change > 0 ? "qty--pos" : "qty--neg"}>
                                            {m.quantity_change > 0 ? "+" : "−"}
                                            {count(Math.abs(m.quantity_change))}
                                        </strong>
                                    </div>
                                </li>
                            ))}
                        </ul>
                    )}
                </section>
            </div>
        </>
    )
}
