# -*- coding: utf-8 -*-
# Copyright Alitec (<http://alitec.sg>).
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

{
    'name': 'CIMB Payment Parser',
    'version': '1.0',
    'category': 'Account',
    'summary': 'Singapore-CIMB Payment Parser',
    'description': """
This module helps to parse the invoice details and generate CIMB file as Electronic codes.

    """,
    'author':'alitec',
    'website': 'http://alitec.sg',
    'depends' : ['air_uob_payment_parser'],
    'data': [
#         'wizard/payment_parser_wizard.xml',
        'payment_parser_view.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}

