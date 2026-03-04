import json
import requests
import re
import os
from odoo import models, fields, api, _
from odoo.exceptions import UserError

from odoo.addons.BiziShipOnOdoo1.api_utils import get_biziship_api_url, get_email2quote_api_key
class SaleOrder(models.Model):
    _inherit = 'sale.order'

    biziship_quote_ids = fields.One2many('biziship.quote', 'sale_order_id', string='Freight Quotes')
    biziship_extracted_json = fields.Text(string='BiziShip Extracted JSON', readonly=True)
    biziship_bol_number = fields.Char(string='BiziShip BOL Number', readonly=True, copy=False)
    biziship_shipment_id = fields.Char(string='BiziShip Shipment ID', readonly=True, copy=False)
    biziship_bol_url = fields.Char(string='BiziShip BOL Document URL', readonly=True, copy=False)
    biziship_has_selected_quote = fields.Boolean(compute='_compute_biziship_has_selected_quote')

    # --- LTL Freight Fields ---
    # Origin & Pickup
    biziship_pickup_date = fields.Date(string="Pickup Date", default=lambda self: fields.Date.context_today(self))
    biziship_origin_zip = fields.Char(string="Pickup Zip Code", default=lambda self: self.env.company.zip or '')
    biziship_origin_country_id = fields.Many2one('res.country', string="Origin Country", default=lambda self: self.env.company.country_id.id if self.env.company.country_id else False)
    
    biziship_origin_residential = fields.Boolean(string="Residential Pickup")
    biziship_origin_liftgate = fields.Boolean(string="Lift Gate Pickup")
    biziship_origin_limited_access = fields.Boolean(string="Limited Access Pickup")

    # Destination
    biziship_dest_zip = fields.Char(string="Destination Zip Code", related="partner_shipping_id.zip", readonly=False, store=True)
    biziship_dest_country_id = fields.Many2one('res.country', string="Destination Country", compute='_compute_biziship_dest_country_id', readonly=False, store=True)
    
    biziship_dest_appointment = fields.Boolean(string="Delivery Appointment")
    biziship_dest_residential = fields.Boolean(string="Residential Delivery")
    biziship_dest_notify = fields.Boolean(string="Notify Consignee")
    biziship_dest_limited_access = fields.Boolean(string="Limited Access Delivery")
    biziship_dest_liftgate = fields.Boolean(string="Lift Gate Delivery")
    biziship_dest_hazmat = fields.Boolean(string="Hazardous Material")

    @api.depends('partner_shipping_id', 'partner_shipping_id.country_id')
    def _compute_biziship_dest_country_id(self):
        us_country = self.env.ref('base.us', raise_if_not_found=False)
        for order in self:
            if order.partner_shipping_id and order.partner_shipping_id.country_id:
                order.biziship_dest_country_id = order.partner_shipping_id.country_id
            elif not order.biziship_dest_country_id and us_country:
                order.biziship_dest_country_id = us_country

    # Cargo details
    biziship_packaging_type = fields.Selection([
        ('pallet', 'Pallet'),
        ('crate', 'Crate'),
        ('box', 'Box'),
        ('drum', 'Drum'),
    ], string="Packaging Type", default="pallet")
    biziship_pieces = fields.Integer(string="Pieces (Handling Units)", default=1)
    biziship_weight = fields.Float(string="Total Weight (lbs)", default=800.0)
    biziship_length = fields.Float(string="Length (in)", default=48.0)
    biziship_width = fields.Float(string="Width (in)", default=40.0)
    biziship_height = fields.Float(string="Height (in)", default=48.0)
    biziship_freight_class = fields.Selection([
        ('50', '50'), ('55', '55'), ('60', '60'), ('65', '65'),
        ('70', '70'), ('77.5', '77.5'), ('85', '85'), ('92.5', '92.5'),
        ('100', '100'), ('110', '110'), ('125', '125'), ('150', '150'),
        ('175', '175'), ('200', '200'), ('250', '250'), ('300', '300'),
        ('400', '400'), ('500', '500')
    ], string="Class", default='50')
    
    biziship_computed_freight_class = fields.Selection([
        ('50', '50'), ('55', '55'), ('60', '60'), ('65', '65'),
        ('70', '70'), ('77.5', '77.5'), ('85', '85'), ('92.5', '92.5'),
        ('100', '100'), ('110', '110'), ('125', '125'), ('150', '150'),
        ('175', '175'), ('200', '200'), ('250', '250'), ('300', '300'),
        ('400', '400'), ('500', '500')
    ], string="Computed Class", compute='_compute_biziship_computed_class', store=True)
    
    biziship_is_class_overridden = fields.Boolean(compute='_compute_biziship_is_class_overridden')
    biziship_class_calculation_error = fields.Char(compute='_compute_biziship_class_calculation_error')
    
    biziship_nmfc = fields.Char(string="NMFC")
    biziship_cargo_desc = fields.Char(string="Cargo Description", default="General Freight")

    @api.depends('biziship_quote_ids.is_selected')
    def _compute_biziship_has_selected_quote(self):
        for order in self:
            order.biziship_has_selected_quote = any(q.is_selected for q in order.biziship_quote_ids)

    def action_open_biziship_quote_confirm(self):
        self.ensure_one()
        selected_quote = self.biziship_quote_ids.filtered(lambda q: q.is_selected)
        if not selected_quote:
            raise models.ValidationError("Please select a quote from the LTL Freight Quotes list first.")
        
        return {
            'name': 'Confirm Quote Selection',
            'type': 'ir.actions.act_window',
            'res_model': 'biziship.quote.confirm.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_quote_id': selected_quote[0].id,
            }
        }

    def action_demo_vinegar_order(self):
        self.ensure_one()
        
        # 1. Find or create a remote customer in CA
        partner = self.env['res.partner'].search([('name', '=', 'Vinegar Customer Co.')], limit=1)
        if not partner:
            ca_state = self.env['res.country.state'].search([('code', '=', 'CA'), ('country_id.code', '=', 'US')], limit=1)
            us_country = self.env.ref('base.us', raise_if_not_found=False)
            partner = self.env['res.partner'].create({
                'name': 'Vinegar Customer Co.',
                'street': '123 Fake St',
                'city': 'Beverly Hills',
                'state_id': ca_state.id if ca_state else False,
                'zip': '90210',
                'country_id': us_country.id if us_country else False,
                'phone': '3105551234',
            })
        
        # 2. Find or create a heavy Pallet of Vinegar product
        product = self.env['product.product'].search([('name', '=', 'Pallet of Vinegar')], limit=1)
        if not product:
            product = self.env['product.product'].create({
                'name': 'Pallet of Vinegar',
                'type': 'consu',
                'weight': 1500.0,
                'list_price': 500.0,
            })
            
        # 3. Clear current order and populate
        self.partner_id = partner
        self.partner_shipping_id = partner
        self.order_line = [(5, 0, 0)] # Delete all existing lines
        self.env['sale.order.line'].create({
            'order_id': self.id,
            'product_id': product.id,
            'product_uom_qty': 1.0,
            'price_unit': 500.0,
        })
        
        return True

    def action_delete_biziship_quotes(self):
        for order in self:
            order.biziship_quote_ids.unlink()
        return True

    def action_delete_biziship_booking(self):
        for order in self:
            order.write({
                'biziship_bol_number': False,
                'biziship_shipment_id': False,
                'biziship_bol_url': False,
                'biziship_extracted_json': False,
            })
            # Also reset selection
            for quote in order.biziship_quote_ids:
                quote.is_selected = False
        return True

    def action_biziship_compute_weight(self):
        for order in self:
            total_weight = sum(line.product_id.weight * line.product_uom_qty for line in order.order_line if line.product_id)
            order.biziship_weight = max(total_weight, 800.0)
        return True

    @api.depends('biziship_weight', 'biziship_length', 'biziship_width', 'biziship_height', 'biziship_pieces')
    def _compute_biziship_computed_class(self):
        for rec in self:
            if rec.biziship_length and rec.biziship_width and rec.biziship_height and rec.biziship_weight and rec.biziship_pieces:
                volume_cf = (rec.biziship_length * rec.biziship_width * rec.biziship_height * rec.biziship_pieces) / 1728.0
                if volume_cf > 0:
                    density = rec.biziship_weight / volume_cf
                    if density < 1: rec.biziship_computed_freight_class = '500'
                    elif density < 2: rec.biziship_computed_freight_class = '400'
                    elif density < 3: rec.biziship_computed_freight_class = '300'
                    elif density < 4: rec.biziship_computed_freight_class = '250'
                    elif density < 5: rec.biziship_computed_freight_class = '200'
                    elif density < 6: rec.biziship_computed_freight_class = '175'
                    elif density < 7: rec.biziship_computed_freight_class = '150'
                    elif density < 8: rec.biziship_computed_freight_class = '125'
                    elif density < 9: rec.biziship_computed_freight_class = '110'
                    elif density < 10.5: rec.biziship_computed_freight_class = '100'
                    elif density < 12: rec.biziship_computed_freight_class = '92.5'
                    elif density < 13.5: rec.biziship_computed_freight_class = '85'
                    elif density < 15: rec.biziship_computed_freight_class = '77.5'
                    elif density < 22.5: rec.biziship_computed_freight_class = '70'
                    elif density < 30: rec.biziship_computed_freight_class = '65'
                    elif density < 35: rec.biziship_computed_freight_class = '60'
                    elif density < 50: rec.biziship_computed_freight_class = '55'
                    else: rec.biziship_computed_freight_class = '50'
                else:
                    rec.biziship_computed_freight_class = '50'
            else:
                rec.biziship_computed_freight_class = '50'

    @api.onchange('biziship_computed_freight_class')
    def _onchange_biziship_computed_class(self):
        for rec in self:
            rec.biziship_freight_class = rec.biziship_computed_freight_class

    @api.depends('biziship_freight_class', 'biziship_computed_freight_class')
    def _compute_biziship_is_class_overridden(self):
        for rec in self:
            rec.biziship_is_class_overridden = bool(
                rec.biziship_freight_class 
                and rec.biziship_computed_freight_class 
                and rec.biziship_freight_class != rec.biziship_computed_freight_class
            )

    @api.depends('biziship_weight', 'biziship_length', 'biziship_width', 'biziship_height', 'biziship_pieces')
    def _compute_biziship_class_calculation_error(self):
        for rec in self:
            errors = []
            if not rec.biziship_weight:
                errors.append("Missing Weight.")
            if not rec.biziship_length or not rec.biziship_width or not rec.biziship_height:
                errors.append("Missing Dimensions.")
            if not rec.biziship_pieces:
                errors.append("Invalid Pieces.")
            
            if errors:
                rec.biziship_class_calculation_error = " ".join(errors)
            else:
                rec.biziship_class_calculation_error = False

    def _format_phone(self, phone_str):
        if not phone_str:
            return ""
        digits = re.sub(r'\D', '', phone_str)
        if len(digits) >= 10:
            return digits[-10:]
        return digits

    def action_biziship_fetch_live_quotes(self):
        self.ensure_one()
        
        # Validation
        if not self.biziship_origin_zip or not self.biziship_dest_zip or not self.biziship_weight or not self.biziship_pickup_date:
            raise UserError(_("Origin Zip, Destination Zip, Weight, and Pickup Date are required to fetch LTL quotes."))

        email2quote_api_url = get_biziship_api_url()
        email2quote_api_key = get_email2quote_api_key()
        
        api_url = f"{email2quote_api_url.rstrip('/')}/quote/details"
        headers = {
            "X-API-Key": email2quote_api_key,
            "Content-Type": "application/json"
        }
        
        # Compile special requirements
        special_reqs = []
        if self.biziship_origin_residential: special_reqs.append("residential_pickup")
        if self.biziship_origin_liftgate: special_reqs.append("liftgate_pickup")
        if self.biziship_origin_limited_access: special_reqs.append("limited_access_pickup")
        if self.biziship_dest_appointment: special_reqs.append("appointment")
        if self.biziship_dest_residential: special_reqs.append("residential_delivery")
        if self.biziship_dest_notify: special_reqs.append("notify_consignee")
        if self.biziship_dest_limited_access: special_reqs.append("limited_access_delivery")
        if self.biziship_dest_liftgate: special_reqs.append("liftgate_delivery")
        if self.biziship_dest_hazmat: special_reqs.append("hazmat")

        # Basic phone retrieval (company vs partner)
        origin_phone = self.company_id.phone or self.env.company.phone or ''
        dest_phone = self.partner_shipping_id.phone or self.partner_id.phone or ''
        
        # Build JSON Payload
        payload = {
            "origin_company": self.company_id.name or self.env.company.name or "",
            "origin_city": self.company_id.city or self.env.company.city or "",
            "origin_state": self.company_id.state_id.code if self.company_id.state_id else "",
            "origin_zip": self.biziship_origin_zip,
            "origin_phone": self._format_phone(origin_phone),
            "destination_company": self.partner_shipping_id.name or self.partner_id.name or "",
            "destination_city": self.partner_shipping_id.city or self.partner_id.city or "",
            "destination_state": self.partner_shipping_id.state_id.code if self.partner_shipping_id.state_id else "",
            "destination_zip": self.biziship_dest_zip,
            "destination_phone": self._format_phone(dest_phone),
            "cargo_description": self.biziship_cargo_desc or "",
            "weight": self.biziship_weight or 0.0,
            "weight_unit": "lbs",
            "length": self.biziship_length or 0.0,
            "width": self.biziship_width or 0.0,
            "height": self.biziship_height or 0.0,
            "dimension_unit": "inches",
            "num_pieces": self.biziship_pieces or 1,
            "packaging_type": self.biziship_packaging_type or "",
            "freight_class": self.biziship_freight_class or "",
            "special_requirements": special_reqs,
            "pickup_date": str(self.biziship_pickup_date) if self.biziship_pickup_date else "",
            "additional_notes": "" # Can add note field later if requested
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
            self.write({'biziship_extracted_json': json.dumps(extracted_details)})
            
            # Clear old quotes before inserting new ones
            self.biziship_quote_ids.unlink()

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
                    'sale_order_id': self.id,
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

        return True
