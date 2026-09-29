import "./styles/Resource.css"

export default function DataTable({ columns, rows, loading, error, empty = "Nothing here yet.", renderActions }) {
    if (error) return <div className="table-wrap"><div className="table-state table-state--error">{error}</div></div>

    return (
        <div className="table-wrap">
            <table className={`data-table${loading ? " is-loading" : ""}`}>
                <thead>
                    <tr>
                        {columns.map((c) => <th key={c.key}>{c.header}</th>)}
                        {renderActions && <th className="col-actions" aria-label="Actions" />}
                    </tr>
                </thead>
                <tbody>
                    {rows.map((row) => (
                        <tr key={row.id}>
                            {columns.map((c) => (
                                <td key={c.key}>{c.render ? c.render(row) : row[c.key] ?? "—"}</td>
                            ))}
                            {renderActions && <td className="col-actions">{renderActions(row)}</td>}
                        </tr>
                    ))}
                </tbody>
            </table>
            {loading && rows.length === 0 && <div className="table-state">Loading…</div>}
            {!loading && rows.length === 0 && <div className="table-state">{empty}</div>}
        </div>
    )
}