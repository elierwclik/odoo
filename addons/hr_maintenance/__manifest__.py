# -*- coding: utf-8 -*-

{
    'name': 'Maintenance - HR',
    'version': '1.0',
    'sequence': 125,
    'category': 'Human Resources',
    'description': """
Bridge between HR and Maintenance.""",
    'depends': ['hr', 'maintenance'],
    'summary': 'Equipment, Assets, Internal Hardware, Allocation Tracking',
    'data': [
        'security/equipment.xml',
        'views/maintenance_views.xml',
        'views/hr_views.xml',
        'wizard/hr_departure_wizard_views.xml',
    ],
    'installable': True,
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
}
