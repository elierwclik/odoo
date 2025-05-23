# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Subcontracting Management with Stock Valuation',
    'version': '0.1',
    'category': 'Supply Chain/Manufacturing',
    'description': """
This bridge module allows to manage subcontracting with valuation.
    """,
    'depends': ['mrp_subcontracting', 'mrp_account'],
    'installable': True,
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'data': [
        'security/mrp_subcontracting_account_security.xml',
        'security/ir.model.access.csv',
    ],
}
