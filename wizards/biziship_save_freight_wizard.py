import requests
import json
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class BizishipSaveFreightWizard(models.TransientModel):
    _name = 'biziship.save.freight.wizard'
    _description = 'Save Freight to My Pool'

    name = fields.Char(string='Freight Name', required=True)
    sale_order_id = fields.Many2one('sale.order', string='Sale Order')

    def action_save_freight(self):
        self.ensure_one()
        token = self.env.user.biziship_token
        if not token:
            raise UserError(_("Please connect your BiziShip account first in your User Profile."))

        order = self.sale_order_id
        
        # Compile accessorial codes (Priority1 codes)
        accessorial_codes = order.biziship_origin_accessorial_ids.mapped('code') + order.biziship_dest_accessorial_ids.mapped('code')
        
        # Origin Checkboxes -> Priority1 Codes
        if order.biziship_origin_residential: accessorial_codes.append("RESPU")
        if order.biziship_origin_liftgate: accessorial_codes.append("LGPU")
        if order.biziship_origin_limited_access: accessorial_codes.append("LTDPU")
        
        # Destination Checkboxes -> Priority1 Codes
        if order.biziship_dest_residential: accessorial_codes.append("RESDEL")
        if order.biziship_dest_liftgate: accessorial_codes.append("LGDEL")
        if order.biziship_dest_limited_access: accessorial_codes.append("LTDDEL")
        if order.biziship_dest_appointment: accessorial_codes.append("APPT")
        if order.biziship_dest_notify: accessorial_codes.append("NOTIFY")
        if order.biziship_dest_hazmat: accessorial_codes.append("HAZM")
        
        accessorial_codes = list(set(accessorial_codes))

        # Prepare freight details according to backend spec
        freight_details = {
            "origin_company": order.biziship_origin_company,
            "origin_address": order.biziship_origin_address,
            "origin_address2": order.biziship_origin_address2,
            "origin_city": order.biziship_origin_city,
            "origin_state": order.biziship_origin_state_id.code if order.biziship_origin_state_id else None,
            "origin_zip": order.biziship_origin_zip,
            "origin_country": order.biziship_origin_country_id.code if order.biziship_origin_country_id else None,
            
            "destination_company": order.biziship_dest_company,
            "destination_address": order.biziship_dest_address,
            "destination_address2": order.biziship_dest_address2,
            "destination_city": order.biziship_dest_city,
            "destination_state": order.biziship_dest_state_id.code if order.biziship_dest_state_id else None,
            "destination_zip": order.biziship_dest_zip,
            "destination_country": order.biziship_dest_country_id.code if order.biziship_dest_country_id else None,
            
            "cargo_description": order.biziship_cargo_desc,
            "special_instructions": order.biziship_special_instructions,
            "po_number": order.biziship_po_number,
            "pickup_date": order.biziship_pickup_date.isoformat() if order.biziship_pickup_date else None,
            
            # Boolean Flags - Pickup
            "origin_residential": order.biziship_origin_residential,
            "origin_liftgate": order.biziship_origin_liftgate,
            "origin_limited_access": order.biziship_origin_limited_access,
            
            # Boolean Flags - Delivery
            "dest_appointment": order.biziship_dest_appointment,
            "dest_residential": order.biziship_dest_residential,
            "dest_notify": order.biziship_dest_notify,
            "dest_limited_access": order.biziship_dest_limited_access,
            "dest_liftgate": order.biziship_dest_liftgate,
            "dest_hazmat": order.biziship_dest_hazmat,

            # Top-level summary fields as requested by spec
            "weight": order.biziship_total_weight,
            "weight_unit": order.biziship_total_weight_unit or "lbs",
            "num_pieces": sum(order.biziship_cargo_line_ids.mapped('pieces')),
            "packaging_type": order.biziship_cargo_line_ids[0].packaging_type if order.biziship_cargo_line_ids else "",
            "freight_class": order.biziship_cargo_line_ids[0].computed_freight_class or order.biziship_cargo_line_ids[0].freight_class if order.biziship_cargo_line_ids else "",
            
            "accessorial_codes": accessorial_codes,
            "line_items": []
        }

        for line in order.biziship_cargo_line_ids:
            freight_details["line_items"].append({
                "packaging_type": line.packaging_type,
                "num_pieces": line.pieces,
                "weight": line.weight,
                "length": line.length,
                "width": line.width,
                "height": line.height,
                "freight_class": line.computed_freight_class or line.freight_class,
                "cargo_description": line.cargo_desc,
            })

        url = "https://api.biziship.ai/saved-freights"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        payload = {
            "name": self.name,
            "freightDetails": freight_details
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            if response.status_code == 201:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Success'),
                        'message': _("Freight saved successfully"),
                        'type': 'success',
                        'sticky': False,
                        'next': {'type': 'ir.actions.act_window_close'},
                    }
                }
            elif response.status_code == 409:
                raise UserError(_("A saved freight named '%s' already exists. Please choose a different name.") % self.name)
            elif response.status_code == 403:
                raise UserError(_("You do not have a company associated with your BiziShip account."))
            elif response.status_code == 401:
                self.env.user.biziship_token = False
                raise UserError(_("Your BiziShip session has expired. Please reconnect in your User Profile."))
            else:
                raise UserError(_("Failed to save freight. Backend returned: %s") % response.text)
        except Exception as e:
            if isinstance(e, UserError):
                raise e
            raise UserError(_("Error connecting to BiziShip: %s") % str(e))
