import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { forgotPassword } from "../api/auth"
import "./styles/Auth.css"

export default function ForgotPasswordPage() {
    const navigate = useNavigate()
    const [form, setForm] = useState({ email: "", name: "", newPassword: "", confirmPassword: "" })
    const [error, setError] = useState("")
    const [submitting, setSubmitting] = useState(false)
    const [done, setDone] = useState(false)

    function update(field) {
        return (e) => setForm((f) => ({ ...f, [field]: e.target.value }))
    }

    async function handleSubmit(e) {
        e.preventDefault()
        setError("")

        if (form.newPassword !== form.confirmPassword) {
            setError("Passwords do not match.")
            return
        }
        if (form.newPassword.length < 8) {
            setError("Password must be at least 8 characters.")
            return
        }

        setSubmitting(true)
        try {
            await forgotPassword({
                email: form.email,
                name: form.name,
                newPassword: form.newPassword,
            })
            setDone(true)
            setTimeout(() => navigate("/login"), 2000)
        } catch (err) {
            const detail = err?.response?.data?.detail
            setError(
                typeof detail === "string"
                    ? detail
                    : "We couldn't verify those account details. Please try again."
            )
        } finally {
            setSubmitting(false)
        }
    }

    return (
        <div className="auth-page">
            <div className="auth-card">
                <h1>Forgot password</h1>
                <p className="auth-subtitle">
                    Confirm your email and full name, then set a new password.
                </p>

                {done ? (
                    <div className="auth-success">
                        Your password has been changed. Redirecting you to sign in…
                    </div>
                ) : (
                    <form onSubmit={handleSubmit}>
                        {error && <div className="auth-error">{error}</div>}

                        <label className="auth-field">
                            <span>Email</span>
                            <input
                                type="email"
                                value={form.email}
                                onChange={update("email")}
                                required
                                autoComplete="email"
                            />
                        </label>

                        <label className="auth-field">
                            <span>Full name on the account</span>
                            <input
                                type="text"
                                value={form.name}
                                onChange={update("name")}
                                required
                                autoComplete="name"
                            />
                        </label>

                        <label className="auth-field">
                            <span>New password</span>
                            <input
                                type="password"
                                value={form.newPassword}
                                onChange={update("newPassword")}
                                required
                                minLength={8}
                                autoComplete="new-password"
                            />
                        </label>

                        <label className="auth-field">
                            <span>Confirm new password</span>
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
                            {submitting ? "Changing password…" : "Change password"}
                        </button>
                    </form>
                )}

                <p className="auth-footer">
                    <Link to="/login">Back to sign in</Link>
                </p>
            </div>
        </div>
    )
}
