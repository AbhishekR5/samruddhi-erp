# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_property_landlord = fields.Boolean(
        string='Is Landlord',
        help='Identifies this partner as a property landlord/owner.',
        index=True
    )
    is_property_tenant = fields.Boolean(
        string='Is Tenant',
        help='Identifies this partner as an active or prospective tenant.',
        index=True
    )
    pan_number = fields.Char(string='PAN Number', size=10, copy=False)
    gstin_number = fields.Char(string='GSTIN', size=15, copy=False)
    emergency_contact_name = fields.Char(string='Emergency Contact Name')
    emergency_contact_phone = fields.Char(string='Emergency Contact Phone')
    emergency_contact_relation = fields.Char(string='Relationship')

    # Related Relationships
    property_ids = fields.One2many(
        'property.property',
        'landlord_id',
        string='Owned/Controlled Properties'
    )
    landlord_contract_ids = fields.One2many(
        'property.landlord.contract',
        'landlord_id',
        string='Landlord Contracts'
    )
    tenant_contract_ids = fields.One2many(
        'property.tenant.contract',
        'tenant_id',
        string='Tenant Contracts'
    )
    rent_schedule_ids = fields.One2many(
        'property.rent.schedule',
        'tenant_id',
        string='Rent Schedules'
    )
    landlord_payment_ids = fields.One2many(
        'property.landlord.payment',
        'landlord_id',
        string='Landlord Payments'
    )
    security_deposit_ids = fields.One2many(
        'property.security.deposit',
        'tenant_id',
        string='Security Deposits'
    )
    maintenance_request_ids = fields.One2many(
        'property.maintenance.request',
        'tenant_id',
        string='Maintenance Requests'
    )

    # Computed KPI counters for smart buttons
    landlord_contract_count = fields.Integer(
        string='Landlord Contracts Count',
        compute='_compute_partner_property_stats'
    )
    tenant_contract_count = fields.Integer(
        string='Tenant Contracts Count',
        compute='_compute_partner_property_stats'
    )
    total_outstanding_rent = fields.Monetary(
        string='Total Outstanding Rent',
        compute='_compute_partner_property_stats',
        currency_field='currency_id'
    )
    total_deposit_held = fields.Monetary(
        string='Total Deposit Held',
        compute='_compute_partner_property_stats',
        currency_field='currency_id'
    )
    total_landlord_payable = fields.Monetary(
        string='Total Landlord Payable',
        compute='_compute_partner_property_stats',
        currency_field='currency_id'
    )

    def _compute_partner_property_stats(self):
        for partner in self:
            partner.landlord_contract_count = len(partner.landlord_contract_ids.filtered(lambda c: c.state != 'cancelled'))
            partner.tenant_contract_count = len(partner.tenant_contract_ids.filtered(lambda c: c.state != 'cancelled'))
            
            # Outstanding rent across pending or overdue schedules
            pending_schedules = partner.rent_schedule_ids.filtered(
                lambda s: s.state in ('pending', 'partial', 'overdue')
            )
            partner.total_outstanding_rent = sum(pending_schedules.mapped('balance_amount'))
            
            # Deposits held currently in 'received' or 'held' state
            held_deposits = partner.security_deposit_ids.filtered(
                lambda d: d.state in ('received', 'held')
            )
            partner.total_deposit_held = sum(held_deposits.mapped('amount'))
            
            # Landlord payables in 'pending', 'partial', or 'overdue' state
            pending_landlord_pays = partner.landlord_payment_ids.filtered(
                lambda p: p.state in ('pending', 'partial', 'overdue')
            )
            partner.total_landlord_payable = sum(pending_landlord_pays.mapped('balance_amount'))

    def action_view_landlord_contracts(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'samruddhi_property_management.action_landlord_contract'
        )
        action['domain'] = [('landlord_id', '=', self.id)]
        action['context'] = {'default_landlord_id': self.id}
        return action

    def action_view_tenant_contracts(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'samruddhi_property_management.action_tenant_contract'
        )
        action['domain'] = [('tenant_id', '=', self.id)]
        action['context'] = {'default_tenant_id': self.id}
        return action

    def action_view_rent_schedules(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'samruddhi_property_management.action_rent_schedule'
        )
        action['domain'] = [('tenant_id', '=', self.id)]
        action['context'] = {'default_tenant_id': self.id}
        return action

    def action_view_landlord_payments(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'samruddhi_property_management.action_landlord_payment'
        )
        action['domain'] = [('landlord_id', '=', self.id)]
        action['context'] = {'default_landlord_id': self.id}
        return action
