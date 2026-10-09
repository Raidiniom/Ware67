import { useCallback, useEffect, useRef, useState } from "react"

import { listCompanyKeys, requestKey, revealKey, revokeCompanyKey } from "../api/apiKeys"
import { errorMessage } from "../api/resources"
import { useAuth } from "../context/AuthContext"
import PageShell from "../components/PageShell"
import DataTable from "../components/DataTable"
import Modal, { ConfirmDialog } from "../components/Modal"
import { KeyStatus, ScopeList, ScopePicker } from "../components/ApiKeyParts"
import { formatDateTime } from "../utils/format"

import "./styles/common.css"
import "../components/styles/Resource.css"
import "../components/styles/Ledger.css"

const KEY_MANAGERS = ["OWNER", "ADMIN"]

function RequestKeyForm({ onSaved, onCancel }) {
    const [form, setForm] = useState({ name: "", purpose: "", scopes: ["products:read"] })
    const [error, setError] = useState("")
    const [saving, setSaving] = useState(false)

    async function handleSubmit(e) {
        e.preventDefault()
        if (form.scopes.length === 0) {
            setError("Choose at least one kind of access.")
            return
        }
        setError("")
        setSaving(true)
        try {
            await requestKey(form)
            onSaved()
        } catch (err) {
            setError(errorMessage(err))
            setSaving(false)
        }
    }

    return (
        <Modal
            title="Request an API key"
            onClose={saving ? () => {} : onCancel}
            footer={
                <>
                    <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={saving}>
                        Cancel
                    </button>
                    <button type="submit" form="request-key-form" className="btn btn-primary" disabled={saving}>
                        {saving ? "Sending…" : "Send request"}
                    </button>
                </>
            }
        >
            <form id="request-key-form" className="record-form" onSubmit={handleSubmit}>
                {error && <div className="form-error">{error}</div>}
                <p className="muted">
                    The WARE67 team reviews every request. Once it&apos;s approved you&apos;ll reveal the key here, once.
                </p>
                <label className="field">
                    <span>Name *</span>
                    <input
                        value={form.name}
                        onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                        maxLength={150}
                        required
                        placeholder="e.g. Online shop sync"
                    />
                </label>
                <label className="field">
                    <span>What will it be used for?</span>
                    <textarea
                        value={form.purpose}
                        onChange={(e) => setForm((f) => ({ ...f, purpose: e.target.value }))}
                        maxLength={1000}
                        rows={3}
                        placeholder="Helps the WARE67 team approve it quickly"
                    />
                </label>
                <ScopePicker value={form.scopes} onChange={(scopes) => setForm((f) => ({ ...f, scopes }))} />
                <small className="field-hint">Ask only for the access the integration needs.</small>
            </form>
        </Modal>
    )
}

// Confirm -> reveal -> show once. The dialog can't be dismissed while the key
// is on screen until the user confirms they've stored it.
function RevealDialog({ apiKey, onDone, onCancel }) {
    const [phase, setPhase] = useState("confirm") // confirm | revealing | shown
    const [rawKey, setRawKey] = useState("")
    const [error, setError] = useState("")
    const [copied, setCopied] = useState(false)
    const [stored, setStored] = useState(false)
    const inputRef = useRef(null)

    async function reveal() {
        setError("")
        setPhase("revealing")
        try {
            const result = await revealKey(apiKey.id)
            setRawKey(result.api_key)
            setPhase("shown")
        } catch (err) {
            setError(errorMessage(err))
            setPhase("confirm")
        }
    }

    async function copy() {
        try {
            await navigator.clipboard.writeText(rawKey)
            setCopied(true)
        } catch {
            // Clipboard can be blocked (e.g. plain http); select it for Ctrl+C instead.
            inputRef.current?.select()
        }
    }

    function finish() {
        setRawKey("")
        onDone()
    }

    if (phase !== "shown") {
        return (
            <Modal
                title={`Reveal "${apiKey.name}"`}
                onClose={phase === "revealing" ? () => {} : onCancel}
                footer={
                    <>
                        <button className="btn btn-ghost" onClick={onCancel} disabled={phase === "revealing"}>
                            Not now
                        </button>
                        <button className="btn btn-primary" onClick={reveal} disabled={phase === "revealing"}>
                            {phase === "revealing" ? "Revealing…" : "Reveal key"}
                        </button>
                    </>
                }
            >
                {error && <div className="form-error" style={{ marginBottom: 12 }}>{error}</div>}
                <p>
                    The key will be shown <strong>once</strong>. Nobody, including the WARE67 team, can show it
                    again. Have your project&apos;s environment settings or password manager open before you continue.
                </p>
                <p className="muted">It will work for 90 days from now.</p>
            </Modal>
        )
    }

    return (
        <Modal
            title="Your API key"
            onClose={stored ? finish : () => {}}
            footer={
                <button className="btn btn-primary" onClick={finish} disabled={!stored}>
                    Done
                </button>
            }
        >
            <p>
                Copy this key now and keep it on your server only (an environment variable or secrets manager).
                Never put it in browser or mobile app code.
            </p>
            <div className="revealed-key">
                <input
                    ref={inputRef}
                    readOnly
                    value={rawKey}
                    aria-label="API key"
                    onFocus={(e) => e.target.select()}
                />
                <button className="btn btn-outline" type="button" onClick={copy}>
                    {copied ? "Copied" : "Copy"}
                </button>
            </div>
            <label className="check" style={{ marginTop: 16 }}>
                <input type="checkbox" checked={stored} onChange={(e) => setStored(e.target.checked)} />
                I&apos;ve stored this key somewhere safe. I understand it won&apos;t be shown again.
            </label>
        </Modal>
    )
}

function KeysManager() {
    const [keys, setKeys] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState("")
    const [requesting, setRequesting] = useState(false)
    const [revealing, setRevealing] = useState(null)
    const [revoking, setRevoking] = useState(null)
    const [revokeBusy, setRevokeBusy] = useState(false)
    const [revokeError, setRevokeError] = useState("")
    const [toast, setToast] = useState("")

    const loadData = useCallback(async () => {
        setLoading(true)
        setError("")
        try {
            setKeys((await listCompanyKeys()).items)
        } catch (err) {
            setError(errorMessage(err, "Couldn't load your API keys."))
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        const timer = setTimeout(() => loadData(), 0)
        return () => clearTimeout(timer)
    }, [loadData])

    useEffect(() => {
        if (!toast) return
        const t = setTimeout(() => setToast(""), 3000)
        return () => clearTimeout(t)
    }, [toast])

    async function confirmRevoke() {
        setRevokeBusy(true)
        setRevokeError("")
        try {
            await revokeCompanyKey(revoking.id)
            setToast(revoking.status === "ACTIVE" ? "Key revoked" : "Request withdrawn")
            setRevoking(null)
            loadData()
        } catch (err) {
            setRevokeError(errorMessage(err))
        } finally {
            setRevokeBusy(false)
        }
    }

    const columns = [
        {
            key: "name",
            header: "Key",
            render: (k) => (
                <div className="cell-stack">
                    <strong>{k.name}</strong>
                    {k.purpose && <small>{k.purpose}</small>}
                </div>
            ),
        },
        { key: "status", header: "Status", render: (k) => <KeyStatus apiKey={k} /> },
        {
            key: "scopes",
            header: "Access",
            render: (k) => <ScopeList scopes={k.scopes || k.requested_scopes} />,
        },
        {
            key: "key_prefix",
            header: "Key starts with",
            render: (k) => (k.key_prefix ? <code>{k.key_prefix}_…</code> : "—"),
        },
        { key: "last_used_at", header: "Last used", render: (k) => formatDateTime(k.last_used_at) },
    ]

    return (
        <PageShell
            title="API keys"
            subtitle="Let your other systems read and update your products. Each key only sees your company's data."
            actions={
                <button className="btn btn-primary" type="button" onClick={() => setRequesting(true)}>
                    + Request key
                </button>
            }
        >
            {error && (
                <div className="page-alert" role="alert">
                    {error}
                </div>
            )}

            <DataTable
                columns={columns}
                rows={keys}
                loading={loading}
                empty="No API keys yet. Request one to connect another system."
                renderActions={(k) => (
                    <div className="row-actions">
                        {k.status === "APPROVED" && (
                            <button className="btn btn-primary btn-sm" type="button" onClick={() => setRevealing(k)}>
                                Reveal key
                            </button>
                        )}
                        {(k.status === "PENDING" || k.status === "APPROVED") && (
                            <button className="btn btn-ghost btn-sm" type="button" onClick={() => setRevoking(k)}>
                                Withdraw
                            </button>
                        )}
                        {k.status === "ACTIVE" && (
                            <button className="btn btn-danger btn-sm" type="button" onClick={() => setRevoking(k)}>
                                Revoke
                            </button>
                        )}
                    </div>
                )}
            />

            {requesting && (
                <RequestKeyForm
                    onCancel={() => setRequesting(false)}
                    onSaved={() => {
                        setRequesting(false)
                        setToast("Request sent to the WARE67 team")
                        loadData()
                    }}
                />
            )}

            {revealing && (
                <RevealDialog
                    apiKey={revealing}
                    onCancel={() => setRevealing(null)}
                    onDone={() => {
                        setRevealing(null)
                        loadData()
                    }}
                />
            )}

            {revoking && (
                <ConfirmDialog
                    title={revoking.status === "ACTIVE" ? "Revoke key" : "Withdraw request"}
                    confirmLabel={revoking.status === "ACTIVE" ? "Revoke" : "Withdraw"}
                    busy={revokeBusy}
                    error={revokeError}
                    onConfirm={confirmRevoke}
                    onCancel={() => {
                        setRevoking(null)
                        setRevokeError("")
                    }}
                >
                    {revoking.status === "ACTIVE" ? (
                        <>
                            <strong>{revoking.name}</strong> will stop working immediately. Anything using it will get
                            errors until you give it a new key. This can&apos;t be undone.
                        </>
                    ) : (
                        <>
                            The request for <strong>{revoking.name}</strong> will be withdrawn. You can request a new
                            key at any time.
                        </>
                    )}
                </ConfirmDialog>
            )}

            {toast && (
                <div className="toast" role="status">
                    {toast}
                </div>
            )}
        </PageShell>
    )
}

export default function ApiKeysPage() {
    const { user } = useAuth()

    if (!user || !KEY_MANAGERS.includes(user.role) || user.is_platform_admin) {
        return (
            <PageShell title="API keys" subtitle="Connect your other systems to WARE67.">
                <div className="table-wrap">
                    <div className="table-state">Only your company&apos;s owners and administrators can manage API keys.</div>
                </div>
            </PageShell>
        )
    }

    return <KeysManager />
}
