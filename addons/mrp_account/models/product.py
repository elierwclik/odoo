# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.tools import float_round, groupby


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def _get_product_accounts(self):
        accounts = super()._get_product_accounts()
        if self.categ_id:
            # If category set on the product take production account from category even if
            # production account on category is False
            production_account = self.categ_id.property_stock_account_production_cost_id
        else:
            ProductCategory = self.env['product.category']
            production_account = (
                self.valuation == 'real_time'
                and ProductCategory._fields['property_stock_account_production_cost_id'].get_company_dependent_fallback(
                    ProductCategory
                )
                or self.env['account.account']
            )
        accounts['production'] = production_account
        return accounts

    def action_bom_cost(self):
        templates = self.filtered(lambda t: t.product_variant_count == 1 and t.bom_count > 0)
        if templates:
            return templates.mapped('product_variant_id').action_bom_cost()

    def button_bom_cost(self):
        templates = self.filtered(lambda t: t.product_variant_count == 1 and t.bom_count > 0)
        if templates:
            return templates.mapped('product_variant_id').button_bom_cost()


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def button_bom_cost(self):
        self.ensure_one()
        self._set_price_from_bom()

    def action_bom_cost(self):
        boms_to_recompute = self.env['mrp.bom'].search(['|', ('product_id', 'in', self.ids), '&', ('product_id', '=', False), ('product_tmpl_id', 'in', self.mapped('product_tmpl_id').ids)])
        for product in self:
            product._set_price_from_bom(boms_to_recompute)

    def _set_price_from_bom(self, boms_to_recompute=False):
        self.ensure_one()
        bom = self.env['mrp.bom']._bom_find(self)[self]
        if bom:
            self.standard_price = self._compute_bom_price(bom, boms_to_recompute=boms_to_recompute)
        else:
            bom = self.env['mrp.bom'].search([('byproduct_ids.product_id', '=', self.id)], order='sequence, product_id, id', limit=1)
            if bom:
                price = self._compute_bom_price(bom, boms_to_recompute=boms_to_recompute, byproduct_bom=True)
                if price:
                    self.standard_price = price

    def _compute_average_price(self, qty_invoiced, qty_to_invoice, stock_moves, is_returned=False):
        self.ensure_one()
        if stock_moves.product_id == self:
            return super()._compute_average_price(qty_invoiced, qty_to_invoice, stock_moves, is_returned=is_returned)
        bom = self.env['mrp.bom']._bom_find(self, company_id=stock_moves.company_id.id, bom_type='phantom')[self]
        if not bom:
            return super()._compute_average_price(qty_invoiced, qty_to_invoice, stock_moves, is_returned=is_returned)
        value = 0
        dummy, bom_lines = bom.explode(self, 1)
        bom_lines = {line: data for line, data in bom_lines}
        for bom_line, moves_list in groupby(stock_moves.filtered(lambda sm: sm.state != 'cancel'), lambda sm: sm.bom_line_id):
            if bom_line not in bom_lines:
                for move in moves_list:
                    component_quantity = next(
                        (bml.product_qty for bml in move.product_id.bom_line_ids if bml in bom_lines),
                        1
                    )
                    value += component_quantity * move.product_id._compute_average_price(qty_invoiced * move.product_qty, qty_to_invoice * move.product_qty, move, is_returned=is_returned)
                continue
            line_qty = bom_line.product_uom_id._compute_quantity(bom_lines[bom_line]['qty'], bom_line.product_id.uom_id)
            moves = self.env['stock.move'].concat(*moves_list)
            value += line_qty * bom_line.product_id._compute_average_price(qty_invoiced * line_qty, qty_to_invoice * line_qty, moves, is_returned=is_returned)
        return value

    def _compute_bom_price(self, bom, boms_to_recompute=False, byproduct_bom=False):
        self.ensure_one()
        if not bom:
            return 0
        if not boms_to_recompute:
            boms_to_recompute = []
        total = 0
        for opt in bom.operation_ids:
            if opt._skip_operation_line(self):
                continue

            total += opt.cost

        for line in bom.bom_line_ids:
            if line._skip_bom_line(self):
                continue

            # Compute recursive if line has `child_line_ids`
            if line.child_bom_id and line.child_bom_id in boms_to_recompute:
                child_total = line.product_id._compute_bom_price(line.child_bom_id, boms_to_recompute=boms_to_recompute)
                total += line.product_id.uom_id._compute_price(child_total, line.product_uom_id) * line.product_qty
            else:
                total += line.product_id.uom_id._compute_price(line.product_id.standard_price, line.product_uom_id) * line.product_qty
        if byproduct_bom:
            byproduct_lines = bom.byproduct_ids.filtered(lambda b: b.product_id == self and b.cost_share != 0)
            product_uom_qty = 0
            for line in byproduct_lines:
                product_uom_qty += line.product_uom_id._compute_quantity(line.product_qty, self.uom_id, round=False)
            byproduct_cost_share = sum(byproduct_lines.mapped('cost_share'))
            if byproduct_cost_share and product_uom_qty:
                return total * byproduct_cost_share / 100 / product_uom_qty
        else:
            byproduct_cost_share = sum(bom.byproduct_ids.mapped('cost_share'))
            if byproduct_cost_share:
                total *= float_round(1 - byproduct_cost_share / 100, precision_rounding=0.0001)
            return bom.product_uom_id._compute_price(total / bom.product_qty, self.uom_id)


class ProductCategory(models.Model):
    _inherit = 'product.category'

    property_stock_account_production_cost_id = fields.Many2one(
        'account.account', 'Production Account', company_dependent=True, ondelete='restrict',
        check_company=True,
        help="""This account will be used as a valuation counterpart for both components and final products for manufacturing orders.
                If there are any workcenter/employee costs, this value will remain on the account once the production is completed.""")

    def _get_stock_account_property_field_names(self):
        return super()._get_stock_account_property_field_names() + ['property_stock_account_production_cost_id']
