import json
import requests
import re
import os
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

from odoo.addons.BiziShip.api_utils import (
    get_biziship_api_url, 
    get_email2quote_api_key, 
    BIZISHIP_MODULE_VERSION, 
    BIZISHIP_APP_NAME,
    KG_TO_LBS,
    convert_to_lbs,
    convert_to_inches
)
class SaleOrder(models.Model):
    _inherit = 'sale.order'

    biziship_quote_ids = fields.One2many('biziship.quote', 'sale_order_id', string='Freight Quotes')
    biziship_extracted_json = fields.Text(string='BiziShip Extracted JSON', readonly=True)
    biziship_bol_number = fields.Char(string='BiziShip BOL Number', readonly=True, copy=False)
    biziship_shipment_id = fields.Char(string='BiziShip Shipment ID', readonly=True, copy=False)
    biziship_bol_url = fields.Char(string='BiziShip BOL Document URL', readonly=True, copy=False)
    biziship_has_selected_quote = fields.Boolean(compute='_compute_biziship_has_selected_quote')

    biziship_documents_json = fields.Text(string='Shipment Documents JSON', readonly=True, copy=False)
    biziship_documents_html = fields.Html(string='Shipment Documents', compute='_compute_biziship_documents_html', readonly=True)
    biziship_po_number = fields.Char(string="PO Number")

    @api.depends('biziship_documents_json', 'biziship_bol_url')
    def _compute_biziship_documents_html(self):
        for order in self:
            html_links = []
            if order.biziship_documents_json:
                try:
                    docs = json.loads(order.biziship_documents_json)
                    if isinstance(docs, list):
                        for doc in docs:
                            url = doc.get('url')
                            label = doc.get('label', doc.get('type', 'Document'))
                            if url:
                                html_links.append(
                                    f'<div class="mb-2">'
                                    f'<a href="{url}" target="_blank" style="color: #0b7a40; font-weight: 500; font-size: 15px; text-decoration: underline; white-space: nowrap; display: inline-block;">'
                                    f'{label} <i class="fa fa-download ms-1"></i></a>'
                                    f'</div>'
                                )
                except Exception:
                    pass
            
            # Fallback to single BOL URL if no valid documents array found, but URL exists
            if not html_links and order.biziship_bol_url:
                html_links.append(
                    f'<div class="mb-2">'
                    f'<a href="{order.biziship_bol_url}" target="_blank" style="color: #0b7a40; font-weight: 500; font-size: 15px; text-decoration: underline; white-space: nowrap; display: inline-block;">'
                    f'Bill of Lading <i class="fa fa-download ms-1"></i></a>'
                    f'</div>'
                )
            
            if html_links:
                order.biziship_documents_html = f'<div class="d-flex flex-column mt-2">{"".join(html_links)}</div>'
            else:
                order.biziship_documents_html = ""

    # --- LTL Freight Fields ---
    # Origin & Pickup
    biziship_pickup_date = fields.Date(string="Pickup Date", default=lambda self: fields.Date.context_today(self))
    biziship_origin_company = fields.Char(string="Origin Company", default=lambda self: self.env.company.name or '')
    biziship_origin_address = fields.Char(string="Pickup Address Line 1", default=lambda self: self.env.company.street or '')
    biziship_origin_address2 = fields.Char(string="Pickup Address Line 2", default=lambda self: self.env.company.street2 or '')
    biziship_origin_zip = fields.Char(string="Pickup Zip Code", default=lambda self: self.env.company.zip or '')
    biziship_origin_country_id = fields.Many2one('res.country', string="Origin Country", default=lambda self: self.env.company.country_id.id if self.env.company.country_id else False)
    
    biziship_origin_residential = fields.Boolean(string="Residential Pickup")
    biziship_origin_liftgate = fields.Boolean(string="Lift Gate Pickup")
    biziship_origin_limited_access = fields.Boolean(string="Limited Access Pickup")
    biziship_origin_accessorial_ids = fields.Many2many(
        'biziship.accessorial',
        'sale_order_origin_accessorial_rel',
        'order_id', 'accessorial_id',
        string="More Services (Pickup)",
        domain="[('type', '=', 'origin')]"
    )

    # Destination
    biziship_dest_company = fields.Char(string="Destination Company", related="partner_shipping_id.name", readonly=False, store=True)

    biziship_priority1_env = fields.Char(string="Priority1 Environment", help="DEV or PROD", readonly=True)
    biziship_dest_address = fields.Char(string="Destination Address Line 1", related="partner_shipping_id.street", readonly=False, store=True)
    biziship_dest_address2 = fields.Char(string="Destination Address Line 2", related="partner_shipping_id.street2", readonly=False, store=True)
    biziship_dest_zip = fields.Char(string="Destination Zip Code", related="partner_shipping_id.zip", readonly=False, store=True)
    biziship_dest_country_id = fields.Many2one('res.country', string="Destination Country", compute='_compute_biziship_dest_country_id', readonly=False, store=True)
    
    biziship_dest_appointment = fields.Boolean(string="Delivery Appointment")
    biziship_dest_residential = fields.Boolean(string="Residential Delivery")
    biziship_dest_notify = fields.Boolean(string="Notify Consignee")
    biziship_dest_limited_access = fields.Boolean(string="Limited Access Delivery")
    biziship_dest_liftgate = fields.Boolean(string="Lift Gate Delivery")
    biziship_dest_hazmat = fields.Boolean(string="Hazardous Material")
    biziship_dest_accessorial_ids = fields.Many2many(
        'biziship.accessorial',
        'sale_order_dest_accessorial_rel',
        'order_id', 'accessorial_id',
        string="More Services (Delivery)",
        domain="[('type', '=', 'destination')]"
    )

    @api.onchange('biziship_dest_residential')
    def _onchange_biziship_dest_residential(self):
        if self.biziship_dest_residential:
            self.biziship_dest_liftgate = True

    @api.depends('partner_shipping_id', 'partner_shipping_id.country_id')
    def _compute_biziship_dest_country_id(self):
        us_country = self.env.ref('base.us', raise_if_not_found=False)
        for order in self:
            if order.partner_shipping_id and order.partner_shipping_id.country_id:
                order.biziship_dest_country_id = order.partner_shipping_id.country_id
            elif not order.biziship_dest_country_id and us_country:
                order.biziship_dest_country_id = us_country

    # Cargo details
    biziship_cargo_line_ids = fields.One2many('biziship.sale.cargo.line', 'sale_order_id', string="Cargo Lines")
    
    biziship_total_weight = fields.Float(string="Total Weight", compute='_compute_biziship_totals', store=True)
    biziship_total_weight_unit = fields.Selection([('lbs', 'lbs'), ('kg', 'kg')], string="Weight Unit", default='lbs', required=True)
    
    biziship_cargo_desc = fields.Char(string="Cargo Description", default="General Freight")
    biziship_special_instructions = fields.Text(string="Special Instructions")

    @api.depends('biziship_cargo_line_ids', 'biziship_cargo_line_ids.weight', 'biziship_cargo_line_ids.weight_unit', 'biziship_total_weight_unit')
    def _compute_biziship_totals(self):
        for order in self:
            total_lbs = 0.0
            for line in order.biziship_cargo_line_ids:
                total_lbs += convert_to_lbs(line.weight, line.weight_unit)
                    
            if order.biziship_total_weight_unit == 'kg':
                order.biziship_total_weight = round(total_lbs / KG_TO_LBS, 2)
            else:
                order.biziship_total_weight = round(total_lbs, 2)

    @api.depends('biziship_quote_ids.is_selected')
    def _compute_biziship_has_selected_quote(self):
        for order in self:
            order.biziship_has_selected_quote = any(q.is_selected for q in order.biziship_quote_ids)

    def action_open_biziship_quote_confirm(self):
        self.ensure_one()
        selected_quote = self.biziship_quote_ids.filtered(lambda q: q.is_selected)
        if not selected_quote:
            raise models.ValidationError("Please select a quote from the LTL Freight Quotes list first.")
        
        if self.biziship_priority1_env == 'PROD':
            return {
                'name': 'Live Freight Booking',
                'type': 'ir.actions.act_window',
                'res_model': 'biziship.booking.warning.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_quote_id': selected_quote[0].id,
                }
            }

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

    def action_biziship_uncheck_all_origin(self):
        for order in self:
            order.write({
                'biziship_origin_residential': False,
                'biziship_origin_liftgate': False,
                'biziship_origin_limited_access': False,
                'biziship_origin_accessorial_ids': [(5, 0, 0)]
            })
        return True

    def action_biziship_uncheck_all_dest(self):
        for order in self:
            order.write({
                'biziship_dest_appointment': False,
                'biziship_dest_residential': False,
                'biziship_dest_notify': False,
                'biziship_dest_limited_access': False,
                'biziship_dest_liftgate': False,
                'biziship_dest_hazmat': False,
                'biziship_dest_accessorial_ids': [(5, 0, 0)]
            })
        return True

    def action_biziship_copy_customer_to_dest(self):
        self.ensure_one()
        if self.partner_id:
            self.write({
                'biziship_dest_company': self.partner_id.name,
                'biziship_dest_address': self.partner_id.street,
                'biziship_dest_address2': self.partner_id.street2,
                'biziship_dest_zip': self.partner_id.zip,
                'biziship_dest_country_id': self.partner_id.country_id.id if self.partner_id.country_id else False,
            })
        return True

    def action_biziship_save_to_pool(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Save Freight to My Pool'),
            'res_model': 'biziship.save.freight.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_sale_order_id': self.id}
        }

    def action_biziship_load_from_pool(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Load Saved Freight'),
            'res_model': 'biziship.load.freight.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_sale_order_id': self.id}
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
                'biziship_documents_json': False,
            })
            # Also reset selection
            for quote in order.biziship_quote_ids:
                quote.is_selected = False
        return True

    def action_biziship_compute_weight(self):
        """Hook for later when computing total weight from order lines."""
        for order in self:
            pass
        return True

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
        if not self.biziship_origin_zip or not self.biziship_dest_zip or not self.biziship_total_weight or not self.biziship_pickup_date:
            raise UserError(_("Origin Zip, Destination Zip, Total Weight, and Pickup Date are required to fetch LTL quotes."))
        if not self.biziship_cargo_line_ids:
            raise UserError(_("At least one cargo line is required to fetch LTL quotes."))
            
        for idx, line in enumerate(self.biziship_cargo_line_ids, start=1):
            if line.pieces <= 0 or line.weight <= 0 or line.length <= 0 or line.width <= 0 or line.height <= 0:
                raise UserError(_("Cargo Line #%s has a missing or zero value. All cargo lines must have Pieces, Weight, Length, Width, and Height greater than 0.") % idx)

        email2quote_api_url = get_biziship_api_url()
        email2quote_api_key = get_email2quote_api_key()
        
        api_url = f"{email2quote_api_url.rstrip('/')}/quote/details"
        headers = {
            "X-API-Key": email2quote_api_key,
            "Content-Type": "application/json",
            "X-User-Email": self.env.user.email or "",
            "X-Client-App": BIZISHIP_APP_NAME,
            "X-Client-Version": BIZISHIP_MODULE_VERSION,
        }
        
        # Compile accessorials starting with tags
        accessorials_list = self.biziship_origin_accessorial_ids.mapped('code') + self.biziship_dest_accessorial_ids.mapped('code')
        
        # Origin Checkboxes
        if self.biziship_origin_residential: accessorials_list.append("RESPU")
        if self.biziship_origin_liftgate: accessorials_list.append("LGPU")
        if self.biziship_origin_limited_access: accessorials_list.append("LTDPU")
        
        # Destination Checkboxes
        if self.biziship_dest_residential: accessorials_list.append("RESDEL")
        if self.biziship_dest_liftgate: accessorials_list.append("LGDEL")
        if self.biziship_dest_limited_access: accessorials_list.append("LTDDEL")
        if self.biziship_dest_appointment: accessorials_list.append("APPT")
        if self.biziship_dest_notify: accessorials_list.append("NOTIFY")
        if self.biziship_dest_hazmat: accessorials_list.append("HAZM")
        
        accessorials_list = list(set(accessorials_list))  # Ensure uniqueness

        # Basic phone retrieval (company vs partner)
        origin_phone = self.company_id.phone or self.env.company.phone or ''
        dest_phone = self.partner_shipping_id.phone or self.partner_id.phone or ''
        
        # Build generic payload weights
        payload_weight = convert_to_lbs(self.biziship_total_weight, self.biziship_total_weight_unit)

        payload_items = []
        for line in self.biziship_cargo_line_ids:
            line_w = convert_to_lbs(line.weight, line.weight_unit)
            
            payload_l = convert_to_inches(line.length, line.dim_unit)
            payload_w = convert_to_inches(line.width, line.dim_unit)
            payload_h = convert_to_inches(line.height, line.dim_unit)
                
            payload_items.append({
                "weight": round(line_w, 2),
                "weight_unit": "lbs",
                "length": round(payload_l, 2),
                "width": round(payload_w, 2),
                "height": round(payload_h, 2),
                "dimension_unit": "inches",
                "num_pieces": line.pieces or 1,
                "packaging_type": line.packaging_type or "",
                "freight_class": line.computed_freight_class or line.freight_class or "",
                "cargo_description": line.cargo_desc or ""
            })

        # Base payload properties
        payload = {
            "origin_company": self.biziship_origin_company or self.company_id.name or self.env.company.name or "",
            "origin_address": self.biziship_origin_address or "",
            "origin_address2": self.biziship_origin_address2 or "",
            "origin_city": self.company_id.city or self.env.company.city or "",
            "origin_state": self.company_id.state_id.code if self.company_id.state_id else "",
            "origin_zip": self.biziship_origin_zip,
            "origin_country": self.biziship_origin_country_id.code if self.biziship_origin_country_id else "US",
            "origin_phone": self._format_phone(origin_phone),
            "destination_company": self.biziship_dest_company or self.partner_shipping_id.name or self.partner_id.name or "",
            "destination_address": self.biziship_dest_address or "",
            "destination_address2": self.biziship_dest_address2 or "",
            "destination_city": self.partner_shipping_id.city or self.partner_id.city or "",
            "destination_state": self.partner_shipping_id.state_id.code if self.partner_shipping_id.state_id else "",
            "destination_zip": self.biziship_dest_zip,
            "destination_country": self.biziship_dest_country_id.code if self.biziship_dest_country_id else "US",
            "destination_phone": self._format_phone(dest_phone),
            "cargo_description": self.biziship_cargo_desc or "",
            "weight": round(payload_weight, 2),
            "weight_unit": "lbs",
            "line_items": payload_items,
            "accessorial_codes": accessorials_list,
            "pickup_date": str(self.biziship_pickup_date) if self.biziship_pickup_date else "",
            "special_instructions": self.biziship_special_instructions or "",
            "is_biziship": True
        }
        
        _logger.info("BiziShip Quote API Request Headers (Sale Order): %s", headers)
        _logger.info("BiziShip Quote API Request Payload (Sale Order): %s", json.dumps(payload, indent=2))
        
        try:
            response = requests.post(api_url, headers=headers, json=payload, timeout=45)
            response.raise_for_status()
            
            response_json = response.json()
            quotes = response_json.get('quotes', [])
            
            # Capture environment from top level
            p1_env = response_json.get('priority1_env', 'DEV')
            self.biziship_priority1_env = p1_env
            
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
                    'carrier_liability_new': q.get('carrier_liability_new'),
                    'carrier_liability_used': q.get('carrier_liability_used'),
                    'origin_address': extracted_details.get('origin_address'),
                    'origin_address2': extracted_details.get('origin_address2'),
                    'destination_address': extracted_details.get('destination_address'),
                    'destination_address2': extracted_details.get('destination_address2'),
                    'origin_terminal_city': extracted_details.get('origin_terminal_city'),
                    'origin_terminal_state': extracted_details.get('origin_terminal_state'),
                    'origin_terminal_phone': extracted_details.get('origin_terminal_phone'),
                    'destination_terminal_city': extracted_details.get('destination_terminal_city'),
                    'destination_terminal_state': extracted_details.get('destination_terminal_state'),
                    'destination_terminal_phone': extracted_details.get('destination_terminal_phone'),
                    'quote_details': details_text,
                })

        except requests.exceptions.HTTPError as e:
            err_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    err_json = e.response.json()
                    if 'errors' in err_json and isinstance(err_json['errors'], list) and len(err_json['errors']) > 0:
                        err_msg = err_json['errors'][0]
                    else:
                        err_msg = err_json.get('detail', err_msg)
                except ValueError:
                    err_msg = e.response.text
            raise UserError(_("%s") % err_msg)
        except requests.exceptions.RequestException as e:
            raise UserError(_("Failed to connect to local Email2Quote API.\nEnsure server is running.\nDetails: %s") % str(e))

        return True
