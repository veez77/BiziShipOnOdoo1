import json
import requests
import os
from odoo import models, fields, api, _
from odoo.exceptions import UserError

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

from odoo.addons.BiziShipOnOdoo1.api_utils import get_biziship_api_url, get_email2quote_api_key


class BizishipQuoteConfirmWizard(models.TransientModel):
    _name = 'biziship.quote.confirm.wizard'
    _description = 'Confirm BiziShip Quote'

    quote_id = fields.Many2one('biziship.quote', string="Selected Quote", required=True)
    carrier_name = fields.Char(related="quote_id.carrier_name", readonly=True)
    total_charge = fields.Float(related="quote_id.total_charge", readonly=True)
    delivery_date = fields.Datetime(related="quote_id.delivery_date", readonly=True)
    currency = fields.Char(related="quote_id.currency", readonly=True)
    currency_id = fields.Many2one(related="quote_id.currency_id", readonly=True)
    quote_id_ref = fields.Char(related="quote_id.quote_id_ref", readonly=True)
    po_number = fields.Char(string="PO Number", compute='_compute_po_number', store=True, readonly=False)

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
            "Content-Type": "application/json"
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
                return "5555555555"
            digits = re.sub(r'\D', '', phone_str)
            if len(digits) >= 10:
                return digits[-10:]
            return "5555555555"

        company = self.env.company
        shipper = {
            "company_name": extracted_data.get("origin_company") or company.name,
            "address_line1": extracted_data.get("origin_address") or company.street or "",
            "address_line2": extracted_data.get("origin_address2") or company.street2 or "",
            "city": extracted_data.get("origin_city") or company.city or "",
            "state": extracted_data.get("origin_state") or (company.state_id.code if company.state_id else ""),
            "zip": extracted_data.get("origin_zip") or company.zip or "",
            "contact": company.name or "Contact",
            "phone": format_phone(extracted_data.get("origin_phone") or company.phone)
        }
        
        partner = sale_order.partner_shipping_id or sale_order.partner_id
        consignee = {
            "company_name": extracted_data.get("destination_company") or partner.name,
            "address_line1": extracted_data.get("destination_address") or partner.street or "",
            "address_line2": extracted_data.get("destination_address2") or partner.street2 or "",
            "city": extracted_data.get("destination_city") or partner.city or "",
            "state": extracted_data.get("destination_state") or (partner.state_id.code if partner.state_id else ""),
            "zip": extracted_data.get("destination_zip") or partner.zip or "",
            "contact": partner.name or "Contact",
            "phone": format_phone(extracted_data.get("destination_phone") or partner.phone)
        }
        
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
            "pickup_date": pickup_date
        }

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
