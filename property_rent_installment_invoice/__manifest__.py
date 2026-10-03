# -*- coding: utf-8 -*-
{
    'name': 'Property Rent Installment & Invoice Integration',
    'version': '19.0.1.0.0',
    'category': 'Real Estate/Accounting',
    'summary': 'Smart buttons between Rent Schedules & Invoices, Partial Payments, and Remaining Balance Tracking',
    'description': """
Property Rent Installment & Accounting Invoice Integration
==========================================================
* Invoice Smart Button on Rent Schedule form view with one-click navigation.
* Rent Installment Smart Button on Customer Invoice (account.move) form view.
* Partial payment recording & status update wizard for Rent Schedules.
* Prominent Remaining Rent Balance KPI card & smart stats on Rent Scheduling form.
* Automatic and on-demand payment reconciliation between Invoices and Rent Installments.
    """,
    'author': 'Custom',
    'license': 'LGPL-3',
    'depends': ['samruddhi_property_management', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'wizards/rent_payment_wizard_views.xml',
        'views/rent_schedule_views.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
