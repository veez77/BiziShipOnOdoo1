from odoo import models, fields

class ResUsers(models.Model):
    _inherit = 'res.users'

    biziship_token = fields.Char(string='BiziShip JWT Token', copy=False, groups='base.group_user')
    biziship_p1_env = fields.Selection([('DEV', 'Development'), ('PROD', 'Production')], string='BiziShip Environment', copy=False)
