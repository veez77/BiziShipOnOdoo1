# BiziShip Odoo Module — Project Reference

## What Is This?

BiziShip is a custom Odoo 17 (Enterprise) module that integrates Odoo Sales Orders with the BiziShip.ai freight brokerage platform. It allows Odoo users to:
- Fetch real-time LTL carrier quotes from BiziShip's ERP API
- Book shipments directly from a Sale Order
- Parse BOL (Bill of Lading) PDFs and auto-populate freight details
- Save and reload freight templates from BiziShip's cloud
- Authenticate Odoo users against BiziShip accounts via email + PIN

---

## Architecture Overview

### Two-Repo Deployment Pipeline
- **Repo 1 (Development):** `C:\Startups\BiziShip.ai\SW\Odoo\biziship` — this repo, pushed to GitHub
- **Repo 2 (Customer Sandbox / HexcelPack):** A separate GitHub repo pushed manually via PowerShell script `C:\Startups\BiziShip.ai\SW\Odoo\deploy_hexcelpack_sandbox.ps1`
- Changes made here must be manually synced to Repo 2 before the customer sandbox will see them

### BiziShip Backend API
- All API calls go through the BiziShip ERP Gateway
- Base URL is determined by `api_utils.get_biziship_api_url()`
- Authentication uses two mechanisms:
  1. **ERP API Key** (`X-ERP-API-Key` header) — stored in Odoo system parameters as `biziship.erp_api_key`
  2. **User JWT Token** (`Authorization: Bearer <token>`) — per-user, stored on `res.users.biziship_token`
- Key API endpoints:
  - `POST /erp/quote` — Fetch LTL quotes
  - `POST /erp/book` — Book a shipment / confirm a quote
  - `POST /erp/bol/extract` — Parse a BOL PDF
  - `GET /erp/saved-freights` — List saved freight templates
  - `POST /erp/auth/login` — Request login PIN
  - `POST /erp/auth/verify-pin` — Verify PIN and get JWT token
  - `POST /erp/validate-address` — Smarty residential address validation

---

## Module Structure

```
biziship/
├── __manifest__.py              # Module metadata, assets
├── api_utils.py                 # API URL resolver, constants, unit converters
├── models/
│   ├── sale_order.py            # Main freight fields and quote-fetch logic on Sale Order
│   ├── biziship_cargo_line.py   # Cargo line model (packaging, weight, dims, class, NMFC)
│   ├── biziship_quote.py        # Carrier quote model
│   ├── biziship_accessorial.py  # Accessorial services (RESPU, LGDEL, APPT, etc.)
│   └── res_users.py             # BiziShip fields on Odoo users
├── wizards/
│   ├── biziship_auth_wizard.py          # BiziShip login (email + PIN flow)
│   ├── biziship_freight_quote_wizard.py # Fetch LTL quotes wizard
│   ├── biziship_quote_confirm_wizard.py # Confirm/book a selected quote
│   ├── biziship_bol_wizard.py           # BOL PDF upload and extraction
│   ├── biziship_save_freight_wizard.py  # Save current freight to BiziShip cloud
│   └── biziship_load_freight_wizard.py  # Load a saved freight from BiziShip cloud
├── views/
│   ├── sale_order_views.xml     # Main Sale Order form with all BiziShip tabs/sections
│   └── res_users_views.xml      # User preferences view for BiziShip account info
├── static/src/
│   ├── css/biziship_modern.css  # All BiziShip CSS styling
│   └── js/                      # JS for tab switching, Google Places, commodity autocomplete
└── data/
    └── accessorial_data.xml     # Seed data for accessorial codes
```

---

## Key Models

### `res.users` (extended)
| Field | Type | Purpose |
|---|---|---|
| `biziship_token` | Char | JWT token from BiziShip after PIN login |
| `biziship_email` | Char | Email used when authenticating with BiziShip (may differ from Odoo login email) |
| `biziship_user_name` | Char | Display name returned by BiziShip after login |
| `biziship_p1_env` | Selection | DEV or PROD environment flag |

**Important:** `biziship_email` is the email sent as `X-User-Email` in all API calls when the user has an active token. If no token, falls back to `env.user.email`.

### `sale.order` (extended)
Contains ~50 extra fields for freight: origin/destination addresses, contact info, accessorials, cargo description, pickup date, fetched quotes, etc.

### `biziship.cargo.line`
One sale order → many cargo lines. Each has: packaging type, pieces, weight, dimensions, freight class, NMFC code, cargo description, hazmat/stackable/used/machinery boolean flags.

### `biziship.quote`
Stores fetched carrier quotes linked to a Sale Order: carrier name, service level, transit days, total charge, terminal info, charge breakdown.

---

## Critical Design Patterns

### X-User-Email Header Logic
Every API call must send the correct user email so the BiziShip backend can link the request to the right account:
```python
"X-User-Email": (
    self.env.user.biziship_email 
    if self.env.user.biziship_token and self.env.user.biziship_email 
    else self.env.user.email
) or "",
```
This ensures that if Andy authenticated with `andy@hexcelpack.com` but his Odoo login is `admin@hexcelpack.com`, the right email goes to the backend.

### BiziShip Login Flow
1. User opens "Connect BiziShip Account" wizard (`biziship.auth.wizard`)
2. Enters email → clicks "Request PIN" → backend sends PIN to that email
3. Enters PIN → clicks "Verify" → backend returns JWT token + user info
4. Token, email, name, env stored on `self.env.user`
5. Token presence is used as "is logged in to BiziShip" gate for Saved Freights

### Saved Freights Gate
Loading saved freights requires a valid `biziship_token`. If the user hasn't logged in to BiziShip via the wizard, the Load Freight wizard shows an error message prompting them to connect first.

### NMFC Suggestion
`biziship_cargo_line.py` → `action_biziship_nmfc_suggest()` calls the backend to suggest an NMFC code based on the cargo description. Only works on saved records (raises UserError if called on unsaved).

---

## CSS Styling

File: `static/src/css/biziship_modern.css`

Key CSS classes:
- `.biziship-cargo-card` — The white card wrapping each cargo line in Kanban/Form views
- `.biziship-cargo-flag-group` — Hazmat/Stackable/Used/Machinery checkbox group
- `.biziship-freight-card` — Cards in the Load Freight wizard
- `.biziship-btn-get-quotes` — The main "Get Quotes" CTA button

**Note:** There are dark mode override blocks at the bottom of the CSS file using selectors like `html[data-bs-theme="dark"]`, `body.o_dark_mode`, `.o_web_client.o_dark_mode`. The card background is white (`#ffffff`) with dark text forced explicitly — this is intentional because Odoo Enterprise's internal dark mode CSS variables were not reliably overridable in sandbox.

---

## Accessorial Codes Reference

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

## Deployment Notes

### Local Dev
- Odoo server: `python odoo-bin -d biziship_db -u biziship -r odoo -w Bilbil01`
- After any Python or XML change: restart server OR upgrade module via Apps menu
- CSS changes: restart server + hard refresh browser (Ctrl+F5)
- Odoo caches all assets to PostgreSQL — file saves alone do NOT take effect

### HexcelPack Sandbox (Odoo.sh)
- Run `deploy_hexcelpack_sandbox.ps1` to sync Repo 1 → Repo 2
- Odoo.sh detects the git push and kicks off a build (takes 2-5 minutes)
- After build: go to Apps → BiziShip → Upgrade in the sandbox
- Hard refresh browser (Ctrl+F5) to bust asset cache

### Database Migration
When adding new fields to models (e.g., `biziship_email` on `res.users`), Odoo will auto-create the DB column on next module upgrade. No manual SQL needed.

---

## Known Issues / History

- **Dark Mode:** The BiziShip cargo card has a white background that doesn't auto-adapt to Odoo Enterprise dark mode. The card is intentionally left light with dark forced text for readability.
- **BOL Groq extraction:** GROQ AI extraction is commented out in `biziship_bol_wizard.py`. Currently uses BiziShip's `/erp/bol/extract` endpoint directly.
- **Email mismatch bug (fixed):** The `X-User-Email` header previously always sent `self.env.user.email` (Odoo login email). Now it correctly sends `biziship_email` (BiziShip-registered email) when available.
