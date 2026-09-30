import { Link } from "react-router-dom"
import "./styles/Resource.css"

export default function PageShell({ title, subtitle, actions, children }) {
    return (
        <div className="page-shell">
            <header className="page-shell-header">
                <Link to="/dashboard" className="page-brand">WARE67</Link>
                <Link to="/dashboard" className="btn btn-ghost">← Dashboard</Link>
            </header>
            <main className="page-shell-main">
                <div className="page-title-row">
                    <div>
                        <h1>{title}</h1>
                        {subtitle && <p>{subtitle}</p>}
                    </div>
                    <div>{actions}</div>
                </div>
                {children}
            </main>
        </div>
    )
}