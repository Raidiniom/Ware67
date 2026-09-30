import { useState } from "react"
import LedgerPage from "../components/LedgerPage"
import Modal from "../components/Modal"
import ProductField, { useProducts } from "../components/ProductField"
import { adjustmentsApi } from "../api/ledger"
import { errorMessage } from "../api/resources"
import { useAuth } from "../context/AuthContext"
import { formatDateTime } from "../utils/format"

const WRITE_ROLES = ["ADMIN", "MANAGER"]

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
        key: "quantity_change",
        header: "Change",
        render: (r) => (
            <span className={`qty ${r.quantity_change > 0 ? "qty--pos" : "qty--neg"}`}>
                {r.quantity_change > 0 ? "+" : "−"}
                {Math.abs(r.quantity_change)}
            </span>
        ),
    },
    { key: "reason", header: "Reason" },
    { key: "user_name", header: "Adjusted by" },
    { key: "notes", header: "Notes" },
]

const EMPTY = { product_id: "", quantity_change: "", reason: "", notes: "" }

function AdjustmentForm({ onSaved, onCancel }) {
    const { products, loading } = useProducts()
    const [v, setV] = useState(EMPTY)
    const [error, setError] = useState("")
    const [saving, setSaving] = useState(false)

    const set = (name) => (e) => setV((s) => ({ ...s, [name]: e.target.value }))

    async function handleSubmit(e) {
        e.preventDefault()
        setError("")

        const change = Number(v.quantity_change)
        if (!Number.isInteger(change) || change === 0) {
            setError("Enter a whole number other than zero.")
            return
        }

        setSaving(true)
        try {
            await adjustmentsApi.create({
                product_id: v.product_id,
                quantity_change: change,
                reason: v.reason.trim(),
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
            title="New adjustment"
            onClose={saving ? () => {} : onCancel}
            footer={
                <>
                    <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={saving}>
                        Cancel
                    </button>
                    <button type="submit" form="adjustment-form" className="btn btn-primary" disabled={saving}>
                        {saving ? "Saving…" : "Save adjustment"}
                    </button>
                </>
            }
        >
            <form id="adjustment-form" className="record-form" onSubmit={handleSubmit}>
                {error && <div className="form-error">{error}</div>}

                <ProductField
                    value={v.product_id}
                    onChange={(id) => setV((s) => ({ ...s, product_id: id }))}
                    products={products}
                    loading={loading}
                />

                <label className="field field--half">
                    <span>Quantity change *</span>
                    <input
                        type="number"
                        step="1"
                        min="-1000000"
                        max="1000000"
                        value={v.quantity_change}
                        onChange={set("quantity_change")}
                        placeholder="e.g. -3 or 10"
                        required
                    />
                    <span className="field-hint">Use a negative number to remove stock.</span>
                </label>
                <label className="field field--half">
                    <span>Reason *</span>
                    <input value={v.reason} onChange={set("reason")} maxLength={150} placeholder="Damaged, recount, expired…" required />
                </label>

                <label className="field">
                    <span>Notes</span>
                    <textarea rows={3} value={v.notes} onChange={set("notes")} />
                </label>
            </form>
        </Modal>
    )
}

export default function AdjustmentsPage() {
    const { user } = useAuth()
    const canCreate = WRITE_ROLES.includes(user?.role)

    return (
        <LedgerPage
            title="Inventory adjustments"
            subtitle="Manual stock corrections, with a reason on record."
            plural="adjustments"
            api={adjustmentsApi}
            columns={columns}
            searchPlaceholder="Search product, SKU, reason, notes…"
            actionLabel="+ New adjustment"
            CreateForm={AdjustmentForm}
            canCreate={canCreate}
            notice={!canCreate ? "You have read-only access to this page." : undefined}
        />
    )
}