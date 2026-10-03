# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PropertySecurityDeposit(models.Model):
    _name = 'property.security.deposit'
    _description = 'Tenant Security Deposit (Liability / Escrow)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True
    _order = 'id desc'

    name = fields.Char(
        string='Deposit Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        index=True
    )
    tenant_id = fields.Many2one(
        'res.partner',
        string='Tenant',
        required=True,
        check_company=True,
        index=True,
        tracking=True
    )
    contract_id = fields.Many2one(
        'property.tenant.contract',
        string='Tenant Contract',
        required=True,
        ondelete='cascade',
        check_company=True,
        index=True,
        tracking=True
    )
    property_id = fields.Many2one(
        'property.property',
        string='Property',
        required=True,
        check_company=True,
        index=True
    )
    unit_id = fields.Many2one(
        'property.unit',
        string='Unit',
        required=True,
        check_company=True,
        index=True
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

    amount = fields.Monetary(
        string='Required Deposit Amount',
        required=True,
        currency_field='currency_id',
        tracking=True,
        help='Refundable security deposit amount. Kept in escrow/liability, NOT rental revenue.'
    )
    received_date = fields.Date(string='Date Received', tracking=True)
    adjustment_amount = fields.Monetary(
        string='Adjusted / Deducted Amount',
        default=0.0,
        currency_field='currency_id',
        tracking=True,
        help='Amount deducted for damages, arrears, or repairs.'
    )
    adjustment_reason = fields.Text(string='Adjustment Reason / Evidence')
    refund_amount = fields.Monetary(
        string='Refunded Amount',
        default=0.0,
        currency_field='currency_id',
        tracking=True
    )
    refund_date = fields.Date(string='Refund Date', tracking=True)

    outstanding_amount = fields.Monetary(
        string='Current Held Balance',
        compute='_compute_outstanding',
        store=True,
        currency_field='currency_id',
        help='Remaining deposit balance available to refund or adjust.'
    )

    state = fields.Selection([
        ('required', 'REQUIRED'),
        ('received', 'RECEIVED'),
        ('held', 'HELD IN ESCROW'),
        ('adjusted', 'ADJUSTED'),
        ('refunded', 'REFUNDED'),
    ], string='Status', default='required', required=True, tracking=True)

    _positive_deposit = models.Constraint('CHECK(amount >= 0)', 'Security deposit must be positive!')
    _positive_adj = models.Constraint('CHECK(adjustment_amount >= 0)', 'Adjustment cannot be negative!')
    _positive_refund = models.Constraint('CHECK(refund_amount >= 0)', 'Refund amount cannot be negative!')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('property.security.deposit') or _('New')
        return super().create(vals_list)

    @api.depends('amount', 'adjustment_amount', 'refund_amount', 'state')
    def _compute_outstanding(self):
        for rec in self:
            if rec.state in ('required',):
                rec.outstanding_amount = 0.0
            else:
                balance = rec.amount - (rec.adjustment_amount + rec.refund_amount)
                rec.outstanding_amount = max(0.0, balance)

    def action_receive_deposit(self):
        self.ensure_one()
        self.write({
            'state': 'held',
            'received_date': fields.Date.today(),
        })
        self.message_post(body=_('Security deposit of %s received and held in escrow.') % self.amount)

    def action_adjust_deposit(self, deduction, reason=''):
        self.ensure_one()
        if deduction <= 0:
            raise UserError(_('Adjustment amount must be positive.'))
        if deduction > self.outstanding_amount:
            raise UserError(_('Cannot deduct more than currently held balance (%s).') % self.outstanding_amount)
        self.write({
            'adjustment_amount': self.adjustment_amount + deduction,
            'adjustment_reason': (self.adjustment_reason or '') + '\n' + reason,
            'state': 'adjusted' if (self.outstanding_amount - deduction) <= 0 else 'held',
        })
        self.message_post(body=_('Adjusted %s from deposit. Reason: %s') % (deduction, reason))

    def action_refund_deposit(self):
        self.ensure_one()
        remaining = self.outstanding_amount
        if remaining <= 0:
            raise UserError(_('No remaining deposit balance available for refund.'))
        self.write({
            'refund_amount': self.refund_amount + remaining,
            'refund_date': fields.Date.today(),
            'state': 'refunded',
        })
        self.message_post(body=_('Refunded remaining deposit of %s to tenant.') % remaining)
