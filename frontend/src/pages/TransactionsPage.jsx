import { useState } from "react"
import LedgerPage from "../components/LedgerPage"
import Modal from "../components/Modal"
import ProductField, { useProducts } from "../components/ProductField"
import { transactionsApi } from "../api/ledger"
import { errorMessage } from "../api/resources"
import { useAuth } from "../context/AuthContext"
import { formatDateTime } from "../utils/format"

// Guests are read-only; everyone else can record stock movements.
const CREATE_ROLES = ["OWNER", "ADMIN", "MANAGER", "STAFF"]

const columns = [
    { key: "created_at", header: "When", render: (r) => <span className="cell-nowrap">{formatDateTime(r.created_at)}</span> },
    {
        key: "product",
        header: "Product",
        render: (r) => (
            <div className="cell-stack">
                <strong>{r.product_name ?? "—"}</strong>
                <small>{r.product_sku}</small>
            </div>
        ),
    },
    {
        key: "type",
        header: "Type",
        render: (r) => (
            <span className={`pill ${r.type === "STOCK_IN" ? "pill--in" : "pill--out"}`}>
                {r.type === "STOCK_IN" ? "Stock in" : "Stock out"}
            </span>
        ),
    },
    {
        key: "quantity",
        header: "Qty",
        render: (r) => (
            <span className={`qty ${r.type === "STOCK_IN" ? "qty--pos" : "qty--neg"}`}>
                {r.type === "STOCK_IN" ? "+" : "−"}
                {r.quantity}
            </span>
        ),
    },
    {
        key: "reference",
        header: "Reference",
        render: (r) => [r.reference_type, r.reference_id].filter(Boolean).join(" · ") || "—",
    },
    { key: "user_name", header: "Recorded by" },
    { key: "notes", header: "Notes" },
]

const filters = [
    {
        key: "type",
        label: "All types",
        options: [
            { value: "STOCK_IN", label: "Stock in" },
            { value: "STOCK_OUT", label: "Stock out" },
        ],
    },
]

const EMPTY = { product_id: "", type: "STOCK_IN", quantity: "1", reference_type: "", reference_id: "", notes: "" }

function TransactionForm({ onSaved, onCancel }) {
    const { products, loading } = useProducts()
    const [v, setV] = useState(EMPTY)
    const [error, setError] = useState("")
    const [saving, setSaving] = useState(false)

    const set = (name) => (e) => setV((s) => ({ ...s, [name]: e.target.value }))

    async function handleSubmit(e) {
        e.preventDefault()
        setError("")
        setSaving(true)
        try {
            await transactionsApi.create({
                product_id: v.product_id,
                type: v.type,
                quantity: Number(v.quantity),
                reference_type: v.reference_type,
                reference_id: v.reference_id,
                notes: v.notes,
            })
            onSaved()
        } catch (err) {
            setError(errorMessage(err))
            setSaving(false)
        }
    }

    return (
        <Modal
            title="Record transaction"
            onClose={saving ? () => {} : onCancel}
            footer={
                <>
                    <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={saving}>
                        Cancel
                    </button>
                    <button type="submit" form="transaction-form" className="btn btn-primary" disabled={saving}>
                        {saving ? "Saving…" : "Record transaction"}
                    </button>
                </>
            }
        >
            <form id="transaction-form" className="record-form" onSubmit={handleSubmit}>
                {error && <div className="form-error">{error}</div>}

                <ProductField
                    value={v.product_id}
                    onChange={(id) => setV((s) => ({ ...s, product_id: id }))}
                    products={products}
                    loading={loading}
                />

                <label className="field field--half">
                    <span>Type *</span>
                    <select value={v.type} onChange={set("type")}>
                        <option value="STOCK_IN">Stock in</option>
                        <option value="STOCK_OUT">Stock out</option>
                    </select>
                </label>
                <label className="field field--half">
                    <span>Quantity *</span>
                    <input type="number" min="1" max="1000000" step="1" value={v.quantity} onChange={set("quantity")} required />
                </label>

                <label className="field field--half">
                    <span>Reference type</span>
                    <input value={v.reference_type} onChange={set("reference_type")} maxLength={50} placeholder="PO, SO, MANUAL…" />
                </label>
                <label className="field field--half">
                    <span>Reference ID</span>
                    <input value={v.reference_id} onChange={set("reference_id")} maxLength={100} placeholder="Order number" />
                </label>

                <label className="field">
                    <span>Notes</span>
                    <textarea rows={3} value={v.notes} onChange={set("notes")} />
                </label>
            </form>
        </Modal>
    )
}

export default function TransactionsPage() {
    const { user } = useAuth()
    const canCreate = CREATE_ROLES.includes(user?.role)

    return (
        <LedgerPage
            title="Transactions"
            subtitle="Stock-in and stock-out history."
            plural="transactions"
            api={transactionsApi}
            columns={columns}
            filters={filters}
            searchPlaceholder="Search product, SKU, reference, notes…"
            actionLabel="+ New transaction"
            CreateForm={TransactionForm}
            canCreate={canCreate}
            notice={!canCreate ? "You have read-only access to this page." : undefined}
        />
    )
}