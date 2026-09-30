import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { register } from "../api/auth"
import AuthShell from "../components/AuthShell"

export default function RegisterPage() {
    const navigate = useNavigate()
    const [form, setForm] = useState({ name: "", email: "", password: "", confirmPassword: "" })
    const [error, setError] = useState("")
    const [submitting, setSubmitting] = useState(false)

    function update(field) {
        return (e) => setForm((f) => ({ ...f, [field]: e.target.value }))
    }

    async function handleSubmit(e) {
        e.preventDefault()
        setError("")

        if (form.password !== form.confirmPassword) {
            setError("Passwords do not match.")
            return
        }
        if (form.password.length < 8) {
            setError("Password must be at least 8 characters.")
            return
        }

        setSubmitting(true)
        try {
            await register({ name: form.name, email: form.email, password: form.password })
            navigate("/login", { state: { registered: true } })
        } catch (err) {
            const detail = err?.response?.data?.detail
            setError(typeof detail === "string" ? detail : "Unable to create your account. Please try again.")
        } finally {
            setSubmitting(false)
        }
    }

    return (
        <AuthShell
            eyebrow="WARE67 / GET STARTED"
            title="Create your account"
            subtitle="Set up access to your team's warehouse operations."
            footer={
                <>
                    Already have an account? <Link to="/login">Sign in</Link>
                </>
            }
        >
            <form onSubmit={handleSubmit}>
                {error && (
                    <div className="auth-error" role="alert">
                        {error}
                    </div>
                )}

                <label className="auth-field">
                    <span>Full name</span>
                    <input type="text" value={form.name} onChange={update("name")} required autoComplete="name" />
                </label>

                <label className="auth-field">
                    <span>Email</span>
                    <input type="email" value={form.email} onChange={update("email")} required autoComplete="email" />
                </label>

                <label className="auth-field">
                    <span>Password</span>
                    <input
                        type="password"
                        value={form.password}
                        onChange={update("password")}
                        required
                        minLength={8}
                        autoComplete="new-password"
                    />
                    <small className="auth-hint">At least 8 characters.</small>
                </label>

                <label className="auth-field">
                    <span>Confirm password</span>
                    <input
                        type="password"
                        value={form.confirmPassword}
                        onChange={update("confirmPassword")}
                        required
                        minLength={8}
                        autoComplete="new-password"
                    />
                </label>

                <button type="submit" className="auth-submit" disabled={submitting}>
                    {submitting ? "Creating account…" : "Create account"}
                    <span>→</span>
                </button>
            </form>
        </AuthShell>
    )
}