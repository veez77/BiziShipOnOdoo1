from odoo import models, fields, api

class BizishipSaleCargoLine(models.Model):
    _name = 'biziship.sale.cargo.line'
    _description = 'BiziShip Sale Cargo Line'

    sale_order_id = fields.Many2one('sale.order', string='Sale Order', required=True, ondelete='cascade')
    
    packaging_type = fields.Selection([
        ('pallet', 'Pallet'),
        ('crate', 'Crate'),
        ('box', 'Box'),
        ('drum', 'Drum'),
    ], string="Packaging Type", default="pallet", required=True)
    
    pieces = fields.Integer(string="Pieces (Handling Units)", default=1, required=True)
    
    weight = fields.Float(string="Weight", default=0.0, required=True)
    weight_unit = fields.Selection([('lbs', 'lbs'), ('kg', 'kg')], string="Weight Unit", default='lbs', required=True)
    last_weight_unit = fields.Selection([('lbs', 'lbs'), ('kg', 'kg')], default='lbs')

    @api.onchange('weight_unit')
    def _onchange_weight_unit(self):
        for rec in self:
            # Fallback for existing records where last_weight_unit is False
            last = rec.last_weight_unit
            if not last:
                last = rec._origin.weight_unit if getattr(rec, '_origin', False) and rec._origin.weight_unit else 'lbs'
                
            if last != rec.weight_unit:
                if rec.weight:
                    if rec.weight_unit == 'kg' and last == 'lbs':
                        rec.weight = round(rec.weight / 2.20462, 2)
                    elif rec.weight_unit == 'lbs' and last == 'kg':
                        rec.weight = round(rec.weight * 2.20462, 2)
            rec.last_weight_unit = rec.weight_unit
    
    length = fields.Float(string="Length", default=48.0, required=True)
    width = fields.Float(string="Width", default=40.0, required=True)
    height = fields.Float(string="Height", default=48.0, required=True)
    dim_unit = fields.Selection([('in', 'in'), ('cm', 'cm'), ('m', 'm'), ('ft', 'ft')], string="Dimension Unit", default='in', required=True)
    last_dim_unit = fields.Selection([('in', 'in'), ('cm', 'cm'), ('m', 'm'), ('ft', 'ft')], default='in')

    @api.onchange('dim_unit')
    def _onchange_dim_unit(self):
        for rec in self:
            last = rec.last_dim_unit
            if not last:
                last = rec._origin.dim_unit if getattr(rec, '_origin', False) and rec._origin.dim_unit else 'in'
                
            if last != rec.dim_unit:
                def convert_dim(val, from_u, to_u):
                    if not val: return val
                    # Convert to base unit: inches
                    in_val = val
                    if from_u == 'cm': in_val = val / 2.54
                    elif from_u == 'm': in_val = val / 0.0254
                    elif from_u == 'ft': in_val = val * 12.0
                    
                    # Convert from inches to target unit
                    out_val = in_val
                    if to_u == 'cm': out_val = in_val * 2.54
                    elif to_u == 'm': out_val = in_val * 0.0254
                    elif to_u == 'ft': out_val = in_val / 12.0
                    
                    return round(out_val, 2)
                    
                rec.length = convert_dim(rec.length, last, rec.dim_unit)
                rec.width = convert_dim(rec.width, last, rec.dim_unit)
                rec.height = convert_dim(rec.height, last, rec.dim_unit)
                
            rec.last_dim_unit = rec.dim_unit
    
    freight_class = fields.Selection([
        ('50', '50'), ('55', '55'), ('60', '60'), ('65', '65'),
        ('70', '70'), ('77.5', '77.5'), ('85', '85'), ('92.5', '92.5'),
        ('100', '100'), ('110', '110'), ('125', '125'), ('150', '150'),
        ('175', '175'), ('250', '250'), ('300', '300'),
        ('400', '400'), ('500', '500')
    ], string="Class", default='50', required=True)
    
    computed_freight_class = fields.Selection([
        ('50', '50'), ('55', '55'), ('60', '60'), ('65', '65'),
        ('70', '70'), ('77.5', '77.5'), ('85', '85'), ('92.5', '92.5'),
        ('100', '100'), ('110', '110'), ('125', '125'), ('150', '150'),
        ('175', '175'), ('250', '250'), ('300', '300'),
        ('400', '400'), ('500', '500')
    ], string="Computed Class", compute='_compute_computed_class', store=True)
    
    is_class_overridden = fields.Boolean(compute='_compute_is_class_overridden')
    nmfc = fields.Char(string="NMFC")
    cargo_desc = fields.Char(string="Cargo Description", default="General Freight")

    @api.depends('weight', 'weight_unit', 'length', 'width', 'height', 'dim_unit', 'pieces')
    def _compute_computed_class(self):
        for rec in self:
            if rec.length and rec.width and rec.height and rec.weight and rec.pieces:
                l, w, h = rec.length, rec.width, rec.height
                if rec.dim_unit == 'cm':
                    l, w, h = l * 0.393701, w * 0.393701, h * 0.393701
                elif rec.dim_unit == 'm':
                    l, w, h = l * 39.3701, w * 39.3701, h * 39.3701
                elif rec.dim_unit == 'ft':
                    l, w, h = l * 12.0, w * 12.0, h * 12.0
                    
                volume_cf = (l * w * h * rec.pieces) / 1728.0
                if volume_cf > 0:
                    effective_weight = rec.weight * 2.20462 if rec.weight_unit == 'kg' else rec.weight
                    density = effective_weight / volume_cf
                    if density < 1: rec.computed_freight_class = '500'
                    elif density < 2: rec.computed_freight_class = '400'
                    elif density < 3: rec.computed_freight_class = '300'
                    elif density < 4: rec.computed_freight_class = '250'
                    elif density < 6: rec.computed_freight_class = '175'
                    elif density < 7: rec.computed_freight_class = '150'
                    elif density < 8: rec.computed_freight_class = '125'
                    elif density < 9: rec.computed_freight_class = '110'
                    elif density < 10.5: rec.computed_freight_class = '100'
                    elif density < 12: rec.computed_freight_class = '92.5'
                    elif density < 13.5: rec.computed_freight_class = '85'
                    elif density < 15: rec.computed_freight_class = '77.5'
                    elif density < 22.5: rec.computed_freight_class = '70'
                    elif density < 30: rec.computed_freight_class = '65'
                    elif density < 35: rec.computed_freight_class = '60'
                    elif density < 50: rec.computed_freight_class = '55'
                    else: rec.computed_freight_class = '50'
                else:
                    rec.computed_freight_class = '50'
            else:
                rec.computed_freight_class = False

    @api.depends('freight_class', 'computed_freight_class')
    def _compute_is_class_overridden(self):
        for rec in self:
            rec.is_class_overridden = (
                rec.freight_class and rec.computed_freight_class 
                and rec.freight_class != rec.computed_freight_class
            )
