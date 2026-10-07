// Endpoint catalogue for the interactive API docs page.
// Mirrors backend/app/api/v1/endpoints/*. Paths are relative to /api/v1.

const PAGE = [
    { name: "skip", hint: "0" },
    { name: "limit", hint: "50 (max 200)" },
]
const BOOL = "true / false"

const ANY = "Any signed-in user"
const WRITE = "Admin or manager"
const ADMIN = "Admin only"
const PUBLIC = "Public"
const PARTNER = "Partner API key (products:read scope)"

function ep(method, path, summary, o = {}) {
    return {
        id: `${method} ${path}`,
        method,
        path,
        summary,
        access: o.access ?? ANY,
        // "bearer" sends the user's access token, "apiKey" sends X-API-Key, "none" sends neither
        auth: o.auth ?? (o.access === PUBLIC ? "none" : "bearer"),
        query: o.query ?? [],
        body: o.body ?? null,
        notes: o.notes ?? null,
    }
}

// list / get / products / create / update / delete for the simple resources
function resource(base, noun, { listQuery, body, hasProducts = true }) {
    return [
        ep("GET", base, `List ${noun}s (paginated, returns { items, total })`, {
            query: [{ name: "search" }, ...listQuery, ...PAGE],
        }),
        ep("GET", `${base}/{id}`, `Get one ${noun}`),
        ...(hasProducts ? [ep("GET", `${base}/{id}/products`, `Products assigned to this ${noun}`)] : []),
        ep("POST", base, `Create a ${noun}`, { access: WRITE, body }),
        ep("PUT", `${base}/{id}`, `Replace a ${noun}`, {
            access: WRITE,
            body,
            notes: "PUT expects the full object, not just the changed fields.",
        }),
        ep("DELETE", `${base}/{id}`, `Delete a ${noun}`, {
            access: WRITE,
            notes: "Products keep existing; they just lose this link.",
        }),
    ]
}

export const GROUPS = [
    {
        name: "Auth",
        endpoints: [
            ep("POST", "/auth/register", "Create an account (starts as GUEST)", {
                access: PUBLIC,
                body: { name: "Jane Cruz", email: "jane@example.com", password: "changeme123" },
            }),
            ep("POST", "/auth/login", "Exchange email and password for tokens", {
                access: PUBLIC,
                body: { email: "jane@example.com", password: "changeme123" },
                notes: "A successful login fills the token field above automatically.",
            }),
            ep("POST", "/auth/refresh", "Swap a refresh token for a new pair", {
                access: PUBLIC,
                body: { refresh_token: "" },
            }),
            ep("GET", "/auth/me", "The signed-in user and their role"),
            ep("POST", "/auth/forgot-password", "Set a new password from an email address", {
                access: PUBLIC,
                body: { email: "jane@example.com", new_password: "newpass123" },
                notes: "There is no email step on this host, so this changes the password immediately.",
            }),
            ep("POST", "/auth/onboard", "Set a user's role and active flag", {
                access: WRITE,
                body: { user_id: "", role: "STAFF", is_active: true },
            }),
            ep("PATCH", "/auth/update-role", "Change a user's role", {
                access: ADMIN,
                body: { user_id: "", role: "MANAGER" },
            }),
            ep("PATCH", "/auth/update-status", "Activate or deactivate a user", {
                access: WRITE,
                body: { user_id: "", is_active: false },
            }),
        ],
    },
    {
        name: "Users & roles",
        endpoints: [
            ep("GET", "/users", "List all accounts", { access: WRITE }),
            ep("POST", "/users", "Create an account", {
                access: WRITE,
                body: { name: "Sam Reyes", email: "sam@example.com", password: "temp12345", role: "STAFF", is_active: true },
                notes: "Managers can only create GUEST or STAFF accounts.",
            }),
            ep("PATCH", "/users/{user_id}", "Update an account (send only changed fields)", {
                access: WRITE,
                body: { role: "STAFF" },
                notes: "Managers cannot modify admin or manager accounts.",
            }),
            ep("GET", "/roles", "List roles and their descriptions", { access: WRITE }),
            ep("PATCH", "/roles/{role_name}", "Edit a role description", {
                access: ADMIN,
                body: { description: "Can record stock movements." },
                notes: "role_name is GUEST, STAFF, MANAGER or ADMIN.",
            }),
        ],
    },
    {
        name: "Products",
        endpoints: [
            ep("GET", "/products", "List products (returns a plain array)", {
                query: [
                    { name: "search" },
                    { name: "category_id" },
                    { name: "supplier_id" },
                    { name: "location_id" },
                    { name: "low_stock", hint: BOOL },
                    { name: "skip", hint: "0" },
                    { name: "limit", hint: "100 (max 200)" },
                ],
            }),
            ep("GET", "/products/{product_id}", "Get one product"),
            ep("POST", "/products", "Create a product", {
                access: WRITE,
                body: {
                    sku: "SKU-001",
                    name: "Sample product",
                    description: "",
                    category_id: null,
                    supplier_id: null,
                    location_id: null,
                    unit: "pcs",
                    price: "9.99",
                    reorder_level: 5,
                    initial_stock: 20,
                },
                notes: "initial_stock creates an opening STOCK_IN transaction.",
            }),
            ep("PATCH", "/products/{product_id}", "Update a product (send only changed fields)", {
                access: WRITE,
                body: { name: "Renamed product", price: "12.50" },
                notes: "Stock cannot be edited here. Use transactions or adjustments.",
            }),
            ep("DELETE", "/products/{product_id}", "Delete a product", {
                access: WRITE,
                notes: "Fails with 409 if the product has transaction or adjustment history.",
            }),
        ],
    },
    {
        name: "Categories",
        endpoints: resource("/categories", "category", {
            listQuery: [{ name: "has_products", hint: BOOL }],
            body: { name: "Hardware", description: "Fasteners, tools and fittings" },
        }),
    },
    {
        name: "Suppliers",
        endpoints: resource("/suppliers", "supplier", {
            listQuery: [{ name: "has_products", hint: BOOL }, { name: "has_email", hint: BOOL }],
            body: {
                name: "Acme Trading",
                contact_person: "Ana Lim",
                contact_number: "+63 912 345 6789",
                email: "orders@acme.example",
                address: "Cebu City",
            },
        }),
    },
    {
        name: "Locations",
        endpoints: [
            ...resource("/locations", "location", {
                listQuery: [
                    { name: "warehouse" },
                    { name: "aisle" },
                    { name: "shelf" },
                    { name: "has_products", hint: BOOL },
                ],
                body: { name: "Bin A-01", description: "", warehouse: "Main", aisle: "A", shelf: "1", bin: "01" },
            }),
            ep("GET", "/locations/warehouses", "Distinct warehouse names"),
        ],
    },
    {
        name: "Transactions",
        endpoints: [
            ep("GET", "/transactions", "Stock-in and stock-out history", {
                query: [
                    { name: "search" },
                    { name: "product_id" },
                    { name: "type", hint: "STOCK_IN / STOCK_OUT" },
                    { name: "user_id" },
                    { name: "reference_type" },
                    { name: "reference_id" },
                    { name: "date_from", hint: "YYYY-MM-DD" },
                    { name: "date_to", hint: "YYYY-MM-DD" },
                    ...PAGE,
                ],
            }),
            ep("GET", "/transactions/{transaction_id}", "Get one transaction"),
            ep("POST", "/transactions", "Record a stock movement", {
                body: {
                    product_id: "",
                    type: "STOCK_IN",
                    quantity: 10,
                    reference_type: "PO",
                    reference_id: "PO-1001",
                    notes: "",
                },
                notes: "STOCK_OUT returns 409 if it would take stock below zero. The user comes from your token.",
            }),
        ],
    },
    {
        name: "Adjustments",
        endpoints: [
            ep("GET", "/adjustments", "Manual stock corrections", {
                query: [
                    { name: "search" },
                    { name: "product_id" },
                    { name: "user_id" },
                    { name: "reason" },
                    { name: "date_from", hint: "YYYY-MM-DD" },
                    { name: "date_to", hint: "YYYY-MM-DD" },
                    ...PAGE,
                ],
            }),
            ep("GET", "/adjustments/{adjustment_id}", "Get one adjustment"),
            ep("POST", "/adjustments", "Correct stock with a reason", {
                access: WRITE,
                body: { product_id: "", quantity_change: -3, reason: "Damaged", notes: "" },
                notes: "quantity_change is signed and cannot be zero.",
            }),
        ],
    },
    {
        name: "Audit logs",
        endpoints: [
            ep("GET", "/audit-logs", "Who did what, and when", {
                access: ADMIN,
                query: [
                    { name: "search" },
                    { name: "user_id" },
                    { name: "action" },
                    { name: "entity" },
                    { name: "entity_id" },
                    { name: "date_from", hint: "YYYY-MM-DD" },
                    { name: "date_to", hint: "YYYY-MM-DD" },
                    ...PAGE,
                ],
            }),
            ep("GET", "/audit-logs/{log_id}", "Get one audit entry", { access: ADMIN }),
        ],
    },
    {
        name: "API keys",
        endpoints: [
            ep("GET", "/api-keys", "List partner API keys (metadata only)", { access: ADMIN }),
            ep("POST", "/api-keys", "Issue a partner API key", {
                access: ADMIN,
                body: { name: "Partner Project Name", scopes: ["products:read"], expires_at: null },
                notes: "The raw api_key is returned once, only in this response, and fills the API key field above. expires_at is optional and must be in the future.",
            }),
            ep("DELETE", "/api-keys/{api_key_id}", "Revoke a partner API key", {
                access: ADMIN,
                notes: "Revoking is permanent. Partners using the key get 401 immediately.",
            }),
        ],
    },
    {
        name: "Partner integration",
        endpoints: [
            ep("GET", "/integration/products", "Read-only product list for partners", {
                access: PARTNER,
                auth: "apiKey",
                query: [{ name: "search" }, { name: "skip", hint: "0" }, { name: "limit", hint: "100 (max 200)" }],
                notes: "Send the key in the X-API-Key header. User tokens are not accepted here.",
            }),
            ep("GET", "/integration/products/{product_id}", "Read one product as a partner", {
                access: PARTNER,
                auth: "apiKey",
            }),
        ],
    },
]