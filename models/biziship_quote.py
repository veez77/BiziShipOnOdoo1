from odoo import models, fields

class BizishipQuote(models.Model):
    _name = 'biziship.quote'
    _description = 'BiziShip Freight Quote'

    sale_order_id = fields.Many2one('sale.order', string='Sales Order', required=True, ondelete='cascade')
    carrier_name = fields.Char(string='Carrier')
    carrier_code = fields.Char(string='Carrier Code')
    service_level = fields.Char(string='Service Level')
    transit_days = fields.Integer(string='Transit Days')
    delivery_date = fields.Datetime(string='Delivery Date')
    total_charge = fields.Float(string='Total Charge')
    currency = fields.Char(string='Currency', default='USD')
    currency_id = fields.Many2one(related='sale_order_id.currency_id')
    quote_id_ref = fields.Char(string='Quote ID')
    is_selected = fields.Boolean(string='Selected', default=False)
    quote_details = fields.Text(string='Quote Details')

    def action_select_quote(self):
        for record in self:
            # Deselect all quotes for this order
            self.search([('sale_order_id', '=', record.sale_order_id.id), ('id', '!=', record.id)]).write({'is_selected': False})
            # Select this one
            record.is_selected = True

    def name_get(self):
        result = []
        for record in self:
            name = f"{record.carrier_name} - {record.total_charge} {record.currency}"
            result.append((record.id, name))
        return result
