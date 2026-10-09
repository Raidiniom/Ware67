import { Link, useNavigate } from "react-router-dom"
import { useAuth } from "../context/AuthContext"

import "./styles/common.css"
import "./styles/DashboardPage.css"

const ALL_MODULES = [
	{
		key: "products",
		path: "/products",
		title: "Products",
		description: "SKUs, pricing, and reorder levels.",
		roles: null,
		icon: "▦",
		category: "Inventory",
	},
	{
		key: "categories",
		path: "/categories",
		title: "Categories",
		description: "Organize products into categories.",
		roles: null,
		icon: "◫",
		category: "Inventory",
	},
	{
		key: "suppliers",
		path: "/suppliers",
		title: "Suppliers",
		description: "Vendor contacts and details.",
		roles: null,
		icon: "◇",
		category: "Inventory",
	},
	{
		key: "locations",
		path: "/locations",
		title: "Locations",
		description: "Warehouses, aisles, shelves, and bins.",
		roles: null,
		icon: "⌖",
		category: "Operations",
	},
	{
		key: "transactions",
		path: "/transactions",
		title: "Transactions",
		description: "Stock-in and stock-out history.",
		roles: null,
		icon: "⇄",
		category: "Operations",
	},
	{
		key: "adjustments",
		path: "/adjustments",
		title: "Inventory Adjustments",
		description: "Manual stock corrections, with a reason on record.",
		roles: null,
		icon: "±",
		category: "Operations",
	},
	{
		key: "audit-logs",
		path: "/audit-logs",
		title: "Audit Logs",
		description: "Who did what, and when.",
		roles: ["OWNER", "ADMIN"],
		icon: "⌁",
		category: "Administration",
	},
	{
		key: "users",
		path: "/users",
		title: "Users & Roles",
		description: "Manage accounts and permissions.",
		roles: ["OWNER", "ADMIN", "MANAGER"],
		icon: "♙",
		category: "Administration",
	},
]

export default function DashboardPage() {
	const { user, logout } = useAuth()
	const navigate = useNavigate()

	function handleLogout() {
		logout()
		navigate("/")
	}

	// The platform team manages companies, never a company's inventory, so
	// none of these modules are theirs.
	const isPlatformAdmin = Boolean(user?.is_platform_admin)
	const modules = isPlatformAdmin
		? []
		: ALL_MODULES.filter((m) => !m.roles || m.roles.includes(user?.role))
	const accessLevel = isPlatformAdmin ? "PLATFORM" : user?.role

	const firstName = user?.name?.split(" ")[0] || "there"

	return (
		<div className="dashboard-page">
			<header className="dashboard-header">
				<Link to="/" className="site-brand">
					WARE<span>67</span>
				</Link>

				<div className="dashboard-header-right">
					<div className="dashboard-user">
						<span className="dashboard-user-status">
							<i />
							ACTIVE SESSION
						</span>

						<strong>{user?.name || "User"}</strong>
					</div>

					<button
						className="btn btn-outline dashboard-signout"
						onClick={handleLogout}
					>
						Sign out
						<span>↗</span>
					</button>
				</div>
			</header>

			<main>
				<section className="dashboard-welcome">
					<div className="welcome-grid" aria-hidden="true" />

					<div className="welcome-content">
						<div className="dashboard-eyebrow">
							<span>WARE67</span>
							<i />
							<span>OPERATIONS CONSOLE</span>
						</div>

						<h1>
							Welcome back,
							<br />
							<span>{firstName}.</span>
						</h1>

						<div className="dashboard-account-info">
							<div>
								<span>ACCOUNT</span>
								<strong>{user?.email}</strong>
							</div>

							{accessLevel && (
								<div>
									<span>ACCESS LEVEL</span>
									<strong
										className={`role-badge role-badge--${accessLevel.toLowerCase()}`}
									>
										{accessLevel}
									</strong>
								</div>
							)}
						</div>
					</div>

					<div className="welcome-mark" aria-hidden="true">
						W67
					</div>
				</section>

				<section className="dashboard-content">
					<div className="modules-heading">
						<div>
							<span className="section-label">01 / MODULES</span>
							<h2>Operations</h2>
						</div>

						<p>
							{isPlatformAdmin
								? "Platform team accounts manage companies and API keys, not a company's inventory. The platform console is coming next."
								: "Select a module to manage and monitor your warehouse operations."}
						</p>
					</div>

					<div className="dashboard-modules">
						{modules.map((m, index) => {
							const body = (
								<>
									<div className="module-card-top">
										<span className="module-number">
											{String(index + 1).padStart(2, "0")}
										</span>

										<span className="module-icon">{m.icon}</span>
									</div>

									<div className="module-card-content">
										<span className="module-category">
											{m.category}
										</span>

										<h3>{m.title}</h3>

										<p>{m.description}</p>
									</div>

									<div className="module-card-footer">
										<span className="module-status">
											{m.path ? "OPEN MODULE" : "COMING SOON"}
										</span>

										<span className="module-arrow">→</span>
									</div>
								</>
							)

							return m.path ? (
								<Link
									className="module-card module-card--link"
									key={m.key}
									to={m.path}
								>
									{body}
								</Link>
							) : (
								<div className="module-card" key={m.key}>
									{body}
								</div>
							)
						})}
					</div>
				</section>
			</main>

			<footer className="dashboard-footer">
				<span>WARE67 / OPERATIONS PLATFORM</span>
				<span>{modules.length} modules available</span>
			</footer>
		</div>
	)
}