import { useEffect, useRef, useState } from "react"
import { productsApi, errorMessage } from "../api/resources"
import "./styles/Resource.css"
import "./styles/Ledger.css"

const RESULT_LIMIT = 20
const DEBOUNCE_MS = 250

const labelOf = (p) => `${p.sku} — ${p.name}`

// Searches the server as you type, so it works however many products a company has.
export default function ProductField({ value, onChange }) {
    const [query, setQuery] = useState("")
    const [selected, setSelected] = useState(null)
    const [open, setOpen] = useState(false)
    const [results, setResults] = useState([])
    const [active, setActive] = useState(0)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState("")
    const inputRef = useRef(null)

    useEffect(() => {
        if (!open) return
        let ignore = false
        const t = setTimeout(() => {
            setLoading(true)
            productsApi
                .list({ search: query.trim(), limit: RESULT_LIMIT })
                .then((list) => {
                    if (ignore) return
                    setResults(list)
                    setActive(0)
                    setError("")
                })
                .catch((err) => {
                    if (!ignore) setError(errorMessage(err, "Couldn't load products."))
                })
                .finally(() => {
                    if (!ignore) setLoading(false)
                })
        }, DEBOUNCE_MS)
        return () => {
            ignore = true
            clearTimeout(t)
        }
    }, [open, query])

    // Text in the box isn't a choice: only a product picked from the list is.
    useEffect(() => {
        inputRef.current?.setCustomValidity(value ? "" : "Choose a product from the list.")
    }, [value])

    function choose(product) {
        setSelected(product)
        setQuery(labelOf(product))
        setOpen(false)
        onChange(product.id)
    }

    function handleInput(e) {
        setQuery(e.target.value)
        setOpen(true)
        if (selected) {
            setSelected(null)
            onChange("")
        }
    }

    function handleFocus(e) {
        e.target.select()
        // Reopening after a choice shows the whole list, not just that product.
        if (selected) setQuery("")
        setOpen(true)
    }

    function handleBlur() {
        setOpen(false)
        if (selected) setQuery(labelOf(selected))
    }

    function handleKeyDown(e) {
        if (!open) return
        if (e.key === "ArrowDown") {
            e.preventDefault()
            setActive((i) => Math.min(i + 1, results.length - 1))
        } else if (e.key === "ArrowUp") {
            e.preventDefault()
            setActive((i) => Math.max(i - 1, 0))
        } else if (e.key === "Enter") {
            e.preventDefault() // choose the product, don't submit the form
            if (results[active]) choose(results[active])
        } else if (e.key === "Escape") {
            e.stopPropagation() // close this list, not the whole dialog
            setOpen(false)
        }
    }

    return (
        <div className="field product-picker">
            <label htmlFor="product-picker-input">
                <span>Product *</span>
            </label>
            <input
                id="product-picker-input"
                ref={inputRef}
                role="combobox"
                aria-expanded={open}
                aria-controls="product-picker-list"
                aria-autocomplete="list"
                autoComplete="off"
                value={query}
                onChange={handleInput}
                onFocus={handleFocus}
                onBlur={handleBlur}
                onKeyDown={handleKeyDown}
                placeholder="Search by SKU or name…"
                required
            />
            {open && (
                <ul id="product-picker-list" className="product-picker-list" role="listbox">
                    {error && <li className="product-picker-note">{error}</li>}
                    {!error && results.length === 0 && (
                        <li className="product-picker-note">{loading ? "Searching…" : "No products match."}</li>
                    )}
                    {!error &&
                        results.map((p, i) => (
                            <li
                                key={p.id}
                                role="option"
                                aria-selected={i === active}
                                className={i === active ? "is-active" : undefined}
                                // mousedown, because a click would blur the input and close the list first
                                onMouseDown={(e) => {
                                    e.preventDefault()
                                    choose(p)
                                }}
                                onMouseEnter={() => setActive(i)}
                            >
                                <span>{labelOf(p)}</span>
                                <small>
                                    {p.current_stock} {p.unit || ""}
                                </small>
                            </li>
                        ))}
                    {!error && results.length === RESULT_LIMIT && (
                        <li className="product-picker-note">Showing the first {RESULT_LIMIT}. Type to narrow it down.</li>
                    )}
                </ul>
            )}
            {selected && (
                <span className="field-hint">
                    Currently in stock: {selected.current_stock} {selected.unit || ""}
                </span>
            )}
        </div>
    )
}
