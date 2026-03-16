import requests
import json
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class BizishipLoadFreightWizard(models.TransientModel):
    _name = 'biziship.load.freight.wizard'
    _description = 'Load Saved Freight'

    freight_line_ids = fields.One2many('biziship.load.freight.line', 'wizard_id', string='Saved Freights')
    sale_order_id = fields.Many2one('sale.order', string='Sale Order')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        return res

    def _populate_freights(self):
        self.ensure_one()
        token = self.env.user.biziship_token
        if not token:
            return
        
        url = "https://api.biziship.ai/saved-freights"
        headers = {"Authorization": f"Bearer {token}"}
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                freights = response.json()
                lines = []
                for f in freights:
                    details = f.get('freightDetails', {})
                    origin_zip = details.get('origin_zip', '-----')
                    dest_zip = details.get('dest_zip', '-----')
                    weight = details.get('weight', 0)
                    weight_unit = details.get('weight_unit', 'lbs')
                    
                    # Count cargo lines
                    cargo_lines = details.get('line_items', [])
                    if not cargo_lines and details.get('cargo_lines_json'):
                        try:
                            cargo_lines = json.loads(details['cargo_lines_json'])
                        except:
                            cargo_lines = []
                    cargo_count = len(cargo_lines) or 1
                    
                    # Formatting strings as per web app
                    origin_info = f"{origin_zip} → {dest_zip}"
                    summary_info = f"{weight} {weight_unit} • {cargo_count} cargo line{'s' if cargo_count > 1 else ''}"
                    
                    created_by = f.get('createdBy', {}).get('fullName', 'Unknown User')
                    created_at_raw = f.get('createdAt', '')
                    date_str = created_at_raw[:10] if created_at_raw else "Recent"
                    creator_info = f"{created_by} • Saved {date_str}"

                    lines.append({
                        'wizard_id': self.id,
                        'freight_id': f['id'],
                        'name': f['name'],
                        'origin_info': origin_info,
                        'summary_info': summary_info,
                        'creator_info': creator_info,
                    })
                if lines:
                    self.env['biziship.load.freight.line'].create(lines)
        except Exception as e:
            _logger.error("BiziShip: Error fetching freights for wizard: %s", str(e))

    def action_load_freight_from_id(self, freight_id):
        """Helper to load a specific freight ID into the order"""
        token = self.env.user.biziship_token
        if not token:
            raise UserError(_("Please connect your BiziShip account first."))

        url = f"https://api.biziship.ai/saved-freights"
        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                raise UserError(_("Failed to fetch freight details."))
            
            freights = response.json()
            selected_freight = next((f for f in freights if f['id'] == freight_id), None)
            
            if not selected_freight or 'freightDetails' not in selected_freight:
                raise UserError(_("Selected freight details not found."))
            
            details = selected_freight['freightDetails']
            _logger.info("BiziShip: Loading Freight Details - %s", json.dumps(details, indent=2))
            order = self.sale_order_id

            def get_val(key, default=''):
                if key not in details:
                    return default
                val = details.get(key)
                return val if val is not None else default

            # 1. Update Sale Order Fields
            pickup_date = details.get('pickup_date') or str(fields.Date.today())
            if pickup_date < str(fields.Date.today()):
                pickup_date = str(fields.Date.today())

            vals = {
                'biziship_pickup_date': pickup_date,
                'biziship_origin_company': get_val('origin_company'),
                'biziship_origin_address': get_val('origin_address'),
                'biziship_origin_address2': get_val('origin_address2'),
                'biziship_origin_zip': get_val('origin_zip'),
                'biziship_cargo_desc': get_val('cargo_description', 'General Freight'),
                'biziship_special_instructions': get_val('special_instructions'),
                'biziship_po_number': get_val('po_number'),
                'biziship_total_weight_unit': (get_val('weight_unit', 'lbs')).lower()[:3],
                
                # Boolean Flags - Pickup
                'biziship_origin_residential': details.get('origin_residential', False),
                'biziship_origin_liftgate': details.get('origin_liftgate', False),
                'biziship_origin_limited_access': details.get('origin_limited_access', False),
                
                # Boolean Flags - Delivery
                'biziship_dest_appointment': details.get('dest_appointment', False),
                'biziship_dest_residential': details.get('dest_residential', False),
                'biziship_dest_notify': details.get('dest_notify', False),
                'biziship_dest_limited_access': details.get('dest_limited_access', False),
                'biziship_dest_liftgate': details.get('dest_liftgate', False),
                'biziship_dest_hazmat': details.get('dest_hazmat', False),
            }
            
            # Destination Address Info (Related fields write through)
            if 'dest_company' in details: vals['biziship_dest_company'] = details['dest_company']
            if 'dest_address' in details: vals['biziship_dest_address'] = details['dest_address']
            if 'dest_address2' in details: vals['biziship_dest_address2'] = details['dest_address2']
            if 'dest_zip' in details: vals['biziship_dest_zip'] = details['dest_zip']
            
            # Country Mapping
            if 'origin_country' in details:
                country = self.env['res.country'].search([('code', '=', details['origin_country'])], limit=1)
                if country: vals['biziship_origin_country_id'] = country.id
            if 'dest_country' in details:
                country = self.env['res.country'].search([('code', '=', details['dest_country'])], limit=1)
                if country: vals['biziship_dest_country_id'] = country.id

            # Extended Accessorials Mapping
            origin_more = details.get('origin_more', [])
            if not isinstance(origin_more, list):
                origin_more = []
            accs_origin = self.env['biziship.accessorial'].search([('code', 'in', origin_more), ('type', '=', 'origin')])
            vals['biziship_origin_accessorial_ids'] = [(6, 0, accs_origin.ids)]

            dest_more = details.get('dest_more', [])
            if not isinstance(dest_more, list):
                dest_more = []
            accs_dest = self.env['biziship.accessorial'].search([('code', 'in', dest_more), ('type', '=', 'destination')])
            vals['biziship_dest_accessorial_ids'] = [(6, 0, accs_dest.ids)]

            _logger.info("BiziShip: Values to write to Order: %s", json.dumps(vals, indent=2))
            order.write(vals)

            # 2. Cargo Mapping Helpers
            def normalize_pkg(pkg):
                if not pkg: return 'pallet'
                pkg = pkg.lower()
                if 'pallet' in pkg: return 'pallet'
                if 'crate' in pkg: return 'crate'
                if 'box' in pkg: return 'box'
                if 'drum' in pkg: return 'drum'
                return 'pallet'

            def normalize_dim_unit(unit):
                if not unit: return 'in'
                unit = unit.lower()
                if 'inch' in unit or unit == 'in': return 'in'
                if 'cm' in unit: return 'cm'
                if 'm' in unit: return 'm'
                if 'ft' in unit: return 'ft'
                return 'in'

            # 3. Handle Cargo Lines (Support JSON string if list is missing)
            order.biziship_cargo_line_ids.unlink()
            line_items = details.get('line_items')
            if not line_items and details.get('cargo_lines_json'):
                try:
                    line_items = json.loads(details['cargo_lines_json'])
                except:
                    line_items = []
            
            if not line_items:
                # Fallback to top-level fields
                line_items = [{
                    'num_pieces': details.get('num_pieces', 1),
                    'weight': details.get('weight', 0),
                    'length': details.get('length', 48),
                    'width': details.get('width', 40),
                    'height': details.get('height', 48),
                    'packaging_type': details.get('packaging_type', 'pallet'),
                    'freight_class': details.get('freight_class', '70'),
                    'cargo_description': details.get('cargo_description', ''),
                    'dimension_unit': details.get('dimension_unit', 'inches'),
                }]

            for item in line_items:
                payload = {
                    'sale_order_id': order.id,
                    'pieces': item.get('num_pieces') or item.get('pieces') or 1,
                    'weight': item.get('weight', 0),
                    'weight_unit': (item.get('weight_unit') or details.get('weight_unit') or 'lbs').lower()[:3],
                    'length': item.get('length', 48),
                    'width': item.get('width', 40),
                    'height': item.get('height', 48),
                    'dim_unit': normalize_dim_unit(item.get('dimension_unit') or details.get('dimension_unit') or item.get('dim_unit')),
                    'packaging_type': normalize_pkg(item.get('packaging_type')),
                    'freight_class': str(item.get('freight_class', '70')),
                    'cargo_desc': item.get('cargo_description') or item.get('description') or '',
                }
                _logger.info("BiziShip: Creating Cargo Line: %s", json.dumps(payload, indent=2))
                order.biziship_cargo_line_ids.create(payload)
            
            return True
        except Exception as e:
            _logger.exception("BiziShip: Error loading freight")
            raise UserError(_("Error loading freight: %s") % str(e))

class BizishipLoadFreightLine(models.TransientModel):
    _name = 'biziship.load.freight.line'
    _description = 'Load Saved Freight Line'

    wizard_id = fields.Many2one('biziship.load.freight.wizard', string='Wizard')
    freight_id = fields.Char(string='Freight ID')
    name = fields.Char(string='Name')
    
    # Summary fields for card display
    origin_info = fields.Char(string='Origin Summary')
    summary_info = fields.Char(string='Weight/Cargo Summary')
    creator_info = fields.Char(string='Creator Summary')

    def action_launch(self):
        self.ensure_one()
        return self.wizard_id.action_load_freight_from_id(self.freight_id)
