# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.fields import Domain


class ProductTag(models.Model):
    _name = 'product.tag'
    _description = 'Product Tag'
    _order = 'sequence, id'

    def _get_default_template_id(self):
        return self.env['product.template'].browse(self.env.context.get('product_template_id'))

    def _get_default_variant_id(self):
        return self.env['product.product'].browse(self.env.context.get('product_variant_id'))

    name = fields.Char(string="Name", required=True, translate=True)
    sequence = fields.Integer(default=10)
    color = fields.Char(string="Color", default='#3C3C3C')
    product_template_ids = fields.Many2many(
        string="Product Templates",
        comodel_name='product.template',
        relation='product_tag_product_template_rel',
        default=_get_default_template_id,
    )
    product_product_ids = fields.Many2many(
        string="Product Variants",
        comodel_name='product.product',
        relation='product_tag_product_product_rel',
        domain="[('attribute_line_ids', '!=', False), ('product_tmpl_id', 'not in', product_template_ids)]",
        default=_get_default_variant_id,
    )
    product_ids = fields.Many2many(
        'product.product', string='All Product Variants using this Tag',
        compute='_compute_product_ids', search='_search_product_ids'
    )
    visible_to_customers = fields.Boolean(
        string="Visible to customers",
        help="Whether the tag is displayed to customers.",
        default=True,
    )
    image = fields.Image(string="Image", max_width=200, max_height=200)

    _name_uniq = models.Constraint(
        'unique (name)',
        'Tag name already exists!',
    )

    @api.depends('product_template_ids', 'product_product_ids')
    def _compute_product_ids(self):
        for tag in self:
            tag.product_ids = tag.product_template_ids.product_variant_ids | tag.product_product_ids

    def copy_data(self, default=None):
        vals_list = super().copy_data(default=default)
        return [dict(vals, name=self.env._("%s (copy)", tag.name)) for tag, vals in zip(self, vals_list)]

    def _search_product_ids(self, operator, operand):
        if Domain.is_negative_operator(operator):
            return NotImplemented
        return ['|', ('product_template_ids.product_variant_ids', operator, operand), ('product_product_ids', operator, operand)]
