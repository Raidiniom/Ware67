import { Link } from "react-router-dom"
import { useAuth } from "../context/AuthContext"
import "../styles/common.css"
import "../styles/SiteHeader.css"

export default function SiteHeader() {
    const { user, loading, logout } = useAuth()

    return (
        <header className="site-header">
            <Link to="/" className="site-brand">WARE67</Link>

            <nav className="site-nav">
                {/* Plain anchor (not <Link>) so this also works — with a
                    normal page navigation — from pages other than the
                    landing page itself. */}
                <a href="/#about">About</a>
                <Link to="/api-docs">API Docs</Link>
            </nav>

            <div className="site-actions">
                {!loading && user ? (
                    <>
                        <Link to="/dashboard" className="btn btn-ghost">Dashboard</Link>
                        <button className="btn btn-outline" onClick={logout}>Sign out</button>
                    </>
                ) : (
                    <>
                        <Link to="/login" className="btn btn-ghost">Sign in</Link>
                        <Link to="/register" className="btn btn-primary">Get started</Link>
                    </>
                )}
            </div>
        </header>
    )
}
