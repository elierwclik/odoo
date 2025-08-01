# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re

import psycopg2

from odoo import SUPERUSER_ID, Command, _, api, fields, models
from odoo.exceptions import UserError
from odoo.modules.registry import Registry
from odoo.tools.safe_eval import safe_eval


class DeliveryCarrier(models.Model):
    _name = 'delivery.carrier'
    _description = "Shipping Methods"
    _order = 'sequence, id'

    ''' A Shipping Provider

    In order to add your own external provider, follow these steps:

    1. Create your model MyProvider that _inherit 'delivery.carrier'
    2. Extend the selection of the field "delivery_type" with a pair
       ('<my_provider>', 'My Provider')
    3. Add your methods:
       <my_provider>_rate_shipment
       <my_provider>_send_shipping
       <my_provider>_get_tracking_link
       <my_provider>_cancel_shipment
       _<my_provider>_get_default_custom_package_code
       (they are documented hereunder)
    '''

    # -------------------------------- #
    # Internals for shipping providers #
    # -------------------------------- #

    name = fields.Char('Delivery Method', required=True, translate=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(help="Determine the display order", default=10)
    # This field will be overwritten by internal shipping providers by adding their own type (ex: 'fedex')
    delivery_type = fields.Selection(
        [('base_on_rule', 'Based on Rules'), ('fixed', 'Fixed Price')],
        string='Provider',
        default='fixed',
        required=True,
    )
    allow_cash_on_delivery = fields.Boolean(
        string="Cash on Delivery",
        help="Allow customers to choose Cash on Delivery as their payment method.",
    )
    integration_level = fields.Selection([('rate', 'Get Rate'), ('rate_and_ship', 'Get Rate and Create Shipment')], string="Integration Level", default='rate_and_ship', help="Action while validating Delivery Orders")
    prod_environment = fields.Boolean("Environment", help="Set to True if your credentials are certified for production.")
    debug_logging = fields.Boolean('Debug logging', help="Log requests in order to ease debugging")
    company_id = fields.Many2one('res.company', string='Company', related='product_id.company_id', store=True, readonly=False)
    product_id = fields.Many2one('product.product', string='Delivery Product', required=True, ondelete='restrict')
    tracking_url = fields.Char(string='Tracking Link', help="This option adds a link for the customer in the portal to track their package easily. Use <shipmenttrackingnumber> as a placeholder in your URL.")
    currency_id = fields.Many2one(related='product_id.currency_id')

    invoice_policy = fields.Selection(
        selection=[('estimated', "Estimated cost")],
        string="Invoicing Policy",
        default='estimated',
        required=True,
        help="Estimated Cost: the customer will be invoiced the estimated cost of the shipping.",
    )

    country_ids = fields.Many2many('res.country', 'delivery_carrier_country_rel', 'carrier_id', 'country_id', 'Countries')
    state_ids = fields.Many2many('res.country.state', 'delivery_carrier_state_rel', 'carrier_id', 'state_id', 'States')
    zip_prefix_ids = fields.Many2many(
        'delivery.zip.prefix', 'delivery_zip_prefix_rel', 'carrier_id', 'zip_prefix_id', 'Zip Prefixes',
        help="Prefixes of zip codes that this carrier applies to. Note that regular expressions can be used to support countries with varying zip code lengths, i.e. '$' can be added to end of prefix to match the exact zip (e.g. '100$' will only match '100' and not '1000')")

    max_weight = fields.Float('Max Weight', help="If the total weight of the order is over this weight, the method won't be available.")
    weight_uom_name = fields.Char(string='Weight unit of measure label', compute='_compute_weight_uom_name')
    max_volume = fields.Float('Max Volume', help="If the total volume of the order is over this volume, the method won't be available.")
    volume_uom_name = fields.Char(string='Volume unit of measure label', compute='_compute_volume_uom_name')
    must_have_tag_ids = fields.Many2many(string='Must Have Tags', comodel_name='product.tag', relation='product_tag_delivery_carrier_must_have_rel',
                                         help="The method is available only if at least one product of the order has one of these tags.")
    excluded_tag_ids = fields.Many2many(string='Excluded Tags', comodel_name='product.tag', relation='product_tag_delivery_carrier_excluded_rel',
                                        help="The method is NOT available if at least one product of the order has one of these tags.")

    carrier_description = fields.Text(
        'Carrier Description', translate=True,
        help="A description of the delivery method that you want to communicate to your customers on the Sales Order and sales confirmation email."
             "E.g. instructions for customers to follow.")

    margin = fields.Float(help='This percentage will be added to the shipping price.')
    fixed_margin = fields.Float(help='This fixed amount will be added to the shipping price.')
    free_over = fields.Boolean('Free if order amount is above', help="If the order total amount (shipping excluded) is above or equal to this value, the customer benefits from a free shipping", default=False)
    amount = fields.Float(
        string="Amount",
        default=1000,
        help="Amount of the order to benefit from a free shipping, expressed in the company currency",
    )

    can_generate_return = fields.Boolean(compute="_compute_can_generate_return")
    return_label_on_delivery = fields.Boolean(string="Generate Return Label", help="The return label is automatically generated at the delivery.")
    get_return_label_from_portal = fields.Boolean(string="Return Label Accessible from Customer Portal", help="The return label can be downloaded by the customer from the customer portal.")

    supports_shipping_insurance = fields.Boolean(compute="_compute_supports_shipping_insurance")
    shipping_insurance = fields.Integer(
        "Insurance Percentage",
        help="Shipping insurance is a service which may reimburse senders whose parcels are lost, stolen, and/or damaged in transit.",
        default=0
    )

    price_rule_ids = fields.One2many(
        'delivery.price.rule', 'carrier_id', 'Pricing Rules', copy=True
    )

    _margin_not_under_100_percent = models.Constraint(
        'CHECK (margin >= -1)',
        'Margin cannot be lower than -100%',
    )
    _shipping_insurance_is_percentage = models.Constraint(
        'CHECK(shipping_insurance >= 0 AND shipping_insurance <= 100)',
        'The shipping insurance must be a percentage between 0 and 100.',
    )

    @api.constrains('must_have_tag_ids', 'excluded_tag_ids')
    def _check_tags(self):
        for carrier in self:
            if carrier.must_have_tag_ids & carrier.excluded_tag_ids:
                raise UserError(_("Carrier %s cannot have the same tag in both Must Have Tags and Excluded Tags.") % carrier.name)

    def _compute_weight_uom_name(self):
        self.weight_uom_name = self.env['product.template']._get_weight_uom_name_from_ir_config_parameter()

    def _compute_volume_uom_name(self):
        self.volume_uom_name = self.env['product.template']._get_volume_uom_name_from_ir_config_parameter()

    @api.depends('delivery_type')
    def _compute_can_generate_return(self):
        for carrier in self:
            carrier.can_generate_return = False

    @api.depends('delivery_type')
    def _compute_supports_shipping_insurance(self):
        for carrier in self:
            carrier.supports_shipping_insurance = False

    def toggle_prod_environment(self):
        for c in self:
            c.prod_environment = not c.prod_environment

    def toggle_debug(self):
        for c in self:
            c.debug_logging = not c.debug_logging

    def install_more_provider(self):
        exclude_apps = ['delivery_barcode', 'delivery_stock_picking_batch', 'delivery_iot']
        return {
            'name': _('New Providers'),
            'view_mode': 'kanban,form',
            'res_model': 'ir.module.module',
            'domain': [['name', '=like', 'delivery_%'], ['name', 'not in', exclude_apps]],
            'type': 'ir.actions.act_window',
            'help': _('''<p class="o_view_nocontent">
                    Buy Odoo Enterprise now to get more providers.
                </p>'''),
        }

    def _is_available_for_order(self, order):
        self.ensure_one()
        order.ensure_one()
        if not self._match(order.partner_shipping_id, order):
            return False

        if self.delivery_type == 'base_on_rule':
            return self.rate_shipment(order).get('success')

        return True

    def available_carriers(self, partner, source):
        return self.filtered(lambda c: c._match(partner, source))

    def _match(self, partner, source):
        self.ensure_one()
        return (
            self._match_address(partner)
            and self._match_must_have_tags(source)
            and self._match_excluded_tags(source)
            and self._match_weight(source)
            and self._match_volume(source)
        )

    def _match_address(self, partner):
        self.ensure_one()
        if self.country_ids and partner.country_id not in self.country_ids:
            return False
        if self.state_ids and partner.state_id not in self.state_ids:
            return False
        if self.zip_prefix_ids:
            regex = re.compile('|'.join(['^' + zip_prefix for zip_prefix in self.zip_prefix_ids.mapped('name')]))
            if not partner.zip or not re.match(regex, partner.zip.upper()):
                return False
        return True

    def _match_must_have_tags(self, source):
        self.ensure_one()
        if source._name == 'sale.order':
            products = source.order_line.product_id
        elif source._name == 'stock.picking':
            products = source.move_ids.product_id
        else:
            raise UserError(_("Invalid source document type"))
        return not self.must_have_tag_ids or any(
            tag in products.all_product_tag_ids
            for tag in self.must_have_tag_ids
        )

    def _match_excluded_tags(self, source):
        self.ensure_one()
        if source._name == 'sale.order':
            products = source.order_line.product_id
        elif source._name == 'stock.picking':
            products = source.move_ids.product_id
        else:
            raise UserError(_("Invalid source document type"))
        return not any(tag in products.all_product_tag_ids for tag in self.excluded_tag_ids)

    def _match_weight(self, source):
        self.ensure_one()
        if source._name == 'sale.order':
            total_weight = sum(
                line.product_id.weight * line.product_qty
                for line in source.order_line
            )
        elif source._name == 'stock.picking':
            total_weight = sum(
                move.product_id.weight * move.product_uom_qty
                for move in source.move_ids
            )
        else:
            raise UserError(_("Invalid source document type"))
        return not self.max_weight or total_weight <= self.max_weight

    def _match_volume(self, source):
        self.ensure_one()
        if source._name == 'sale.order':
            total_volume = sum(
                line.product_id.volume * line.product_qty
                for line in source.order_line
            )
        elif source._name == 'stock.picking':
            total_volume = sum(
                move.product_id.volume * move.product_uom_qty
                for move in source.move_ids
            )
        else:
            raise UserError(_("Invalid source document type"))
        return not self.max_volume or total_volume <= self.max_volume

    @api.onchange('integration_level')
    def _onchange_integration_level(self):
        if self.integration_level == 'rate':
            self.invoice_policy = 'estimated'

    @api.onchange('can_generate_return')
    def _onchange_can_generate_return(self):
        if not self.can_generate_return:
            self.return_label_on_delivery = False

    @api.onchange('return_label_on_delivery')
    def _onchange_return_label_on_delivery(self):
        if not self.return_label_on_delivery:
            self.get_return_label_from_portal = False

    @api.onchange('country_ids')
    def _onchange_country_ids(self):
        self.state_ids -= self.state_ids.filtered(
            lambda state: state._origin.id not in self.country_ids.state_ids.ids
        )
        if not self.country_ids:
            self.zip_prefix_ids = [Command.clear()]

    def copy_data(self, default=None):
        vals_list = super().copy_data(default=default)
        return [dict(vals, name=self.env._("%s (copy)", carrier.name)) for carrier, vals in zip(self, vals_list)]

    def _get_delivery_type(self):
        """Return the delivery type.

        This method needs to be overridden by a delivery carrier module if the delivery type is not
        stored on the field `delivery_type`.
        """
        self.ensure_one()
        return self.delivery_type

    def _apply_margins(self, price, order=False):
        self.ensure_one()
        if self.delivery_type == 'fixed':
            return float(price)
        fixed_margin_in_sale_currency = self._compute_currency(order, self.fixed_margin, 'company_to_pricelist') if order else self.fixed_margin
        return float(price) * (1.0 + self.margin) + fixed_margin_in_sale_currency

    # -------------------------- #
    # API for external providers #
    # -------------------------- #

    def rate_shipment(self, order):
        ''' Compute the price of the order shipment

        :param order: record of sale.order
        :returns: a dict with structure
          ::

            {'success': boolean,
             'price': a float,
             'error_message': a string containing an error message,
             'warning_message': a string containing a warning message}
        :rtype: dict
        '''
        # TODO maybe the currency code?
        self.ensure_one()
        if hasattr(self, '%s_rate_shipment' % self.delivery_type):
            res = getattr(self, '%s_rate_shipment' % self.delivery_type)(order)
            # apply fiscal position
            company = self.company_id or order.company_id or self.env.company
            res['price'] = self.product_id._get_tax_included_unit_price(
                company,
                company.currency_id,
                order.date_order,
                'sale',
                fiscal_position=order.fiscal_position_id,
                product_price_unit=res['price'],
                product_currency=company.currency_id
            )
            # apply margin on computed price
            res['price'] = self._apply_margins(res['price'], order)
            # save the real price in case a free_over rule overide it to 0
            res['carrier_price'] = res['price']
            # free when order is large enough
            amount_without_delivery = order._compute_amount_total_without_delivery()
            if (
                res['success']
                and self.free_over
                and self.delivery_type != 'base_on_rule'
                and self._compute_currency(order, amount_without_delivery, 'pricelist_to_company') >= self.amount
            ):
                res['warning_message'] = _('The shipping is free since the order amount exceeds %.2f.', self.amount)
                res['price'] = 0.0
            return res
        else:
            return {
                'success': False,
                'price': 0.0,
                'error_message': _('Error: this delivery method is not available.'),
                'warning_message': False,
            }

    def log_xml(self, xml_string, func):
        self.ensure_one()

        if self.debug_logging:
            self.env.flush_all()
            db_name = self.env.cr.dbname

            # Use a new cursor to avoid rollback that could be caused by an upper method
            try:
                db_registry = Registry(db_name)
                with db_registry.cursor() as cr:
                    env = api.Environment(cr, SUPERUSER_ID, {})
                    IrLogging = env['ir.logging']
                    IrLogging.sudo().create({'name': 'delivery.carrier',
                              'type': 'server',
                              'dbname': db_name,
                              'level': 'DEBUG',
                              'message': xml_string,
                              'path': self.delivery_type,
                              'func': func,
                              'line': 1})
            except psycopg2.Error:
                pass

    # ------------------------------------------------ #
    # Fixed price shipping, aka a very simple provider #
    # ------------------------------------------------ #

    fixed_price = fields.Float(compute='_compute_fixed_price', inverse='_set_product_fixed_price', store=True, string='Fixed Price')

    @api.depends('product_id.list_price', 'product_id.product_tmpl_id.list_price')
    def _compute_fixed_price(self):
        for carrier in self:
            carrier.fixed_price = carrier.product_id.list_price

    def _set_product_fixed_price(self):
        for carrier in self:
            carrier.product_id.list_price = carrier.fixed_price

    def fixed_rate_shipment(self, order):
        carrier = self._match_address(order.partner_shipping_id)
        if not carrier:
            return {'success': False,
                    'price': 0.0,
                    'error_message': _('Error: this delivery method is not available for this address.'),
                    'warning_message': False}
        price = order.pricelist_id._get_product_price(self.product_id, 1.0)
        return {'success': True,
                'price': price,
                'error_message': False,
                'warning_message': False}

    # ----------------------------------- #
    # Based on rule delivery type methods #
    # ----------------------------------- #

    def base_on_rule_rate_shipment(self, order):
        carrier = self._match_address(order.partner_shipping_id)
        if not carrier:
            return {'success': False,
                    'price': 0.0,
                    'error_message': _('Error: this delivery method is not available for this address.'),
                    'warning_message': False}

        try:
            price_unit = self._get_price_available(order)
        except UserError as e:
            return {'success': False,
                    'price': 0.0,
                    'error_message': e.args[0],
                    'warning_message': False}

        price_unit = self._compute_currency(order, price_unit, 'company_to_pricelist')

        return {'success': True,
                'price': price_unit,
                'error_message': False,
                'warning_message': False}

    def _get_conversion_currencies(self, order, conversion):
        company_currency = (self.company_id or self.env['res.company']._get_main_company()).currency_id
        pricelist_currency = order.currency_id

        if conversion == 'company_to_pricelist':
            return company_currency, pricelist_currency
        elif conversion == 'pricelist_to_company':
            return pricelist_currency, company_currency

    def _compute_currency(self, order, price, conversion):
        from_currency, to_currency = self._get_conversion_currencies(order, conversion)
        if from_currency.id == to_currency.id:
            return price
        return from_currency._convert(price, to_currency, order.company_id, order.date_order or fields.Date.today())

    def _get_price_available(self, order):
        self.ensure_one()
        self = self.sudo()
        order = order.sudo()
        total = weight = volume = quantity = wv = 0
        total_delivery = 0.0
        for line in order.order_line:
            if line.state == 'cancel':
                continue
            if line.is_delivery:
                total_delivery += line.price_total
            if not line.product_id or line.is_delivery:
                continue
            if line.product_id.type == "service":
                continue
            qty = line.product_uom_id._compute_quantity(line.product_uom_qty, line.product_id.uom_id)
            weight += (line.product_id.weight or 0.0) * qty
            volume += (line.product_id.volume or 0.0) * qty
            wv += (line.product_id.weight or 0.0) * (line.product_id.volume or 0.0) * qty
            quantity += qty
        total = (order.amount_total or 0.0) - total_delivery

        total = self._compute_currency(order, total, 'pricelist_to_company')
        # weight is either,
        # 1- weight chosen by user in choose.delivery.carrier wizard passed by context
        # 2- saved weight to use on sale order
        # 3- total order line weight as fallback
        weight = self.env.context.get('order_weight') or order.shipping_weight or weight
        return self._get_price_from_picking(total, weight, volume, quantity, wv=wv)

    def _get_price_dict(self, total, weight, volume, quantity, wv=0.):
        '''Hook allowing to retrieve dict to be used in _get_price_from_picking() function.
        Hook to be overridden when we need to add some field to product and use it in variable factor from price rules. '''
        return {
            'price': total,
            'volume': volume,
            'weight': weight,
            'wv': wv or volume * weight,
            'quantity': quantity
        }

    def _get_price_from_picking(self, total, weight, volume, quantity, wv=0.):
        price = 0.0
        criteria_found = False
        price_dict = self._get_price_dict(total, weight, volume, quantity, wv=wv)
        for line in self.price_rule_ids:
            test = safe_eval(line.variable + line.operator + str(line.max_value), price_dict)
            if test:
                price = line.list_base_price + line.list_price * price_dict[line.variable_factor]
                criteria_found = True
                break
        if not criteria_found:
            raise UserError(_("Not available for current order"))

        return price
