# BiziShip Odoo Module — Antigravity Project Reference

## What Is This?

BiziShip is a custom Odoo 17 (Enterprise) module that integrates Odoo Sales Orders with the BiziShip.ai freight brokerage platform. It allows Odoo users to:
- Fetch real-time LTL carrier quotes from BiziShip's ERP API
- Book shipments directly from a Sale Order
- Parse BOL (Bill of Lading) PDFs and auto-populate freight details
- Save and reload freight templates from BiziShip's cloud
- Authenticate Odoo users against BiziShip accounts via email + PIN
- Manage company-level NMFC Favorites (description + NMFC code pairs)

---

## Tech Stack

- **Backend:** Python 3.11, Odoo 17 Enterprise (ORM, XML views, wizard pattern)
- **Frontend:** Odoo OWL 2 (component framework), QWeb XML templates, Bootstrap 5
- **API:** BiziShip ERP Gateway (REST, JSON) — AWS API Gateway
- **Database:** PostgreSQL (managed by Odoo ORM — never write raw SQL)
- **Assets:** Odoo asset bundling via `__manifest__.py` `web.assets_backend`
- **Deployment:** Git → GitHub → Odoo.sh (customer sandbox)

---

## Critical Rules

- **Never write raw SQL.** Use Odoo ORM (`self.env['model'].search(...)`, `record.write(...)`, etc.)
- **Never call `record.load()` to refresh UI fields** — it causes a full form reload. Patch `record.data` directly for stored fields, or return values from RPC and apply them in JS.
- **`@api.model` RPC calls from OWL:** Pass extra arguments as `kwargs`, not positional args. Use `orm.call(model, method, [], { key: value })`. Positional args beyond IDs cause a "takes N arguments but M were given" TypeError.
- **All API calls must include both auth headers:**
  ```python
  "X-ERP-API-Key": erp_api_key,
  "X-User-Email": (user.biziship_email if user.biziship_token and user.biziship_email else user.email) or "",
  ```
- **After any Python/XML change:** restart Odoo server. CSS-only changes also require server restart + Ctrl+F5 (assets are cached in PostgreSQL).
- **New model fields** auto-create DB columns on module upgrade (`-u biziship`). No manual SQL needed.
- **Module upgrade command:** `python odoo-bin -d biziship_db -u biziship -r odoo -w Bilbil01`

---

## Architecture Overview

### Two-Repo Deployment Pipeline
- **Repo 1 (Development):** `C:\Startups\BiziShip.ai\SW\Odoo\biziship` — this repo, pushed to GitHub
- **Repo 2 (Customer Sandbox / HexcelPack):** Separate GitHub repo synced via `C:\Startups\BiziShip.ai\SW\Odoo\deploy_hexcelpack_sandbox.ps1`

### BiziShip Backend API
- Base URL: `api_utils.get_biziship_api_url()` (resolves DEV vs PROD)
- Auth: `X-ERP-API-Key` (system param `biziship.erp_api_key`) + `X-User-Email` (per-user)
- Key endpoints:
  - `POST /erp/quote` — Fetch LTL quotes
  - `POST /erp/book` — Book a shipment
  - `POST /erp/bol/extract` — Parse BOL PDF
  - `GET /erp/saved-freights` — List saved freight templates
  - `POST /erp/auth/login` — Request login PIN
  - `POST /erp/auth/verify-pin` — Verify PIN, get JWT
  - `POST /erp/validate-address` — Smarty residential address validation
  - `GET /erp/auth/me` — Fetch connected user profile
  - `GET /erp/shipments/:id/documents` — Fetch booking documents
  - `POST /erp/nmfc/suggest` — AI NMFC suggestion
  - `GET /erp/company/nmfc-favorites` — List company NMFC favorites
  - `POST /erp/company/nmfc-favorites` — Save a new favorite
  - `DELETE /erp/company/nmfc-favorites/:id` — Delete a favorite

---

## Module Structure

```
biziship/
├── __manifest__.py              # Module metadata + asset registration
├── api_utils.py                 # API URL resolver, constants, unit converters
├── models/
│   ├── sale_order.py            # ~50 freight fields + quote/book logic on Sale Order
│   ├── biziship_cargo_line.py   # Cargo line model + NMFC suggest + NMFC Favorites API
│   ├── biziship_quote.py        # Carrier quote model
│   ├── biziship_accessorial.py  # Accessorial services
│   └── res_users.py             # BiziShip token/email/name/env fields on users
├── wizards/
│   ├── biziship_auth_wizard.py          # Email + PIN login flow
│   ├── biziship_freight_quote_wizard.py # Fetch LTL quotes
│   ├── biziship_quote_confirm_wizard.py # Confirm/book a quote
│   ├── biziship_bol_wizard.py           # BOL PDF upload + extraction
│   ├── biziship_save_freight_wizard.py  # Save freight to BiziShip cloud
│   └── biziship_load_freight_wizard.py  # Load saved freight from BiziShip cloud
├── views/
│   ├── sale_order_views.xml     # Main Sale Order form (all BiziShip tabs)
│   └── res_users_views.xml      # User preferences for BiziShip account
├── static/src/
│   ├── css/biziship_modern.css              # All BiziShip CSS
│   ├── js/biziship_tab_handler.js           # OWL FormController patch (tab switch, profile refresh)
│   ├── js/biziship_places_autocomplete.js   # Google Places address autocomplete
│   ├── js/biziship_commodity_autocomplete.js # Cargo description autocomplete widget
│   ├── js/biziship_nmfc_favorites.js        # NMFC Favorites OWL dialog + field widget
│   ├── xml/biziship_commodity_templates.xml
│   └── xml/biziship_nmfc_favorites.xml      # OWL templates for favorites dialog
└── data/
    └── accessorial_data.xml     # Seed data for accessorial codes
```

---

## Key Models

### `res.users` (extended)
| Field | Type | Purpose |
|---|---|---|
| `biziship_token` | Char | JWT from BiziShip after PIN login |
| `biziship_email` | Char | Email used with BiziShip (may differ from Odoo login email) |
| `biziship_user_name` | Char | Display name from BiziShip |
| `biziship_p1_env` | Selection | DEV or PROD environment |

### `sale.order` (extended)
~50 freight fields: origin/destination addresses, contacts, accessorials, cargo, pickup date, quotes, booking details, documents JSON.

Key stored fields: `biziship_connected_email`, `biziship_booking_id` (UUID from `/book`), `biziship_shipment_id` (P1 integer), `biziship_pro_number`, `biziship_priority1_env`, `biziship_demo_tries`.

### `biziship.cargo.line`
One2Many from sale.order. Fields: packaging type, pieces, weight/unit, L/W/H/dim_unit, freight class, computed class, NMFC, cargo description, hazmat/stackable/used/machinery flags, NMFC suggestion fields, `biziship_nmfc_fav_trigger` (non-stored, widget attachment only).

### `biziship.quote`
Fetched carrier quotes linked to a Sale Order.

---

## OWL Frontend Patterns

### FormController patch (`biziship_tab_handler.js`)
Patches Odoo's `FormController` to:
- Call `action_biziship_refresh_profile_rpc` on mount and on freight tab click
- Apply result directly to `record.data` (no reload): `data.biziship_connected_email = result.biziship_connected_email`
- Auto-switch to Quotes tab when `biziship_last_fetch_nonce` changes

### Field Widget Registration
```javascript
registry.category("fields").add("widget_name", {
    component: MyComponent,
    supportedTypes: ["boolean"],  // or "char", etc.
});
```
Used for: `biziship_commodity` (char autocomplete), `biziship_nmfc_star` (favorites button).

### OWL Dialog Pattern
```javascript
// Open a dialog:
this.dialog.add(MyDialogComponent, { record: this.props.record });

// Dialog receives `close` as injected prop from dialog service
// Call this.props.close() to close programmatically
```

### Updating kanban record fields from a widget (no page refresh)
```javascript
this.props.record.update({
    field_name: new_value,
    another_field: false,  // clears it
});
```

---

## CSS Notes

File: `static/src/css/biziship_modern.css`

Key classes: `.biziship-cargo-card`, `.biziship-cargo-flag-group`, `.biziship-freight-card`, `.biziship-btn-get-quotes`

Dark mode overrides at bottom of file use `html[data-bs-theme="dark"]` / `body.o_dark_mode`. Cargo card is intentionally white with forced dark text (Odoo Enterprise dark mode CSS variables were not reliably overridable).

---

## Accessorial Codes

| Code | Meaning | Type |
|---|---|---|
| RESPU | Residential Pickup | Origin |
| LGPU | Liftgate Pickup | Origin |
| LTDPU | Limited Access Pickup | Origin |
| RESDEL | Residential Delivery | Destination |
| LGDEL | Liftgate Delivery | Destination |
| LTDDEL | Limited Access Delivery | Destination |
| APPT | Appointment Delivery | Destination |
| NOTIFY | Notify Before Delivery | Destination |
| HAZM | Hazardous Material | Destination |

---

## Deployment

### Local Dev
```
python odoo-bin -d biziship_db -u biziship -r odoo -w Bilbil01
```
Python 3.11 required. Pinned: `cryptography==3.4.8`, `pyOpenSSL==21.0.0`, `urllib3==1.26.5`.

### HexcelPack Sandbox (Odoo.sh)
1. Run `deploy_hexcelpack_sandbox.ps1` (syncs to customer repo)
2. Odoo.sh auto-builds on push (2–5 min)
3. Apps → BiziShip → Upgrade
4. Hard refresh (Ctrl+F5)
