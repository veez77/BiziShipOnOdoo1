import json
import requests
import os
from odoo import models, fields, _
from odoo.exceptions import UserError

def get_secrets():
    secrets_path = os.path.join(os.path.dirname(__file__), '..', 'secrets.json')
    if os.path.exists(secrets_path):
        with open(secrets_path, 'r') as f:
            return json.load(f)
    return {}


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

    def action_confirm_and_send(self):
        self.ensure_one()
        secrets = get_secrets()
        email2quote_api_url = secrets.get("EMAIL2QUOTE_API_URL", "http://localhost:8000")
        email2quote_api_key = secrets.get("EMAIL2QUOTE_API_KEY", "")
        
        local_api_book_url = f"{email2quote_api_url.rstrip('/')}/book"
        headers = {
            "X-API-Key": email2quote_api_key,
            "Content-Type": "application/json"
        }
        
        sale_order = self.quote_id.sale_order_id
        
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
            "company_name": company.name or "Shipper LLC",
            "address_line1": f"{company.street or ''} {company.street2 or ''}".strip() or "123 Main St",
            "city": extracted_data.get("origin_city", company.city or ""),
            "state": extracted_data.get("origin_state", company.state_id.code if company.state_id else ""),
            "zip": extracted_data.get("origin_zip", company.zip or ""),
            "contact": company.name or "Contact",
            "phone": format_phone(extracted_data.get("origin_phone", company.phone))
        }
        
        partner = sale_order.partner_shipping_id or sale_order.partner_id
        consignee = {
            "company_name": partner.name or "Consignee LLC",
            "address_line1": f"{partner.street or ''} {partner.street2 or ''}".strip() or "456 Main St",
            "city": extracted_data.get("destination_city", partner.city or ""),
            "state": extracted_data.get("destination_state", partner.state_id.code if partner.state_id else ""),
            "zip": extracted_data.get("destination_zip", partner.zip or ""),
            "contact": partner.name or "Contact",
            "phone": format_phone(extracted_data.get("destination_phone", partner.phone))
        }
        
        from datetime import timedelta
        
        today = fields.Date.context_today(self)
        tomorrow = today + timedelta(days=1)
        pickup_date = extracted_data.get("pickup_date")
        if not pickup_date or str(pickup_date) < str(today):
            pickup_date = str(tomorrow)
            
        payload = {
            "quote_id": self.quote_id_ref,
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
                raise UserError(_("Email2Quote API error: %s") % response.text)
                
            response_json = response.json()
            sale_order.write({
                'biziship_bol_number': response_json.get('bol_number'),
                'biziship_shipment_id': response_json.get('shipment_id'),
                'biziship_bol_url': response_json.get('bol_url')
            })
            
        except requests.exceptions.RequestException as e:
            error_details = e.response.text if hasattr(e, 'response') and e.response is not None else str(e)
            raise UserError(_("Failed to contact Email2Quote booking API.\n\nDetails:\n%s") % error_details)

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
