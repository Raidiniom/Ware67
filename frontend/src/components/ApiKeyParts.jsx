import { SCOPES } from "../api/apiKeys"
import { formatDateTime } from "../utils/format"
import "./styles/Ledger.css"
import "./styles/ApiKeys.css"

const STATUS = {
    PENDING: { label: "Waiting for review", pill: "pill--neutral" },
    APPROVED: { label: "Ready to reveal", pill: "pill--in" },
    ACTIVE: { label: "Active", pill: "pill--in" },
    REJECTED: { label: "Rejected", pill: "pill--danger" },
    REVOKED: { label: "Revoked", pill: "pill--danger" },
    LAPSED: { label: "Lapsed", pill: "pill--neutral" },
    EXPIRED: { label: "Expired", pill: "pill--out" },
}

// One line under the status explaining what it means for this key.
function statusDetail(key) {
    switch (key.status) {
        case "PENDING":
            return `Requested ${formatDateTime(key.created_at)}`
        case "APPROVED":
            return `Reveal by ${formatDateTime(key.reveal_deadline)}`
        case "ACTIVE":
            return `Expires ${formatDateTime(key.expires_at)}`
        case "EXPIRED":
            return `Expired ${formatDateTime(key.expires_at)}`
        case "REJECTED":
            return key.rejection_reason
        case "REVOKED":
            return `Revoked ${formatDateTime(key.revoked_at)}`
        case "LAPSED":
            return "Not revealed in time. Request a new key."
        default:
            return null
    }
}

export function KeyStatus({ apiKey }) {
    const s = STATUS[apiKey.status] || { label: apiKey.status, pill: "pill--neutral" }
    const detail = statusDetail(apiKey)
    return (
        <div className="cell-stack">
            <span className={`pill ${s.pill}`}>{s.label}</span>
            {detail && <small>{detail}</small>}
        </div>
    )
}

export function ScopeList({ scopes }) {
    if (!scopes?.length) return "—"
    return (
        <div className="cell-stack">
            {scopes.map((scope) => (
                <small key={scope}>
                    <code>{scope}</code>
                </small>
            ))}
        </div>
    )
}

// Checkboxes for scopes. `allowed` limits the choices (when approving, only
// what the company asked for can be granted).
export function ScopePicker({ value, onChange, allowed }) {
    const options = allowed ? SCOPES.filter((s) => allowed.includes(s.value)) : SCOPES

    function toggle(scope) {
        onChange(value.includes(scope) ? value.filter((v) => v !== scope) : [...value, scope])
    }

    return (
        <fieldset className="scope-picker">
            <legend>Access</legend>
            {options.map((s) => (
                <label className="scope-option" key={s.value}>
                    <input type="checkbox" checked={value.includes(s.value)} onChange={() => toggle(s.value)} />
                    <div>
                        <strong>{s.label}</strong>
                        <small>{s.hint}</small>
                    </div>
                </label>
            ))}
        </fieldset>
    )
}
