import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router-dom"

import {
    createProduct,
    deleteProduct,
    listProducts,
    updateProduct,
} from "../api/products"
import { useAuth } from "../context/AuthContext"
import "./styles/common.css"
import "./styles/ProductsPage.css"

const EMPTY_FORM = {
    sku: "",
    name: "",
    description: "",
    unit: "",
    price: "0.00",
    reorder_level: "0",
}

function getErrorMessage(error) {
    const detail = error?.response?.data?.detail
    if (typeof detail === "string") return detail
    if (Array.isArray(detail)) {
        return detail.map((item) => item.msg).filter(Boolean).join(", ")
    }
    return "Something went wrong. Please try again."
}

export default function ProductsPage() {
    const { user } = useAuth()
    const canManage = ["ADMIN", "MANAGER"].includes(user?.role)
    const [products, setProducts] = useState([])
    const [search, setSearch] = useState("")
    const [form, setForm] = useState(EMPTY_FORM)
    const [editingId, setEditingId] = useState(null)
    const [showForm, setShowForm] = useState(false)
    const [loading, setLoading] = useState(true)
    const [submitting, setSubmitting] = useState(false)
    const [error, setError] = useState("")

    const loadProducts = useCallback(async (query = "") => {
        setLoading(true)
        setError("")
        try {
            setProducts(await listProducts(query))
        } catch (requestError) {
            setError(getErrorMessage(requestError))
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        let active = true

        listProducts()
            .then((data) => {
                if (active) setProducts(data)
            })
            .catch((requestError) => {
                if (active) setError(getErrorMessage(requestError))
            })
            .finally(() => {
                if (active) setLoading(false)
            })

        return () => {
            active = false
        }
    }, [])

    function updateField(field) {
        return (event) => setForm((current) => ({ ...current, [field]: event.target.value }))
    }

    function openCreateForm() {
        setEditingId(null)
        setForm(EMPTY_FORM)
        setError("")
        setShowForm(true)
    }

    function openEditForm(product) {
        setEditingId(product.id)
        setForm({
            sku: product.sku,
            name: product.name,
            description: product.description || "",
            unit: product.unit || "",
            price: product.price,
            reorder_level: product.reorder_level,
        })
        setError("")
        setShowForm(true)
    }

    function closeForm() {
        setShowForm(false)
        setEditingId(null)
        setForm(EMPTY_FORM)
    }

    async function handleSearch(event) {
        event.preventDefault()
        await loadProducts(search.trim())
    }

    async function handleSubmit(event) {
        event.preventDefault()
        setSubmitting(true)
        setError("")

        const payload = {
            sku: form.sku,
            name: form.name,
            description: form.description || null,
            unit: form.unit || null,
            price: Number(form.price),
            reorder_level: Number(form.reorder_level),
        }

        try {
            if (editingId) await updateProduct(editingId, payload)
            else await createProduct(payload)
            closeForm()
            await loadProducts(search.trim())
        } catch (requestError) {
            setError(getErrorMessage(requestError))
        } finally {
            setSubmitting(false)
        }
    }

    async function handleDelete(product) {
        const confirmed = window.confirm(`Delete ${product.name} (${product.sku})?`)
        if (!confirmed) return

        setError("")
        try {
            await deleteProduct(product.id)
            await loadProducts(search.trim())
        } catch (requestError) {
            setError(getErrorMessage(requestError))
        }
    }

    return (
        <main className="products-page">
            <header className="products-header">
                <div>
                    <Link to="/dashboard" className="products-back">← Dashboard</Link>
                    <h1>Products</h1>
                    <p>Manage warehouse SKUs, pricing, units, and reorder levels.</p>
                </div>
                {canManage && (
                    <button className="btn btn-primary" type="button" onClick={openCreateForm}>
                        Add product
                    </button>
                )}
            </header>

            <section className="products-toolbar">
                <form className="products-search" onSubmit={handleSearch}>
                    <label htmlFor="product-search">Search by name or SKU</label>
                    <div>
                        <input
                            id="product-search"
                            type="search"
                            value={search}
                            onChange={(event) => setSearch(event.target.value)}
                            placeholder="e.g. TEST-001"
                        />
                        <button className="btn btn-outline" type="submit">Search</button>
                        {search && (
                            <button
                                className="btn btn-ghost"
                                type="button"
                                onClick={() => {
                                    setSearch("")
                                    loadProducts()
                                }}
                            >
                                Clear
                            </button>
                        )}
                    </div>
                </form>
                <span className="products-count">
                    {products.length} product{products.length === 1 ? "" : "s"}
                </span>
            </section>

            {error && <div className="products-alert" role="alert">{error}</div>}

            {showForm && canManage && (
                <section className="product-form-card">
                    <div className="product-form-heading">
                        <div>
                            <h2>{editingId ? "Edit product" : "Add product"}</h2>
                            <p>Fields marked with * are required.</p>
                        </div>
                        <button className="btn btn-ghost" type="button" onClick={closeForm}>Cancel</button>
                    </div>

                    <form className="product-form" onSubmit={handleSubmit}>
                        <label>
                            <span>SKU *</span>
                            <input value={form.sku} onChange={updateField("sku")} maxLength={100} required />
                        </label>
                        <label>
                            <span>Name *</span>
                            <input value={form.name} onChange={updateField("name")} maxLength={200} required />
                        </label>
                        <label>
                            <span>Unit</span>
                            <input value={form.unit} onChange={updateField("unit")} maxLength={50} placeholder="piece, box, kg…" />
                        </label>
                        <label>
                            <span>Price</span>
                            <input type="number" value={form.price} onChange={updateField("price")} min="0" step="0.01" required />
                        </label>
                        <label>
                            <span>Reorder level</span>
                            <input type="number" value={form.reorder_level} onChange={updateField("reorder_level")} min="0" step="1" required />
                        </label>
                        <label className="product-form-description">
                            <span>Description</span>
                            <textarea value={form.description} onChange={updateField("description")} rows={3} />
                        </label>
                        <div className="product-form-actions">
                            <button className="btn btn-primary" type="submit" disabled={submitting}>
                                {submitting ? "Saving…" : editingId ? "Save changes" : "Create product"}
                            </button>
                        </div>
                    </form>
                </section>
            )}

            <section className="products-table-card">
                {loading ? (
                    <p className="products-empty">Loading products…</p>
                ) : products.length === 0 ? (
                    <div className="products-empty">
                        <h2>No products found</h2>
                        <p>{search ? "Try a different search." : "Create the first warehouse product."}</p>
                    </div>
                ) : (
                    <div className="products-table-wrap">
                        <table className="products-table">
                            <thead>
                                <tr>
                                    <th>SKU</th>
                                    <th>Name</th>
                                    <th>Unit</th>
                                    <th>Price</th>
                                    <th>Reorder level</th>
                                    {canManage && <th>Actions</th>}
                                </tr>
                            </thead>
                            <tbody>
                                {products.map((product) => (
                                    <tr key={product.id}>
                                        <td><code>{product.sku}</code></td>
                                        <td>
                                            <strong>{product.name}</strong>
                                            {product.description && <small>{product.description}</small>}
                                        </td>
                                        <td>{product.unit || "—"}</td>
                                        <td>₱{Number(product.price).toFixed(2)}</td>
                                        <td>{product.reorder_level}</td>
                                        {canManage && (
                                            <td>
                                                <div className="product-row-actions">
                                                    <button className="btn btn-ghost" type="button" onClick={() => openEditForm(product)}>Edit</button>
                                                    <button className="btn product-delete" type="button" onClick={() => handleDelete(product)}>Delete</button>
                                                </div>
                                            </td>
                                        )}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </section>
        </main>
    )
}
