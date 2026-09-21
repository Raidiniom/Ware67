import { Link } from "react-router-dom"
import SiteHeader from "../components/SiteHeader"
import "../styles/common.css"
import "./styles/LandingPage.css"
import "./styles/ApiDocsPage.css"

const apiBase = import.meta.env.VITE_API_BASE_URL || ""
// VITE_API_BASE_URL includes the /api/v1 prefix (e.g. https://ware67-api.dcism.org/api/v1);
// FastAPI's auto-generated docs live at the API root instead, so strip it back off.
const apiRoot = apiBase.replace(/\/api\/v1\/?$/, "")

const endpoints = [
    {
        method: "POST",
        path: "/api/v1/auth/register",
        description: "Create a new account (Staff role by default).",
        body: `{
  "name": "Jane Cruz",
  "email": "jane@example.com",
  "password": "********"
}`,
    },
    {
        method: "POST",
        path: "/api/v1/auth/login",
        description: "Exchange email + password for an access/refresh token pair.",
        body: `{
  "email": "jane@example.com",
  "password": "********"
}`,
    },
    {
        method: "POST",
        path: "/api/v1/auth/refresh",
        description: "Exchange a refresh token for a new access/refresh pair.",
        body: `{
  "refresh_token": "..."
}`,
    },
    {
        method: "GET",
        path: "/api/v1/auth/me",
        description: "Return the currently authenticated user. Requires an Authorization: Bearer <access_token> header.",
        body: null,
    },
    {
        method: "POST",
        path: "/api/v1/auth/forgot-password",
        description: "Verify email + the full name on the account, then set a new password directly (no email step is available on this host).",
        body: `{
  "email": "jane@example.com",
  "name": "Jane Cruz",
  "new_password": "********"
}`,
    },
]

export default function ApiDocsPage() {
    return (
        <div className="landing">
            <SiteHeader />

            <section className="landing-hero api-docs-hero">
                <h1>API documentation</h1>
                <p>
                    The endpoints below are what's live today. For the full
                    interactive reference — and to try requests right from
                    the browser — use the auto-generated docs:
                </p>
                <div className="landing-cta">
                    {apiRoot && (
                        <>
                            <a
                                className="btn btn-primary"
                                href={`${apiRoot}/docs`}
                                target="_blank"
                                rel="noreferrer"
                            >
                                Swagger UI
                            </a>
                            <a
                                className="btn btn-ghost"
                                href={`${apiRoot}/redoc`}
                                target="_blank"
                                rel="noreferrer"
                            >
                                ReDoc
                            </a>
                        </>
                    )}
                </div>
            </section>

            <section className="landing-about">
                <h2>Auth endpoints</h2>
                <p>
                    All routes are prefixed with <code>/api/v1</code>. Routes
                    marked as requiring auth expect an{" "}
                    <code>Authorization: Bearer &lt;access_token&gt;</code>{" "}
                    header.
                </p>

                <div className="endpoint-list">
                    {endpoints.map((ep) => (
                        <div className="endpoint-card" key={ep.method + ep.path}>
                            <div className="endpoint-head">
                                <span className={`endpoint-method endpoint-method--${ep.method.toLowerCase()}`}>
                                    {ep.method}
                                </span>
                                <code>{ep.path}</code>
                            </div>
                            <p>{ep.description}</p>
                            {ep.body && <pre className="endpoint-body">{ep.body}</pre>}
                        </div>
                    ))}
                </div>
            </section>

            <footer className="landing-footer">
                <p><Link to="/">Back home</Link></p>
            </footer>
        </div>
    )
}
