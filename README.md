# ☕ Odoo POS Cafe

> A full-featured, web-based Point-of-Sale system built with Django — designed specifically for cafes and restaurants. Handles everything from table management and kitchen display to self-ordering via QR codes and sales reporting.

---

## 👥 Team

| Role | Name |
|---|---|
| FullStack Development | Akshat Bhatt |
| UI/UX Design | Bhatt Neel |

---

## 📋 Problem Statement

Modern cafes and small restaurants often struggle with fragmented operations — orders get lost between front-of-house and kitchen, payment reconciliation at shift-end is manual and error-prone, and customer wait times increase due to miscommunication. Off-the-shelf POS solutions like Odoo are expensive, bloated, and require heavy configuration.

**Odoo POS Cafe** solves this by providing a lightweight, purpose-built POS web application that mirrors the core workflows of enterprise restaurant software, but is deployable on any machine with Python — no licensing fees, no heavy setup.

### Core Problems Addressed

**1. Order Chaos Between Staff and Kitchen**
Waitstaff taking orders on paper leads to mistakes and delays. This system introduces a real-time Kitchen Display System (KDS) where orders flow digitally from the cashier's tablet to the kitchen screen the moment they are placed, with stage tracking (To Cook → Preparing → Completed).

**2. No Table-Level Order Tracking**
Without a POS, it's impossible to know at a glance which tables are occupied, what they've ordered, and what's still pending in the kitchen. This system provides a visual floor plan with live occupancy status for every table across multiple floors.

**3. Manual Shift Reconciliation**
At the end of every shift, cashiers need to report total sales. Without tooling, this means manually tallying receipts. POS Sessions in this system automatically calculate closing sales amounts from all paid orders when a session is closed.

**4. No Self-Ordering Option**
Busy cafes lose sales when customers have to wait for a waiter. This system lets customers scan a QR code on their table and place orders directly from their phone — orders are automatically sent to the kitchen.

**5. Fragmented Payment Handling**
This system supports Cash, Digital/Card, and UPI QR code payments out of the box, with dynamically generated UPI QR codes that pre-fill the payment amount — reducing errors and speeding up checkout.

---

## 🏗️ Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.x |
| Web Framework | Django 5.2.12 |
| Database | SQLite (dev) / PostgreSQL-compatible |
| ORM | Django ORM |
| Auth | Django Custom AbstractUser |
| Image Handling | Pillow 12.2.0 |
| QR Codes | qrcode 8.2, external QR API (qrserver.com) |
| ASGI Server | ASGIref 3.11.1 |
| Frontend | Vanilla HTML/CSS/JS, Django Templates |
| Static/Media | Django staticfiles + media serving |

---

## 📁 Project Structure

```
odoo-pos-cafe/
├── core/                        # Django project configuration
│   ├── settings.py              # App settings, installed apps, DB config
│   ├── urls.py                  # Root URL dispatcher
│   ├── wsgi.py                  # WSGI entry point
│   └── asgi.py                  # ASGI entry point
│
├── accounts/                    # Authentication & user management app
│   ├── models.py                # Custom User model (role-based)
│   ├── views.py                 # Login, signup, logout, profile views
│   ├── forms.py                 # SignupForm with custom fields
│   ├── urls.py                  # Auth URL patterns
│   ├── admin.py                 # Admin registration
│   └── templates/
│       └── accounts/
│           ├── login.html
│           └── signup.html
│
├── pos/                         # Core POS application
│   ├── models.py                # All domain models (Floor, Table, Order, etc.)
│   ├── views.py                 # All POS views and API endpoints
│   ├── urls.py                  # POS URL patterns
│   ├── admin.py                 # Admin panel configuration
│   └── templates/
│       └── pos/
│           ├── floor.html           # Table map / floor view
│           ├── order.html           # Order entry screen
│           ├── payment.html         # Payment selection
│           ├── payment_confirm.html # Receipt / confirmation
│           ├── kitchen.html         # Kitchen display system
│           ├── customer_display.html# Customer-facing order screen
│           ├── self_order.html      # QR code self-ordering
│           ├── backend.html         # Manager dashboard
│           └── reports.html         # Sales reports
│
├── management/                  # Custom Django management commands
│   └── commands/
│       └── seed_cafe_data.py    # Seeds demo menu, tables, and floors
│
├── static/
│   ├── css/
│   │   ├── base.css
│   │   ├── landing.css
│   │   └── nav.css
│   └── images/                  # Product images (static copy)
│
├── media/
│   └── product_images/          # Uploaded product images (runtime)
│
├── .env                         # Environment variables (do not commit)
├── requirements.txt             # Python dependencies
├── manage.py                    # Django management script
├── db.sqlite3                   # SQLite database (dev only)
└── seed_cafe_data.py            # Standalone seeder script
```

---

## 🗄️ Data Models

### `User` (accounts app)
Extends Django's `AbstractUser` with restaurant-specific roles.

| Field | Type | Description |
|---|---|---|
| `username` | CharField | Login identifier (inherited) |
| `role` | CharField | One of: `admin`, `manager`, `cashier`, `kitchen` |
| `phone` | CharField | Optional contact number |
| `is_active_session` | BooleanField | Whether user has an open POS session |
| `current_session_id` | IntegerField | FK reference to active session |
| `created_at` | DateTimeField | Account creation timestamp |
| `updated_at` | DateTimeField | Last profile update timestamp |

---

### `Floor`
Represents a physical level in the restaurant (Ground, Rooftop, etc.)

| Field | Type | Description |
|---|---|---|
| `name` | CharField | Display name (e.g. "Ground Floor") |
| `is_active` | BooleanField | Soft delete flag |
| `created_at` | DateTimeField | Auto-populated |

---

### `Table`
A physical table on a floor that customers sit at.

| Field | Type | Description |
|---|---|---|
| `floor` | FK → Floor | Which floor this table is on |
| `number` | PositiveIntegerField | Table number (unique per floor) |
| `seats` | PositiveIntegerField | Seating capacity |
| `is_active` | BooleanField | Soft delete flag |
| `is_occupied` | property | `True` if an open/sent order exists on this table |

---

### `Category`
Menu section grouping (e.g. Beverages, Snacks, Desserts).

| Field | Type | Description |
|---|---|---|
| `name` | CharField | Category display name |
| `send_to_kitchen` | BooleanField | If `False`, item skips kitchen (e.g. bottled drinks) |
| `display_order` | PositiveIntegerField | Custom sort order in UI |

---

### `Product`
An individual menu item.

| Field | Type | Description |
|---|---|---|
| `name` | CharField | Item name |
| `image` | ImageField | Product photo |
| `category` | FK → Category | Menu section |
| `price` | DecimalField | Base price (before tax) |
| `unit` | CharField | Unit of sale (piece, plate, etc.) |
| `tax_rate` | DecimalField | GST/VAT percentage |
| `description` | TextField | Long-form description |
| `is_available` | BooleanField | Toggle availability |
| `price_with_tax` | property | `price × (1 + tax_rate/100)` |

---

### `ProductVariant`
Options/modifiers for a product (Size: Large, Spice: Extra).

| Field | Type | Description |
|---|---|---|
| `product` | FK → Product | Parent product |
| `attribute` | CharField | Modifier name (e.g. "Size") |
| `value` | CharField | Modifier value (e.g. "Large") |
| `extra_price` | DecimalField | Additional charge for this variant |

---

### `PaymentMethod`
Configurable payment types available at this outlet.

| Field | Type | Description |
|---|---|---|
| `type` | CharField | One of: `cash`, `digital`, `upi` |
| `is_enabled` | BooleanField | Toggle on/off per outlet |
| `upi_id` | CharField | UPI VPA for QR code generation (UPI only) |

---

### `POSSession`
Represents a cashier's work shift.

| Field | Type | Description |
|---|---|---|
| `user` | FK → User | Cashier who opened this session |
| `status` | CharField | `open` or `closed` |
| `opened_at` | DateTimeField | Shift start time |
| `closed_at` | DateTimeField | Shift end time |
| `closing_sale_amount` | DecimalField | Auto-calculated total sales on close |
| `notes` | TextField | Manager notes / discrepancy remarks |

**Methods:**
- `close()` — Sums all paid order `grand_total` values, sets `closing_sale_amount`, marks session `closed`.

---

### `Order`
A customer's order, tied to a session and optionally a table.

| Field | Type | Description |
|---|---|---|
| `session` | FK → POSSession | Active cashier session |
| `table` | FK → Table (nullable) | Dine-in table; null = takeaway |
| `status` | CharField | `open` → `sent` → `paid` / `cancelled` |
| `payment_method` | CharField | `cash`, `digital`, or `upi` (set on payment) |
| `subtotal` | DecimalField | Sum of all line totals (pre-tax) |
| `tax_total` | DecimalField | Total tax across all lines |
| `grand_total` | DecimalField | `subtotal + tax_total` |
| `notes` | TextField | Special kitchen instructions |
| `self_order_token` | UUIDField | Unique token for QR self-ordering |

**Methods:**
- `recalculate()` — Recomputes `subtotal`, `tax_total`, and `grand_total` from all lines.

---

### `OrderLine`
A single line item within an order.

| Field | Type | Description |
|---|---|---|
| `order` | FK → Order | Parent order |
| `product` | FK → Product | Ordered product |
| `variant` | FK → ProductVariant (nullable) | Selected variant if any |
| `quantity` | PositiveIntegerField | Number of units |
| `unit_price` | DecimalField | Price at time of order (snapshot) |
| `tax_rate` | DecimalField | Tax rate snapshot |
| `is_prepared` | BooleanField | Kitchen marks this item as done |
| `line_total` | property | `unit_price × quantity` |
| `tax_amount` | property | `line_total × tax_rate / 100` |

---

### `KitchenTicket`
Kitchen-facing representation of an order (1-to-1 with Order).

| Field | Type | Description |
|---|---|---|
| `order` | OneToOneField → Order | Associated order |
| `stage` | CharField | `to_cook` → `preparing` → `completed` |
| `created_at` | DateTimeField | When ticket was created |
| `updated_at` | DateTimeField | Last stage change |

**Methods:**
- `advance()` — Progresses stage through the state machine: `to_cook → preparing → completed`.

---

## 🔌 API Reference

All endpoints are Django view-based (not REST framework). AJAX endpoints return JSON; page endpoints return rendered HTML.

Base URL prefix: `/pos/`

---

### 🔐 Authentication (accounts app)

| Method | URL | Auth | Description |
|---|---|---|---|
| GET/POST | `/accounts/login/` | No | Login with username & password |
| GET/POST | `/accounts/signup/` | No | Create a new user account |
| GET | `/accounts/logout/` | Yes | Logout and clear POS session state |
| GET/POST | `/accounts/profile/` | Yes | View and update user profile |

---

### 🕐 Session Management

| Method | URL | Auth | Description |
|---|---|---|---|
| GET | `/pos/open-session/` | Yes | Open (or resume) a POS session; redirects to floor view |
| POST | `/pos/close-session/` | Yes | Close active session and compute closing sales amount |

**`GET /pos/open-session/`**
Auto-creates a session if none exists. Redirects to `/pos/floor/`.

**`POST /pos/close-session/`**
Calculates `closing_sale_amount` from all `paid` orders in the session. Redirects to backend dashboard.

---

### 🗺️ Floor & Table View

| Method | URL | Auth | Description |
|---|---|---|---|
| GET | `/pos/floor/` | Yes | Renders floor map with all active tables and occupancy status |

**`GET /pos/floor/`**
Returns HTML page with all active floors and their tables. Each table displays its `is_occupied` status.

---

### 🛒 Order Management

| Method | URL | Auth | Description |
|---|---|---|---|
| GET | `/pos/order/<table_id>/` | Yes | Order entry screen for a table; creates order if none exists |
| POST | `/pos/order/<order_id>/add/` | Yes | Add product to order (AJAX) |
| POST | `/pos/line/<line_id>/update/` | Yes | Update or delete an order line (AJAX) |
| POST | `/pos/order/<order_id>/send/` | Yes | Send order to kitchen and lock it |

---

**`POST /pos/order/<order_id>/add/`**

Adds a product to the order. If the same product+variant already exists in the order, increments quantity by 1.

Request body (form-encoded):
```
product_id=<int>
variant_id=<int>   (optional)
```

Response (JSON):
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

---

**`POST /pos/line/<line_id>/update/`**

Updates the quantity of an order line. If `qty` is 0 or less, the line is deleted.

Request body (form-encoded):
```
qty=<int>
```

Response (JSON) — when qty > 0:
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

Response (JSON) — when line deleted (qty ≤ 0):
```json
{
  "ok": true,
  "grand_total": "302.40",
  "subtotal": "280.00",
  "tax_total": "22.40"
}
```

---

**`POST /pos/order/<order_id>/send/`**

Marks order as `sent`, creates a `KitchenTicket`, and redirects back to the order screen. Returns an error if the order has no items.

---

### 💳 Payment

| Method | URL | Auth | Description |
|---|---|---|---|
| GET | `/pos/payment/<order_id>/` | Yes | Payment screen with QR code generation for UPI |
| POST | `/pos/payment/<order_id>/process/` | Yes | Process payment and mark order as paid |
| GET | `/pos/payment/<order_id>/confirm/` | Yes | Receipt/confirmation screen |

---

**`GET /pos/payment/<order_id>/`**

Renders payment screen. If UPI is enabled and a `upi_id` is configured, generates a QR code URL via:
```
https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=upi://pay?pa=...&am=<amount>&tn=Table<n>
```

**`POST /pos/payment/<order_id>/process/`**

Request body (form-encoded):
```
method=cash|digital|upi
```

Validates that the payment method is currently enabled before accepting. On success, sets `order.payment_method` and `order.status = paid`. Redirects to confirmation screen.

---

### 🍳 Kitchen Display System

| Method | URL | Auth | Description |
|---|---|---|---|
| GET | `/pos/kitchen/` | No | Kitchen display (kiosk-style, no login required) |
| POST | `/pos/kitchen/ticket/<ticket_id>/advance/` | No | Advance ticket to next stage (AJAX) |
| POST | `/pos/kitchen/line/<line_id>/prepared/` | No | Toggle individual item as prepared (AJAX) |

---

**`POST /pos/kitchen/ticket/<ticket_id>/advance/`**

Advances a kitchen ticket through its state machine: `to_cook → preparing → completed`.

Response (JSON):
```json
{
  "ok": true,
  "stage": "preparing"
}
```

---

**`POST /pos/kitchen/line/<line_id>/prepared/`**

Toggles `is_prepared` on a specific order line (used for per-item visual strikethrough on kitchen screen).

Response (JSON):
```json
{
  "ok": true,
  "prepared": true
}
```

---

### 📺 Customer Display

| Method | URL | Auth | Description |
|---|---|---|---|
| GET | `/pos/customer/<order_id>/` | No | Read-only order view for customer-facing screen |

Renders a clean, read-only summary of the order. Intended for a second monitor or TV mounted in the dining area.

---

### 📱 QR Self-Ordering

| Method | URL | Auth | Description |
|---|---|---|---|
| GET/POST | `/pos/self-order/<uuid:token>/` | No | Customer self-ordering via QR code |

**`GET /pos/self-order/<token>/`**
Displays the full menu to the customer.

**`POST /pos/self-order/<token>/`**
Adds a product to the order. If this is the first item, automatically transitions the order from `open` to `sent` and creates a `KitchenTicket`. Customers can continue adding items.

Request body (form-encoded):
```
product_id=<int>
```

---

### ⚙️ Backend / Configuration

| Method | URL | Auth | Description |
|---|---|---|---|
| GET | `/pos/backend/` | Yes | Manager configuration dashboard |
| POST | `/pos/backend/payment/<pm_id>/toggle/` | Yes | Enable/disable a payment method (AJAX) |

**`POST /pos/backend/payment/<pm_id>/toggle/`**

Response (JSON):
```json
{
  "ok": true,
  "enabled": false
}
```

---

### 📊 Reports

| Method | URL | Auth | Description |
|---|---|---|---|
| GET | `/pos/reports/` | Yes | Sales reports with filtering |

**`GET /pos/reports/`**

Query parameters:

| Parameter | Type | Description |
|---|---|---|
| `period` | string | `today` (default), `week`, or `custom` |
| `date_from` | date | Start date for custom range (`YYYY-MM-DD`) |
| `date_to` | date | End date for custom range (`YYYY-MM-DD`) |
| `session_id` | int | Filter by specific POS session |
| `responsible_id` | int | Filter by cashier user ID |
| `product_id` | int | Filter orders containing a specific product |

Returns aggregated totals (`total_revenue`, `total_orders`) and a list of up to 50 matching paid orders.

---

## 🔄 Order Lifecycle

```
         Cashier creates order
                 │
                 ▼
         Status: OPEN  ◄──── Items can be added/edited
                 │
    [Send to Kitchen]
                 │
                 ▼
         Status: SENT  ──── KitchenTicket created
                 │               │
                 │       Kitchen: to_cook → preparing → completed
                 │
    [Process Payment]
                 │
                 ▼
         Status: PAID  ──── Session sales updated
                 │
           (or CANCELLED at any point by manager)
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- pip

### Installation

```bash
# 1. Clone the repository
git clone <repo-url>
cd odoo-pos-cafe

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate      # Linux/Mac
venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env .env.local
# Edit .env.local with your SECRET_KEY and other settings

# 5. Apply migrations
python manage.py migrate

# 6. Seed demo data (floors, tables, menu items)
python manage.py seed_cafe_data

# 7. Create a superuser
python manage.py createsuperuser

# 8. Run the development server
python manage.py runserver
```

### Access Points

| URL | Description |
|---|---|
| `http://127.0.0.1:8000/` | Landing page |
| `http://127.0.0.1:8000/accounts/login/` | Staff login |
| `http://127.0.0.1:8000/pos/floor/` | POS floor view (requires login) |
| `http://127.0.0.1:8000/pos/kitchen/` | Kitchen display (no login) |
| `http://127.0.0.1:8000/admin/` | Django admin panel |

---

## 👤 User Roles

| Role | Access Level |
|---|---|
| `admin` | Full system access including admin panel |
| `manager` | Reports, backend config, session overview |
| `cashier` | Floor, orders, payments |
| `kitchen` | Kitchen display only |

> Note: Role-based view protection is partially implemented. Full middleware-level enforcement is planned for a future release.

---

## 🌱 Seed Data

The management command `seed_cafe_data` populates the database with:
- Multiple floors (Ground Floor, First Floor)
- Tables across each floor
- Menu categories (Breakfast, Snacks, Beverages, Fast Food, Desserts, Combos, Add-ons)
- 35+ menu items with images and pricing
- Payment methods (Cash, Digital/Card, UPI)

Run with:
```bash
python manage.py seed_cafe_data
```

---

## 🔐 Environment Variables

| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | `True` for development, `False` for production |
| `ALLOWED_HOSTS` | Comma-separated list of allowed hostnames |

---

## 🧪 Dependencies

```
Django==5.2.12
asgiref==3.11.1
Pillow==12.2.0
qrcode==8.2
sqlparse==0.5.5
tzdata==2026.1
colorama==0.4.6
```

---

## 🗺️ Roadmap / Known TODOs

- [ ] Role-based access control enforcement at middleware level
- [ ] Manager override to edit locked (sent) orders
- [ ] Password change and email verification on profile
- [ ] Pagination on reports for large datasets
- [ ] Local QR code generation (replace external API)
- [ ] Database indexes on `updated_at`, `session_id` for reports performance
- [ ] PostgreSQL migration guide for production
- [ ] WebSocket-based real-time kitchen display (currently requires manual refresh)

---

## 📄 License

This project was built as part of a practical demonstration of a cafe POS system. All rights reserved by the development team.
