// Endpoint catalogue for the interactive API docs page.
// Mirrors backend/app/api/v1/endpoints/*. Paths are relative to /api/v1.

const PAGE = [
    { name: "skip", hint: "0" },
    { name: "limit", hint: "50 (max 200)" },
]
const BOOL = "true / false"

// Every company route only ever sees the caller's own company's data.
const ANY = "Any member of the company"
const WRITE = "Owner, admin or manager"
const ADMIN = "Owner or admin"
const OWNER = "Company owner"
const PLATFORM = "WARE67 platform team"
const PUBLIC = "Public"
const partner = (scope) => `Partner API key (${scope} scope)`
const READ_SCOPE = partner("products:read")

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
            ep("POST", "/auth/register", "Sign up a company (you become its OWNER)", {
                access: PUBLIC,
                body: { company_name: "Cruz Hardware", name: "Jane Cruz", email: "jane@example.com", password: "changeme123" },
                notes: "Creates a new company. Teammates are added afterwards with POST /users.",
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
            ep("POST", "/auth/onboard", "Set a user's role and active flag", {
                access: WRITE,
                body: { user_id: "", role: "STAFF", is_active: true },
                notes: "Owners can assign any role, admins any but OWNER, managers only GUEST and STAFF. Only users in your own company can be found.",
            }),
            ep("PATCH", "/auth/update-role", "Change a user's role", {
                access: ADMIN,
                body: { user_id: "", role: "MANAGER" },
            }),
            ep("PATCH", "/auth/update-status", "Activate or deactivate a user", {
                access: WRITE,
                body: { user_id: "", is_active: false },
                notes: "Managers can only change guest and staff accounts; only owners can change owners. Nobody can deactivate themselves.",
            }),
        ],
    },
    {
        name: "Users & roles",
        endpoints: [
            ep("GET", "/users", "List your company's accounts", { access: WRITE }),
            ep("POST", "/users", "Create an account", {
                access: WRITE,
                body: { name: "Sam Reyes", email: "sam@example.com", password: "temp12345", role: "STAFF", is_active: true },
                notes: "The account joins your company. Managers can only create GUEST or STAFF accounts; only owners can create OWNER accounts.",
            }),
            ep("PATCH", "/users/{user_id}", "Update an account (send only changed fields)", {
                access: WRITE,
                body: { role: "STAFF" },
                notes: "Managers can only modify guest and staff accounts; only owners can modify owners. Nobody can lower their own role.",
            }),
            ep("GET", "/roles", "List roles and their descriptions", { access: WRITE }),
            ep("PATCH", "/roles/{role_name}", "Edit a role description", {
                access: PLATFORM,
                body: { description: "Can record stock movements." },
                notes: "role_name is GUEST, STAFF, MANAGER, ADMIN or OWNER. Descriptions are shared by every company.",
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
                access: "Staff, manager or admin",
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
        name: "Company",
        endpoints: [
            ep("GET", "/company", "Your company"),
            ep("PATCH", "/company", "Rename your company", {
                access: OWNER,
                body: { name: "Cruz Hardware Inc." },
            }),
        ],
    },
    {
        name: "Platform",
        endpoints: [
            ep("GET", "/platform/companies", "All companies, with member counts", {
                access: PLATFORM,
                query: [{ name: "search" }, { name: "is_active", hint: BOOL }, ...PAGE],
            }),
            ep("GET", "/platform/companies/{company_id}", "One company", { access: PLATFORM }),
            ep("PATCH", "/platform/companies/{company_id}", "Rename, deactivate or reactivate a company", {
                access: PLATFORM,
                body: { is_active: false },
                notes: "A deactivated company's members can't sign in and its API keys stop working immediately.",
            }),
            ep("GET", "/platform/audit-logs", "Platform-level audit log (companies and API keys)", {
                access: PLATFORM,
                query: [
                    { name: "search" },
                    { name: "action" },
                    { name: "entity", hint: "COMPANY / API_KEY" },
                    { name: "date_from", hint: "YYYY-MM-DD" },
                    { name: "date_to", hint: "YYYY-MM-DD" },
                    ...PAGE,
                ],
                notes: "Never includes product, stock or user activity inside companies.",
            }),
            ep("GET", "/platform/audit-logs/{log_id}", "One platform audit entry", { access: PLATFORM }),
        ],
    },
    {
        name: "API keys",
        endpoints: [
            ep("GET", "/company/api-keys", "Your company's keys and key requests", {
                access: ADMIN,
                query: PAGE,
                notes: "status is PENDING, APPROVED, REJECTED, ACTIVE, REVOKED, LAPSED (approved but not revealed in time) or EXPIRED. Never includes the key itself.",
            }),
            ep("POST", "/company/api-keys", "Request a partner API key", {
                access: ADMIN,
                body: { name: "Partner Project Name", scopes: ["products:read"], purpose: "Sync our online shop's catalogue" },
                notes: "Scopes are products:read, products:create, products:update and products:delete; ask only for what the integration needs. The WARE67 team reviews the request; no key exists until you reveal it.",
            }),
            ep("POST", "/company/api-keys/{api_key_id}/reveal", "Reveal an approved key (once)", {
                access: ADMIN,
                notes: "Generates the key and returns it in api_key, exactly once, and fills the API key field above. It works for 90 days from now. Reveal within 7 days of approval or the approval lapses.",
            }),
            ep("DELETE", "/company/api-keys/{api_key_id}", "Withdraw a request or revoke a key", {
                access: ADMIN,
                notes: "Revoking is permanent; partners using the key get 401 immediately. Revoking twice returns 409.",
            }),
            ep("GET", "/platform/api-keys", "All keys and requests (status=PENDING is the review queue)", {
                access: PLATFORM,
                query: [{ name: "status", hint: "PENDING / APPROVED / ACTIVE / ..." }, { name: "company_id" }, ...PAGE],
            }),
            ep("GET", "/platform/api-keys/expiring", "Live keys expiring soon", {
                access: PLATFORM,
                query: [{ name: "days", hint: "14 (max 90)" }],
            }),
            ep("GET", "/platform/api-keys/{api_key_id}", "One key or request", { access: PLATFORM }),
            ep("POST", "/platform/api-keys/{api_key_id}/approve", "Approve a request", {
                access: PLATFORM,
                body: { scopes: ["products:read"] },
                notes: "Leave scopes out to grant everything requested, or list fewer. You can't grant scopes that weren't requested.",
            }),
            ep("POST", "/platform/api-keys/{api_key_id}/reject", "Reject a request", {
                access: PLATFORM,
                body: { reason: "Please request read-only access first." },
                notes: "The company sees the reason.",
            }),
            ep("DELETE", "/platform/api-keys/{api_key_id}", "Revoke any key or request", { access: PLATFORM }),
        ],
    },
    {
        name: "Partner integration",
        endpoints: [
            ep("GET", "/integration/products", "Product list for partners", {
                access: READ_SCOPE,
                auth: "apiKey",
                query: [
                    { name: "search" },
                    { name: "category_id" },
                    { name: "supplier_id" },
                    { name: "location_id" },
                    { name: "low_stock", hint: BOOL },
                    { name: "skip", hint: "0" },
                    { name: "limit", hint: "100 (max 200)" },
                ],
                notes: "Send the key in the X-API-Key header. A key only sees its own company's data. User tokens are not accepted on /integration routes. Each key may make 120 requests per minute; past that you get 429 with a Retry-After header.",
            }),
            ep("GET", "/integration/products/{product_id}", "Read one product as a partner", {
                access: READ_SCOPE,
                auth: "apiKey",
            }),
            ep("POST", "/integration/products", "Create a product as a partner", {
                access: partner("products:create"),
                auth: "apiKey",
                body: {
                    sku: "SKU-PARTNER-001",
                    name: "Partner product",
                    description: "",
                    category_id: null,
                    supplier_id: null,
                    location_id: null,
                    unit: "pcs",
                    price: "9.99",
                    reorder_level: 5,
                    initial_stock: 0,
                },
                notes: "Recorded as the API key, in its company's audit log and ledger. initial_stock creates an opening STOCK_IN transaction.",
            }),
            ep("PATCH", "/integration/products/{product_id}", "Update a product as a partner (send only changed fields)", {
                access: partner("products:update"),
                auth: "apiKey",
                body: { name: "Renamed partner product", price: "12.50" },
                notes: "Stock cannot be edited here.",
            }),
            ep("DELETE", "/integration/products/{product_id}", "Delete a product as a partner", {
                access: partner("products:delete"),
                auth: "apiKey",
                notes: "Fails with 409 if the product has transaction or adjustment history.",
            }),
            ep("GET", "/integration/categories", "Categories, for filling category_id", { access: READ_SCOPE, auth: "apiKey" }),
            ep("GET", "/integration/suppliers", "Suppliers, for filling supplier_id", { access: READ_SCOPE, auth: "apiKey" }),
            ep("GET", "/integration/locations", "Locations, for filling location_id", { access: READ_SCOPE, auth: "apiKey" }),
        ],
    },
]