import requests
import json
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class BizishipLoadFreightWizard(models.TransientModel):
    _name = 'biziship.load.freight.wizard'
    _description = 'Load Saved Freight'

    freight_id = fields.Selection(selection='_get_saved_freights', string='Select Freight', required=True)
    sale_order_id = fields.Many2one('sale.order', string='Sale Order')

    @api.model
    def _get_saved_freights(self):
        token = self.env.user.biziship_token
        if not token:
            return []
        
        url = "https://api.biziship.ai/saved-freights"
        headers = {"Authorization": f"Bearer {token}"}
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                freights = response.json()
                return [(f['id'], f['name']) for f in freights]
            elif response.status_code == 401:
                return []
            return []
        except:
            return []

    def action_load_freight(self):
        self.ensure_one()
        token = self.env.user.biziship_token
        if not token:
            raise UserError(_("Please connect your BiziShip account first."))

        url = f"https://api.biziship.ai/saved-freights"
        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            # We need to find the full data for the selected ID.
            # Backend GET /saved-freights returns the list with freightDetails.
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                raise UserError(_("Failed to fetch freight details."))
            
            freights = response.json()
            selected_freight = next((f for f in freights if f['id'] == self.freight_id), None)
            
            if not selected_freight or 'freightDetails' not in selected_freight:
                raise UserError(_("Selected freight details not found."))
            
            details = selected_freight['freightDetails']
            order = self.sale_order_id
            
            vals = {
                'biziship_origin_company': details.get('origin_company'),
                'biziship_origin_address': details.get('origin_address'),
                'biziship_origin_address2': details.get('origin_address2'),
                'biziship_origin_zip': details.get('origin_zip'),
                'biziship_dest_company': details.get('destination_company'),
                'biziship_dest_address': details.get('destination_address'),
                'biziship_dest_address2': details.get('destination_address2'),
                'biziship_dest_zip': details.get('destination_zip'),
                'biziship_cargo_desc': details.get('cargo_description', 'General Freight'),
                'biziship_special_instructions': details.get('special_instructions'),
                'biziship_po_number': details.get('po_number'),
                'biziship_total_weight_unit': details.get('weight_unit', 'lbs'),
            }
            
            # Map countries if codes are provided
            if details.get('origin_country_id'):
                country = self.env['res.country'].search([('code', '=', details['origin_country_id'])], limit=1)
                if country:
                    vals['biziship_origin_country_id'] = country.id
            if details.get('destination_country_id'):
                country = self.env['res.country'].search([('code', '=', details['destination_country_id'])], limit=1)
                if country:
                    vals['biziship_dest_country_id'] = country.id

            order.write(vals)

            # Handle Cargo Lines
            order.biziship_cargo_line_ids.unlink()
            line_items = details.get('line_items', [])
            if not line_items:
                # Fallback to top-level legacy fields if line_items empty
                order.biziship_cargo_line_ids.create({
                    'sale_order_id': order.id,
                    'packaging_type': details.get('packaging_type', 'Pallet'),
                    'pieces': details.get('num_pieces', 1),
                    'weight': details.get('weight', 0),
                    'length': details.get('length', 48),
                    'width': details.get('width', 40),
                    'height': details.get('height', 48),
                    'freight_class': details.get('freight_class', '70'),
                    'description': details.get('cargo_description', ''),
                })
            else:
                for item in line_items:
                    order.biziship_cargo_line_ids.create({
                        'sale_order_id': order.id,
                        'packaging_type': item.get('packaging_type', 'Pallet'),
                        'pieces': item.get('pieces', 1),
                        'weight': item.get('weight', 0),
                        'length': item.get('length', 48),
                        'width': item.get('width', 40),
                        'height': item.get('height', 48),
                        'freight_class': item.get('freight_class', '70'),
                        'description': item.get('description', ''),
                    })
            
            return True
        except Exception as e:
            raise UserError(_("Error loading freight: %s") % str(e))
