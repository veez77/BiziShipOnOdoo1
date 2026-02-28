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
