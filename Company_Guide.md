# Getting Started with WARE67

WARE67 is a warehouse and inventory system for your business: products,
suppliers, storage locations, stock movements and a full history of who did
what. This guide takes you from signing up to connecting your own systems
through the WARE67 API.

- **App:** https://ware67.dcism.org
- **API:** https://ware67-api.dcism.org/api/v1
- **Interactive API reference:** https://ware67.dcism.org/api-docs

> **Your data is private.** Each company only ever sees its own products,
> stock, people and history. Not even the WARE67 team can browse your
> inventory.

---

## 1. Sign up your company

1. Open https://ware67.dcism.org and click **Get started**.
2. Fill in:
   - **Company name**: your business name.
   - **Your full name**, **email** and **password** (at least 8 characters).
3. Click **Create account**, then sign in.

Signing up creates your company and makes you its **Owner**, the account with
full control. Do this once per business; your teammates don't sign up
themselves (see step 3).

## 2. Find your way around

After signing in you land on your **dashboard**. Each card opens one part of
the app. You only see the cards your role allows (see
[Roles](#roles-who-can-do-what)).

| Module | What it's for |
| ------ | ------------- |
| **Products** | Your items: SKU, name, price, unit, reorder level and current stock |
| **Categories** | Group products (e.g. "Hardware", "Beverages") |
| **Suppliers** | Who you buy from, with contact details |
| **Locations** | Where things are stored: warehouse, aisle, shelf, bin |
| **Transactions** | Stock coming in and going out |
| **Inventory Adjustments** | Corrections, with a reason (damaged, recount, expired…) |
| **Audit Logs** | Who did what, and when |
| **Users & Roles** | Add teammates and set what they can do |
| **API Keys** | Connect your other systems to WARE67 |

## 3. Add your team

Teammates are added by you rather than signing up, so they automatically join
your company.

1. Open **Users & Roles** and click **+ New user**.
2. Enter their name, email and a temporary password, and choose a role.
3. Share the temporary password with them through a channel you trust.

From the same page you can change someone's role, reset their password or
deactivate their account when they leave. Deactivated people can't sign in,
but everything they did stays in the history.

### Roles: who can do what

| Role | Inventory | Record stock in/out | Corrections | Manage people | Audit logs | API keys |
| ---- | --------- | ------------------- | ----------- | ------------- | ---------- | -------- |
| **Owner** | Full | ✅ | ✅ | Everyone | ✅ | ✅ |
| **Admin** | Full | ✅ | ✅ | Everyone except owners | ✅ | ✅ |
| **Manager** | Full | ✅ | ✅ | Staff and guests | ❌ | ❌ |
| **Staff** | View | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Guest** | View | ❌ | ❌ | ❌ | ❌ | ❌ |

A few rules keep your company safe:

- Only an **Owner** can make someone else an Owner, or change an Owner's account.
- Nobody can lower their own role or deactivate themselves, so your company
  always keeps at least one Owner.
- **Forgot a password?** There are no self-service resets. Ask an Owner,
  Admin or Manager in your company to set a temporary one for you from
  **Users & Roles** (Managers can reset staff and guest accounts only).

## 4. Set up your inventory

A good order to set things up:

1. **Categories**, **Suppliers** and **Locations** first, so you can pick them
   when adding products.
2. **Products**: give each a SKU (unique within your company), name, price
   and **reorder level**. Use **opening stock** to record what you already
   have on hand; it's saved as the first stock-in.
3. Use the **low stock** filter on Products to see everything at or below its
   reorder level.

### Changing stock

Stock can't be typed over directly. Every change is recorded, so your numbers
always add up:

- **Transactions**: everyday movement. Choose **Stock in** (deliveries,
  returns) or **Stock out** (sales, usage). Add a reference such as a purchase
  order (`PO`) or sales order (`SO`) number to find it later.
- **Inventory Adjustments**: corrections after a count, or for damaged or
  expired goods. A reason is required.

WARE67 won't let stock go below zero; it tells you how much is on hand
instead.

A product with stock history can't be deleted, which keeps your records
complete. Deleting a category, supplier or location just unassigns it from its
products.

## 5. Connect your other systems (API keys)

If you run an online shop, a point-of-sale system or your own app, it can read
and update your WARE67 products through the API using an **API key**. Only
**Owners** and **Admins** can manage keys.

### Step 1: Request a key

1. Open **API Keys** and click **+ Request key**.
2. Give it a name (e.g. "Online shop sync") and say what it's for.
3. Tick only the access the integration needs:

   | Access | Lets the key… |
   | ------ | ------------- |
   | Read products | List and view products, categories, suppliers and locations |
   | Create products | Add new products, with opening stock |
   | Update products | Change product details (not stock) |
   | Delete products | Remove products that have no stock history |

4. Click **Send request**. It shows as **Waiting for review**.

### Step 2: Wait for approval

The WARE67 team reviews each request. They may approve it, approve it with
less access than you asked for, or reject it with a reason, which you'll see
on the API Keys page.

### Step 3: Reveal your key, once

When the status says **Ready to reveal**, click **Reveal key**. You have
**7 days** to do this before the approval lapses.

> ⚠️ **The key is shown exactly once.** Nobody can show it to you again,
> including the WARE67 team. Have your server's settings or your password
> manager open before you reveal it, and click **Copy** straight away.

Your key looks like `ware67_1a2b3c4d5e6f_...` and works for **90 days**.

### Step 4: Use it

Send the key in the `X-API-Key` header from your **server**:

```bash
curl -H "X-API-Key: YOUR_API_KEY" \
  "https://ware67-api.dcism.org/api/v1/integration/products"
```

Create a product (needs *Create products* access):

```bash
curl -X POST \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"sku":"SHOP-001","name":"Blue Mug","price":"9.99","initial_stock":25}' \
  "https://ware67-api.dcism.org/api/v1/integration/products"
```

Available endpoints:

| Method | Path | Access needed |
| ------ | ---- | ------------- |
| `GET` | `/integration/products` | Read |
| `GET` | `/integration/products/{id}` | Read |
| `POST` | `/integration/products` | Create |
| `PATCH` | `/integration/products/{id}` | Update |
| `DELETE` | `/integration/products/{id}` | Delete |
| `GET` | `/integration/categories`, `/suppliers`, `/locations` | Read (use these to get IDs for products) |

`GET /integration/products` supports `search`, `category_id`, `supplier_id`,
`location_id`, `low_stock=true`, and paging with `skip` and `limit` (up to 200).

You can try every endpoint in the browser at
https://ware67.dcism.org/api-docs.

### Errors you might see

| Status | Meaning | What to do |
| ------ | ------- | ---------- |
| `401` | Key missing, wrong, revoked or expired | Check the header; request a new key if it expired |
| `403` | The key doesn't have the access this call needs | Request a key with that access |
| `404` | Not found | The ID is wrong, or belongs to another company |
| `409` | Conflict | e.g. the SKU already exists, or the product has stock history |
| `429` | Too many requests | Wait the number of seconds in the `Retry-After` header. Each key can make 120 requests a minute. |

### Keeping your key safe

A key can change your products, so treat it like a password:

- ✅ Keep it in a server environment variable or a secrets manager.
- ❌ Never put it in a website's JavaScript, a mobile app, or a code
  repository. Anything sent to a customer's device can be copied.
- 🚨 **If it leaks**, open **API Keys** and click **Revoke**. It stops working
  immediately.

### Renewing before it expires

Keys work for 90 days. Before yours expires: request a new key, wait for
approval, reveal it, switch your system over, then revoke the old key. Both
keys work in the meantime, so there's no downtime.

---

## Quick reference

| I want to… | Go to |
| ---------- | ----- |
| Add a teammate | Users & Roles → **+ New user** |
| Reset someone's password | Users & Roles → **Reset password** |
| Record a delivery or sale | Transactions → Stock in / Stock out |
| Fix stock after a count | Inventory Adjustments |
| See what's running low | Products → **low stock** filter |
| See who changed something | Audit Logs (Owners and Admins) |
| Connect another system | API Keys → **+ Request key** |
| Stop a leaked key | API Keys → **Revoke** |
