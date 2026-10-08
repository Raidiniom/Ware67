import { useMemo, useState } from "react"
import { Link } from "react-router-dom"
import axios from "axios"
import { useAuth } from "../context/AuthContext"
import { GROUPS } from "../api/docs"
import "./styles/ApiDocsPage.css"

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "https://ware67-api.dcism.org/api/v1").replace(/\/$/, "")
const API_ROOT = API_BASE.replace(/\/api\/v1$/, "")
const ALL = GROUPS.flatMap((g) => g.endpoints.map((e) => ({ ...e, group: g.name })))

const pathParams = (path) => [...path.matchAll(/\{(\w+)\}/g)].map((m) => m[1])
const pretty = (v) => JSON.stringify(v, null, 2)

function buildUrl(ep, params, query) {
    let path = ep.path
    for (const name of pathParams(ep.path)) {
        path = path.replace(`{${name}}`, encodeURIComponent(params[name] || `{${name}}`))
    }
    const qs = new URLSearchParams(Object.entries(query).filter(([, v]) => v !== "" && v != null))
    return `${API_BASE}${path}${qs.toString() ? `?${qs}` : ""}`
}

function authHeaders(ep, creds) {
    if (ep.auth === "bearer" && creds.token) return { Authorization: `Bearer ${creds.token}` }
    if (ep.auth === "apiKey" && creds.apiKey) return { "X-API-Key": creds.apiKey }
    return {}
}

function toCurl(ep, url, creds, body) {
    const lines = [`curl -X ${ep.method} '${url}'`]
    for (const [name, value] of Object.entries(authHeaders(ep, creds))) lines.push(`  -H '${name}: ${value}'`)
    if (body) {
        lines.push(`  -H 'Content-Type: application/json'`)
        lines.push(`  -d '${body.replace(/\s*\n\s*/g, " ")}'`)
    }
    return lines.join(" \\\n")
}

function statusClass(code) {
    if (code >= 500) return "docs-status docs-status--err"
    if (code >= 400) return "docs-status docs-status--warn"
    return "docs-status docs-status--ok"
}

function Try({ ep, creds, onToken, onApiKey }) {
    const params = pathParams(ep.path)
    const [pv, setPv] = useState({})
    const [qv, setQv] = useState({})
    const [body, setBody] = useState(ep.body ? pretty(ep.body) : "")
    const [busy, setBusy] = useState(false)
    const [res, setRes] = useState(null)
    const [copied, setCopied] = useState(false)

    const missing = params.filter((p) => !pv[p]?.trim())
    const url = buildUrl(ep, pv, qv)

    async function send() {
        let data
        if (ep.body) {
            try {
                data = JSON.parse(body)
            } catch {
                setRes({ clientError: "The request body is not valid JSON." })
                return
            }
        }
        setBusy(true)
        setRes(null)
        const started = performance.now()
        try {
            const r = await axios.request({
                method: ep.method,
                url,
                data,
                headers: authHeaders(ep, creds),
                validateStatus: () => true,
            })
            setRes({
                status: r.status,
                ms: Math.round(performance.now() - started),
                text: r.data === "" || r.data == null ? "" : typeof r.data === "string" ? r.data : pretty(r.data),
            })
            if (ep.path === "/auth/login" && r.status === 200 && r.data?.access_token) {
                onToken(r.data.access_token)
            }
            if (ep.path === "/api-keys" && ep.method === "POST" && r.status === 201 && r.data?.api_key) {
                onApiKey(r.data.api_key)
            }
        } catch {
            setRes({ clientError: "Couldn't reach the server. Check your connection, or that the backend is running and CORS allows this origin." })
        } finally {
            setBusy(false)
        }
    }

    async function copy() {
        try {
            await navigator.clipboard.writeText(toCurl(ep, url, creds, ep.body ? body : ""))
            setCopied(true)
            setTimeout(() => setCopied(false), 1500)
        } catch {
            /* clipboard unavailable */
        }
    }

    return (
        <div className="docs-try">
            {params.length > 0 && (
                <fieldset className="docs-fields">
                    <legend>Path</legend>
                    {params.map((p) => (
                        <label key={p}>
                            <span>{p}</span>
                            <input value={pv[p] ?? ""} onChange={(e) => setPv({ ...pv, [p]: e.target.value })} placeholder="required" />
                        </label>
                    ))}
                </fieldset>
            )}

            {ep.query.length > 0 && (
                <fieldset className="docs-fields">
                    <legend>Query</legend>
                    {ep.query.map((q) => (
                        <label key={q.name}>
                            <span>{q.name}</span>
                            <input value={qv[q.name] ?? ""} onChange={(e) => setQv({ ...qv, [q.name]: e.target.value })} placeholder={q.hint || ""} />
                        </label>
                    ))}
                </fieldset>
            )}

            {ep.body && (
                <label className="docs-body">
                    <span>JSON body</span>
                    <textarea value={body} onChange={(e) => setBody(e.target.value)} spellCheck={false} rows={Math.min(14, body.split("\n").length + 1)} />
                </label>
            )}

            <div className="docs-urlbar">
                <code title={url}>{ep.method} {url}</code>
                <button type="button" className="btn btn-ghost btn-sm" onClick={copy}>{copied ? "Copied" : "Copy as cURL"}</button>
                <button type="button" className="btn btn-primary btn-sm" onClick={send} disabled={busy || missing.length > 0}>
                    {busy ? "Sending…" : "Send request"}
                </button>
            </div>
            {missing.length > 0 && <p className="docs-hint">Fill in {missing.join(", ")} to send.</p>}
            {ep.auth === "bearer" && !creds.token && <p className="docs-hint">No token set. This request will likely return 401.</p>}
            {ep.auth === "apiKey" && !creds.apiKey && <p className="docs-hint">No API key set. Paste a partner key above, or this request will return 401.</p>}

            {res?.clientError && <div className="docs-alert" role="alert">{res.clientError}</div>}
            {res && !res.clientError && (
                <div className="docs-response" role="status">
                    <div className="docs-response-head">
                        <span className={statusClass(res.status)}>{res.status}</span>
                        <span>{res.ms} ms</span>
                    </div>
                    <pre>{res.text || "No content."}</pre>
                </div>
            )}
        </div>
    )
}

export default function ApiDocsPage() {
    const { user } = useAuth()
    const [selectedId, setSelectedId] = useState(ALL[0].id)
    const [filter, setFilter] = useState("")
    const [token, setToken] = useState(() => localStorage.getItem("ware67_token") || "")
    // Kept in memory only: partner keys are secrets and should not outlive the tab.
    const [apiKey, setApiKey] = useState("")

    const selected = ALL.find((e) => e.id === selectedId)

    const groups = useMemo(() => {
        const f = filter.trim().toLowerCase()
        return GROUPS.map((g) => ({
            ...g,
            endpoints: g.endpoints.filter((e) => !f || `${e.method} ${e.path} ${e.summary}`.toLowerCase().includes(f)),
        })).filter((g) => g.endpoints.length)
    }, [filter])

    return (
        <div className="docs-page">
            <header className="docs-header">
                <Link to="/" className="docs-brand">WARE<span>67</span></Link>
                <nav>
                    <a href={`${API_ROOT}/docs`} target="_blank" rel="noreferrer">Swagger UI</a>
                    <a href={`${API_ROOT}/redoc`} target="_blank" rel="noreferrer">ReDoc</a>
                    <Link to={user ? "/dashboard" : "/login"}>{user ? "Dashboard" : "Sign in"}</Link>
                </nav>
            </header>

            <section className="docs-intro">
                <h1>API reference</h1>
                <p>
                    Pick an endpoint, fill in what it needs and send it. Requests go to <code>{API_BASE}</code> and
                    run against live data, so deletes and stock changes are real.
                </p>
                <div className="docs-auth">
                    <label>
                        <span>Bearer token</span>
                        <input
                            type="password"
                            value={token}
                            onChange={(e) => setToken(e.target.value.trim())}
                            placeholder="Paste an access token, or call POST /auth/login"
                            autoComplete="off"
                        />
                    </label>
                    <button
                        type="button"
                        className="btn btn-ghost btn-sm"
                        onClick={() => setToken(localStorage.getItem("ware67_token") || "")}
                        disabled={!localStorage.getItem("ware67_token")}
                    >
                        Use my session
                    </button>
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => setToken("")} disabled={!token}>
                        Clear
                    </button>
                </div>
                <div className="docs-auth">
                    <label>
                        <span>Partner API key</span>
                        <input
                            type="password"
                            value={apiKey}
                            onChange={(e) => setApiKey(e.target.value.trim())}
                            placeholder="Sent as X-API-Key on the Partner integration endpoints"
                            autoComplete="off"
                        />
                    </label>
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => setApiKey("")} disabled={!apiKey}>
                        Clear
                    </button>
                </div>
                <p className="docs-hint">
                    Access tokens expire after a short time. A 401 means it is time to log in again. Partner keys are
                    issued by an admin via <code>POST /api-keys</code> and are never stored by this page.
                </p>
            </section>

            <div className="docs-layout">
                <aside className="docs-nav" aria-label="Endpoints">
                    <input type="search" value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Filter endpoints…" aria-label="Filter endpoints" />
                    {groups.length === 0 && <p className="docs-hint">No endpoints match “{filter}”.</p>}
                    {groups.map((g) => (
                        <div key={g.name} className="docs-group">
                            <h2>{g.name}</h2>
                            <ul>
                                {g.endpoints.map((e) => (
                                    <li key={e.id}>
                                        <button
                                            type="button"
                                            className={e.id === selectedId ? "is-active" : ""}
                                            aria-current={e.id === selectedId}
                                            onClick={() => setSelectedId(e.id)}
                                        >
                                            <span className={`docs-method docs-method--${e.method.toLowerCase()}`}>{e.method}</span>
                                            <span className="docs-path">{e.path}</span>
                                        </button>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    ))}
                </aside>

                <main className="docs-main">
                    <div className="docs-endpoint-head">
                        <span className={`docs-method docs-method--${selected.method.toLowerCase()}`}>{selected.method}</span>
                        <code>{selected.path}</code>
                    </div>
                    <h2>{selected.summary}</h2>
                    <p className="docs-meta">
                        {selected.group}. Access: <strong>{selected.access}</strong>
                    </p>
                    {selected.notes && <p className="docs-note">{selected.notes}</p>}
                    <Try key={selected.id} ep={selected} creds={{ token, apiKey }} onToken={setToken} onApiKey={setApiKey} />
                </main>
            </div>
        </div>
    )
}
