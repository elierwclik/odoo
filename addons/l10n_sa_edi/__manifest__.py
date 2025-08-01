# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Saudi Arabia - E-invoicing',
    'author': 'Odoo S.A.',
    'countries': ['sa'],
    'version': '0.2',
    'depends': [
        'account_edi',
        'account_edi_ubl_cii',
        'l10n_sa',
        'base_vat',
        'certificate',
    ],
    'summary': """
        E-Invoicing, Universal Business Language
    """,
    'description': """
E-invoice implementation for Saudi Arabia; Integration with ZATCA
    """,
    'category': 'Accounting/Localizations/EDI',
    'license': 'LGPL-3',
    'data': [
        'security/ir.model.access.csv',
        'data/account_edi_format.xml',
        'data/ubl_21_zatca.xml',
        'data/res_country_data.xml',
        'wizard/l10n_sa_edi_otp_wizard.xml',
        'views/account_tax_views.xml',
        'views/account_journal_views.xml',
        'views/res_partner_views.xml',
        'views/res_company_views.xml',
        'views/res_config_settings_view.xml',
        'views/report_invoice.xml',
    ],
    'demo': [
        'demo/demo_company.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'l10n_sa_edi/static/src/scss/form_view.scss',
        ]
    }
}
