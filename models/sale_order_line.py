# -*- encoding: utf-8 -*-
from odoo import api, fields, models, _


class sale_order_line(models.Model):
    _inherit = 'sale.order.line'

    pack_type = fields.Selection(related='product_id.pack_price_type', readonly=True)
    pack_depth = fields.Integer(string='Depth', help='Depth of the product if it is part of a pack.')
    pack_parent_line_id = fields.Many2one('sale.order.line', string='Pack', help='The pack that contains this product.', ondelete="cascade")
    pack_child_line_ids = fields.One2many('sale.order.line', 'pack_parent_line_id', string='Lines in pack')

    @api.one
    @api.constrains('product_id', 'price_unit', 'product_uom_qty')
    def expand_pack_line(self):
        detailed_packs = ['components_price', 'totalice_price', 'fixed_price']
        if self.state == 'draft' and self.product_id.pack and self.pack_type in detailed_packs:
            for subline in self.product_id.pack_line_ids:
                vals = subline.get_sale_order_line_vals(self, self.order_id)
                vals['sequence'] = self.sequence

                existing_subline = self.search([('product_id', '=', subline.product_id.id),
                                                ('pack_parent_line_id', '=', self.id)], limit=1)
                # if subline already exists we update, if not we create
                if existing_subline:
                    existing_subline.write(vals)
                else:
                    self.create(vals)
