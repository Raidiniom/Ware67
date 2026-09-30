import { useEffect, useState } from "react"
import { productsApi } from "../api/resources"
import "./styles/Resource.css"
import "./styles/Ledger.css"

// The products endpoint caps `limit` at 200.
export function useProducts() {
    const [products, setProducts] = useState([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        let ignore = false
        productsApi
            .list({ limit: 200 })
            .then((list) => {
                if (!ignore) setProducts(list)
            })
            .catch(() => {})
            .finally(() => {
                if (!ignore) setLoading(false)
            })
        return () => {
            ignore = true
        }
    }, [])

    return { products, loading }
}

export default function ProductField({ value, onChange, products, loading }) {
    const selected = products.find((p) => p.id === value)

    return (
        <label className="field">
            <span>Product *</span>
            <select value={value} onChange={(e) => onChange(e.target.value)} required disabled={loading}>
                <option value="">{loading ? "Loading products…" : "Select a product"}</option>
                {products.map((p) => (
                    <option key={p.id} value={p.id}>
                        {p.sku} — {p.name}
                    </option>
                ))}
            </select>
            {selected && (
                <span className="field-hint">
                    Currently in stock: {selected.current_stock} {selected.unit || ""}
                </span>
            )}
        </label>
    )
}