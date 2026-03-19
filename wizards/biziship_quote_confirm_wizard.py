import json
import requests
import os
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

ACCESSORIAL_MAPPING = {
    "APPT": "Delivery Appointment",
    "LGDEL": "Lift Gate Delivery",
    "LGPU": "Lift Gate Pickup",
    "RESDEL": "Residential Delivery",
    "RESPU": "Residential Pickup",
    "INDEL": "Inside Delivery",
    "INPU": "Inside Pickup",
    "LTDDEL": "Limited Access Delivery",
    "LTDPU": "Limited Access Pickup",
    "NOTIFY": "Notify Consignee",
    "HAZM": "Hazardous Material",
    "SORTDEL": "Sort/Segregate Delivery",
    "SORTPU": "Sort/Segregate Pickup",
    "CONDEL": "Construction Site Delivery",
    "CONPU": "Construction Site Pickup",
    "PFZ": "Protection From Freezing",
    "CNVDEL": "Trade Show Delivery",
    "CNVPU": "Trade Show Pickup"
}

from odoo.addons.BiziShip.api_utils import get_biziship_api_url, get_email2quote_api_key, BIZISHIP_MODULE_VERSION, BIZISHIP_APP_NAME


class BizishipQuoteConfirmWizard(models.TransientModel):
    _name = 'biziship.quote.confirm.wizard'
    _description = 'Confirm BiziShip Quote'

    quote_id = fields.Many2one('biziship.quote', string="Selected Quote", required=True)
    sale_order_id = fields.Many2one(related="quote_id.sale_order_id", readonly=True)
    biziship_cargo_line_ids = fields.One2many(related="sale_order_id.biziship_cargo_line_ids", readonly=True)
    
    # Terminals
    origin_terminal_city = fields.Char(related="quote_id.origin_terminal_city", readonly=True)
    origin_terminal_state = fields.Char(related="quote_id.origin_terminal_state", readonly=True)
    origin_terminal_phone = fields.Char(related="quote_id.origin_terminal_phone", readonly=True)
    destination_terminal_city = fields.Char(related="quote_id.destination_terminal_city", readonly=True)
    destination_terminal_state = fields.Char(related="quote_id.destination_terminal_state", readonly=True)
    destination_terminal_phone = fields.Char(related="quote_id.destination_terminal_phone", readonly=True)
    
    # Pickup Date & Totals
    biziship_pickup_date = fields.Date(related="sale_order_id.biziship_pickup_date", readonly=True)
    biziship_total_weight = fields.Float(related="sale_order_id.biziship_total_weight", readonly=True)
    biziship_total_weight_unit = fields.Selection(related="sale_order_id.biziship_total_weight_unit", readonly=True)

    # Origin Details
    origin_company = fields.Char(related="sale_order_id.biziship_origin_company", readonly=True)
    origin_address = fields.Char(related="quote_id.origin_address", string="Origin Address", readonly=True)
    origin_address2 = fields.Char(related="quote_id.origin_address2", string="Origin Address 2", readonly=True)
    origin_city = fields.Char(related="sale_order_id.biziship_origin_city", string="Origin City", readonly=True)
    origin_state = fields.Char(related="sale_order_id.biziship_origin_state_id.code", string="Origin State", readonly=True)
    origin_zip = fields.Char(related="sale_order_id.biziship_origin_zip", string="Origin Zip", readonly=True)
    origin_phone = fields.Char(related="sale_order_id.company_id.phone", string="Origin Phone", readonly=True)
    origin_contact_name = fields.Char(related="sale_order_id.biziship_origin_contact_name", readonly=True)
    origin_contact_phone = fields.Char(related="sale_order_id.biziship_origin_contact_phone", readonly=True)
    origin_contact_email = fields.Char(related="sale_order_id.biziship_origin_contact_email", readonly=True)
    
    # Destination Details
    destination_company = fields.Char(related="sale_order_id.biziship_dest_company", readonly=True)
    destination_address = fields.Char(related="quote_id.destination_address", string="Dest Address", readonly=True)
    destination_address2 = fields.Char(related="quote_id.destination_address2", string="Dest Address 2", readonly=True)
    destination_city = fields.Char(related="sale_order_id.biziship_dest_city", string="Dest City", readonly=True)
    destination_state = fields.Char(related="sale_order_id.biziship_dest_state_id.code", string="Dest State", readonly=True)
    destination_zip = fields.Char(related="sale_order_id.biziship_dest_zip", string="Dest Zip", readonly=True)
    destination_phone = fields.Char(related="sale_order_id.partner_shipping_id.phone", string="Dest Phone", readonly=True)
    destination_contact_name = fields.Char(related="sale_order_id.biziship_dest_contact_name", readonly=True)
    destination_contact_phone = fields.Char(related="sale_order_id.biziship_dest_contact_phone", readonly=True)
    destination_contact_email = fields.Char(related="sale_order_id.biziship_dest_contact_email", readonly=True)

    # Quote Detailed Charges
    quote_details = fields.Text(related="quote_id.quote_details", readonly=True)

    carrier_name = fields.Char(related="quote_id.carrier_name", readonly=True)
    carrier_code = fields.Char(related="quote_id.carrier_code", readonly=True)
    total_charge = fields.Float(related="quote_id.total_charge", readonly=True)
    carrier_liability_new = fields.Float(related="quote_id.carrier_liability_new", readonly=True)
    carrier_liability_used = fields.Float(related="quote_id.carrier_liability_used", readonly=True)
    delivery_date = fields.Datetime(related="quote_id.delivery_date", readonly=True)
    currency = fields.Char(related="quote_id.currency", readonly=True)
    currency_id = fields.Many2one(related="quote_id.currency_id", readonly=True)
    quote_id_ref = fields.Char(related="quote_id.quote_id_ref", readonly=True)
    biziship_special_instructions = fields.Text(related="sale_order_id.biziship_special_instructions", readonly=True)
    priority1_env = fields.Char(related="sale_order_id.biziship_priority1_env", readonly=True)
    po_number = fields.Char(string="PO Number", compute='_compute_po_number', store=True, readonly=False)

    carrier_logo = fields.Binary(related="quote_id.carrier_logo", string="Carrier Logo", readonly=True)


    accessorial_services_text = fields.Text(string="Accessorial Services", compute='_compute_accessorial_services')
    has_accessorials = fields.Boolean(compute='_compute_accessorial_services')

    @api.depends('quote_id.sale_order_id.biziship_po_number', 'quote_id.sale_order_id.biziship_extracted_json')
    def _compute_po_number(self):
        for rec in self:
            po = False
            if rec.quote_id and rec.quote_id.sale_order_id:
                po = rec.quote_id.sale_order_id.biziship_po_number
                
                # Fallback to extracted JSON if empty
                if not po and rec.quote_id.sale_order_id.biziship_extracted_json:
                    try:
                        data = json.loads(rec.quote_id.sale_order_id.biziship_extracted_json)
                        po = data.get('po_number', False)
                    except Exception:
                        pass
            rec.po_number = po

    @api.depends('quote_id.sale_order_id.biziship_extracted_json')
    def _compute_accessorial_services(self):
        for rec in self:
            services_text = ""
            has_acc = False
            if rec.quote_id and rec.quote_id.sale_order_id and rec.quote_id.sale_order_id.biziship_extracted_json:
                try:
                    data = json.loads(rec.quote_id.sale_order_id.biziship_extracted_json)
                    codes = data.get('accessorial_codes', [])
                    if codes:
                        labels = [ACCESSORIAL_MAPPING.get(code, code) for code in codes]
                        services_text = "\n".join(f"• {label}" for label in labels)
                        has_acc = True
                except Exception:
                    pass
            rec.accessorial_services_text = services_text
            rec.has_accessorials = has_acc


    def action_confirm_and_send(self):
        self.ensure_one()
        
        if not self.po_number:
            raise UserError(_("Please provide a PO Number before submitting the quote."))
            
        email2quote_api_url = get_biziship_api_url()
        email2quote_api_key = get_email2quote_api_key()
        
        local_api_book_url = f"{email2quote_api_url.rstrip('/')}/book"
        headers = {
            "X-API-Key": email2quote_api_key,
            "Content-Type": "application/json",
            "X-User-Email": self.env.user.email or "",
            "X-Client-App": BIZISHIP_APP_NAME,
            "X-Client-Version": BIZISHIP_MODULE_VERSION,
        }
        
        sale_order = self.quote_id.sale_order_id
        
        # Save the confirmed PO Number back to the Sale Order if it was modified here
        if sale_order.biziship_po_number != self.po_number:
            sale_order.biziship_po_number = self.po_number
        
        
        extracted_data = {}
        if sale_order.biziship_extracted_json:
            try:
                extracted_data = json.loads(sale_order.biziship_extracted_json)
            except Exception:
                pass
                
        import re
        def format_phone(phone_str):
            if not phone_str:
                return None
            digits = re.sub(r'\D', '', phone_str)
            if len(digits) >= 10:
                return digits[-10:]
            return None

        company = self.env.company
        shipper = {
            "company_name": sale_order.biziship_origin_company or extracted_data.get("origin_company") or company.name,
            "address_line1": sale_order.biziship_origin_address or extracted_data.get("origin_address") or company.street or "",
            "address_line2": sale_order.biziship_origin_address2 or extracted_data.get("origin_address2") or company.street2 or "",
            "city": sale_order.biziship_origin_city or extracted_data.get("origin_city") or company.city or "",
            "state": sale_order.biziship_origin_state_id.code if sale_order.biziship_origin_state_id else (extracted_data.get("origin_state") or (company.state_id.code if company.state_id else "")),
            "zip": sale_order.biziship_origin_zip or extracted_data.get("origin_zip") or company.zip or "",
        }
        # Only add contact fields if explicitly set by the user
        if sale_order.biziship_origin_contact_name:
            shipper["contact_name"] = sale_order.biziship_origin_contact_name
            shipper["contact"] = sale_order.biziship_origin_contact_name
        origin_phone = format_phone(sale_order.biziship_origin_contact_phone)
        if origin_phone:
            shipper["phone"] = origin_phone
        if sale_order.biziship_origin_contact_email:
            shipper["email"] = sale_order.biziship_origin_contact_email

        partner = sale_order.partner_shipping_id or sale_order.partner_id
        consignee = {
            "company_name": sale_order.biziship_dest_company or extracted_data.get("destination_company") or partner.name,
            "address_line1": sale_order.biziship_dest_address or extracted_data.get("destination_address") or partner.street or "",
            "address_line2": sale_order.biziship_dest_address2 or extracted_data.get("destination_address2") or partner.street2 or "",
            "city": sale_order.biziship_dest_city or extracted_data.get("destination_city") or partner.city or "",
            "state": sale_order.biziship_dest_state_id.code if sale_order.biziship_dest_state_id else (extracted_data.get("destination_state") or (partner.state_id.code if partner.state_id else "")),
            "zip": sale_order.biziship_dest_zip or extracted_data.get("destination_zip") or partner.zip or "",
        }
        # Only add contact fields if explicitly set by the user
        if sale_order.biziship_dest_contact_name:
            consignee["contact_name"] = sale_order.biziship_dest_contact_name
            consignee["contact"] = sale_order.biziship_dest_contact_name
        dest_phone = format_phone(sale_order.biziship_dest_contact_phone)
        if dest_phone:
            consignee["phone"] = dest_phone
        if sale_order.biziship_dest_contact_email:
            consignee["email"] = sale_order.biziship_dest_contact_email
        
        from datetime import timedelta
        
        today = fields.Date.context_today(self)
        tomorrow = today + timedelta(days=1)
        pickup_date = extracted_data.get("pickup_date")
        if not pickup_date or str(pickup_date) < str(today):
            pickup_date = str(tomorrow)
            
        payload = {
            "quote_id": self.quote_id_ref,
            "po_number": self.po_number or "",
            "shipper": shipper,
            "consignee": consignee,
            "pickup_date": pickup_date,
            "pickup_note": sale_order.biziship_special_instructions or ""
        }

        _logger.info("BiziShip Booking API Request Headers: %s", headers)
        _logger.info("BiziShip Booking API Request Payload: %s", json.dumps(payload, indent=2))

        try:
            response = requests.post(
                local_api_book_url, 
                headers=headers, 
                json=payload, 
                timeout=45
            )
            if not response.ok:
                try:
                    error_json = response.json()
                    if 'errors' in error_json and isinstance(error_json['errors'], list) and len(error_json['errors']) > 0:
                        error_msg = error_json['errors'][0]
                    else:
                        error_msg = error_json.get('detail', response.text)
                except Exception:
                    error_msg = response.text
                raise UserError(_("%s") % error_msg)
                
            response_json = response.json()
            sale_order.write({
                'biziship_bol_number': response_json.get('bol_number'),
                'biziship_shipment_id': response_json.get('shipment_id'),
                'biziship_bol_url': response_json.get('bol_url'),
                'biziship_documents_json': json.dumps(response_json.get('documents', [])) if response_json.get('documents') else False
            })
            
        except requests.exceptions.RequestException as e:
            error_details = e.response.text if hasattr(e, 'response') and e.response is not None else str(e)
            raise UserError(_("Failed to contact Email2Quote booking API.\n\nDetails:\n%s") % error_details)

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
