# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PropertyLandlordContract(models.Model):
    _name = 'property.landlord.contract'
    _description = 'Landlord Contract (Landlord -> Samruddhi)'
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
    landlord_id = fields.Many2one(
        'res.partner',
        string='Landlord / Owner',
        required=True,
        domain="[('is_property_landlord', '=', True)]",
        check_company=True,
        tracking=True,
        index=True
    )
    property_id = fields.Many2one(
        'property.property',
        string='Property',
        required=True,
        domain="[('control_type', 'in', ['rented', 'leased'])]",
        check_company=True,
        tracking=True,
        index=True
    )
    unit_id = fields.Many2one(
        'property.unit',
        string='Covered Unit (Optional)',
        domain="[('property_id', '=', property_id)]",
        check_company=True,
        help='Leave empty if this contract covers the entire property.'
    )
    contract_type = fields.Selection([
        ('rent', 'RENT (Rent from Landlord)'),
        ('lease', 'LEASE (Lease from Landlord)'),
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

    monthly_amount = fields.Monetary(
        string='Monthly Amount Payable',
        required=True,
        currency_field='currency_id',
        tracking=True
    )
    security_deposit = fields.Monetary(
        string='Security Deposit Paid to Landlord',
        currency_field='currency_id'
    )
    payment_frequency = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('semi_annual', 'Semi-Annual'),
        ('annual', 'Annual'),
    ], string='Payment Frequency', default='monthly', required=True)

    payment_due_day = fields.Integer(string='Payment Due Day of Month', default=5)
    notice_period = fields.Integer(string='Notice Period (Days)', default=30)
    rent_escalation = fields.Float(string='Rent Escalation (%) per year', default=5.0)
    renewal_terms = fields.Text(string='Renewal Terms & Notes')

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
        'landlord_contract_attachment_rel',
        'contract_id',
        'attachment_id',
        string='Signed Contracts & Documents'
    )

    payment_ids = fields.One2many(
        'property.landlord.payment',
        'contract_id',
        string='Payment Schedules'
    )
    payment_count = fields.Integer(compute='_compute_payment_count')
    total_disbursed = fields.Monetary(
        string='Total Disbursed',
        compute='_compute_payment_summary',
        currency_field='currency_id'
    )
    total_payable_balance = fields.Monetary(
        string='Total Payable Balance',
        compute='_compute_payment_summary',
        currency_field='currency_id'
    )

    _due_day_valid = models.Constraint('CHECK(payment_due_day >= 1 AND payment_due_day <= 31)', 'Due day must be between 1 and 31!')
    _positive_monthly_amount = models.Constraint('CHECK(monthly_amount >= 0)', 'Monthly amount cannot be negative!')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('property.landlord.contract') or _('New')
        return super().create(vals_list)

    @api.constrains('start_date', 'end_date')
    def _check_contract_dates(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.start_date >= rec.end_date:
                raise ValidationError(_('Contract start date must be strictly before end date!'))

    @api.constrains('property_id')
    def _check_property_ownership(self):
        for rec in self:
            if rec.property_id.control_type == 'owned':
                raise ValidationError(_('Cannot create a Landlord Contract for an OWNED property (%s). Owned properties belong to Samruddhi.') % rec.property_id.name)

    def _compute_payment_count(self):
        for rec in self:
            rec.payment_count = len(rec.payment_ids)

    @api.depends('payment_ids.paid_amount', 'payment_ids.balance_amount')
    def _compute_payment_summary(self):
        for rec in self:
            rec.total_disbursed = sum(rec.payment_ids.mapped('paid_amount'))
            rec.total_payable_balance = sum(rec.payment_ids.mapped('balance_amount'))

    def action_activate(self):
        self.ensure_one()
        if not self.payment_ids:
            self.action_generate_payment_schedules()
        self.write({'state': 'active'})
        self.message_post(body=_('Landlord Contract %s activated successfully.') % self.name)

    def action_terminate(self):
        self.ensure_one()
        self.write({'state': 'terminated'})
        self.message_post(body=_('Landlord Contract %s terminated.') % self.name)

    def action_cancel(self):
        self.ensure_one()
        self.payment_ids.filtered(lambda p: p.state in ('pending', 'overdue')).write({'state': 'cancelled'})
        self.write({'state': 'cancelled'})
        self.message_post(body=_('Landlord Contract %s cancelled.') % self.name)

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_generate_payment_schedules(self):
        self.ensure_one()
        Payment = self.env['property.landlord.payment']
        if not self.start_date or not self.end_date:
            raise UserError(_('Please configure start and end dates before generating payment schedules.'))

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
        installment_amount = self.monthly_amount * months_mult

        current_period_start = self.start_date
        created_count = 0

        while current_period_start < self.end_date:
            period_end = min(current_period_start + step - relativedelta(days=1), self.end_date)
            # Due date calculation based on due_day
            due_day = min(self.payment_due_day or 5, 28)
            due_date = current_period_start.replace(day=due_day)
            if due_date < current_period_start:
                due_date = current_period_start

            # Check if schedule already exists for this period to prevent duplication
            existing = Payment.search([
                ('contract_id', '=', self.id),
                ('period_start', '=', current_period_start),
            ], limit=1)

            if not existing:
                Payment.create({
                    'contract_id': self.id,
                    'landlord_id': self.landlord_id.id,
                    'property_id': self.property_id.id,
                    'unit_id': self.unit_id.id if self.unit_id else False,
                    'period_start': current_period_start,
                    'period_end': period_end,
                    'due_date': due_date,
                    'amount': installment_amount,
                    'company_id': self.company_id.id,
                    'state': 'pending',
                })
                created_count += 1

            current_period_start = current_period_start + step

        self.message_post(body=_('%d Landlord payment schedules generated.') % created_count)
        return True

    def action_view_payments(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('samruddhi_property_management.action_landlord_payment')
        action['domain'] = [('contract_id', '=', self.id)]
        action['context'] = {'default_contract_id': self.id, 'default_landlord_id': self.landlord_id.id}
        return action
