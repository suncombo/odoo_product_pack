# -*- encoding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in root directory
##############################################################################
from odoo import fields, models, api, _
from odoo.exceptions import Warning
import math


class product_product(models.Model):
    _inherit = 'product.product'

    @api.multi
    def _product_available(self, field_names=None, arg=False):
        pack_products = self.filtered(lambda p: p.pack == True)
        res = super(product_product, self - pack_products)._product_available(field_names, arg)

        for product in pack_products:
            pack_qty_available = []
            pack_virtual_available = []
            for pack_line in product.pack_line_ids:
                subproduct_stock = pack_line.product_id._product_available(field_names, arg)[pack_line.product_id.id]
                sub_qty = pack_line.quantity
                if sub_qty:
                    pack_qty_available.append(math.floor(
                        subproduct_stock['qty_available'] / sub_qty))
                    pack_virtual_available.append(math.floor(
                        subproduct_stock['virtual_available'] / sub_qty))
            # TODO calcular correctamente pack virtual available para negativos
            res[product.id] = {
                'qty_available': (
                    pack_qty_available and min(pack_qty_available) or False),
                'incoming_qty': 0,
                'outgoing_qty': 0,
                'virtual_available': (
                    pack_virtual_available and min(pack_virtual_available) or False),
            }
        return res

    pack_line_ids = fields.One2many('product.pack.line', 'parent_product_id', string='Pack Products',
                                    help='List of products that are part of this pack.')
    used_pack_line_ids = fields.One2many('product.pack.line', 'product_id', string='On Packs',
                                         help='List of packs where product is used.')

    @api.one
    @api.constrains('pack_line_ids')
    def check_recursion(self):
        pack_lines = self.pack_line_ids
        while pack_lines:
            if self in pack_lines.mapped('product_id'):
                raise Warning(_(
                    'Error! You cannot create recursive packs.\n'
                    'Product id: %s') % self.id)
            pack_lines = pack_lines.mapped('product_id.pack_line_ids')

    @api.multi
    def price_compute(self, price_type, uom=False, currency=False, company=False):
        res = super(product_product, self).price_compute(price_type, uom, currency, company)
        for product in self:
            if (product.pack and
                        product.pack_price_type == 'totalice_price'):
                pack_price = 0.0
                for pack_line in product.pack_line_ids:
                    product_line_price = pack_line.product_id.price_compute(price_type)[pack_line.product_id.id]
                    pack_price += (product_line_price * pack_line.quantity)
                res[product.id] = pack_price
        return res


class product_template(models.Model):
    _inherit = 'product.template'

    # TODO rename a pack_type
    pack_price_type = fields.Selection([
        ('components_price', 'Detailed - Components Prices'),
        ('totalice_price', 'Detailed - Totaliced Price'),
        ('fixed_price', 'Detailed - Fixed Price'),
    ],
        string='Pack Type',
        help="""
        * Detailed - Components Prices: Detail lines with prices on sales order.
        * Detailed - Totaliced Price: Detail lines on sales order totalicing lines prices on pack (don't show component prices).
        * Detailed - Fixed Price: Detail lines on sales order and use product pack price (ignore line prices).
        """)
    pack = fields.Boolean('Pack?', help='Is a Product Pack?')
    pack_line_ids = fields.One2many(related='product_variant_ids.pack_line_ids')
    used_pack_line_ids = fields.One2many(related='product_variant_ids.used_pack_line_ids')

    @api.one
    @api.constrains('company_id', 'pack_line_ids', 'used_pack_line_ids')
    def check_pack_line_company(self):
        """
        Check packs are related to packs of same company
        """
        for line in self.pack_line_ids:
            if line.product_id.company_id != self.company_id:
                raise Warning(_(
                    'Pack lines products company must be the same as the\
                    parent product company'))
        for line in self.used_pack_line_ids:
            if line.parent_product_id.company_id != self.company_id:
                raise Warning(_(
                    'Pack lines products company must be the same as the\
                    parent product company'))

    @api.multi
    def write(self, vals):
        """
        We remove from prod.prod to avoid error
        """
        if vals.get('pack_line_ids', False):
            self.product_variant_ids.write(
                {'pack_line_ids': vals.pop('pack_line_ids')})
        return super(product_template, self).write(vals)

    @api.multi
    def price_compute(self, price_type, uom=False, currency=False, company=False):
        res = super(product_template, self).price_compute(price_type, uom, currency, company)
        for product in self:
            if (product.pack and product.pack_price_type == 'totalice_price'):
                pack_price = 0.0
                for pack_line in product.pack_line_ids:
                    product_line_price = pack_line.product_id.price_compute(price_type)[pack_line.product_id.id]
                    pack_price += (product_line_price * pack_line.quantity)
                res[product.id] = pack_price
        return res

    @api.onchange('pack', 'pack_price_type')
    def onchange_pack_type(self):
        if self.pack == True and self.pack_price_type in ['totalice_price', 'fixed_price']:
            self.type = 'service'
