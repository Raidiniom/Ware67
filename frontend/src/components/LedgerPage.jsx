import { useEffect, useState } from "react"
import { errorMessage } from "../api/resources"
import PageShell from "./PageShell"
import DataTable from "./DataTable"
import Pagination from "./Pagination"
import "../pages/styles/common.css"
import "./styles/Resource.css"
import "./styles/Ledger.css"

const PAGE_SIZE = 20

/**
 * List page for append-only records (transactions, adjustments, audit logs).
 *
 * NOTE: pass `columns` and `filters` as module-level constants so they stay
 * referentially stable.
 *
 * Props
 * - api:         { list(params) } returning { items, total }
 * - filters:     [{ key, label, options: [{ value, label }] }]
 * - CreateForm:  component receiving { onSaved, onCancel }, shown in a modal
 * - canCreate:   whether to show the create button
 * - Detail:      component receiving { row, onClose }; adds a "View" row action
 * - notice:      optional note under the toolbar (e.g. read-only message)
 */
export default function LedgerPage({
    title,
    subtitle,
    plural,
    api,
    columns,
    filters = [],
    dateRange = true,
    searchPlaceholder = "Search…",
    actionLabel,
    CreateForm,
    canCreate = false,
    Detail,
    notice,
}) {
    const [search, setSearch] = useState("")
    const [debounced, setDebounced] = useState("")
    const [filterValues, setFilterValues] = useState({})
    const [dates, setDates] = useState({ date_from: "", date_to: "" })
    const [skip, setSkip] = useState(0)
    const [data, setData] = useState({ items: [], total: 0 })
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState("")
    const [reloadKey, setReloadKey] = useState(0)

    const [creating, setCreating] = useState(false)
    const [viewing, setViewing] = useState(null)
    const [toast, setToast] = useState("")

    useEffect(() => {
        const t = setTimeout(() => {
            setDebounced(search.trim())
            setSkip(0)
        }, 300)
        return () => clearTimeout(t)
    }, [search])

    useEffect(() => {
        let ignore = false
        setLoading(true)
        api
            .list({ search: debounced, ...filterValues, ...dates, skip, limit: PAGE_SIZE })
            .then((res) => {
                if (ignore) return
                if (res.items.length === 0 && skip > 0) {
                    setSkip(Math.max(0, skip - PAGE_SIZE))
                    return
                }
                setData(res)
                setError("")
            })
            .catch((err) => {
                if (!ignore) setError(errorMessage(err, `Couldn't load ${plural}.`))
            })
            .finally(() => {
                if (!ignore) setLoading(false)
            })
        return () => {
            ignore = true
        }
    }, [api, plural, debounced, filterValues, dates, skip, reloadKey])

    useEffect(() => {
        if (!toast) return
        const t = setTimeout(() => setToast(""), 3000)
        return () => clearTimeout(t)
    }, [toast])

    function changeFilter(key, value) {
        setFilterValues((v) => ({ ...v, [key]: value }))
        setSkip(0)
    }

    function changeDate(key, value) {
        setDates((d) => ({ ...d, [key]: value }))
        setSkip(0)
    }

    const isFiltered =
        Boolean(debounced) || Object.values(filterValues).some(Boolean) || Boolean(dates.date_from || dates.date_to)

    function clearAll() {
        setSearch("")
        setDebounced("")
        setFilterValues({})
        setDates({ date_from: "", date_to: "" })
        setSkip(0)
    }

    return (
        <PageShell
            title={title}
            subtitle={subtitle}
            actions={
                canCreate &&
                CreateForm && (
                    <button className="btn btn-primary" onClick={() => setCreating(true)}>
                        {actionLabel}
                    </button>
                )
            }
        >
            <div className="toolbar">
                <input
                    type="search"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder={searchPlaceholder}
                    aria-label="Search"
                />
                {filters.map((f) => (
                    <select
                        key={f.key}
                        value={filterValues[f.key] ?? ""}
                        onChange={(e) => changeFilter(f.key, e.target.value)}
                        aria-label={f.label}
                    >
                        <option value="">{f.label}</option>
                        {f.options.map((o) => (
                            <option key={o.value} value={o.value}>
                                {o.label}
                            </option>
                        ))}
                    </select>
                ))}
                {dateRange && (
                    <>
                        <label className="date-field">
                            From
                            <input
                                type="date"
                                value={dates.date_from}
                                max={dates.date_to || undefined}
                                onChange={(e) => changeDate("date_from", e.target.value)}
                            />
                        </label>
                        <label className="date-field">
                            To
                            <input
                                type="date"
                                value={dates.date_to}
                                min={dates.date_from || undefined}
                                onChange={(e) => changeDate("date_to", e.target.value)}
                            />
                        </label>
                    </>
                )}
                {isFiltered && (
                    <button type="button" className="link-btn" onClick={clearAll}>
                        Clear filters
                    </button>
                )}
            </div>

            {notice && <p className="muted">{notice}</p>}

            <DataTable
                columns={columns}
                rows={data.items}
                loading={loading}
                error={error}
                empty={isFiltered ? `No ${plural} match your search or filters.` : `No ${plural} yet.`}
                renderActions={
                    Detail &&
                    ((row) => (
                        <div className="row-actions">
                            <button className="btn btn-ghost btn-sm" onClick={() => setViewing(row)}>
                                View
                            </button>
                        </div>
                    ))
                }
            />

            <Pagination skip={skip} limit={PAGE_SIZE} total={data.total} onChange={setSkip} />

            {creating && CreateForm && (
                <CreateForm
                    onCancel={() => setCreating(false)}
                    onSaved={() => {
                        setCreating(false)
                        setToast("Saved")
                        setSkip(0)
                        setReloadKey((k) => k + 1)
                    }}
                />
            )}

            {viewing && Detail && <Detail row={viewing} onClose={() => setViewing(null)} />}

            {toast && (
                <div className="toast" role="status">
                    {toast}
                </div>
            )}
        </PageShell>
    )
}