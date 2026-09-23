import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router-dom"

import {
    createManagedUser,
    listManagedUsers,
    listRoles,
    updateManagedUser,
    updateRoleDescription,
} from "../api/management"
import { useAuth } from "../context/AuthContext"
import "./styles/common.css"
import "./styles/UsersPage.css"

const ROLES = ["GUEST", "STAFF", "MANAGER", "ADMIN"]
const EMPTY_FORM = { name: "", email: "", password: "", role: "GUEST", is_active: true }

function getErrorMessage(error) {
    const detail = error?.response?.data?.detail
    if (typeof detail === "string") return detail
    if (Array.isArray(detail)) return detail.map((item) => item.msg).filter(Boolean).join(", ")
    return "Something went wrong. Please try again."
}

export default function UsersPage() {
    const { user } = useAuth()
    const isAdmin = user?.role === "ADMIN"
    const [activeTab, setActiveTab] = useState("users")
    const [users, setUsers] = useState([])
    const [roles, setRoles] = useState([])
    const [form, setForm] = useState(EMPTY_FORM)
    const [showForm, setShowForm] = useState(false)
    const [loading, setLoading] = useState(true)
    const [submitting, setSubmitting] = useState(false)
    const [error, setError] = useState("")

    const loadData = useCallback(async () => {
        setLoading(true)
        setError("")
        try {
            const [userData, roleData] = await Promise.all([listManagedUsers(), listRoles()])
            setUsers(userData)
            setRoles(roleData)
        } catch (requestError) {
            setError(getErrorMessage(requestError))
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        const timer = setTimeout(() => loadData(), 0)
        return () => clearTimeout(timer)
    }, [loadData])

    function updateField(field) {
        return (event) => setForm((current) => ({
            ...current,
            [field]: field === "is_active" ? event.target.checked : event.target.value,
        }))
    }

    function openForm() {
        setForm(EMPTY_FORM)
        setError("")
        setShowForm(true)
    }

    async function handleCreate(event) {
        event.preventDefault()
        setSubmitting(true)
        setError("")
        try {
            await createManagedUser(form)
            setShowForm(false)
            await loadData()
        } catch (requestError) {
            setError(getErrorMessage(requestError))
        } finally {
            setSubmitting(false)
        }
    }

    async function changeUser(userId, payload) {
        setError("")
        try {
            await updateManagedUser(userId, payload)
            await loadData()
        } catch (requestError) {
            setError(getErrorMessage(requestError))
        }
    }

    async function saveRole(role) {
        setError("")
        try {
            const updated = await updateRoleDescription(role.name, role.description || "")
            setRoles((current) => current.map((item) => item.name === updated.name ? updated : item))
        } catch (requestError) {
            setError(getErrorMessage(requestError))
        }
    }

    return (
        <main className="users-page">
            <header className="users-header">
                <div>
                    <Link to="/dashboard" className="users-back">← Dashboard</Link>
                    <h1>Users &amp; roles</h1>
                    <p>Control warehouse access without losing track of who can do what.</p>
                </div>
                {activeTab === "users" && <button className="btn btn-primary" type="button" onClick={openForm}>Add user</button>}
            </header>

            <nav className="users-tabs" aria-label="User management sections">
                <button className={activeTab === "users" ? "users-tab users-tab--active" : "users-tab"} onClick={() => setActiveTab("users")}>Users <span>{users.length}</span></button>
                <button className={activeTab === "roles" ? "users-tab users-tab--active" : "users-tab"} onClick={() => setActiveTab("roles")}>Roles <span>{roles.length}</span></button>
            </nav>

            {error && <div className="users-alert" role="alert">{error}</div>}

            {activeTab === "users" && showForm && (
                <section className="users-form-card">
                    <div className="users-form-heading"><div><h2>New account</h2><p>The user will receive access immediately if active.</p></div><button className="btn btn-ghost" type="button" onClick={() => setShowForm(false)}>Cancel</button></div>
                    <form className="users-form" onSubmit={handleCreate}>
                        <label><span>Full name *</span><input value={form.name} onChange={updateField("name")} required /></label>
                        <label><span>Email *</span><input type="email" value={form.email} onChange={updateField("email")} required /></label>
                        <label><span>Temporary password *</span><input type="password" value={form.password} onChange={updateField("password")} minLength={8} required /></label>
                        <label><span>Role</span><select value={form.role} onChange={updateField("role")}>{ROLES.filter((role) => isAdmin || !["ADMIN", "MANAGER"].includes(role)).map((role) => <option key={role}>{role}</option>)}</select></label>
                        <label className="users-checkbox"><input type="checkbox" checked={form.is_active} onChange={updateField("is_active")} /><span>Active account</span></label>
                        <div className="users-form-actions"><button className="btn btn-primary" disabled={submitting}>{submitting ? "Creating…" : "Create account"}</button></div>
                    </form>
                </section>
            )}

            {loading ? <p className="users-empty">Loading access records…</p> : activeTab === "users" ? (
                <section className="users-table-card"><div className="users-table-wrap"><table className="users-table"><thead><tr><th>Account</th><th>Role</th><th>Status</th><th>Actions</th></tr></thead><tbody>{users.map((managedUser) => <tr key={managedUser.id}><td><strong>{managedUser.name}</strong><small>{managedUser.email}</small></td><td><select value={managedUser.role} disabled={!isAdmin && ["ADMIN", "MANAGER"].includes(managedUser.role)} onChange={(event) => changeUser(managedUser.id, { role: event.target.value })}>{ROLES.filter((role) => isAdmin || !["ADMIN", "MANAGER"].includes(role)).map((role) => <option key={role}>{role}</option>)}</select></td><td><span className={`user-status user-status--${managedUser.is_active ? "active" : "inactive"}`}>{managedUser.is_active ? "Active" : "Inactive"}</span></td><td><button className="btn btn-ghost" type="button" onClick={() => changeUser(managedUser.id, { is_active: !managedUser.is_active })}>{managedUser.is_active ? "Deactivate" : "Activate"}</button></td></tr>)}</tbody></table></div></section>
            ) : (
                <section className="roles-grid">{roles.map((role) => <RoleCard key={role.id} role={role} editable={isAdmin} onSave={saveRole} />)}</section>
            )}
        </main>
    )
}

function RoleCard({ role, editable, onSave }) {
    const [description, setDescription] = useState(role.description || "")
    return <article className="role-card"><div className="role-card-heading"><span className={`role-mark role-mark--${role.name.toLowerCase()}`}>{role.name.slice(0, 1)}</span><div><h2>{role.name}</h2><p>System permission level</p></div></div><textarea value={description} onChange={(event) => setDescription(event.target.value)} disabled={!editable} rows={3} maxLength={1000} /><div className="role-card-footer">{editable ? <button className="btn btn-outline" type="button" onClick={() => onSave({ ...role, description })}>Save description</button> : <span>Only administrators can edit role details.</span>}</div></article>
}