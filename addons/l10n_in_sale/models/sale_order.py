# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    l10n_in_reseller_partner_id = fields.Many2one('res.partner',
        string='Reseller', domain="[('vat', '!=', False), '|', ('company_id', '=', False), ('company_id', '=', company_id)]", readonly=False)

    @api.depends('partner_id', 'partner_shipping_id')
    def _compute_fiscal_position_id(self):

        def _get_fiscal_state(order, foreign_state):
            """
            Maps each order to its corresponding fiscal state based on its type,
            fiscal conditions, and the state of the associated partner or company.
            """

            if (
                order.country_code != 'IN'
                # Partner's FP takes precedence through super
                or order.partner_shipping_id.property_account_position_id
                or order.partner_id.property_account_position_id
            ):
                return False
            elif order.partner_shipping_id.l10n_in_gst_treatment == 'special_economic_zone':
                # Special Economic Zone
                return foreign_state

            # Computing Place of Supply for particular order
            partner = (
                order.partner_id.commercial_partner_id == order.partner_shipping_id.commercial_partner_id
                and order.partner_shipping_id
                or order.partner_id
            )
            if partner.country_id and partner.country_id.code != 'IN':
                return foreign_state
            partner_state = partner.state_id or order.partner_id.commercial_partner_id.state_id or order.company_id.state_id
            country_code = partner_state.country_id.code or order.country_code
            return partner_state if country_code == 'IN' else foreign_state

        FiscalPosition = self.env['account.fiscal.position']
        foreign_state = self.env['res.country.state'].search([('code', '!=', 'IN')], limit=1)
        for state_id, orders in self.grouped(lambda order: _get_fiscal_state(order, foreign_state)).items():
            if state_id:
                virtual_partner = self.env['res.partner'].new({
                    'state_id': state_id.id,
                    'country_id': state_id.country_id.id,
                })
                # Group orders by company to avoid multi-company conflicts
                for company_id, company_orders in orders.grouped('company_id').items():
                    company_orders.fiscal_position_id = FiscalPosition.with_company(
                        company_id.id
                    )._get_fiscal_position(virtual_partner)
            else:
                super(SaleOrder, orders)._compute_fiscal_position_id()

    def _prepare_invoice(self):
        invoice_vals = super(SaleOrder, self)._prepare_invoice()
        if self.country_code == 'IN':
            invoice_vals['l10n_in_reseller_partner_id'] = self.l10n_in_reseller_partner_id.id
        return invoice_vals
