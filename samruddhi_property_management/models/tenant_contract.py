# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PropertyTenantContract(models.Model):
    _name = 'property.tenant.contract'
    _description = 'Tenant Contract (Samruddhi -> Tenant)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True
    _order = 'start_date desc, id desc'

    name = fields.Char(
        string='Contract Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        index=True
    )
    contract_number = fields.Char(string='Legal / Agreement Ref', copy=False, tracking=True)
    tenant_id = fields.Many2one(
        'res.partner',
        string='Tenant',
        required=True,
        domain="[('is_property_tenant', '=', True)]",
        check_company=True,
        tracking=True,
        index=True
    )
    property_id = fields.Many2one(
        'property.property',
        string='Property',
        required=True,
        check_company=True,
        tracking=True,
        index=True
    )
    unit_id = fields.Many2one(
        'property.unit',
        string='Unit',
        required=True,
        domain="[('property_id', '=', property_id)]",
        check_company=True,
        tracking=True,
        index=True
    )
    contract_type = fields.Selection([
        ('rent', 'RENT (Rent to Tenant)'),
        ('lease', 'LEASE (Lease to Tenant)'),
    ], string='Contract Type', default='rent', required=True, tracking=True)

    start_date = fields.Date(string='Start Date', required=True, tracking=True)
    end_date = fields.Date(string='End Date', required=True, tracking=True)

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

    monthly_rent = fields.Monetary(
        string='Monthly Rent Receivable',
        required=True,
        currency_field='currency_id',
        tracking=True
    )
    security_deposit = fields.Monetary(
        string='Security Deposit Required',
        currency_field='currency_id',
        tracking=True
    )
    payment_frequency = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('semi_annual', 'Semi-Annual'),
        ('annual', 'Annual'),
    ], string='Payment Frequency', default='monthly', required=True)

    payment_due_day = fields.Integer(string='Payment Due Day', default=1)
    grace_period = fields.Integer(string='Grace Period (Days)', default=5)
    late_fee = fields.Monetary(string='Late Fee / Penalty Amount', currency_field='currency_id', default=0.0)
    notice_period = fields.Integer(string='Notice Period (Days)', default=30)
    rent_escalation = fields.Float(string='Rent Escalation (%) per year', default=5.0)
    renewal_terms = fields.Text(string='Renewal Terms & Special Conditions')

    state = fields.Selection([
        ('draft', 'DRAFT'),
        ('active', 'ACTIVE'),
        ('expiring', 'EXPIRING SOON'),
        ('expired', 'EXPIRED'),
        ('terminated', 'TERMINATED'),
        ('cancelled', 'CANCELLED'),
    ], string='Status', default='draft', required=True, tracking=True)

    document_ids = fields.Many2many(
        'ir.attachment',
        'tenant_contract_attachment_rel',
        'contract_id',
        'attachment_id',
        string='Signed Contracts & Documents'
    )

    # Relational Children
    rent_schedule_ids = fields.One2many(
        'property.rent.schedule',
        'contract_id',
        string='Rent Schedules'
    )
    security_deposit_ids = fields.One2many(
        'property.security.deposit',
        'contract_id',
        string='Security Deposits'
    )
    maintenance_ids = fields.One2many(
        'property.maintenance.request',
        'contract_id',
        string='Maintenance Requests'
    )

    # Computed Counts and Financials
    rent_schedule_count = fields.Integer(compute='_compute_counts')
    deposit_count = fields.Integer(compute='_compute_counts')
    maintenance_count = fields.Integer(compute='_compute_counts')

    total_rent_billed = fields.Monetary(
        string='Total Rent Billed',
        compute='_compute_rent_summary',
        currency_field='currency_id'
    )
    total_rent_collected = fields.Monetary(
        string='Total Rent Collected',
        compute='_compute_rent_summary',
        currency_field='currency_id'
    )
    total_rent_outstanding = fields.Monetary(
        string='Total Rent Outstanding',
        compute='_compute_rent_summary',
        currency_field='currency_id'
    )

    _due_day_valid = models.Constraint('CHECK(payment_due_day >= 1 AND payment_due_day <= 31)', 'Due day must be between 1 and 31!')
    _positive_monthly_rent = models.Constraint('CHECK(monthly_rent >= 0)', 'Monthly rent cannot be negative!')
    _positive_security_deposit = models.Constraint('CHECK(security_deposit >= 0)', 'Security deposit cannot be negative!')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('property.tenant.contract') or _('New')
        return super().create(vals_list)

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.start_date >= rec.end_date:
                raise ValidationError(_('Contract start date must be strictly before end date!'))

    @api.constrains('unit_id', 'start_date', 'end_date', 'state')
    def _check_unit_overlap(self):
        """Do not allow two active tenant contracts for the same unit with overlapping dates."""
        for rec in self:
            if rec.state in ('active', 'draft') and rec.unit_id and rec.start_date and rec.end_date:
                # Search other contracts on same unit
                overlapping = self.search([
                    ('id', '!=', rec.id),
                    ('unit_id', '=', rec.unit_id.id),
                    ('state', 'in', ['active']),
                    ('start_date', '<=', rec.end_date),
                    ('end_date', '>=', rec.start_date),
                ])
                if overlapping:
                    conflict = overlapping[0]
                    raise ValidationError(_(
                        'Unit "%s" is already booked by Active Contract "%s" (%s to %s). Overlapping tenant contracts are forbidden!'
                    ) % (rec.unit_id.name, conflict.name, conflict.start_date, conflict.end_date))

    @api.constrains('unit_id', 'property_id')
    def _check_unit_property_match(self):
        for rec in self:
            if rec.unit_id and rec.property_id and rec.unit_id.property_id != rec.property_id:
                raise ValidationError(_('Selected Unit "%s" does not belong to Property "%s"!') % (
                    rec.unit_id.name, rec.property_id.name
                ))

    def _compute_counts(self):
        for rec in self:
            rec.rent_schedule_count = len(rec.rent_schedule_ids)
            rec.deposit_count = len(rec.security_deposit_ids)
            rec.maintenance_count = len(rec.maintenance_ids)

    @api.depends('rent_schedule_ids.amount', 'rent_schedule_ids.paid_amount', 'rent_schedule_ids.balance_amount')
    def _compute_rent_summary(self):
        for rec in self:
            rec.total_rent_billed = sum(rec.rent_schedule_ids.mapped('amount'))
            rec.total_rent_collected = sum(rec.rent_schedule_ids.mapped('paid_amount'))
            rec.total_rent_outstanding = sum(rec.rent_schedule_ids.mapped('balance_amount'))

    def action_activate(self):
        self.ensure_one()
        # Ensure schedule generation
        if not self.rent_schedule_ids:
            self.action_generate_rent_schedules()

        # Ensure deposit record is created if deposit specified
        if self.security_deposit > 0 and not self.security_deposit_ids:
            self.env['property.security.deposit'].create({
                'contract_id': self.id,
                'tenant_id': self.tenant_id.id,
                'property_id': self.property_id.id,
                'unit_id': self.unit_id.id,
                'amount': self.security_deposit,
                'company_id': self.company_id.id,
                'state': 'required',
            })

        self.write({'state': 'active'})
        # Mark unit as occupied
        if self.unit_id:
            self.unit_id.write({'status': 'occupied'})
        self.message_post(body=_('Tenant Contract %s activated. Unit marked as OCCUPIED.') % self.name)

    def action_terminate(self):
        self.ensure_one()
        self.write({'state': 'terminated'})
        # Mark unit available if no other active contract
        if self.unit_id:
            self.unit_id._compute_active_contract()
        self.message_post(body=_('Tenant Contract %s terminated.') % self.name)

    def action_cancel(self):
        self.ensure_one()
        self.rent_schedule_ids.filtered(lambda s: s.state in ('pending', 'overdue')).write({'state': 'cancelled'})
        self.write({'state': 'cancelled'})
        if self.unit_id:
            self.unit_id._compute_active_contract()
        self.message_post(body=_('Tenant Contract %s cancelled.') % self.name)

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_generate_rent_schedules(self):
        self.ensure_one()
        Schedule = self.env['property.rent.schedule']
        if not self.start_date or not self.end_date:
            raise UserError(_('Please configure start and end dates before generating rent schedules.'))

        delta_map = {
            'monthly': relativedelta(months=1),
            'quarterly': relativedelta(months=3),
            'semi_annual': relativedelta(months=6),
            'annual': relativedelta(years=1),
        }
        multiplier_map = {
            'monthly': 1,
            'quarterly': 3,
            'semi_annual': 6,
            'annual': 12,
        }

        step = delta_map.get(self.payment_frequency, relativedelta(months=1))
        months_mult = multiplier_map.get(self.payment_frequency, 1)
        installment_amount = self.monthly_rent * months_mult

        current_period_start = self.start_date
        created_count = 0

        while current_period_start < self.end_date:
            period_end = min(current_period_start + step - relativedelta(days=1), self.end_date)
            due_day = min(self.payment_due_day or 1, 28)
            due_date = current_period_start.replace(day=due_day)
            if due_date < current_period_start:
                due_date = current_period_start

            # Check if schedule already exists for this period
            existing = Schedule.search([
                ('contract_id', '=', self.id),
                ('period_start', '=', current_period_start),
            ], limit=1)

            if not existing:
                Schedule.create({
                    'contract_id': self.id,
                    'tenant_id': self.tenant_id.id,
                    'property_id': self.property_id.id,
                    'unit_id': self.unit_id.id,
                    'period_start': current_period_start,
                    'period_end': period_end,
                    'due_date': due_date,
                    'amount': installment_amount,
                    'company_id': self.company_id.id,
                    'state': 'pending',
                })
                created_count += 1

            current_period_start = current_period_start + step

        self.message_post(body=_('%d Tenant rent schedules generated.') % created_count)
        return True

    def action_view_rent_schedules(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('samruddhi_property_management.action_rent_schedule')
        action['domain'] = [('contract_id', '=', self.id)]
        action['context'] = {'default_contract_id': self.id, 'default_tenant_id': self.tenant_id.id}
        return action

    def action_view_deposits(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('samruddhi_property_management.action_security_deposit')
        action['domain'] = [('contract_id', '=', self.id)]
        action['context'] = {'default_contract_id': self.id, 'default_tenant_id': self.tenant_id.id}
        return action
