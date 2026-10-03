# -*- coding: utf-8 -*-
{
    'name': 'Samruddhi Property Management',
    'version': '19.0.1.0.0',
    'category': 'Real Estate/Property Management',
    'summary': 'Comprehensive Property Management ERP for Owned, Rented, and Leased Properties',
    'description': """
Samruddhi Property Management ERP
=================================
Complete property management solution supporting:
- Independent Property Control (Owned, Rented from Landlord, Leased from Landlord)
- Independent Tenant Agreements (Rent, Lease)
- Landlord & Tenant Contracts with full lifecycle management
- Rent schedules, payment tracking, and landlord disbursement schedules
- Segregated Security Deposit escrow management
- Operating expense tracking and property-level profitability
- Maintenance request management with chatter and SLA tracking
- Multi-company isolation and multi-currency support
- Landlord & Tenant self-service portal
- Automated contract expiry, rent generation, and overdue alerts
- Executive KPI dashboard and QWeb PDF statements
    """,
    'author': 'Samruddhi ERP Team',
    'website': 'https://www.samruddhi.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'portal',
        'account',
    ],
    'data': [
        # Security
        'security/security.xml',
        'security/ir.model.access.csv',
        'security/record_rules.xml',
        # Data & Sequences
        'data/sequence.xml',
        'data/cron.xml',
        # Views
        'views/menu_views.xml',
        'views/property_views.xml',
        'views/unit_views.xml',
        'views/partner_views.xml',
        'views/landlord_contract_views.xml',
        'views/tenant_contract_views.xml',
        'views/rent_schedule_views.xml',
        'views/landlord_payment_views.xml',
        'views/deposit_views.xml',
        'views/expense_views.xml',
        'views/maintenance_views.xml',
        'views/dashboard_views.xml',
        # Reports
        'reports/report_actions.xml',
        'reports/property_report_template.xml',
        'reports/landlord_statement_template.xml',
        'reports/tenant_statement_template.xml',
        'reports/contract_report_template.xml',
        'reports/profitability_report_template.xml',
        # Portal
        'views/portal_templates.xml',
    ],
    'demo': [
        'demo/demo_data.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
