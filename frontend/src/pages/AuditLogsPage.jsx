import LedgerPage from "../components/LedgerPage"
import PageShell from "../components/PageShell"
import Modal from "../components/Modal"
import { auditLogsApi } from "../api/ledger"
import { useAuth } from "../context/AuthContext"
import { formatDateTime } from "../utils/format"

const ACTIONS = [
    "CREATE",
    "UPDATE",
    "DELETE",
    "STOCK_IN",
    "STOCK_OUT",
    "INVENTORY_ADJUSTMENT",
    "LOGIN",
    "LOGIN_FAILED",
    "REGISTER",
    "FORGOT_PASSWORD",
    "ONBOARD",
    "UPDATE_ROLE",
    "UPDATE_STATUS",
]

const ENTITIES = ["PRODUCT", "CATEGORY", "SUPPLIER", "LOCATION", "USER", "ROLE", "TRANSACTION", "INVENTORY_ADJUSTMENT"]

const toOptions = (list) => list.map((value) => ({ value, label: value.replaceAll("_", " ").toLowerCase() }))

const filters = [
    { key: "action", label: "All actions", options: toOptions(ACTIONS) },
    { key: "entity", label: "All entities", options: toOptions(ENTITIES) },
]

function actionClass(action) {
    if (action === "DELETE" || action === "LOGIN_FAILED") return "pill pill--danger"
    if (action === "CREATE" || action === "STOCK_IN" || action === "REGISTER") return "pill pill--in"
    if (action === "STOCK_OUT" || action === "INVENTORY_ADJUSTMENT") return "pill pill--out"
    if (action?.startsWith("LOGIN")) return "pill pill--neutral"
    return "pill"
}

const label = (value) => (value ? value.replaceAll("_", " ").toLowerCase() : "—")

const columns = [
    { key: "created_at", header: "When", render: (r) => <span className="cell-nowrap">{formatDateTime(r.created_at)}</span> },
    {
        key: "user",
        header: "User",
        render: (r) =>
            r.user_name || r.user_email ? (
                <div className="cell-stack">
                    <strong>{r.user_name ?? "—"}</strong>
                    <small>{r.user_email}</small>
                </div>
            ) : (
                "System / unknown"
            ),
    },
    { key: "action", header: "Action", render: (r) => <span className={actionClass(r.action)}>{label(r.action)}</span> },
    { key: "entity", header: "Entity", render: (r) => label(r.entity) },
    { key: "ip_address", header: "IP address" },
]

function AuditDetail({ row, onClose }) {
    return (
        <Modal
            title="Audit entry"
            wide
            onClose={onClose}
            footer={
                <button className="btn btn-ghost" onClick={onClose}>
                    Close
                </button>
            }
        >
            <dl className="detail-grid">
                <dt>When</dt>
                <dd>{formatDateTime(row.created_at)}</dd>
                <dt>User</dt>
                <dd>{row.user_name ? `${row.user_name} (${row.user_email})` : "System / unknown"}</dd>
                <dt>Action</dt>
                <dd>{label(row.action)}</dd>
                <dt>Entity</dt>
                <dd>
                    {label(row.entity)}
                    {row.entity_id ? ` — ${row.entity_id}` : ""}
                </dd>
                <dt>IP address</dt>
                <dd>{row.ip_address ?? "—"}</dd>
            </dl>
            <pre className="detail-json">{row.details ? JSON.stringify(row.details, null, 2) : "No extra details recorded."}</pre>
        </Modal>
    )
}

export default function AuditLogsPage() {
    const { user } = useAuth()

    if (user?.role !== "ADMIN") {
        return (
            <PageShell title="Audit logs" subtitle="Who did what, and when.">
                <div className="table-wrap">
                    <div className="table-state">Only administrators can view audit logs.</div>
                </div>
            </PageShell>
        )
    }

    return (
        <LedgerPage
            title="Audit logs"
            subtitle="Who did what, and when."
            plural="audit entries"
            api={auditLogsApi}
            columns={columns}
            filters={filters}
            searchPlaceholder="Search user, action, entity, IP…"
            Detail={AuditDetail}
        />
    )
}