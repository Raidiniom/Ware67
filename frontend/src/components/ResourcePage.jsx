import { useEffect, useState } from "react"
import { useAuth } from "../context/AuthContext"
import { errorMessage } from "../api/resources"
import PageShell from "./PageShell"
import DataTable from "./DataTable"
import Pagination from "./Pagination"
import Modal, { ConfirmDialog } from "./Modal"
import "../pages/styles/common.css"
import "./styles/Resource.css"

const PAGE_SIZE = 20
const WRITE_ROLES = ["OWNER", "ADMIN", "MANAGER"]
const PRODUCT_COLUMNS = [
    { key: "sku", header: "SKU" },
    { key: "name", header: "Name" },
    { key: "current_stock", header: "In stock" },
]

function FilterSelect({ filter, value, onChange }) {
    const [options, setOptions] = useState(filter.options ?? [])

    useEffect(() => {
        if (!filter.loadOptions) return
        let ignore = false
        filter
            .loadOptions()
            .then((list) => {
                if (!ignore) setOptions(list.map((v) => ({ value: v, label: v })))
            })
            .catch(() => {})
        return () => {
            ignore = true
        }
    }, [filter])

    return (
        <select value={value} onChange={(e) => onChange(e.target.value)} aria-label={filter.label}>
            <option value="">{filter.label}</option>
            {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
    )
}

function RecordForm({ singular, fields, record, api, onSaved, onCancel }) {
    const isEdit = Boolean(record.id)
    const [values, setValues] = useState(() =>
        Object.fromEntries(fields.map((f) => [f.name, record[f.name] ?? ""]))
    )
    const [error, setError] = useState("")
    const [saving, setSaving] = useState(false)

    const set = (name) => (e) => setValues((v) => ({ ...v, [name]: e.target.value }))

    async function handleSubmit(e) {
        e.preventDefault()
        setError("")
        setSaving(true)
        try {
            const saved = isEdit ? await api.update(record.id, values) : await api.create(values)
            onSaved(saved, isEdit)
        } catch (err) {
            setError(errorMessage(err))
            setSaving(false)
        }
    }

    return (
        <Modal
            title={`${isEdit ? "Edit" : "New"} ${singular}`}
            onClose={saving ? () => {} : onCancel}
            footer={
                <>
                    <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={saving}>Cancel</button>
                    <button type="submit" form="record-form" className="btn btn-primary" disabled={saving}>
                        {saving ? "Saving…" : isEdit ? "Save changes" : "Create"}
                    </button>
                </>
            }
        >
            <form id="record-form" className="record-form" onSubmit={handleSubmit}>
                {error && <div className="form-error">{error}</div>}
                {fields.map((f) => (
                    <label key={f.name} className={`field${f.half ? " field--half" : ""}`}>
                        <span>{f.label}{f.required && " *"}</span>
                        {f.type === "textarea" ? (
                            <textarea rows={3} value={values[f.name]} onChange={set(f.name)} maxLength={f.maxLength} required={f.required} />
                        ) : (
                            <input type={f.type || "text"} value={values[f.name]} onChange={set(f.name)} maxLength={f.maxLength} required={f.required} />
                        )}
                    </label>
                ))}
            </form>
        </Modal>
    )
}

function ProductsModal({ record, api, onClose }) {
    const [state, setState] = useState({ loading: true, items: [], error: "" })

    useEffect(() => {
        let ignore = false
        api
            .products(record.id)
            .then((items) => {
                if (!ignore) setState({ loading: false, items, error: "" })
            })
            .catch((err) => {
                if (!ignore) setState({ loading: false, items: [], error: errorMessage(err) })
            })
        return () => {
            ignore = true
        }
    }, [api, record.id])

    return (
        <Modal
            title={`Products — ${record.name}`}
            onClose={onClose}
            wide
            footer={<button className="btn btn-ghost" onClick={onClose}>Close</button>}
        >
            <DataTable columns={PRODUCT_COLUMNS} rows={state.items} loading={state.loading} error={state.error} empty="No products assigned." />
        </Modal>
    )
}

// NOTE: pass `columns`, `fields`, and `filters` as module-level constants
// (not created inside a component) so they stay referentially stable.
export default function ResourcePage({ title, subtitle, singular, plural, api, columns, fields, filters = [], searchPlaceholder = "Search…" }) {
    const { user } = useAuth()
    const canWrite = WRITE_ROLES.includes(user?.role)
    const Singular = singular.charAt(0).toUpperCase() + singular.slice(1)

    const [search, setSearch] = useState("")
    const [debounced, setDebounced] = useState("")
    const [filterValues, setFilterValues] = useState({})
    const [skip, setSkip] = useState(0)
    const [data, setData] = useState({ items: [], total: 0 })
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState("")
    const [reloadKey, setReloadKey] = useState(0)

    const [editing, setEditing] = useState(null) // {} = new record, object = edit
    const [viewing, setViewing] = useState(null)
    const [deleting, setDeleting] = useState(null)
    const [deleteBusy, setDeleteBusy] = useState(false)
    const [deleteError, setDeleteError] = useState("")
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
            .list({ search: debounced, ...filterValues, skip, limit: PAGE_SIZE })
            .then((res) => {
                if (ignore) return
                if (res.items.length === 0 && skip > 0) {
                    setSkip(Math.max(0, skip - PAGE_SIZE)) // deleted the last row of a page
                    return
                }
                setData(res)
                setError("")
            })
            .catch((err) => {
                if (!ignore) setError(errorMessage(err, "Couldn't load data."))
            })
            .finally(() => {
                if (!ignore) setLoading(false)
            })
        return () => {
            ignore = true
        }
    }, [api, debounced, filterValues, skip, reloadKey])

    useEffect(() => {
        if (!toast) return
        const t = setTimeout(() => setToast(""), 3000)
        return () => clearTimeout(t)
    }, [toast])

    const reload = () => setReloadKey((k) => k + 1)

    function changeFilter(key, value) {
        setFilterValues((v) => ({ ...v, [key]: value }))
        setSkip(0)
    }

    function handleSaved(_saved, wasEdit) {
        setEditing(null)
        setToast(`${Singular} ${wasEdit ? "updated" : "created"}`)
        reload()
    }

    function askDelete(row) {
        setDeleteError("")
        setDeleting(row)
    }

    async function confirmDelete() {
        setDeleteBusy(true)
        setDeleteError("")
        try {
            await api.remove(deleting.id)
            setDeleting(null)
            setToast(`${Singular} deleted`)
            reload()
        } catch (err) {
            setDeleteError(errorMessage(err))
        } finally {
            setDeleteBusy(false)
        }
    }

    const allColumns = [
        ...columns,
        {
            key: "product_count",
            header: "Products",
            render: (row) => (
                <button className="link-btn" onClick={() => setViewing(row)}>{row.product_count}</button>
            ),
        },
    ]

    const isFiltered = Boolean(debounced) || Object.values(filterValues).some(Boolean)

    return (
        <PageShell
            title={title}
            subtitle={subtitle}
            actions={
                canWrite && (
                    <button className="btn btn-primary" onClick={() => setEditing({})}>+ New {singular}</button>
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
                    <FilterSelect key={f.key} filter={f} value={filterValues[f.key] ?? ""} onChange={(v) => changeFilter(f.key, v)} />
                ))}
            </div>

            {!canWrite && <p className="muted">You have read-only access to this page.</p>}

            <DataTable
                columns={allColumns}
                rows={data.items}
                loading={loading}
                error={error}
                empty={isFiltered ? `No ${plural} match your search or filters.` : `No ${plural} yet.`}
                renderActions={
                    canWrite &&
                    ((row) => (
                        <div className="row-actions">
                            <button className="btn btn-ghost btn-sm" onClick={() => setEditing(row)}>Edit</button>
                            <button className="btn btn-danger btn-sm" onClick={() => askDelete(row)}>Delete</button>
                        </div>
                    ))
                }
            />

            <Pagination skip={skip} limit={PAGE_SIZE} total={data.total} onChange={setSkip} />

            {editing && (
                <RecordForm
                    key={editing.id ?? "new"}
                    singular={singular}
                    fields={fields}
                    record={editing}
                    api={api}
                    onSaved={handleSaved}
                    onCancel={() => setEditing(null)}
                />
            )}

            {viewing && <ProductsModal record={viewing} api={api} onClose={() => setViewing(null)} />}

            {deleting && (
                <ConfirmDialog
                    title={`Delete ${singular}`}
                    busy={deleteBusy}
                    error={deleteError}
                    onConfirm={confirmDelete}
                    onCancel={() => setDeleting(null)}
                >
                    Delete <strong>{deleting.name}</strong>?
                    {deleting.product_count > 0 &&
                        ` ${deleting.product_count} product(s) will be kept but will no longer have a ${singular}.`}
                </ConfirmDialog>
            )}

            {toast && <div className="toast" role="status">{toast}</div>}
        </PageShell>
    )
}