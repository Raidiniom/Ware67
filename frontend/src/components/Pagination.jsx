import "./styles/Resource.css"

export default function Pagination({ skip, limit, total, onChange }) {
    if (total === 0) return null
    return (
        <div className="pager">
            <span>Showing {skip + 1}–{Math.min(skip + limit, total)} of {total}</span>
            <div className="pager-buttons">
                <button className="btn btn-ghost btn-sm" disabled={skip === 0} onClick={() => onChange(Math.max(0, skip - limit))}>
                    Previous
                </button>
                <button className="btn btn-ghost btn-sm" disabled={skip + limit >= total} onClick={() => onChange(skip + limit)}>
                    Next
                </button>
            </div>
        </div>
    )
}