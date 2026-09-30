import { Link } from "react-router-dom"
import "../pages/styles/Auth.css"

export default function AuthShell({ eyebrow, title, subtitle, footer, children }) {
    return (
        <main className="auth-page">
            <aside className="auth-aside">
                <Link to="/" className="auth-brand">
                    WARE<span>67</span>
                </Link>

                <div className="auth-aside-copy">
                    <span className="auth-aside-eyebrow">WAREHOUSE OPERATIONS</span>
                    <h2>
                        Know what is moving, before it moves.
                    </h2>
                    <p>
                        One clear operational picture — inventory, people, and the work keeping everything in motion.
                    </p>
                </div>
            </aside>

            <section className="auth-main">
                <div className="auth-card">
                    <span className="auth-eyebrow">{eyebrow}</span>
                    <h1>{title}</h1>
                    {subtitle && <p className="auth-subtitle">{subtitle}</p>}

                    {children}

                    {footer && <p className="auth-footer">{footer}</p>}
                </div>
            </section>
        </main>
    )
}