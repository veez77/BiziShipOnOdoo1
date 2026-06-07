# Bug Report: BiziShip Destination Fields Silently Overwriting Customer Address Records

**Date Discovered:** June 7, 2026  
**Severity:** Critical  
**Status:** Fixed  
**Module:** BiziShip.ai for Odoo (`biziship`)  
**File:** `models/sale_order.py`, lines 226–230  

---

## Summary

Editing any destination address field (street, city, zip, state) in the BiziShip **LTL Freight Details** tab of a Sale Order permanently and silently overwrites the delivery partner's master address record in Odoo Contacts — corrupting it across the entire system for all users and all documents.

---

## Root Cause

Five fields on `sale.order` were defined as Odoo `related` fields pointing at the delivery partner (`partner_shipping_id`) address fields, with `readonly=False`:

```python
# BUGGY CODE (before fix)
biziship_dest_address  = fields.Char(related="partner_shipping_id.street",    readonly=False, store=True)
biziship_dest_address2 = fields.Char(related="partner_shipping_id.street2",   readonly=False, store=True)
biziship_dest_city     = fields.Char(related="partner_shipping_id.city",       readonly=False, store=True)
biziship_dest_state_id = fields.Many2one(related="partner_shipping_id.state_id", readonly=False, store=True)
biziship_dest_zip      = fields.Char(related="partner_shipping_id.zip",        readonly=False, store=True)
```

In Odoo ORM, a `related` field with `readonly=False` creates a **two-way binding**:

- **Reading** the field → reads from the related partner record (intended ✅)
- **Writing** to the field → writes back to the related partner record (unintended ❌)

The developer's intent was to use `related=` as a convenient shortcut to auto-populate the BiziShip destination fields from the delivery partner when the sale order is opened. The `store=True` was added so users could then independently edit those fields for a specific shipment. However, the combination of `related=` + `readonly=False` + `store=True` does not achieve this — instead it creates a transparent two-way pipe to the partner record. Every edit propagates back to `res.partner`.

---

## How the Bug Is Triggered

1. A sales user opens a Sale Order that has a customer with a **Delivery Address** set (`partner_shipping_id`)
2. The user navigates to the **LTL Freight Details** tab in BiziShip
3. The user edits any of the following destination fields for freight purposes:
   - Destination Address Line 1
   - Destination Address Line 2  
   - Destination City
   - Destination State
   - Destination Zip Code
4. The user saves the sale order (or Odoo auto-saves on navigation)
5. The delivery partner's (`partner_shipping_id`) address record in **Contacts** is permanently overwritten with the new values

No confirmation, no warning, no audit trail visible to the user.

---

## Impact

### Direct Impact
- The **delivery partner's master address** in Odoo Contacts is overwritten silently
- If the `partner_shipping_id` is the main customer company, the **billing and shipping address** shown on all their documents (invoices, delivery orders, quotations) is corrupted
- If the `partner_shipping_id` is a child delivery address contact, that specific delivery address is corrupted

### Scope of Damage
- Every sale order where a user adjusted the BiziShip destination address for a shipment (e.g., to correct a zip code, change a city for a specific delivery) has potentially corrupted the corresponding partner record
- The corrupted address then propagates to all other sale orders, invoices, and delivery orders linked to that partner — past and future
- **The damage is invisible:** users have no reason to suspect their freight edits are touching Contacts

### Confirmed Incident
Discovered when a HexcelPack production customer complained their delivery address had been changed. Reproduction confirmed:
- Editing the BiziShip destination city on a sale order
- Navigating to the delivery partner record
- Observing the partner's city field changed to match the value entered in BiziShip

---

## Solution

Remove the `related=` attribute from all five destination address fields, making them plain independent fields stored on the sale order only.

```python
# FIXED CODE (after fix)
biziship_dest_address  = fields.Char(string="Destination Address Line 1")
biziship_dest_address2 = fields.Char(string="Destination Address Line 2")
biziship_dest_city     = fields.Char(string="Destination City")
biziship_dest_state_id = fields.Many2one('res.country.state', string="Destination State")
biziship_dest_zip      = fields.Char(string="Destination Zip Code", size=5)
```

**Why this is safe:**  
Auto-population from the partner was already handled by two explicit mechanisms that remain fully functional:
1. **`_biziship_copy_customer_details()`** method — explicitly reads from `partner_shipping_id` and writes to the BiziShip fields on demand
2. **"Copy Customer Details" button** — calls the above method when the user wants to refresh from the partner

After the fix:
- Editing destination fields in BiziShip → stays on the sale order only ✅
- Partner/Contacts records → never touched by BiziShip freight edits ✅
- "Copy Customer Details" button → still works exactly as before ✅
- Existing stored values in the database → unchanged (values already stored in `sale.order` table are preserved) ✅

---

## Design Rule Going Forward

**Never use `related=` + `readonly=False` to point BiziShip sale order fields at standard Odoo model fields (`res.partner`, `res.users`, etc.).**

Use `@api.onchange` or explicit method calls for one-way population:

```python
# CORRECT PATTERN for "default from partner, editable independently"
biziship_dest_city = fields.Char(string="Destination City")

@api.onchange('partner_shipping_id')
def _onchange_partner_shipping_biziship_dest(self):
    if self.partner_shipping_id:
        self.biziship_dest_city = self.partner_shipping_id.city
```

`related=` is appropriate only for read-only display fields or for fields that intentionally and explicitly need two-way sync with another model.

---

## Verification of No Other Occurrences

A full audit of all `related=` + `readonly=False` usages and all `.write()` calls in the BiziShip module was performed on June 7, 2026. The five destination address fields were the **only** instance where BiziShip fields wrote back to standard Odoo records (`res.partner`). All other write operations target BiziShip-owned fields only.
