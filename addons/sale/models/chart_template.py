from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    def _get_property_accounts(self, additional_properties):
        property_accounts = super()._get_property_accounts(additional_properties)
        property_accounts['downpayment_account_id'] = 'res.company'
        return property_accounts
