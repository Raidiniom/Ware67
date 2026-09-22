import { Link, useNavigate } from "react-router-dom"
import { useAuth } from "../context/AuthContext"
import "./styles/common.css"
import "./styles/DashboardPage.css"

// Mirrors backend/schema/ware67_schema.sql — one card per table/entity.
// These are placeholders until each module gets its own endpoints + UI.
const ALL_MODULES = [
    { key: "products", title: "Products", description: "SKUs, pricing, and reorder levels.", roles: null, href: "/products" },
    { key: "categories", title: "Categories", description: "Organize products into categories.", roles: null },
    { key: "suppliers", title: "Suppliers", description: "Vendor contacts and details.", roles: null },
    { key: "locations", title: "Locations", description: "Warehouses, aisles, shelves, and bins.", roles: null },
    { key: "transactions", title: "Transactions", description: "Stock-in and stock-out history.", roles: null },
    { key: "adjustments", title: "Inventory Adjustments", description: "Manual stock corrections, with a reason on record.", roles: null },
    { key: "audit-logs", title: "Audit Logs", description: "Who did what, and when.", roles: ["ADMIN"] },
    { key: "users", title: "Users & Roles", description: "Manage accounts and permissions.", roles: ["ADMIN", "MANAGER"] },
]

export default function DashboardPage() {
    const { user, logout } = useAuth()
    const navigate = useNavigate()

    function handleLogout() {
        logout()
        navigate("/")
    }

    const modules = ALL_MODULES.filter((m) => !m.roles || m.roles.includes(user?.role))
    const firstName = user?.name?.split(" ")[0] || "there"

    return (
        <div className="dashboard">
            <header className="dashboard-header">
                <Link to="/" className="site-brand">WARE67</Link>
                <button className="btn btn-outline" onClick={handleLogout}>Sign out</button>
            </header>

            <section className="dashboard-welcome">
                <h1>Welcome back, {firstName} 👋</h1>
                <p>
                    Signed in as <strong>{user?.email}</strong>
                    {user?.role && (
                        <span className={`role-badge role-badge--${user.role.toLowerCase()}`}>
                            {user.role}
                        </span>
                    )}
                </p>
            </section>

            <section className="dashboard-modules">
                {modules.map((m) => (
                    <div className={`module-card${m.href ? " module-card--available" : ""}`} key={m.key}>
                        <h3>{m.title}</h3>
                        <p>{m.description}</p>
                        {m.href ? (
                            <Link to={m.href} className="module-link">Open module →</Link>
                        ) : (
                            <span className="module-status">Coming soon</span>
                        )}
                    </div>
                ))}
            </section>
        </div>
    )
}
