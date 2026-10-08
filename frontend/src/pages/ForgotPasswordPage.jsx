import { Link } from "react-router-dom"
import AuthShell from "../components/AuthShell"

// There is no email/SMS provider on this host, so a user can't prove they own
// an address. Self-service resets were removed (anyone knowing an email could
// take over the account); an administrator or manager resets it instead from
// Users & roles.
export default function ForgotPasswordPage() {
    return (
        <AuthShell
            eyebrow="WARE67 / ACCOUNT RECOVERY"
            title="Forgot password"
            subtitle="Password resets are handled by your team's administrators."
            footer={<Link to="/login">← Back to sign in</Link>}
        >
            <div className="auth-success" role="status">
                Ask a WARE67 administrator or manager to reset your password. They can set a temporary
                password for you from <strong>Users &amp; roles</strong>, which you can use to sign in.
            </div>
            <p className="auth-hint">
                Managers can reset staff and guest accounts. Administrator and manager accounts can only be
                reset by an administrator.
            </p>
        </AuthShell>
    )
}
