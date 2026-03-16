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
        
        # Prepare freight details according to backend spec
        freight_details = {
            "origin_company": order.biziship_origin_company,
            "origin_address": order.biziship_origin_address,
            "origin_address2": order.biziship_origin_address2,
            "origin_zip": order.biziship_origin_zip,
            "origin_country_id": order.biziship_origin_country_id.code if order.biziship_origin_country_id else None,
            "destination_company": order.biziship_dest_company,
            "destination_address": order.biziship_dest_address,
            "destination_address2": order.biziship_dest_address2,
            "destination_zip": order.biziship_dest_zip,
            "destination_country_id": order.biziship_dest_country_id.code if order.biziship_dest_country_id else None,
            "cargo_description": order.biziship_cargo_desc,
            "special_instructions": order.biziship_special_instructions,
            "po_number": order.biziship_po_number,
            "pickup_date": order.biziship_pickup_date.isoformat() if order.biziship_pickup_date else None,
            "weight_unit": order.biziship_total_weight_unit or "lbs",
            "line_items": []
        }

        for line in order.biziship_cargo_line_ids:
            freight_details["line_items"].append({
                "packaging_type": line.packaging_type,
                "pieces": line.pieces,
                "weight": line.weight,
                "length": line.length,
                "width": line.width,
                "height": line.height,
                "freight_class": line.freight_class,
                "description": line.description,
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
                        'message': _("Freight '%s' saved to your pool.") % self.name,
                        'type': 'success',
                        'sticky': False,
                    }
                }
            elif response.status_code == 409:
                raise UserError(_("A freight with this name already exists in your company."))
            elif response.status_code == 401:
                self.env.user.biziship_token = False
                raise UserError(_("Your BiziShip session has expired. Please reconnect in your User Profile."))
            else:
                raise UserError(_("Failed to save freight. Backend returned: %s") % response.text)
        except Exception as e:
            raise UserError(_("Error connecting to BiziShip: %s") % str(e))
