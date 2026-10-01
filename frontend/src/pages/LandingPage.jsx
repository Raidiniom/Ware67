import { Link } from "react-router-dom"
import { useAuth } from "../context/AuthContext"
import "./styles/Landing.css"


export default function LandingPage() {
	const { user } = useAuth()

	return (
		<main className="landing-page">
			<nav className="landing-nav" aria-label="Main navigation">
				<Link to="/" className="brand-mark">
					WARE<span>67</span>
				</Link>

				<div className="landing-nav-links">
					<a href="#about">About</a>
					<Link to="/api-docs">API</Link>

					{user ? (
						<Link className="nav-action" to="/dashboard">
							Open dashboard <span>↗</span>
						</Link>
					) : (
						<Link className="nav-action" to="/login">
							Sign in <span>↗</span>
						</Link>
					)}
				</div>
			</nav>

			<section className="landing-hero">
				<div className="hero-grid" aria-hidden="true" />

				<div className="hero-copy">
					<div className="eyebrow-row">
						<span className="eyebrow">WAREHOUSE OPERATIONS</span>
						<span className="eyebrow-line" />
						<span className="eyebrow-code">/ 67</span>
					</div>

					<h1>
						Know what is
						<span> moving,</span>
						<br />
						before it moves.
					</h1>

					<p className="hero-description">
						WARE67 gives your team one clear operational picture —
						inventory, people, and the work keeping everything in motion.
					</p>

					<div className="hero-actions">
						{user ? (
							<Link className="primary-button" to="/dashboard">
								Go to dashboard <span>→</span>
							</Link>
						) : (
							<Link className="primary-button" to="/register">
								Create your account <span>→</span>
							</Link>
						)}

						<a className="text-button" href="#api">
							Explore the API <span>↓</span>
						</a>
					</div>

					<div className="hero-meta">
						<div>
							<span className="meta-label">STATUS</span>
							<strong>
								<i className="status-dot" />
								Operational
							</strong>
						</div>

						<div>
							<span className="meta-label">PLATFORM</span>
							<strong>WARE67 Core</strong>
						</div>
					</div>
				</div>

				<div className="hero-aside">
					<div className="hero-aside-card">
						<span className="card-kicker">01 / CONTROL</span>

						<strong>One operational picture.</strong>

						<p>
							Bring the important parts of warehouse operations into one
							place.
						</p>
					</div>

					<div className="hero-aside-mark">W67</div>
				</div>
			</section>

			<section className="landing-strip" id="about">
				<div className="section-intro">
					<span className="strip-number">WHY WARE67</span>

					<h2>
						Less noise.
						<br />
						More control.
					</h2>
				</div>

				<div className="feature-card">
					<span className="strip-number">01</span>

					<div className="feature-icon">◎</div>

					<strong>One source of truth</strong>

					<p>
						Keep the team aligned around the same live operational picture.
					</p>
				</div>

				<div className="feature-card">
					<span className="strip-number">02</span>

					<div className="feature-icon">↳</div>

					<strong>Roles that fit the work</strong>

					<p>
						Staff, managers, and admins get the access they need.
					</p>
				</div>

				<div className="feature-card">
					<span className="strip-number">03</span>

					<div className="feature-icon">⌁</div>

					<strong>Ready to connect</strong>

					<p>
						Use the documented API to bring WARE67 into your tools.
					</p>
				</div>
			</section>

			<section className="api-section" id="api">
				<div className="api-copy">
					<p className="eyebrow">FOR BUILDERS</p>

					<h2>Connect to the operation.</h2>

					<p>
						Build on the same REST API used by the WARE67 app.
						Authentication, refresh tokens, and current-user data are ready
						to use.
					</p>

					<div className="api-pills">
						<span>REST API</span>
						<span>AUTHENTICATION</span>
						<span>JSON</span>
					</div>
				</div>

				<div className="api-card">
					<div className="api-card-header">
						<span className="api-method">GET</span>

						<span className="api-live">
							<i />
							LIVE
						</span>
					</div>

					<code>/api/v1/auth/me</code>

					<p>View the authenticated user and their role.</p>

					<div className="api-card-footer">
						<span>API ENDPOINT</span>

						<Link to="/api-docs" className="api-link">
							Open interactive docs <span>↗</span>
						</Link>
					</div>
				</div>
			</section>

			<footer className="landing-footer">
				<span className="brand-mark">
					WARE<span>67</span>
				</span>

				<span>Inventory clarity for teams in motion.</span>

				{!user && (
					<Link to="/login">
						Already have an account? Sign in →
					</Link>
				)}
			</footer>
		</main>
	)
}