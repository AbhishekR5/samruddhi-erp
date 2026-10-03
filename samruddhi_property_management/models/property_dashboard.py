# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _


class PropertyDashboard(models.Model):
    _name = 'property.dashboard'
    _description = 'Property Management Executive Dashboard'

    name = fields.Char(default='Property Executive Dashboard')

    @api.model
    def get_dashboard_metrics(self):
        """Returns consolidated KPI metrics for the user's current company."""
        company_id = self.env.company.id
        today = fields.Date.today()
        first_of_month = today.replace(day=1)
        next_month = first_of_month + relativedelta(months=1)

        # Properties & Units
        properties = self.env['property.property'].search([('company_id', '=', company_id), ('active', '=', True)])
        units = self.env['property.unit'].search([('company_id', '=', company_id), ('active', '=', True)])
        total_properties = len(properties)
        total_units = len(units)
        occupied_units = len(units.filtered(lambda u: u.status == 'occupied'))
        vacant_units = len(units.filtered(lambda u: u.status == 'available'))
        occupancy_rate = (occupied_units / total_units * 100.0) if total_units > 0 else 0.0

        # Contracts
        active_tenant_contracts = self.env['property.tenant.contract'].search([
            ('company_id', '=', company_id),
            ('state', '=', 'active')
        ])
        active_landlord_contracts = self.env['property.landlord.contract'].search([
            ('company_id', '=', company_id),
            ('state', '=', 'active')
        ])

        monthly_tenant_revenue = sum(active_tenant_contracts.mapped('monthly_rent'))
        monthly_landlord_cost = sum(active_landlord_contracts.mapped('monthly_amount'))

        # Expenses this month
        month_expenses = self.env['property.expense'].search([
            ('company_id', '=', company_id),
            ('date', '>=', first_of_month),
            ('date', '<', next_month),
            ('payment_state', '!=', 'cancelled')
        ])
        monthly_expenses_amount = sum(month_expenses.mapped('amount'))
        monthly_net_income = monthly_tenant_revenue - monthly_landlord_cost - monthly_expenses_amount

        # Rent Collections (Schedules due this month or overdue)
        month_schedules = self.env['property.rent.schedule'].search([
            ('company_id', '=', company_id),
            ('due_date', '>=', first_of_month),
            ('due_date', '<', next_month),
            ('state', '!=', 'cancelled')
        ])
        collected_rent_month = sum(month_schedules.mapped('paid_amount'))
        pending_rent_month = sum(month_schedules.mapped('balance_amount'))

        all_overdue = self.env['property.rent.schedule'].search([
            ('company_id', '=', company_id),
            ('state', '=', 'overdue')
        ])
        overdue_rent_total = sum(all_overdue.mapped('balance_amount'))

        # Landlord Payables
        all_landlord_payables = self.env['property.landlord.payment'].search([
            ('company_id', '=', company_id),
            ('state', 'in', ('pending', 'partial', 'overdue'))
        ])
        total_landlord_payable = sum(all_landlord_payables.mapped('balance_amount'))

        # Deposits Held
        held_deposits = self.env['property.security.deposit'].search([
            ('company_id', '=', company_id),
            ('state', 'in', ('received', 'held'))
        ])
        total_deposit_held = sum(held_deposits.mapped('amount'))

        # Expiring Contracts (next 30 days)
        expiring_limit = today + relativedelta(days=30)
        expiring_tenant = self.env['property.tenant.contract'].search_count([
            ('company_id', '=', company_id),
            ('state', '=', 'active'),
            ('end_date', '<=', expiring_limit),
            ('end_date', '>=', today)
        ])
        expiring_landlord = self.env['property.landlord.contract'].search_count([
            ('company_id', '=', company_id),
            ('state', '=', 'active'),
            ('end_date', '<=', expiring_limit),
            ('end_date', '>=', today)
        ])

        # Maintenance Tickets
        open_maintenance = self.env['property.maintenance.request'].search_count([
            ('company_id', '=', company_id),
            ('state', 'in', ('new', 'assigned', 'in_progress', 'waiting'))
        ])

        return {
            'currency_symbol': self.env.company.currency_id.symbol or '₹',
            'total_properties': total_properties,
            'total_units': total_units,
            'occupied_units': occupied_units,
            'vacant_units': vacant_units,
            'occupancy_rate': round(occupancy_rate, 1),
            'monthly_tenant_revenue': monthly_tenant_revenue,
            'monthly_landlord_cost': monthly_landlord_cost,
            'monthly_expenses_amount': monthly_expenses_amount,
            'monthly_net_income': monthly_net_income,
            'collected_rent_month': collected_rent_month,
            'pending_rent_month': pending_rent_month,
            'overdue_rent_total': overdue_rent_total,
            'total_landlord_payable': total_landlord_payable,
            'total_deposit_held': total_deposit_held,
            'expiring_contracts_count': expiring_tenant + expiring_landlord,
            'open_maintenance_count': open_maintenance,
        }
