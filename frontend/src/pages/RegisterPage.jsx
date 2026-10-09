import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { register } from "../api/auth"
import { errorMessage } from "../api/resources"
import AuthShell from "../components/AuthShell"

export default function RegisterPage() {
    const navigate = useNavigate()
    const [form, setForm] = useState({ companyName: "", name: "", email: "", password: "", confirmPassword: "" })
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
            await register({
                companyName: form.companyName,
                name: form.name,
                email: form.email,
                password: form.password,
            })
            navigate("/login", { state: { registered: true } })
        } catch (err) {
            // Shows validation details too (e.g. an invalid email), not just plain messages.
            setError(errorMessage(err, "Unable to create your account. Please try again."))
        } finally {
            setSubmitting(false)
        }
    }

    return (
        <AuthShell
            eyebrow="WARE67 / GET STARTED"
            title="Create your company"
            subtitle="Sign up your business. You'll be its owner and can add your team afterwards."
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
                    <span>Company name</span>
                    <input
                        type="text"
                        value={form.companyName}
                        onChange={update("companyName")}
                        required
                        maxLength={150}
                        autoComplete="organization"
                    />
                </label>

                <label className="auth-field">
                    <span>Your full name</span>
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