import { Link } from "react-router-dom"
import { useAuth } from "../context/AuthContext"
import "./styles/Landing.css"

export default function DashboardPage() {
    const { user, logout } = useAuth()
    const firstName = user?.name?.trim().split(/\s+/)[0] || "there"
    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "https://ware67-api.dcism.org"

    return (
        <main className="dashboard-page">
            <header className="dashboard-header"><Link to="/" className="brand-mark">WARE<span>67</span></Link><div className="dashboard-account"><div><strong>{user?.name}</strong><span>{user?.role || "STAFF"}</span></div><button type="button" className="logout-button" onClick={logout}>Sign out</button></div></header>
            <section className="dashboard-welcome"><p className="eyebrow">YOUR WORKSPACE</p><h1>Good to see you, {firstName}.</h1><p>This is your WARE67 operations dashboard. The workspace is ready for the next inventory modules.</p></section>
            <section className="dashboard-grid">
                <article className="dashboard-panel dashboard-panel-featured"><span className="panel-index">01 / OVERVIEW</span><h2>Operations overview</h2><p>Inventory and activity insights will appear here as the next modules come online.</p><span className="panel-status">Coming next</span></article>
                <article className="dashboard-panel"><span className="panel-index">02 / ACCOUNT</span><h2>Your profile</h2><dl><div><dt>Name</dt><dd>{user?.name}</dd></div><div><dt>Email</dt><dd>{user?.email}</dd></div><div><dt>Role</dt><dd>{user?.role}</dd></div></dl></article>
                <article className="dashboard-panel"><span className="panel-index">03 / ACCESS</span><h2>API documentation</h2><p>Explore the endpoints available to your integrations.</p><a className="api-link" href={`${apiBaseUrl}/docs`} target="_blank" rel="noreferrer">Open Swagger UI <span aria-hidden="true">-&gt;</span></a></article>
            </section>
        </main>
    )
}