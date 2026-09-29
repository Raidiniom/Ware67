import { useEffect, useMemo, useState } from "react"
import { useAuth } from "../context/AuthContext"
import { categoriesApi, suppliersApi, locationsApi, productsApi, errorMessage } from "../api/resources"
import PageShell from "../components/PageShell"
import DataTable from "../components/DataTable"
import Modal, { ConfirmDialog } from "../components/Modal"
import "./styles/common.css"
import "../components/styles/Resource.css"

const PAGE_SIZE = 20
const WRITE_ROLES = ["ADMIN", "MANAGER"]
const EMPTY = { sku: "", name: "", description: "", category_id: "", supplier_id: "", location_id: "", unit: "", price: "0.00", reorder_level: "0", initial_stock: "0" }

// Dropdown data. The list endpoints cap `limit` at 200.
function useLookups() {
    const [lookups, setLookups] = useState({ categories: [], suppliers: [], locations: [] })
    useEffect(() => {
        let ignore = false
        Promise.all([
            categoriesApi.list({ limit: 200 }),
            suppliersApi.list({ limit: 200 }),
            locationsApi.list({ limit: 200 }),
        ])
            .then(([c, s, l]) => {
                if (!ignore) setLookups({ categories: c.items, suppliers: s.items, locations: l.items })
            })
            .catch(() => {})
        return () => {
            ignore = true
        }
    }, [])
    return lookups
}

function Select({ value, onChange, options, placeholder, label }) {
    return (
        <select value={value} onChange={(e) => onChange(e.target.value)} aria-label={label}>
            <option value="">{placeholder}</option>
            {options.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
        </select>
    )
}

function ProductForm({ record, lookups, onSaved, onCancel }) {
    const isEdit = Boolean(record.id)
    const [v, setV] = useState(() => ({
        ...EMPTY,
        ...Object.fromEntries(
            Object.keys(EMPTY).filter((k) => record[k] != null).map((k) => [k, String(record[k])])
        ),
    }))
    const [error, setError] = useState("")
    const [saving, setSaving] = useState(false)

    const set = (name) => (e) => setV((s) => ({ ...s, [name]: e.target.value }))

    async function handleSubmit(e) {
        e.preventDefault()
        setError("")
        setSaving(true)
        const payload = {
            sku: v.sku.trim(),
            name: v.name.trim(),
            description: v.description,
            category_id: v.category_id || null,   // "" would fail the server's reference check
            supplier_id: v.supplier_id || null,
            location_id: v.location_id || null,
            unit: v.unit,
            price: v.price === "" ? "0" : v.price,
            reorder_level: Number(v.reorder_level || 0),
        }
        if (!isEdit) payload.initial_stock = Number(v.initial_stock || 0)
        try {
            const saved = isEdit ? await productsApi.update(record.id, payload) : await productsApi.create(payload)
            onSaved(saved, isEdit)
        } catch (err) {
            setError(errorMessage(err))
            setSaving(false)
        }
    }

    const select = (name, label, options) => (
        <label className="field field--half">
            <span>{label}</span>
            <select value={v[name]} onChange={set(name)}>
                <option value="">— None —</option>
                {options.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
            </select>
        </label>
    )

    return (
        <Modal
            title={isEdit ? `Edit product` : "New product"}
            wide
            onClose={saving ? () => {} : onCancel}
            footer={
                <>
                    <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={saving}>Cancel</button>
                    <button type="submit" form="product-form" className="btn btn-primary" disabled={saving}>
                        {saving ? "Saving…" : isEdit ? "Save changes" : "Create"}
                    </button>
                </>
            }
        >
            <form id="product-form" className="record-form" onSubmit={handleSubmit}>
                {error && <div className="form-error">{error}</div>}
                <label className="field field--half">
                    <span>SKU *</span>
                    <input value={v.sku} onChange={set("sku")} maxLength={100} required />
                </label>
                <label className="field field--half">
                    <span>Unit</span>
                    <input value={v.unit} onChange={set("unit")} maxLength={50} placeholder="pcs, box, kg…" />
                </label>
                <label className="field">
                    <span>Name *</span>
                    <input value={v.name} onChange={set("name")} maxLength={200} required />
                </label>
                <label className="field">
                    <span>Description</span>
                    <textarea rows={2} value={v.description} onChange={set("description")} />
                </label>
                {select("category_id", "Category", lookups.categories)}
                {select("supplier_id", "Supplier", lookups.suppliers)}
                {select("location_id", "Location", lookups.locations)}
                <label className="field field--half">
                    <span>Price</span>
                    <input type="number" min="0" step="0.01" value={v.price} onChange={set("price")} />
                </label>
                <label className="field field--half">
                    <span>Reorder level</span>
                    <input type="number" min="0" step="1" value={v.reorder_level} onChange={set("reorder_level")} />
                </label>
                {isEdit ? (
                    <p className="muted field">
                        In stock: <strong>{record.current_stock}</strong>. Stock changes through Transactions or Adjustments.
                    </p>
                ) : (
                    <label className="field field--half">
                        <span>Opening stock</span>
                        <input type="number" min="0" step="1" value={v.initial_stock} onChange={set("initial_stock")} />
                    </label>
                )}
            </form>
        </Modal>
    )
}

export default function ProductsPage() {
    const { user } = useAuth()
    const canWrite = WRITE_ROLES.includes(user?.role)
    const lookups = useLookups()

    const nameOf = useMemo(() => {
        const map = (list) => Object.fromEntries(list.map((x) => [x.id, x.name]))
        return { category: map(lookups.categories), supplier: map(lookups.suppliers), location: map(lookups.locations) }
    }, [lookups])

    const [search, setSearch] = useState("")
    const [debounced, setDebounced] = useState("")
    const [filters, setFilters] = useState({ category_id: "", supplier_id: "", location_id: "", low_stock: false })
    const [skip, setSkip] = useState(0)
    const [rows, setRows] = useState([])
    const [hasNext, setHasNext] = useState(false)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState("")
    const [reloadKey, setReloadKey] = useState(0)

    const [editing, setEditing] = useState(null)
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
        productsApi
            .list({
                search: debounced,
                category_id: filters.category_id,
                supplier_id: filters.supplier_id,
                location_id: filters.location_id,
                low_stock: filters.low_stock ? "true" : "",
                skip,
                limit: PAGE_SIZE + 1, // one extra row tells us whether a next page exists
            })
            .then((list) => {
                if (ignore) return
                if (list.length === 0 && skip > 0) {
                    setSkip(Math.max(0, skip - PAGE_SIZE))
                    return
                }
                setHasNext(list.length > PAGE_SIZE)
                setRows(list.slice(0, PAGE_SIZE))
                setError("")
            })
            .catch((err) => {
                if (!ignore) setError(errorMessage(err, "Couldn't load products."))
            })
            .finally(() => {
                if (!ignore) setLoading(false)
            })
        return () => {
            ignore = true
        }
    }, [debounced, filters, skip, reloadKey])

    useEffect(() => {
        if (!toast) return
        const t = setTimeout(() => setToast(""), 3000)
        return () => clearTimeout(t)
    }, [toast])

    const reload = () => setReloadKey((k) => k + 1)

    function setFilter(key, value) {
        setFilters((f) => ({ ...f, [key]: value }))
        setSkip(0)
    }

    async function confirmDelete() {
        setDeleteBusy(true)
        setDeleteError("")
        try {
            await productsApi.remove(deleting.id)
            setDeleting(null)
            setToast("Product deleted")
            reload()
        } catch (err) {
            setDeleteError(errorMessage(err))
        } finally {
            setDeleteBusy(false)
        }
    }

    const columns = [
        { key: "sku", header: "SKU" },
        { key: "name", header: "Name" },
        { key: "category_id", header: "Category", render: (r) => nameOf.category[r.category_id] ?? "—" },
        { key: "supplier_id", header: "Supplier", render: (r) => nameOf.supplier[r.supplier_id] ?? "—" },
        { key: "location_id", header: "Location", render: (r) => nameOf.location[r.location_id] ?? "—" },
        { key: "price", header: "Price", render: (r) => Number(r.price).toFixed(2) },
        {
            key: "current_stock",
            header: "In stock",
            render: (r) => (
                <>
                    {r.current_stock} {r.unit || ""}
                    {r.current_stock <= r.reorder_level && <span className="badge badge--warn">Low</span>}
                </>
            ),
        },
    ]

    const isFiltered = Boolean(debounced) || filters.category_id || filters.supplier_id || filters.location_id || filters.low_stock

    return (
        <PageShell
            title="Products"
            subtitle="SKUs, pricing, and reorder levels."
            actions={canWrite && <button className="btn btn-primary" onClick={() => setEditing({})}>+ New product</button>}
        >
            <div className="toolbar">
                <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search SKU or name…" aria-label="Search" />
                <Select label="Category" placeholder="All categories" value={filters.category_id} onChange={(v) => setFilter("category_id", v)} options={lookups.categories} />
                <Select label="Supplier" placeholder="All suppliers" value={filters.supplier_id} onChange={(v) => setFilter("supplier_id", v)} options={lookups.suppliers} />
                <Select label="Location" placeholder="All locations" value={filters.location_id} onChange={(v) => setFilter("location_id", v)} options={lookups.locations} />
                <label className="check">
                    <input type="checkbox" checked={filters.low_stock} onChange={(e) => setFilter("low_stock", e.target.checked)} />
                    Low stock only
                </label>
            </div>

            {!canWrite && <p className="muted">You have read-only access to this page.</p>}

            <DataTable
                columns={columns}
                rows={rows}
                loading={loading}
                error={error}
                empty={isFiltered ? "No products match your search or filters." : "No products yet."}
                renderActions={
                    canWrite &&
                    ((row) => (
                        <div className="row-actions">
                            <button className="btn btn-ghost btn-sm" onClick={() => setEditing(row)}>Edit</button>
                            <button className="btn btn-danger btn-sm" onClick={() => { setDeleteError(""); setDeleting(row) }}>Delete</button>
                        </div>
                    ))
                }
            />

            {(skip > 0 || hasNext) && (
                <div className="pager">
                    <span>Page {skip / PAGE_SIZE + 1}</span>
                    <div className="pager-buttons">
                        <button className="btn btn-ghost btn-sm" disabled={skip === 0} onClick={() => setSkip(Math.max(0, skip - PAGE_SIZE))}>Previous</button>
                        <button className="btn btn-ghost btn-sm" disabled={!hasNext} onClick={() => setSkip(skip + PAGE_SIZE)}>Next</button>
                    </div>
                </div>
            )}

            {editing && (
                <ProductForm
                    key={editing.id ?? "new"}
                    record={editing}
                    lookups={lookups}
                    onCancel={() => setEditing(null)}
                    onSaved={(_p, wasEdit) => {
                        setEditing(null)
                        setToast(`Product ${wasEdit ? "updated" : "created"}`)
                        reload()
                    }}
                />
            )}

            {deleting && (
                <ConfirmDialog title="Delete product" busy={deleteBusy} error={deleteError} onConfirm={confirmDelete} onCancel={() => setDeleting(null)}>
                    Delete <strong>{deleting.name}</strong> ({deleting.sku})? Products with transaction or adjustment history can't be deleted.
                </ConfirmDialog>
            )}

            {toast && <div className="toast" role="status">{toast}</div>}
        </PageShell>
    )
}