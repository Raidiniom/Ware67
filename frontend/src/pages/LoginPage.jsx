import { useState } from "react"
import { Link, useLocation, useNavigate } from "react-router-dom"
import { useAuth } from "../context/AuthContext"
import "./styles/Auth.css"

export default function LoginPage() {
    const { login } = useAuth()
    const navigate = useNavigate()
    const location = useLocation()

    const [email, setEmail] = useState("")
    const [password, setPassword] = useState("")
    const [error, setError] = useState("")
    const [submitting, setSubmitting] = useState(false)

    const from = location.state?.from?.pathname || "/dashboard"
    const justRegistered = location.state?.registered

    async function handleSubmit(e) {
        e.preventDefault()
        setError("")
        setSubmitting(true)
        try {
            await login(email, password)
            navigate(from, { replace: true })
        } catch (err) {
            const detail = err?.response?.data?.detail
            setError(typeof detail === "string" ? detail : "Unable to sign in. Please check your credentials.")
        } finally {
            setSubmitting(false)
        }
    }

    return (
        <div className="auth-page">
            <form className="auth-card" onSubmit={handleSubmit}>
                <h1>Sign in</h1>
                <p className="auth-subtitle">Welcome back to WARE67</p>

                {justRegistered && (
                    <div className="auth-success" style={{ marginBottom: 16 }}>
                        Account created! Sign in with your new credentials.
                    </div>
                )}
                {error && <div className="auth-error">{error}</div>}

                <label className="auth-field">
                    <span>Email</span>
                    <input
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        required
                        autoComplete="email"
                    />
                </label>

                <label className="auth-field">
                    <span>Password</span>
                    <input
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        required
                        autoComplete="current-password"
                    />
                </label>

                <div className="auth-row">
                    <Link to="/forgot-password">Forgot password?</Link>
                </div>

                <button type="submit" className="auth-submit" disabled={submitting}>
                    {submitting ? "Signing in…" : "Sign in"}
                </button>

                <p className="auth-footer">
                    Don&apos;t have an account? <Link to="/register">Create one</Link>
                </p>
            </form>
        </div>
    )
}
