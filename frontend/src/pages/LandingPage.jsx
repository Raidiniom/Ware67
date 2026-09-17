import { Link } from "react-router-dom"
import { useAuth } from "../context/AuthContext"
import "./styles/Landing.css"

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "https://ware67-api.dcism.org"

export default function LandingPage() {
	const { user } = useAuth()

	return (
		<main className="landing-page">
			<nav className="landing-nav" aria-label="Main navigation">
				<Link to="/" className="brand-mark">WARE<span>67</span></Link>
				<div className="landing-nav-links">
					<a href="#about">About us</a>
					<a href="#api">API docs</a>
					{user ? <Link className="nav-action" to="/dashboard">Open dashboard</Link> : <Link className="nav-action" to="/login">Sign in</Link>}
				</div>
			</nav>
			<section className="landing-hero">
				<div className="hero-copy">
					<p className="eyebrow">WAREHOUSE OPERATIONS / 67</p>
					<h1>Know what is moving, before it moves.</h1>
					<p className="hero-description">WARE67 gives your team one clear view of inventory, people, and the work keeping your operation in motion.</p>
					<div className="hero-actions">
						{user ? <Link className="primary-button" to="/dashboard">Go to dashboard <span aria-hidden="true">-&gt;</span></Link> : <Link className="primary-button" to="/register">Create your account <span aria-hidden="true">-&gt;</span></Link>}
						<a className="text-button" href="#api">Explore the API <span aria-hidden="true">↓</span></a>
					</div>
				</div>
				<div className="hero-aside" aria-label="Platform status"><span className="status-dot" /><span>Operations platform</span><strong>Built for the floor.</strong></div>
			</section>
			<section className="landing-strip" id="about">
				<div><span className="strip-number">01</span><strong>One source of truth</strong><p>Keep the team aligned around the same live operational picture.</p></div>
				<div><span className="strip-number">02</span><strong>Roles that fit the work</strong><p>Staff, managers, and admins get the access they need.</p></div>
				<div><span className="strip-number">03</span><strong>Ready to connect</strong><p>Use the documented API to bring WARE67 into your tools.</p></div>
			</section>
			<section className="api-section" id="api">
				<div><p className="eyebrow">FOR BUILDERS</p><h2>Connect to the operation.</h2><p>Build on the same REST API used by the WARE67 app. Authentication, refresh tokens, and current-user data are ready to use.</p></div>
				<div className="api-card"><div className="api-card-top"><span className="api-method">GET</span><code>/api/v1/auth/me</code></div><p>View the authenticated user and their role.</p><a href={`${apiBaseUrl}/docs`} target="_blank" rel="noreferrer" className="api-link">Open interactive docs <span aria-hidden="true">-&gt;</span></a></div>
			</section>
			<footer className="landing-footer"><span className="brand-mark">WARE<span>67</span></span><span>Inventory clarity for teams in motion.</span>{!user && <Link to="/login">Already have an account? Sign in</Link>}</footer>
		</main>
	)
}