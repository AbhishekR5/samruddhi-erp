# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PropertyMaintenanceRequest(models.Model):
    _name = 'property.maintenance.request'
    _description = 'Property Maintenance Ticket / Work Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True
    _order = 'priority desc, request_date desc, id desc'

    name = fields.Char(
        string='Ticket Ref',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        index=True
    )
    title = fields.Char(string='Subject / Issue Title', required=True, tracking=True)
    property_id = fields.Many2one(
        'property.property',
        string='Property',
        required=True,
        check_company=True,
        index=True,
        tracking=True
    )
    unit_id = fields.Many2one(
        'property.unit',
        string='Unit (Optional)',
        domain="[('property_id', '=', property_id)]",
        check_company=True,
        index=True,
        tracking=True
    )
    tenant_id = fields.Many2one(
        'res.partner',
        string='Tenant / Reporter',
        domain="[('is_property_tenant', '=', True)]",
        check_company=True,
        index=True,
        tracking=True
    )
    contract_id = fields.Many2one(
        'property.tenant.contract',
        string='Tenant Contract',
        domain="[('unit_id', '=?', unit_id), ('tenant_id', '=?', tenant_id)]",
        check_company=True
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string='Currency',
        readonly=True
    )

    description = fields.Html(string='Issue Description & Photos')
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Urgent / Critical'),
    ], string='Priority', default='1', tracking=True)

    request_date = fields.Date(string='Request Date', default=fields.Date.today, required=True, tracking=True)
    assigned_user_id = fields.Many2one(
        'res.users',
        string='Assigned Maintenance Officer',
        check_company=True,
        tracking=True
    )
    vendor_id = fields.Many2one(
        'res.partner',
        string='Contractor / Vendor',
        check_company=True,
        tracking=True
    )

    estimated_cost = fields.Monetary(string='Estimated Cost', currency_field='currency_id')
    actual_cost = fields.Monetary(string='Actual Incurred Cost', currency_field='currency_id', tracking=True)
    completion_date = fields.Date(string='Completion Date', tracking=True)

    state = fields.Selection([
        ('new', 'NEW TICKET'),
        ('assigned', 'ASSIGNED'),
        ('in_progress', 'IN PROGRESS'),
        ('waiting', 'WAITING ON PARTS / VENDOR'),
        ('completed', 'COMPLETED'),
        ('cancelled', 'CANCELLED'),
    ], string='Status', default='new', required=True, tracking=True)

    expense_id = fields.Many2one(
        'property.expense',
        string='Linked Property Expense',
        check_company=True,
        copy=False
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('property.maintenance.request') or _('New')
        return super().create(vals_list)

    @api.onchange('unit_id')
    def _onchange_unit_id(self):
        if self.unit_id:
            self.property_id = self.unit_id.property_id
            if self.unit_id.active_contract_id:
                self.contract_id = self.unit_id.active_contract_id
                self.tenant_id = self.unit_id.active_contract_id.tenant_id

    def action_assign(self):
        self.write({'state': 'assigned'})

    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_wait(self):
        self.write({'state': 'waiting'})

    def action_complete(self):
        self.ensure_one()
        self.write({
            'state': 'completed',
            'completion_date': fields.Date.today(),
        })
        # Auto-create expense record if actual cost was incurred and no expense exists
        if self.actual_cost > 0 and not self.expense_id:
            expense = self.env['property.expense'].create({
                'property_id': self.property_id.id,
                'unit_id': self.unit_id.id if self.unit_id else False,
                'vendor_id': self.vendor_id.id if self.vendor_id else False,
                'expense_category': 'maintenance',
                'date': fields.Date.today(),
                'amount': self.actual_cost,
                'description': _('Maintenance Ticket: %s - %s') % (self.name, self.title),
                'company_id': self.company_id.id,
                'payment_state': 'submitted',
            })
            self.write({'expense_id': expense.id})
            self.message_post(body=_('Ticket completed. Automatically logged Property Expense %s.') % expense.name)
        else:
            self.message_post(body=_('Maintenance Ticket %s completed.') % self.name)

    def action_cancel(self):
        self.write({'state': 'cancelled'})
