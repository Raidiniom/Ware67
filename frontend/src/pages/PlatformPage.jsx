import { useCallback, useEffect, useState } from "react"

import { approveKey, listAllKeys, listExpiringKeys, rejectKey, revokeAnyKey } from "../api/apiKeys"
import { listCompanies, setCompanyActive } from "../api/platform"
import { errorMessage } from "../api/resources"
import { useAuth } from "../context/AuthContext"
import PageShell from "../components/PageShell"
import DataTable from "../components/DataTable"
import Pagination from "../components/Pagination"
import Modal, { ConfirmDialog } from "../components/Modal"
import { KeyStatus, ScopeList, ScopePicker } from "../components/ApiKeyParts"
import { formatDateTime } from "../utils/format"

import "./styles/common.css"
import "../components/styles/Resource.css"
import "../components/styles/Ledger.css"

const PAGE_SIZE = 50
const REVOCABLE = ["PENDING", "APPROVED", "ACTIVE"]
const STATUS_FILTERS = ["", "PENDING", "APPROVED", "ACTIVE", "REJECTED", "REVOKED", "LAPSED"]

// Loads one list and reloads it on demand; shared by every tab.
function useList(load) {
    const [rows, setRows] = useState([])
    const [total, setTotal] = useState(0)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState("")

    const reload = useCallback(async () => {
        setLoading(true)
        setError("")
        try {
            const data = await load()
            setRows(data.items)
            setTotal(data.total)
        } catch (err) {
            setError(errorMessage(err))
        } finally {
            setLoading(false)
        }
    }, [load])

    useEffect(() => {
        const timer = setTimeout(() => reload(), 0)
        return () => clearTimeout(timer)
    }, [reload])

    return { rows, total, loading, error, reload }
}

const companyColumn = {
    key: "company_name",
    header: "Company",
    render: (k) => <strong>{k.company_name}</strong>,
}

const keyNameColumn = {
    key: "name",
    header: "Key",
    render: (k) => (
        <div className="cell-stack">
            <strong>{k.name}</strong>
            {k.purpose && <small>{k.purpose}</small>}
        </div>
    ),
}

// --- review dialogs -------------------------------------------------------

function ApproveDialog({ apiKey, onDone, onCancel }) {
    const [scopes, setScopes] = useState(apiKey.requested_scopes)
    const [error, setError] = useState("")
    const [busy, setBusy] = useState(false)

    async function approve() {
        if (scopes.length === 0) {
            setError("Grant at least one kind of access, or reject the request instead.")
            return
        }
        setBusy(true)
        setError("")
        try {
            await approveKey(apiKey.id, scopes)
            onDone("Request approved")
        } catch (err) {
            setError(errorMessage(err))
            setBusy(false)
        }
    }

    return (
        <Modal
            title={`Approve "${apiKey.name}"`}
            onClose={busy ? () => {} : onCancel}
            footer={
                <>
                    <button className="btn btn-ghost" onClick={onCancel} disabled={busy}>Cancel</button>
                    <button className="btn btn-primary" onClick={approve} disabled={busy}>
                        {busy ? "Approving…" : "Approve"}
                    </button>
                </>
            }
        >
            {error && <div className="form-error" style={{ marginBottom: 12 }}>{error}</div>}
            <p>
                <strong>{apiKey.company_name}</strong> asked for this key.
                {apiKey.purpose && <> Purpose: <em>{apiKey.purpose}</em></>}
            </p>
            <ScopePicker value={scopes} onChange={setScopes} allowed={apiKey.requested_scopes} />
            <p className="muted">
                Untick anything they don&apos;t need. They then have 7 days to reveal the key; you&apos;ll never see it.
            </p>
        </Modal>
    )
}

function RejectDialog({ apiKey, onDone, onCancel }) {
    const [reason, setReason] = useState("")
    const [error, setError] = useState("")
    const [busy, setBusy] = useState(false)

    async function reject(e) {
        e.preventDefault()
        setBusy(true)
        setError("")
        try {
            await rejectKey(apiKey.id, reason)
            onDone("Request rejected")
        } catch (err) {
            setError(errorMessage(err))
            setBusy(false)
        }
    }

    return (
        <Modal
            title={`Reject "${apiKey.name}"`}
            onClose={busy ? () => {} : onCancel}
            footer={
                <>
                    <button className="btn btn-ghost" onClick={onCancel} disabled={busy}>Cancel</button>
                    <button type="submit" form="reject-key-form" className="btn btn-danger-solid" disabled={busy}>
                        {busy ? "Rejecting…" : "Reject"}
                    </button>
                </>
            }
        >
            <form id="reject-key-form" className="record-form" onSubmit={reject}>
                {error && <div className="form-error">{error}</div>}
                <label className="field">
                    <span>Reason *</span>
                    <textarea
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                        rows={3}
                        maxLength={1000}
                        required
                        placeholder="Shown to the company, e.g. Please request read-only access first."
                    />
                </label>
            </form>
        </Modal>
    )
}

function RevokeKeyDialog({ apiKey, onDone, onCancel }) {
    const [busy, setBusy] = useState(false)
    const [error, setError] = useState("")

    async function revoke() {
        setBusy(true)
        setError("")
        try {
            await revokeAnyKey(apiKey.id)
            onDone("Key revoked")
        } catch (err) {
            setError(errorMessage(err))
            setBusy(false)
        }
    }

    return (
        <ConfirmDialog title="Revoke key" confirmLabel="Revoke" busy={busy} error={error}
            onConfirm={revoke} onCancel={onCancel}>
            <strong>{apiKey.name}</strong> ({apiKey.company_name}) will stop working immediately. This can&apos;t be
            undone; the company would have to request a new key.
        </ConfirmDialog>
    )
}

// --- tabs -----------------------------------------------------------------

function RequestsTab({ onChanged, notify }) {
    const load = useCallback(() => listAllKeys({ status: "PENDING", limit: 200 }), [])
    const { rows, loading, error, reload } = useList(load)
    const [approving, setApproving] = useState(null)
    const [rejecting, setRejecting] = useState(null)

    function done(message) {
        setApproving(null)
        setRejecting(null)
        notify(message)
        reload()
        onChanged()
    }

    const columns = [
        companyColumn,
        keyNameColumn,
        { key: "requested_scopes", header: "Asked for", render: (k) => <ScopeList scopes={k.requested_scopes} /> },
        { key: "created_at", header: "Requested", render: (k) => formatDateTime(k.created_at) },
    ]

    return (
        <>
            <DataTable
                columns={columns}
                rows={rows}
                loading={loading}
                error={error}
                empty="No requests waiting. All caught up."
                renderActions={(k) => (
                    <div className="row-actions">
                        <button className="btn btn-primary btn-sm" type="button" onClick={() => setApproving(k)}>
                            Approve
                        </button>
                        <button className="btn btn-ghost btn-sm" type="button" onClick={() => setRejecting(k)}>
                            Reject
                        </button>
                    </div>
                )}
            />
            {approving && <ApproveDialog apiKey={approving} onDone={done} onCancel={() => setApproving(null)} />}
            {rejecting && <RejectDialog apiKey={rejecting} onDone={done} onCancel={() => setRejecting(null)} />}
        </>
    )
}

function AllKeysTab({ notify }) {
    const [status, setStatus] = useState("")
    const [skip, setSkip] = useState(0)
    const load = useCallback(() => listAllKeys({ status, skip, limit: PAGE_SIZE }), [status, skip])
    const { rows, total, loading, error, reload } = useList(load)
    const [revoking, setRevoking] = useState(null)

    const columns = [
        companyColumn,
        keyNameColumn,
        { key: "status", header: "Status", render: (k) => <KeyStatus apiKey={k} /> },
        { key: "scopes", header: "Access", render: (k) => <ScopeList scopes={k.scopes || k.requested_scopes} /> },
        { key: "key_prefix", header: "Key starts with", render: (k) => (k.key_prefix ? <code>{k.key_prefix}_…</code> : "—") },
        { key: "last_used_at", header: "Last used", render: (k) => formatDateTime(k.last_used_at) },
    ]

    return (
        <>
            <div className="toolbar">
                <select
                    value={status}
                    aria-label="Filter by status"
                    onChange={(e) => {
                        setStatus(e.target.value)
                        setSkip(0)
                    }}
                >
                    {STATUS_FILTERS.map((s) => (
                        <option key={s} value={s}>{s ? s.charAt(0) + s.slice(1).toLowerCase() : "All statuses"}</option>
                    ))}
                </select>
            </div>
            <DataTable
                columns={columns}
                rows={rows}
                loading={loading}
                error={error}
                empty="No keys match."
                renderActions={(k) =>
                    REVOCABLE.includes(k.status) && (
                        <div className="row-actions">
                            <button className="btn btn-danger btn-sm" type="button" onClick={() => setRevoking(k)}>
                                Revoke
                            </button>
                        </div>
                    )
                }
            />
            <Pagination skip={skip} limit={PAGE_SIZE} total={total} onChange={setSkip} />
            {revoking && (
                <RevokeKeyDialog
                    apiKey={revoking}
                    onCancel={() => setRevoking(null)}
                    onDone={(message) => {
                        setRevoking(null)
                        notify(message)
                        reload()
                    }}
                />
            )}
        </>
    )
}

function daysLeft(value) {
    const ms = new Date(value).getTime() - Date.now()
    const days = Math.max(0, Math.ceil(ms / 86_400_000))
    return days === 1 ? "1 day" : `${days} days`
}

function ExpiringTab({ notify }) {
    const [days, setDays] = useState(14)
    const load = useCallback(() => listExpiringKeys(days), [days])
    const { rows, loading, error, reload } = useList(load)
    const [revoking, setRevoking] = useState(null)

    const columns = [
        companyColumn,
        keyNameColumn,
        {
            key: "expires_at",
            header: "Expires",
            render: (k) => (
                <div className="cell-stack">
                    <strong>in {daysLeft(k.expires_at)}</strong>
                    <small>{formatDateTime(k.expires_at)}</small>
                </div>
            ),
        },
        { key: "key_prefix", header: "Key starts with", render: (k) => <code>{k.key_prefix}_…</code> },
        { key: "last_used_at", header: "Last used", render: (k) => formatDateTime(k.last_used_at) },
    ]

    return (
        <>
            <div className="toolbar">
                <select value={days} aria-label="Expiring within" onChange={(e) => setDays(Number(e.target.value))}>
                    {[7, 14, 30, 60].map((d) => (
                        <option key={d} value={d}>Expiring within {d} days</option>
                    ))}
                </select>
                <span className="muted">Remind these companies to request a replacement key.</span>
            </div>
            <DataTable
                columns={columns}
                rows={rows}
                loading={loading}
                error={error}
                empty="No keys expire in this window."
                renderActions={(k) => (
                    <div className="row-actions">
                        <button className="btn btn-danger btn-sm" type="button" onClick={() => setRevoking(k)}>
                            Revoke
                        </button>
                    </div>
                )}
            />
            {revoking && (
                <RevokeKeyDialog
                    apiKey={revoking}
                    onCancel={() => setRevoking(null)}
                    onDone={(message) => {
                        setRevoking(null)
                        notify(message)
                        reload()
                    }}
                />
            )}
        </>
    )
}

function CompaniesTab({ notify }) {
    const [search, setSearch] = useState("")
    const [query, setQuery] = useState("")
    const [skip, setSkip] = useState(0)
    const load = useCallback(() => listCompanies({ search: query, skip, limit: PAGE_SIZE }), [query, skip])
    const { rows, total, loading, error, reload } = useList(load)
    const [changing, setChanging] = useState(null)
    const [busy, setBusy] = useState(false)
    const [changeError, setChangeError] = useState("")

    // Search after typing stops, not on every keystroke.
    useEffect(() => {
        const t = setTimeout(() => {
            setQuery(search.trim())
            setSkip(0)
        }, 300)
        return () => clearTimeout(t)
    }, [search])

    async function confirmChange() {
        setBusy(true)
        setChangeError("")
        try {
            await setCompanyActive(changing.id, !changing.is_active)
            notify(changing.is_active ? "Company deactivated" : "Company reactivated")
            setChanging(null)
            reload()
        } catch (err) {
            setChangeError(errorMessage(err))
        } finally {
            setBusy(false)
        }
    }

    const columns = [
        { key: "name", header: "Company", render: (c) => <strong>{c.name}</strong> },
        { key: "member_count", header: "Members" },
        {
            key: "is_active",
            header: "Status",
            render: (c) => (
                <span className={`pill ${c.is_active ? "pill--in" : "pill--danger"}`}>
                    {c.is_active ? "Active" : "Deactivated"}
                </span>
            ),
        },
        { key: "created_at", header: "Signed up", render: (c) => formatDateTime(c.created_at) },
    ]

    return (
        <>
            <div className="toolbar">
                <input
                    type="search"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search companies…"
                    aria-label="Search companies"
                />
            </div>
            <DataTable
                columns={columns}
                rows={rows}
                loading={loading}
                error={error}
                empty="No companies found."
                renderActions={(c) => (
                    <div className="row-actions">
                        <button
                            className={`btn btn-sm ${c.is_active ? "btn-danger" : "btn-ghost"}`}
                            type="button"
                            onClick={() => setChanging(c)}
                        >
                            {c.is_active ? "Deactivate" : "Reactivate"}
                        </button>
                    </div>
                )}
            />
            <Pagination skip={skip} limit={PAGE_SIZE} total={total} onChange={setSkip} />
            {changing && (
                <ConfirmDialog
                    title={changing.is_active ? "Deactivate company" : "Reactivate company"}
                    confirmLabel={changing.is_active ? "Deactivate" : "Reactivate"}
                    busy={busy}
                    error={changeError}
                    onConfirm={confirmChange}
                    onCancel={() => {
                        setChanging(null)
                        setChangeError("")
                    }}
                >
                    {changing.is_active ? (
                        <>
                            <strong>{changing.name}</strong>&apos;s {changing.member_count} members won&apos;t be able
                            to sign in and its API keys stop working immediately. Its data is kept, and you can
                            reactivate it later.
                        </>
                    ) : (
                        <>
                            <strong>{changing.name}</strong>&apos;s members can sign in again and its unexpired API keys
                            work again.
                        </>
                    )}
                </ConfirmDialog>
            )}
        </>
    )
}

// --- page -----------------------------------------------------------------

const TABS = [
    { key: "requests", label: "Key requests" },
    { key: "keys", label: "All keys" },
    { key: "expiring", label: "Expiring soon" },
    { key: "companies", label: "Companies" },
]

function Console() {
    const [tab, setTab] = useState("requests")
    const [pending, setPending] = useState(null)
    const [toast, setToast] = useState("")

    const loadPending = useCallback(async () => {
        try {
            setPending((await listAllKeys({ status: "PENDING", limit: 1 })).total)
        } catch {
            setPending(null)
        }
    }, [])

    useEffect(() => {
        const timer = setTimeout(() => loadPending(), 0)
        return () => clearTimeout(timer)
    }, [loadPending])

    useEffect(() => {
        if (!toast) return
        const t = setTimeout(() => setToast(""), 3000)
        return () => clearTimeout(t)
    }, [toast])

    return (
        <PageShell
            title="Platform console"
            subtitle="Review API key requests and manage companies. Company inventory is never visible here."
        >
            <nav className="tabs" aria-label="Platform sections">
                {TABS.map((t) => (
                    <button
                        key={t.key}
                        type="button"
                        className={`tab${tab === t.key ? " tab--active" : ""}`}
                        onClick={() => setTab(t.key)}
                    >
                        {t.label}
                        {t.key === "requests" && pending ? <span>{pending}</span> : null}
                    </button>
                ))}
            </nav>

            {tab === "requests" && <RequestsTab notify={setToast} onChanged={loadPending} />}
            {tab === "keys" && <AllKeysTab notify={setToast} />}
            {tab === "expiring" && <ExpiringTab notify={setToast} />}
            {tab === "companies" && <CompaniesTab notify={setToast} />}

            {toast && (
                <div className="toast" role="status">
                    {toast}
                </div>
            )}
        </PageShell>
    )
}

export default function PlatformPage() {
    const { user } = useAuth()

    if (!user?.is_platform_admin) {
        return (
            <PageShell title="Platform console" subtitle="For the WARE67 team.">
                <div className="table-wrap">
                    <div className="table-state">Only the WARE67 platform team can open this page.</div>
                </div>
            </PageShell>
        )
    }

    return <Console />
}
