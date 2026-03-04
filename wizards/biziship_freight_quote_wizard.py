import json
import requests
import re
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import os

from odoo.addons.BiziShipOnOdoo1.api_utils import get_biziship_api_url, get_email2quote_api_key

class BizishipFreightQuoteWizard(models.TransientModel):
    _name = 'biziship.freight.quote.wizard'
    _description = 'Get Direct LTL Freight Quotes'

    order_id = fields.Many2one('sale.order', string="Sale Order", required=True)
    
    # Pre-filled Origin
    origin_company = fields.Char(string="Origin Company")
    origin_city = fields.Char(string="Origin City")
    origin_state = fields.Char(string="Origin State", help="2-letter abbreviation")
    origin_zip = fields.Char(string="Origin Zip Code", required=True)
    origin_phone = fields.Char(string="Origin Phone")
    
    # Pre-filled Destination
    destination_company = fields.Char(string="Destination Company")
    destination_city = fields.Char(string="Destination City")
    destination_state = fields.Char(string="Destination State", help="2-letter abbreviation")
    destination_zip = fields.Char(string="Destination Zip Code", required=True)
    destination_phone = fields.Char(string="Destination Phone")
    
    # Freight Cargo details
    cargo_description = fields.Char(string="Cargo Description", default="General Freight")
    weight = fields.Float(string="Total Weight (lbs)", required=True, default=800.0)
    length = fields.Float(string="Length (in)", default=48.0)
    width = fields.Float(string="Width (in)", default=40.0)
    height = fields.Float(string="Height (in)", default=48.0)
    num_pieces = fields.Integer(string="Pieces (Handling Units)", default=1, required=True)
    packaging_type = fields.Selection([
        ('pallet', 'Pallet'),
        ('crate', 'Crate'),
        ('box', 'Box'),
        ('drum', 'Drum'),
    ], string="Packaging Type", default="pallet")
    freight_class = fields.Selection([
        ('50', '50'), ('55', '55'), ('60', '60'), ('65', '65'),
        ('70', '70'), ('77.5', '77.5'), ('85', '85'), ('92.5', '92.5'),
        ('100', '100'), ('110', '110'), ('125', '125'), ('150', '150'),
        ('175', '175'), ('200', '200'), ('250', '250'), ('300', '300'),
        ('400', '400'), ('500', '500')
    ], string="Freight Class", required=True, default='50')
    
    special_requirements = fields.Char(string="Special Requirements", help="Comma-separated. e.g. liftgate,residential_delivery")
    pickup_date = fields.Date(string="Pickup Date", required=True)
    additional_notes = fields.Text(string="Additional Notes")

    @api.model
    def default_get(self, fields_list):
        res = super(BizishipFreightQuoteWizard, self).default_get(fields_list)
        active_id = self.env.context.get('active_id')
        if not active_id:
            return res
            
        order = self.env['sale.order'].browse(active_id)
        if not order.exists():
            return res
            
        res['order_id'] = order.id
        
        # Origin mapping (Company warehouse)
        company = self.env.company
        res['origin_company'] = company.name or ''
        res['origin_city'] = company.city or ''
        res['origin_state'] = company.state_id.code if company.state_id else ''
        res['origin_zip'] = company.zip or '43341'
        res['origin_phone'] = company.phone or ''
        
        # Destination mapping (Customer)
        partner = order.partner_shipping_id or order.partner_id
        res['destination_company'] = partner.name or ''
        res['destination_city'] = partner.city or ''
        res['destination_state'] = partner.state_id.code if partner.state_id else ''
        res['destination_zip'] = partner.zip or '93036'
        res['destination_phone'] = partner.phone or ''
        
        # Automatically calculate weight from order lines if available
        total_weight = sum(line.product_id.weight * line.product_uom_qty for line in order.order_line if line.product_id)
        # Odoo's default demo products have a weight of 0.08, which overrides the 800.0 default. 
        # We enforce a minimum of 800.0 lbs for LTL quoting.
        res['weight'] = max(total_weight, 800.0)
            
        # Default Pickup Date to Tomorrow
        from datetime import timedelta
        res['pickup_date'] = fields.Date.context_today(self) + timedelta(days=1)
            
        return res

    @api.onchange('weight', 'length', 'width', 'height', 'num_pieces')
    def _onchange_dimensions_for_class(self):
        for rec in self:
            if rec.length and rec.width and rec.height and rec.weight and rec.num_pieces:
                volume_cf = (rec.length * rec.width * rec.height * rec.num_pieces) / 1728.0
                if volume_cf > 0:
                    density = rec.weight / volume_cf
                    if density < 1:
                        rec.freight_class = '500'
                    elif density < 2:
                        rec.freight_class = '400'
                    elif density < 3:
                        rec.freight_class = '300'
                    elif density < 4:
                        rec.freight_class = '250'
                    elif density < 5:
                        rec.freight_class = '200'
                    elif density < 6:
                        rec.freight_class = '175'
                    elif density < 7:
                        rec.freight_class = '150'
                    elif density < 8:
                        rec.freight_class = '125'
                    elif density < 9:
                        rec.freight_class = '110'
                    elif density < 10.5:
                        rec.freight_class = '100'
                    elif density < 12:
                        rec.freight_class = '92.5'
                    elif density < 13.5:
                        rec.freight_class = '85'
                    elif density < 15:
                        rec.freight_class = '77.5'
                    elif density < 22.5:
                        rec.freight_class = '70'
                    elif density < 30:
                        rec.freight_class = '65'
                    elif density < 35:
                        rec.freight_class = '60'
                    elif density < 50:
                        rec.freight_class = '55'
                    else:
                        rec.freight_class = '50'

    def _format_phone(self, phone_str):
        if not phone_str:
            return ""
        digits = re.sub(r'\D', '', phone_str)
        if len(digits) >= 10:
            return digits[-10:]
        return digits

    def action_get_quotes(self):
        self.ensure_one()
        
        email2quote_api_url = get_biziship_api_url()
        email2quote_api_key = get_email2quote_api_key()
        
        api_url = f"{email2quote_api_url.rstrip('/')}/quote/details"
        headers = {
            "X-API-Key": email2quote_api_key,
            "Content-Type": "application/json"
        }
        
        # Build JSON Payload
        payload = {
            "origin_company": self.origin_company or "",
            "origin_city": self.origin_city or "",
            "origin_state": self.origin_state or "",
            "origin_zip": self.origin_zip or "43341",
            "origin_phone": self._format_phone(self.origin_phone),
            "destination_company": self.destination_company or "",
            "destination_city": self.destination_city or "",
            "destination_state": self.destination_state or "",
            "destination_zip": self.destination_zip or "93036",
            "destination_phone": self._format_phone(self.destination_phone),
            "cargo_description": self.cargo_description or "",
            "weight": self.weight or 0.0,
            "weight_unit": "lbs",
            "length": self.length or 0.0,
            "width": self.width or 0.0,
            "height": self.height or 0.0,
            "dimension_unit": "inches",
            "num_pieces": self.num_pieces or 1,
            "packaging_type": self.packaging_type or "",
            "freight_class": self.freight_class or "",
            "special_requirements": [req.strip() for req in self.special_requirements.split(',')] if self.special_requirements else [],
            "pickup_date": str(self.pickup_date) if self.pickup_date else "",
            "additional_notes": self.additional_notes or ""
        }
        
        try:
            response = requests.post(api_url, headers=headers, json=payload, timeout=45)
            response.raise_for_status()
            
            response_json = response.json()
            quotes = response_json.get('quotes', [])
            
            if not quotes:
                raise UserError(_("No carrier quotes available for this lane. Check origin/destination zip codes or freight details."))
            
            # Save the JSON dict string directly to the sales order
            extracted_details = response_json.get('extracted_details', payload)
            self.order_id.write({'biziship_extracted_json': json.dumps(extracted_details)})
            
            # Clear old quotes before inserting new ones
            self.order_id.biziship_quote_ids.unlink()

            for q in quotes:
                delivery_date_raw = q.get('delivery_date')
                if delivery_date_raw and 'T' in delivery_date_raw:
                    delivery_date_raw = delivery_date_raw.replace('T', ' ')[:19]

                # Parse charges array into text
                charges = q.get('charges', [])
                details_lines = []
                for c in charges:
                    c_code = c.get('code', '')
                    c_desc = c.get('description', '')
                    c_amount = c.get('amount')
                    if c_amount is None:
                        c_amount = 0.0
                    details_lines.append(f"{str(c_desc):<40} ${c_amount:,.2f}")
                
                details_text = "\n".join(details_lines) if details_lines else "No detailed charges provided."

                self.env['biziship.quote'].sudo().create({
                    'sale_order_id': self.order_id.id,
                    'carrier_name': q.get('carrier_name'),
                    'carrier_code': q.get('carrier_code'),
                    'service_level': q.get('service_level'),
                    'transit_days': q.get('transit_days'),
                    'delivery_date': delivery_date_raw,
                    'total_charge': q.get('total_charge'),
                    'currency': q.get('currency', 'USD'),
                    'quote_id_ref': q.get('quote_id'),
                    'quote_details': details_text,
                })

        except requests.exceptions.HTTPError as e:
            err_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    err_json = e.response.json()
                    err_msg = err_json.get('detail', err_msg)
                except ValueError:
                    err_msg = e.response.text
            raise UserError(_("Email2Quote API Error:\n%s") % err_msg)
        except requests.exceptions.RequestException as e:
            raise UserError(_("Failed to connect to local Email2Quote API.\nEnsure server is running.\nDetails: %s") % str(e))

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
