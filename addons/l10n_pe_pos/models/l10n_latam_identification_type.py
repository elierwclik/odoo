# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api


class L10n_LatamIdentificationType(models.Model):
    _name = 'l10n_latam.identification.type'
    _inherit = ['l10n_latam.identification.type', 'pos.load.mixin']

    @api.model
    def _load_pos_data_domain(self, data, config):
        if self.env.company.country_id.code == "PE":
            return [("l10n_pe_vat_code", "!=", False)]
        else:
            return super()._load_pos_data_domain(data, config)

    @api.model
    def _load_pos_data_fields(self, config):
        return ['name']
