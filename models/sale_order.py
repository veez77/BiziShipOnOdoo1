from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    biziship_quote_ids = fields.One2many('biziship.quote', 'sale_order_id', string='Freight Quotes')
    biziship_extracted_json = fields.Text(string='BiziShip Extracted JSON', readonly=True)
    biziship_bol_number = fields.Char(string='BiziShip BOL Number', readonly=True, copy=False)
    biziship_shipment_id = fields.Char(string='BiziShip Shipment ID', readonly=True, copy=False)
    biziship_bol_url = fields.Char(string='BiziShip BOL Document URL', readonly=True, copy=False)
    biziship_has_selected_quote = fields.Boolean(compute='_compute_biziship_has_selected_quote')

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
