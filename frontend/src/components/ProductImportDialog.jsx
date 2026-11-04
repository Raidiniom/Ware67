import { useState } from "react"
import { productsApi, errorMessage } from "../api/resources"
import { saveBlob } from "../utils/download"
import Modal from "./Modal"
import "./styles/Resource.css"

const TEMPLATE =
    "sku,name,description,category,supplier,location,unit,price,reorder_level,initial_stock\n" +
    "SKU-001,Blue Mug,Ceramic 350ml,Kitchenware,Acme Trading,Bin A-01,pcs,9.99,5,25\n"

function downloadTemplate() {
    saveBlob(new Blob([TEMPLATE], { type: "text/csv" }), "products-template.csv")
}

const plural = (n, one, many) => `${n.toLocaleString()} ${n === 1 ? one : many}`

function NewNames({ one, many, names }) {
    if (names.length === 0) return null
    return (
        <li>
            {plural(names.length, `new ${one}`, `new ${many}`)}: {names.slice(0, 5).join(", ")}
            {names.length > 5 && ` and ${names.length - 5} more`}
        </li>
    )
}

// Checks the file first (a dry run), then imports only once it's confirmed.
export default function ProductImportDialog({ onImported, onCancel }) {
    const [file, setFile] = useState(null)
    const [preview, setPreview] = useState(null)
    const [rowErrors, setRowErrors] = useState([])
    const [error, setError] = useState("")
    const [busy, setBusy] = useState(false)

    function showFailure(err) {
        setPreview(null)
        setRowErrors(err?.response?.data?.errors ?? [])
        setError(errorMessage(err, "Couldn't read that file."))
    }

    async function handleFile(e) {
        const chosen = e.target.files[0]
        e.target.value = "" // so choosing the same file again, once fixed, still fires
        if (!chosen) return
        setFile(chosen)
        setPreview(null)
        setRowErrors([])
        setError("")
        setBusy(true)
        try {
            setPreview(await productsApi.importCsv(chosen, { dryRun: true }))
        } catch (err) {
            showFailure(err)
        } finally {
            setBusy(false)
        }
    }

    async function handleImport() {
        setBusy(true)
        setError("")
        try {
            const result = await productsApi.importCsv(file, { dryRun: false })
            onImported(result)
        } catch (err) {
            showFailure(err)
            setBusy(false)
        }
    }

    return (
        <Modal
            title="Import products from CSV"
            wide
            onClose={busy ? () => {} : onCancel}
            footer={
                <>
                    <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={busy}>
                        Cancel
                    </button>
                    <button type="button" className="btn btn-primary" onClick={handleImport} disabled={busy || !preview}>
                        {busy && preview
                            ? "Importing…"
                            : preview
                              ? `Import ${plural(preview.products, "product", "products")}`
                              : "Import"}
                    </button>
                </>
            }
        >
            <div className="import-dialog">
                <p>
                    Only <code>sku</code> and <code>name</code> are required. Categories, suppliers and locations are
                    matched by name, and created if they don't exist yet. Existing SKUs aren't changed: a file that
                    repeats one is refused, and nothing is imported unless every row is valid.{" "}
                    <button type="button" className="link-btn" onClick={downloadTemplate}>
                        Download a template
                    </button>
                </p>

                <label className="field">
                    <span>CSV file (2 MB and 5,000 rows at most)</span>
                    <input type="file" accept=".csv,text/csv" onChange={handleFile} disabled={busy} />
                </label>
                {file && <p className="muted">{busy && !preview ? `Checking ${file.name}…` : file.name}</p>}

                {error && <div className="form-error">{error}</div>}

                {rowErrors.length > 0 && (
                    <div className="import-errors">
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>Row</th>
                                    <th>Column</th>
                                    <th>Problem</th>
                                </tr>
                            </thead>
                            <tbody>
                                {rowErrors.map((e, i) => (
                                    <tr key={i}>
                                        <td>{e.row}</td>
                                        <td>{e.field ?? "—"}</td>
                                        <td>{e.message}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}

                {preview && (
                    <div className="import-preview" role="status">
                        <strong>Ready to import. Nothing has been saved yet.</strong>
                        <ul>
                            <li>{plural(preview.products, "product", "products")}</li>
                            <li>{plural(preview.opening_stock_units, "unit", "units")} of opening stock, recorded as stock-in</li>
                            <NewNames one="category" many="categories" names={preview.new_categories} />
                            <NewNames one="supplier" many="suppliers" names={preview.new_suppliers} />
                            <NewNames one="location" many="locations" names={preview.new_locations} />
                        </ul>
                    </div>
                )}
            </div>
        </Modal>
    )
}
