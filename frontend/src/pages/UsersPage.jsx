import { useCallback, useEffect, useState } from "react"

import {
    createManagedUser,
    listManagedUsers,
    listRoles,
    updateManagedUser,
} from "../api/management"
import { errorMessage } from "../api/resources"
import { useAuth } from "../context/AuthContext"
import PageShell from "../components/PageShell"
import DataTable from "../components/DataTable"
import Modal, { ConfirmDialog } from "../components/Modal"
import "./styles/common.css"
import "../components/styles/Resource.css"
import "../components/styles/Ledger.css"
import "./styles/UsersPage.css"

const ROLES = ["GUEST", "STAFF", "MANAGER", "ADMIN", "OWNER"]
const USER_MANAGERS = ["OWNER", "ADMIN", "MANAGER"]
const EMPTY_FORM = { name: "", email: "", password: "", role: "GUEST", is_active: true }

// Mirrors backend/app/services/user_permissions.py: owners hand out any role,
// admins any but owner, managers only staff and guest.
function assignableRoles(actorRole) {
    if (actorRole === "OWNER") return ROLES
    if (actorRole === "ADMIN") return ROLES.filter((role) => role !== "OWNER")
    return ["GUEST", "STAFF"]
}

// Who may change whose account: owners anyone, admins anyone but owners,
// managers only staff and guests.
function canManage(actorRole, targetRole) {
    if (actorRole === "OWNER") return true
    if (actorRole === "ADMIN") return targetRole !== "OWNER"
    return targetRole === "GUEST" || targetRole === "STAFF"
}

function UserForm({ actorRole, onSaved, onCancel }) {
    const [form, setForm] = useState(EMPTY_FORM)
    const [error, setError] = useState("")
    const [saving, setSaving] = useState(false)

    const set = (name) => (e) =>
        setForm((f) => ({ ...f, [name]: name === "is_active" ? e.target.checked : e.target.value }))

    async function handleSubmit(e) {
        e.preventDefault()
        setError("")
        setSaving(true)
        try {
            await createManagedUser(form)
            onSaved()
        } catch (err) {
            setError(errorMessage(err))
            setSaving(false)
        }
    }

    return (
        <Modal
            title="New account"
            onClose={saving ? () => {} : onCancel}
            footer={
                <>
                    <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={saving}>
                        Cancel
                    </button>
                    <button type="submit" form="user-form" className="btn btn-primary" disabled={saving}>
                        {saving ? "Creating…" : "Create account"}
                    </button>
                </>
            }
        >
            <form id="user-form" className="record-form" onSubmit={handleSubmit}>
                {error && <div className="form-error">{error}</div>}

                <label className="field">
                    <span>Full name *</span>
                    <input value={form.name} onChange={set("name")} maxLength={150} required autoComplete="off" />
                </label>
                <label className="field">
                    <span>Email *</span>
                    <input type="email" value={form.email} onChange={set("email")} required autoComplete="off" />
                </label>
                <label className="field field--half">
                    <span>Temporary password *</span>
                    <input
                        type="password"
                        value={form.password}
                        onChange={set("password")}
                        minLength={8}
                        maxLength={128}
                        required
                        autoComplete="new-password"
                    />
                </label>
                <label className="field field--half">
                    <span>Role</span>
                    <select value={form.role} onChange={set("role")}>
                        {assignableRoles(actorRole).map((role) => (
                            <option key={role} value={role}>
                                {role}
                            </option>
                        ))}
                    </select>
                </label>
                <label className="check">
                    <input type="checkbox" checked={form.is_active} onChange={set("is_active")} />
                    Active account — can sign in immediately
                </label>
            </form>
        </Modal>
    )
}

function ResetPasswordForm({ user, onSaved, onCancel }) {
    const [password, setPassword] = useState("")
    const [confirm, setConfirm] = useState("")
    const [error, setError] = useState("")
    const [saving, setSaving] = useState(false)

    async function handleSubmit(e) {
        e.preventDefault()
        if (password !== confirm) {
            setError("Passwords do not match.")
            return
        }
        setError("")
        setSaving(true)
        try {
            await updateManagedUser(user.id, { password })
            onSaved()
        } catch (err) {
            setError(errorMessage(err))
            setSaving(false)
        }
    }

    return (
        <Modal
            title={`Reset password for ${user.name}`}
            onClose={saving ? () => {} : onCancel}
            footer={
                <>
                    <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={saving}>
                        Cancel
                    </button>
                    <button type="submit" form="reset-password-form" className="btn btn-primary" disabled={saving}>
                        {saving ? "Saving…" : "Set password"}
                    </button>
                </>
            }
        >
            <form id="reset-password-form" className="record-form" onSubmit={handleSubmit}>
                {error && <div className="form-error">{error}</div>}
                <p className="muted">
                    Share this temporary password with {user.email} through a channel you trust.
                </p>
                <label className="field field--half">
                    <span>Temporary password *</span>
                    <input
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        minLength={8}
                        maxLength={128}
                        required
                        autoComplete="new-password"
                    />
                </label>
                <label className="field field--half">
                    <span>Confirm *</span>
                    <input
                        type="password"
                        value={confirm}
                        onChange={(e) => setConfirm(e.target.value)}
                        minLength={8}
                        maxLength={128}
                        required
                        autoComplete="new-password"
                    />
                </label>
            </form>
        </Modal>
    )
}

// Role descriptions are shared by every company, so only the WARE67 platform
// team can edit them; companies see them read-only.
function RoleCard({ role }) {
    return (
        <article className="role-card">
            <div className="role-card-heading">
                <span className={`role-mark role-mark--${role.name.toLowerCase()}`}>{role.name.slice(0, 1)}</span>
                <div>
                    <h2>{role.name}</h2>
                    <p>System permission level</p>
                </div>
            </div>
            <textarea
                value={role.description || ""}
                disabled
                rows={3}
                aria-label={`${role.name} description`}
            />
            <div className="role-card-footer">
                <span>Role descriptions are managed by the WARE67 team.</span>
            </div>
        </article>
    )
}

function UsersManager({ actorRole, currentUserId }) {
    const [activeTab, setActiveTab] = useState("users")
    const [users, setUsers] = useState([])
    const [roles, setRoles] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState("")
    const [creating, setCreating] = useState(false)
    const [deactivating, setDeactivating] = useState(null)
    const [deactivateBusy, setDeactivateBusy] = useState(false)
    const [resetting, setResetting] = useState(null)
    const [toast, setToast] = useState("")

    const loadData = useCallback(async () => {
        setLoading(true)
        setError("")
        try {
            const [userData, roleData] = await Promise.all([listManagedUsers(), listRoles()])
            setUsers(userData)
            setRoles(roleData)
        } catch (err) {
            setError(errorMessage(err, "Couldn't load users."))
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

    async function changeUser(userId, payload, message) {
        setError("")
        try {
            await updateManagedUser(userId, payload)
            setToast(message)
            await loadData()
            return true
        } catch (err) {
            setError(errorMessage(err))
            return false
        }
    }

    async function confirmDeactivate() {
        setDeactivateBusy(true)
        await changeUser(deactivating.id, { is_active: false }, "Account deactivated")
        setDeactivateBusy(false)
        setDeactivating(null)
    }

    const options = assignableRoles(actorRole)

    const columns = [
        {
            key: "account",
            header: "Account",
            render: (u) => (
                <div className="cell-stack">
                    <strong>
                        {u.name}
                        {u.id === currentUserId && <span className="badge">You</span>}
                    </strong>
                    <small>{u.email}</small>
                </div>
            ),
        },
        {
            key: "role",
            header: "Role",
            render: (u) => {
                const locked = !canManage(actorRole, u.role)
                return (
                    <select
                        className="role-select"
                        value={u.role}
                        disabled={locked}
                        aria-label={`Role for ${u.name}`}
                        onChange={(e) => changeUser(u.id, { role: e.target.value }, "Role updated")}
                    >
                        {(locked ? [u.role] : options).map((role) => (
                            <option key={role} value={role}>
                                {role}
                            </option>
                        ))}
                    </select>
                )
            },
        },
        {
            key: "is_active",
            header: "Status",
            render: (u) => (
                <span className={`pill ${u.is_active ? "pill--in" : "pill--danger"}`}>
                    {u.is_active ? "Active" : "Inactive"}
                </span>
            ),
        },
    ]

    return (
        <PageShell
            title="Users & roles"
            subtitle="Control warehouse access without losing track of who can do what."
            actions={
                activeTab === "users" && (
                    <button className="btn btn-primary" type="button" onClick={() => setCreating(true)}>
                        + New user
                    </button>
                )
            }
        >
            <nav className="tabs" aria-label="User management sections">
                <button
                    type="button"
                    className={`tab${activeTab === "users" ? " tab--active" : ""}`}
                    onClick={() => setActiveTab("users")}
                >
                    Users <span>{users.length}</span>
                </button>
                <button
                    type="button"
                    className={`tab${activeTab === "roles" ? " tab--active" : ""}`}
                    onClick={() => setActiveTab("roles")}
                >
                    Roles <span>{roles.length}</span>
                </button>
            </nav>

            {error && (
                <div className="page-alert" role="alert">
                    {error}
                </div>
            )}

            {activeTab === "users" ? (
                <DataTable
                    columns={columns}
                    rows={users}
                    loading={loading}
                    empty="No users yet."
                    renderActions={(u) => (
                        <div className="row-actions">
                            <button
                                className="btn btn-ghost btn-sm"
                                type="button"
                                disabled={!canManage(actorRole, u.role)}
                                onClick={() => setResetting(u)}
                            >
                                Reset password
                            </button>
                            {u.is_active ? (
                                <button
                                    className="btn btn-danger btn-sm"
                                    type="button"
                                    disabled={u.id === currentUserId || !canManage(actorRole, u.role)}
                                    onClick={() => setDeactivating(u)}
                                >
                                    Deactivate
                                </button>
                            ) : (
                                <button
                                    className="btn btn-ghost btn-sm"
                                    type="button"
                                    disabled={!canManage(actorRole, u.role)}
                                    onClick={() => changeUser(u.id, { is_active: true }, "Account activated")}
                                >
                                    Activate
                                </button>
                            )}
                        </div>
                    )}
                />
            ) : loading ? (
                <div className="table-wrap">
                    <div className="table-state">Loading roles…</div>
                </div>
            ) : (
                <section className="roles-grid">
                    {roles.map((role) => (
                        <RoleCard key={role.id} role={role} />
                    ))}
                </section>
            )}

            {creating && (
                <UserForm
                    actorRole={actorRole}
                    onCancel={() => setCreating(false)}
                    onSaved={() => {
                        setCreating(false)
                        setToast("Account created")
                        loadData()
                    }}
                />
            )}

            {resetting && (
                <ResetPasswordForm
                    user={resetting}
                    onCancel={() => setResetting(null)}
                    onSaved={() => {
                        setResetting(null)
                        setToast("Password reset")
                    }}
                />
            )}

            {deactivating && (
                <ConfirmDialog
                    title="Deactivate account"
                    confirmLabel="Deactivate"
                    busy={deactivateBusy}
                    onConfirm={confirmDeactivate}
                    onCancel={() => setDeactivating(null)}
                >
                    <strong>{deactivating.name}</strong> will no longer be able to sign in. You can reactivate the account
                    at any time.
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

export default function UsersPage() {
    const { user } = useAuth()

    if (!user || !USER_MANAGERS.includes(user.role)) {
        return (
            <PageShell title="Users & roles" subtitle="Control warehouse access.">
                <div className="table-wrap">
                    <div className="table-state">Only owners, administrators and managers can manage users.</div>
                </div>
            </PageShell>
        )
    }

    return <UsersManager actorRole={user.role} currentUserId={user.id} />
}