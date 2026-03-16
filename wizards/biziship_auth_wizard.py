import requests
import json
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class BizishipAuthWizard(models.TransientModel):
    _name = 'biziship.auth.wizard'
    _description = 'BiziShip Authentication Wizard'

    email = fields.Char(string='Email', required=True)
    pin = fields.Char(string='PIN Code')
    state = fields.Selection([
        ('request', 'Request PIN'),
        ('verify', 'Verify PIN')
    ], default='request')

    @api.model
    def default_get(self, fields):
        res = super(BizishipAuthWizard, self).default_get(fields)
        if 'email' in fields and not res.get('email'):
            res['email'] = self.env.user.email
        return res

    def action_request_pin(self):
        url = "https://api.biziship.ai/auth/request-pin"
        try:
            response = requests.post(url, json={'email': self.email}, timeout=10)
            if response.status_code == 200:
                self.state = 'verify'
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'biziship.auth.wizard',
                    'view_mode': 'form',
                    'res_id': self.id,
                    'target': 'new',
                }
            else:
                raise UserError(_("Failed to request PIN. Please check your email and try again."))
        except Exception as e:
            raise UserError(_("Error connecting to BiziShip: %s") % str(e))

    def action_verify_pin(self):
        url = "https://api.biziship.ai/auth/verify-pin"
        try:
            response = requests.post(url, json={
                'email': self.email,
                'pin': self.pin
            }, timeout=10)
            if response.status_code == 200:
                data = response.json()
                token = data.get('token')
                user_data = data.get('user', {})
                env = user_data.get('priority1Env', 'DEV')
                
                self.env.user.write({
                    'biziship_token': token,
                    'biziship_p1_env': env
                })
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Success'),
                        'message': _('Successfully connected to BiziShip!'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                raise UserError(_("Invalid PIN. Please try again."))
        except Exception as e:
            raise UserError(_("Error connecting to BiziShip: %s") % str(e))
