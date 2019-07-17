# -*- coding: utf-8 -*-
# Copyright Alitec (<http://alitec.sg>).
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

{
    'name': 'UOB Payment Parser',
    'version': '1.0',
    'category': 'Account',
    'summary': 'Singapore-UOB Payment Parser',
    'description': """
This module helps to parse the invoice details and generate UOB file as Electronic codes.

    """,
    'author':'alitec',
    'website': 'http://alitec.sg',
    'depends' : ['account_check_printing'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/payment_parser_wizard.xml',
        'payment_parser.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}

