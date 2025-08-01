# Part of Odoo. See LICENSE file for full copyright and licensing details.

from random import randint

from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command


class ProductTemplateAttributeValue(models.Model):
    """Materialized relationship between attribute values
    and product template generated by the product.template.attribute.line"""

    _name = 'product.template.attribute.value'
    _description = "Product Template Attribute Value"
    _order = 'attribute_line_id, product_attribute_value_id, id'

    def _get_default_color(self):
        return randint(1, 11)

    # Not just `active` because we always want to show the values except in
    # specific case, as opposed to `active_test`.
    ptav_active = fields.Boolean(string="Active", default=True)
    name = fields.Char(string="Value", related="product_attribute_value_id.name")

    # defining fields: the product template attribute line and the product attribute value
    product_attribute_value_id = fields.Many2one(
        comodel_name='product.attribute.value',
        string="Attribute Value",
        required=True, ondelete='cascade', index=True)
    attribute_line_id = fields.Many2one(
        comodel_name='product.template.attribute.line',
        required=True, ondelete='cascade', index=True)
    # configuration fields: the price_extra and the exclusion rules
    price_extra = fields.Float(
        string="Extra Price",
        default=0.0,
        digits='Product Price',
        help="Extra price for the variant with this attribute value on sale price."
            " eg. 200 price extra, 1000 + 200 = 1200.")
    currency_id = fields.Many2one(related='attribute_line_id.product_tmpl_id.currency_id')

    exclude_for = fields.One2many(
        comodel_name='product.template.attribute.exclusion',
        inverse_name='product_template_attribute_value_id',
        string="Exclude for",
        help="Make this attribute value not compatible with "
             "other values of the product or some attribute values of optional and accessory products.")

    # related fields: product template and product attribute
    product_tmpl_id = fields.Many2one(
        related='attribute_line_id.product_tmpl_id', store=True, index=True)
    attribute_id = fields.Many2one(
        related='attribute_line_id.attribute_id', store=True, index=True)
    ptav_product_variant_ids = fields.Many2many(
        comodel_name='product.product', relation='product_variant_combination',
        string="Related Variants", readonly=True)

    html_color = fields.Char(string="HTML Color Index", related='product_attribute_value_id.html_color')
    is_custom = fields.Boolean(related='product_attribute_value_id.is_custom')
    display_type = fields.Selection(related='product_attribute_value_id.display_type')
    color = fields.Integer(string="Color", default=_get_default_color)
    image = fields.Image(related='product_attribute_value_id.image')

    _attribute_value_unique = models.Constraint(
        'unique(attribute_line_id, product_attribute_value_id)',
        'Each value should be defined only once per attribute per product.',
    )

    @api.constrains('attribute_line_id', 'product_attribute_value_id')
    def _check_valid_values(self):
        for ptav in self:
            if ptav.ptav_active and ptav.product_attribute_value_id not in ptav.attribute_line_id.value_ids:
                raise ValidationError(_(
                    "The value %(value)s is not defined for the attribute %(attribute)s"
                    " on the product %(product)s.",
                    value=ptav.product_attribute_value_id.display_name,
                    attribute=ptav.attribute_id.display_name,
                    product=ptav.product_tmpl_id.display_name,
                ))

    @api.model_create_multi
    def create(self, vals_list):
        if any('ptav_product_variant_ids' in v for v in vals_list):
            # Force write on this relation from `product.product` to properly
            # trigger `_compute_combination_indices`.
            raise UserError(_("You cannot update related variants from the values. Please update related values from the variants."))
        return super().create(vals_list)

    def write(self, vals):
        values = vals
        if 'ptav_product_variant_ids' in values:
            # Force write on this relation from `product.product` to properly
            # trigger `_compute_combination_indices`.
            raise UserError(_("You cannot update related variants from the values. Please update related values from the variants."))
        pav_in_values = 'product_attribute_value_id' in values
        product_in_values = 'product_tmpl_id' in values
        if pav_in_values or product_in_values:
            for ptav in self:
                if pav_in_values and ptav.product_attribute_value_id.id != values['product_attribute_value_id']:
                    raise UserError(_(
                        "You cannot change the value of the value %(value)s set on product %(product)s.",
                        value=ptav.display_name,
                        product=ptav.product_tmpl_id.display_name,
                    ))
                if product_in_values and ptav.product_tmpl_id.id != values['product_tmpl_id']:
                    raise UserError(_(
                        "You cannot change the product of the value %(value)s set on product %(product)s.",
                        value=ptav.display_name,
                        product=ptav.product_tmpl_id.display_name,
                    ))
        res = super().write(values)
        if 'exclude_for' in values:
            self.product_tmpl_id._create_variant_ids()
        return res

    def unlink(self):
        """Override to:
        - Clean up the variants that use any of the values in self:
            - Remove the value from the variant if the value belonged to an
                attribute line with only one value.
            - Unlink or archive all related variants.
        - Archive the value if unlink is not possible.

        Archiving is typically needed when the value is referenced elsewhere
        (on a variant that can't be deleted, on a sales order line, ...).
        """
        # Directly remove the values from the variants for lines that had single
        # value (counting also the values that are archived).
        single_values = self.filtered(lambda ptav: len(ptav.attribute_line_id.product_template_value_ids) == 1)
        for ptav in single_values:
            ptav.ptav_product_variant_ids.write({
                'product_template_attribute_value_ids': [Command.unlink(ptav.id)],
            })
        # Try to remove the variants before deleting to potentially remove some
        # blocking references.
        self.ptav_product_variant_ids._unlink_or_archive()
        # Now delete or archive the values.
        ptav_to_archive = self.env['product.template.attribute.value']
        for ptav in self:
            try:
                with self.env.cr.savepoint(), tools.mute_logger('odoo.sql_db'):
                    super(ProductTemplateAttributeValue, ptav).unlink()
            except Exception:
                # We catch all kind of exceptions to be sure that the operation
                # doesn't fail.
                ptav_to_archive += ptav
        ptav_to_archive.write({'ptav_active': False})
        return True

    @api.depends('attribute_id')
    def _compute_display_name(self):
        """Override because in general the name of the value is confusing if it
        is displayed without the name of the corresponding attribute.
        Eg. on exclusion rules form
        """
        for value in self:
            value.display_name = f"{value.attribute_id.name}: {value.name}"

    def _only_active(self):
        return self.filtered(lambda ptav: ptav.ptav_active)

    def _without_no_variant_attributes(self):
        return self.filtered(lambda ptav: ptav.attribute_id.create_variant != 'no_variant')

    def _ids2str(self):
        return ','.join([str(i) for i in sorted(self.ids)])

    def _get_combination_name(self):
        """Exclude values from single value lines or from no_variant attributes."""
        ptavs = self._without_no_variant_attributes().with_prefetch(self._prefetch_ids)
        ptavs = ptavs._filter_single_value_lines().with_prefetch(self._prefetch_ids)
        return ", ".join([ptav.name for ptav in ptavs])

    def _filter_single_value_lines(self):
        """Return `self` with values from single value lines filtered out
        depending on the active state of all the values in `self`.

        If any value in `self` is archived, archived values are also taken into
        account when checking for single values.
        This allows to display the correct name for archived variants.

        If all values in `self` are active, only active values are taken into
        account when checking for single values.
        This allows to display the correct name for active combinations.
        """
        only_active = all(ptav.ptav_active for ptav in self)
        return self.filtered(lambda ptav: not ptav._is_from_single_value_line(only_active))

    def _is_from_single_value_line(self, only_active=True):
        """Return whether `self` is from a single value line, counting also
        archived values if `only_active` is False.
        """
        self.ensure_one()
        all_values = self.attribute_line_id.product_template_value_ids
        if only_active:
            all_values = all_values._only_active()
        return len(all_values) == 1
