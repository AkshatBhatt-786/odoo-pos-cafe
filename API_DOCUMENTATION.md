# API Documentation — Odoo POS Cafe

> **Project:** Odoo POS Cafe  
> **Framework:** Django 5.2.12  
> **API Style:** View-based (HTML + AJAX/JSON)  
> **Base URL:** `http://<host>/`  
> **Authors:** Akshat Bhatt (Frontend & Backend), Bhatt Neel (UI/UX Design)

---

## Overview

This system exposes two types of endpoints:

- **Page Endpoints** — Return rendered HTML via Django Templates. Used for full page loads.
- **AJAX Endpoints** — Return `application/json`. Called from JavaScript in the browser for real-time cart and kitchen interactions.

Authentication uses Django's built-in session-based auth. Endpoints marked **Auth Required** will redirect to `/accounts/login/` if the user is not authenticated.

---

## Table of Contents

1. [Authentication APIs](#1-authentication-apis)
2. [Session Management APIs](#2-session-management-apis)
3. [Floor & Table APIs](#3-floor--table-apis)
4. [Order Management APIs](#4-order-management-apis)
5. [Payment APIs](#5-payment-apis)
6. [Kitchen Display APIs](#6-kitchen-display-apis)
7. [Customer Display API](#7-customer-display-api)
8. [Self-Ordering API](#8-self-ordering-api)
9. [Backend Configuration APIs](#9-backend-configuration-apis)
10. [Reports API](#10-reports-api)
11. [Error Handling](#11-error-handling)
12. [Data Models Quick Reference](#12-data-models-quick-reference)

---

## 1. Authentication APIs

Base path: `/accounts/`

---

### `POST /accounts/login/`

Authenticates a user and creates a Django session.

**Auth Required:** No  
**Returns:** HTML redirect on success; HTML page with error on failure.

**Request Body (form-encoded):**

| Field | Type | Required | Description |
|---|---|---|---|
| `username` | string | Yes | The user's login username |
| `password` | string | Yes | The user's password |
| `remember_me` | checkbox | No | If omitted, session expires on browser close |

**Behavior:**
- On success: redirects to `?next=` parameter value, or `/pos/floor/` by default.
- On failure: re-renders login page with generic error message (does not reveal if user exists).
- Already authenticated users are immediately redirected to `/pos/floor/`.

**Example curl:**
```bash
curl -X POST http://localhost:8000/accounts/login/ \
  -d "username=cashier1&password=secret123"
```

---

### `POST /accounts/signup/`

Creates a new user account and automatically logs them in.

**Auth Required:** No  
**Returns:** HTML redirect on success; HTML form with errors on failure.

**Request Body (form-encoded):**

| Field | Type | Required | Description |
|---|---|---|---|
| `username` | string | Yes | Unique login identifier |
| `email` | string | Yes | User email address |
| `password1` | string | Yes | Password |
| `password2` | string | Yes | Password confirmation |
| `role` | string | Yes | One of: `admin`, `manager`, `cashier`, `kitchen` |
| `phone` | string | No | Contact phone number |

**Behavior:**
- On success: creates user, logs them in, redirects to `/pos/floor/`.
- On failure: re-renders form with field-level validation errors.

---

### `GET /accounts/logout/`

Logs the user out and clears their active POS session state.

**Auth Required:** Yes  
**Returns:** Redirect to landing page `/`.

**Side Effects:**
- Sets `user.is_active_session = False`
- Clears `user.current_session_id`
- Terminates the Django session

---

### `GET /accounts/profile/`

Renders the user's profile page.

**Auth Required:** Yes  
**Returns:** HTML page with user profile data.

---

### `POST /accounts/profile/`

Updates user profile fields.

**Auth Required:** Yes  
**Returns:** Redirect to `/accounts/profile/` with a success flash message.

**Request Body (form-encoded):**

| Field | Type | Required | Description |
|---|---|---|---|
| `phone` | string | No | New phone number; keeps existing if omitted |

---

## 2. Session Management APIs

Base path: `/pos/`

A **POS Session** represents a cashier's active shift. Most POS operations require an open session. Sessions are opened at shift start and closed at shift end; closing auto-calculates total sales.

---

### `GET /pos/open-session/`

Opens a new POS session for the logged-in user, or resumes an existing open one. A user can only have one open session at a time.

**Auth Required:** Yes  
**Returns:** Redirect to `/pos/floor/` with a success flash message.

**Session Object Created:**
```json
{
  "id": 12,
  "user": "cashier1",
  "status": "open",
  "opened_at": "2026-04-05T09:30:00Z"
}
```

---

### `POST /pos/close-session/`

Closes the current open session and computes the `closing_sale_amount` from all paid orders in that session.

**Auth Required:** Yes  
**HTTP Method:** POST only (prevents accidental closure via GET)  
**Returns:** Redirect to `/pos/backend/` with a flash message showing closing total.

**What Happens:**
1. Fetches all `Order` records with `status="paid"` linked to this session.
2. Sums their `grand_total` values.
3. Sets `session.closing_sale_amount`, `session.closed_at`, and `session.status = "closed"`.

**Flash Message Example:**
```
Session #12 closed. Total: ₹4,280.50
```

---

## 3. Floor & Table APIs

---

### `GET /pos/floor/`

Renders the visual floor plan showing all active floors and their tables.

**Auth Required:** Yes  
**Returns:** HTML page.

**Context Data:**

| Key | Type | Description |
|---|---|---|
| `session` | POSSession | The user's active session |
| `floors` | QuerySet[Floor] | All active floors with prefetched tables |

Each table in the template exposes:
- `table.number` — Table identifier
- `table.seats` — Seating capacity
- `table.is_occupied` — `true` if an open/sent order exists for this table

---

## 4. Order Management APIs

---

### `GET /pos/order/<table_id>/`

Renders the order entry screen for a specific table. If no active order exists for this table in the current session, a new `Order` is automatically created.

**Auth Required:** Yes  
**URL Parameter:** `table_id` (integer) — ID of the Table record  
**Returns:** HTML page.

**Context Data:**

| Key | Type | Description |
|---|---|---|
| `session` | POSSession | Active session |
| `table` | Table | The selected table |
| `order` | Order | Current open/sent order |
| `categories` | QuerySet[Category] | Menu categories with available products |
| `lines` | QuerySet[OrderLine] | Current order items |

**Order Creation Logic:**
- Looks for an existing order with `status in ["open", "sent"]` for this table + session.
- If none found, creates a new `Order` with `status="open"`.

---

### `POST /pos/order/<order_id>/add/`

Adds a product (with optional variant) to an order. If the same product+variant combination already exists in the order, its quantity is incremented by 1 instead of creating a duplicate line.

**Auth Required:** Yes  
**HTTP Method:** POST  
**Content-Type:** `application/x-www-form-urlencoded`  
**Returns:** JSON

**Request Parameters:**

| Field | Type | Required | Description |
|---|---|---|---|
| `product_id` | integer | Yes | ID of the Product to add |
| `variant_id` | integer | No | ID of ProductVariant; applies extra price |

**Success Response `200 OK`:**
```json
{
  "ok": true,
  "line_id": 42,
  "qty": 2,
  "line_total": "280.00",
  "subtotal": "560.00",
  "tax_total": "44.80",
  "grand_total": "604.80"
}
```

**Error Conditions:**
- `403` or redirect if user is not authenticated
- `404` if `product_id` doesn't exist or product is unavailable
- `404` if `variant_id` is provided but doesn't belong to the product
- `404` if order doesn't belong to the logged-in user's session

**Price Calculation:**
```
unit_price = product.price + (variant.extra_price if variant else 0)
```

---

### `POST /pos/line/<line_id>/update/`

Updates the quantity of an existing order line. Setting quantity to `0` (or any negative value) deletes the line entirely. Order totals are recalculated after each update.

**Auth Required:** Yes  
**HTTP Method:** POST  
**Content-Type:** `application/x-www-form-urlencoded`  
**Returns:** JSON

**Request Parameters:**

| Field | Type | Required | Description |
|---|---|---|---|
| `qty` | integer | Yes | New quantity; set to 0 to remove the line |

**Success Response `200 OK` — Line Updated:**
```json
{
  "ok": true,
  "qty": 3,
  "line_total": "420.00",
  "subtotal": "840.00",
  "tax_total": "67.20",
  "grand_total": "907.20"
}
```

**Success Response `200 OK` — Line Deleted (qty ≤ 0):**
```json
{
  "ok": true,
  "grand_total": "484.00",
  "subtotal": "420.00",
  "tax_total": "33.60"
}
```

---

### `POST /pos/order/<order_id>/send/`

Sends the order to the kitchen by changing its status to `"sent"` and creating a `KitchenTicket`. Once sent, the order is locked from casual editing.

**Auth Required:** Yes  
**HTTP Method:** POST  
**Returns:** Redirect to the order screen for the same table.

**Preconditions:**
- Order must belong to the logged-in user's session.
- Order must have at least one line item (empty orders are rejected with an error flash).

**Side Effects:**
- `order.status` → `"sent"`
- `KitchenTicket` created with `stage = "to_cook"` (idempotent — `get_or_create` is used)

**Flash Message on Empty Order:**
```
Cannot send empty order to kitchen.
```

---

## 5. Payment APIs

---

### `GET /pos/payment/<order_id>/`

Renders the payment screen showing order summary and available payment methods. If UPI is enabled and configured, a QR code image URL is generated.

**Auth Required:** Yes  
**Returns:** HTML page.

**Context Data:**

| Key | Type | Description |
|---|---|---|
| `order` | Order | The order being paid |
| `lines` | QuerySet[OrderLine] | Line items |
| `payment_methods` | QuerySet[PaymentMethod] | All enabled payment methods |
| `upi_method` | PaymentMethod | UPI method if enabled, else None |
| `qr_url` | string | QR code image URL for UPI, else None |

**UPI QR Code URL Format:**
```
https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=upi://pay
  ?pa=<upi_id>
  &pn=CafePOS
  &am=<grand_total>
  &tn=Table<table_number>
  &cu=INR
```

---

### `POST /pos/payment/<order_id>/process/`

Processes payment for an order: sets the payment method and marks the order as `"paid"`.

**Auth Required:** Yes  
**HTTP Method:** POST  
**Content-Type:** `application/x-www-form-urlencoded`  
**Returns:** Redirect to `/pos/payment/<order_id>/confirm/` on success.

**Request Parameters:**

| Field | Type | Required | Description |
|---|---|---|---|
| `method` | string | Yes | One of: `cash`, `digital`, `upi` |

**Validation:**
- Only payment methods currently flagged `is_enabled=True` are accepted.
- An invalid or disabled method redirects back to the payment screen with an error.

**Side Effects:**
- `order.payment_method` set to provided method
- `order.status` → `"paid"`

---

### `GET /pos/payment/<order_id>/confirm/`

Renders the receipt/confirmation screen after a successful payment.

**Auth Required:** Yes  
**Returns:** HTML page.

**Precondition:** Order must have `status="paid"` and belong to the current user's session. Returns `404` otherwise.

---

## 6. Kitchen Display APIs

Kitchen views are **intentionally unauthenticated** — the kitchen display runs as a kiosk on a dedicated tablet that kitchen staff interact with directly.

---

### `GET /pos/kitchen/`

Renders the kitchen display system showing all active (non-completed) tickets and the 10 most recently completed tickets for reference.

**Auth Required:** No (kiosk-style)  
**Returns:** HTML page (auto-refreshing in browser).

**Context Data:**

| Key | Type | Description |
|---|---|---|
| `tickets` | QuerySet[KitchenTicket] | All tickets with `stage != "completed"`, oldest first (FIFO) |
| `completed` | QuerySet[KitchenTicket] | Last 10 completed tickets, newest first |

Each ticket includes the associated order's table info and all line items.

---

### `POST /pos/kitchen/ticket/<ticket_id>/advance/`

Advances a kitchen ticket to the next stage in the state machine.

**State Machine:**
```
to_cook → preparing → completed
```

**Auth Required:** No  
**HTTP Method:** POST  
**Returns:** JSON

**URL Parameter:** `ticket_id` (integer)

**Success Response `200 OK`:**
```json
{
  "ok": true,
  "stage": "preparing"
}
```

Calling `advance()` on a `completed` ticket is a no-op (stage stays `completed`).

---

### `POST /pos/kitchen/line/<line_id>/prepared/`

Toggles the `is_prepared` flag on a specific order line. Kitchen staff use this to mark individual items as done (shown as a strikethrough in the UI).

**Auth Required:** No  
**HTTP Method:** POST  
**Returns:** JSON

**URL Parameter:** `line_id` (integer)

**Success Response `200 OK`:**
```json
{
  "ok": true,
  "prepared": true
}
```

Calling again toggles back to `false` (it's a true boolean toggle).

---

## 7. Customer Display API

---

### `GET /pos/customer/<order_id>/`

Renders a clean, read-only view of an order for a customer-facing screen (e.g., a second monitor or TV in the dining area).

**Auth Required:** No  
**Returns:** HTML page.

**Context Data:**

| Key | Type | Description |
|---|---|---|
| `order` | Order | The order to display |
| `lines` | QuerySet[OrderLine] | Line items with product names and quantities |

---

## 8. Self-Ordering API

Customers scan a QR code printed on their table (or generated by the cashier). The QR code encodes a UUID token unique to their order, giving them access to self-ordering without any login.

---

### `GET /pos/self-order/<token>/`

Renders the customer-facing self-order menu. Customers can browse the full menu and add items.

**Auth Required:** No  
**URL Parameter:** `token` (UUID) — The `self_order_token` from the Order  
**Returns:** HTML page.

**Context Data:**

| Key | Type | Description |
|---|---|---|
| `order` | Order | The customer's order |
| `categories` | QuerySet[Category] | All categories with available products |
| `lines` | QuerySet[OrderLine] | Items already in the order |

---

### `POST /pos/self-order/<token>/`

Adds a product to the customer's order. If this is the first item, the order is automatically sent to the kitchen (status transitions from `open` → `sent` and a `KitchenTicket` is created).

**Auth Required:** No  
**HTTP Method:** POST  
**Content-Type:** `application/x-www-form-urlencoded`  
**Returns:** HTML page (re-renders self_order.html with updated state)

**Request Parameters:**

| Field | Type | Required | Description |
|---|---|---|---|
| `product_id` | integer | Yes | Product to add to the order |

**Auto-Kitchen Logic:**
```python
if order.status == "open":
    order.status = "sent"
    KitchenTicket.objects.get_or_create(order=order)
```

Customers can continue adding items to a `sent` order — each new POST recalculates totals but does not re-fire kitchen ticket creation (idempotent).

---

## 9. Backend Configuration APIs

---

### `GET /pos/backend/`

Renders the manager configuration dashboard showing system status, session info, and menu/table counts.

**Auth Required:** Yes  
**Returns:** HTML page.

**Context Data:**

| Key | Type | Description |
|---|---|---|
| `session` | POSSession or None | User's current open session |
| `last_closed` | POSSession or None | Most recently closed session |
| `product_count` | integer | Total product count |
| `category_count` | integer | Total category count |
| `floor_count` | integer | Active floor count |
| `table_count` | integer | Active table count |
| `payment_methods` | QuerySet | All payment method configurations |
| `floors` | QuerySet | Active floors with tables |
| `products` | QuerySet | All products with categories |
| `categories` | QuerySet | All categories |

---

### `POST /pos/backend/payment/<pm_id>/toggle/`

Toggles the `is_enabled` flag on a payment method. Used to quickly disable a payment type if a card machine goes down or UPI gateway is unavailable.

**Auth Required:** Yes  
**HTTP Method:** POST  
**Returns:** JSON

**URL Parameter:** `pm_id` (integer) — ID of the PaymentMethod

**Success Response `200 OK`:**
```json
{
  "ok": true,
  "enabled": false
}
```

Subsequent call toggles it back:
```json
{
  "ok": true,
  "enabled": true
}
```

---

## 10. Reports API

---

### `GET /pos/reports/`

Returns a filtered, aggregated sales report. Only `paid` orders are included.

**Auth Required:** Yes  
**Returns:** HTML page with totals and order list.

**Query Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `period` | string | `today` | `today`, `week`, or `custom` |
| `date_from` | date | — | Start date (`YYYY-MM-DD`), used when `period=custom` |
| `date_to` | date | — | End date (`YYYY-MM-DD`), used when `period=custom` |
| `session_id` | integer | — | Filter by a specific POS session ID |
| `responsible_id` | integer | — | Filter by cashier (user) ID |
| `product_id` | integer | — | Filter orders containing a specific product |

**Context Data:**

| Key | Type | Description |
|---|---|---|
| `orders` | QuerySet | Up to 50 paid orders, newest first |
| `total_revenue` | Decimal | Sum of `grand_total` across filtered orders |
| `total_orders` | integer | Count of distinct filtered orders |
| `period` | string | Applied period filter |
| `sessions` | QuerySet | Last 20 POS sessions (for filter dropdown) |
| `users` | QuerySet | Users with POS sessions (for cashier filter) |
| `products` | QuerySet | All products (for product filter) |
| `selected_session` | string | Currently applied session filter |
| `selected_responsible` | string | Currently applied cashier filter |
| `selected_product` | string | Currently applied product filter |

**Example Requests:**

```
GET /pos/reports/?period=today
GET /pos/reports/?period=week
GET /pos/reports/?period=custom&date_from=2026-04-01&date_to=2026-04-05
GET /pos/reports/?period=today&responsible_id=3
GET /pos/reports/?period=week&product_id=12
```

---

## 11. Error Handling

### Authentication Errors

All `@login_required` endpoints redirect to `/accounts/login/?next=<original_url>` if the user is not authenticated.

### 404 Responses

`get_object_or_404()` is used throughout. If a record is not found or the user doesn't have access (e.g., order belonging to a different user's session), Django returns a standard `404 Not Found` page.

### Validation Errors (AJAX Endpoints)

AJAX endpoints do not currently return structured error objects. On invalid input (e.g., missing `product_id`), a `400` or `404` response is returned. Frontend JS should handle these gracefully.

### Flash Messages

Page-returning views use Django's `messages` framework for feedback:

| Type | Trigger |
|---|---|
| `success` | Session opened, payment confirmed, order sent |
| `error` | Empty order sent to kitchen, invalid payment method |
| `info` | Session closed, user logged out |

---

## 12. Data Models Quick Reference

```
User
├── username, email, password (inherited from AbstractUser)
├── role: admin | manager | cashier | kitchen
├── phone
├── is_active_session
└── current_session_id

Floor
└── Tables[]
    └── Orders[] (via session)

Category
└── Products[]
    └── ProductVariants[]

POSSession (user's shift)
└── Orders[]
    └── OrderLines[]
        ├── product → Product
        └── variant → ProductVariant (optional)
    └── KitchenTicket (1-to-1)

PaymentMethod
└── type: cash | digital | upi
└── upi_id (for QR generation)
```

### Order Status Flow

```
open → sent → paid
            → cancelled
```

### Kitchen Ticket Stage Flow

```
to_cook → preparing → completed
```

---

*API documentation for Odoo POS Cafe.*