# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PropertyRentSchedule(models.Model):
    _name = 'property.rent.schedule'
    _description = 'Tenant Rent Payment Schedule'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True
    _order = 'due_date asc, id asc'

    name = fields.Char(
        string='Schedule Ref',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        index=True
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
    tenant_id = fields.Many2one(
        'res.partner',
        string='Tenant',
        required=True,
        check_company=True,
        index=True
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

    period_start = fields.Date(string='Period Start', required=True)
    period_end = fields.Date(string='Period End', required=True)
    due_date = fields.Date(string='Due Date', required=True, index=True, tracking=True)

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

    amount = fields.Monetary(string='Rent Due', required=True, currency_field='currency_id', tracking=True)
    paid_amount = fields.Monetary(string='Paid Amount', default=0.0, currency_field='currency_id', tracking=True)
    balance_amount = fields.Monetary(
        string='Balance Due',
        compute='_compute_balance',
        store=True,
        aggregator='sum',
        currency_field='currency_id'
    )
    payment_date = fields.Date(string='Payment Received Date')

    state = fields.Selection([
        ('pending', 'PENDING'),
        ('partial', 'PARTIALLY PAID'),
        ('paid', 'PAID'),
        ('overdue', 'OVERDUE'),
        ('cancelled', 'CANCELLED'),
    ], string='Status', compute='_compute_balance', store=True, readonly=False, tracking=True)

    move_id = fields.Many2one(
        'account.move',
        string='Customer Invoice',
        check_company=True,
        copy=False,
        help='Linked Odoo Customer Invoice for accounting reconciliation.'
    )

    _positive_amount = models.Constraint('CHECK(amount >= 0)', 'Rent amount cannot be negative!')
    _positive_paid = models.Constraint('CHECK(paid_amount >= 0)', 'Paid amount cannot be negative!')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('property.rent.schedule') or _('New')
        return super().create(vals_list)

    @api.depends('amount', 'paid_amount', 'due_date')
    def _compute_balance(self):
        today = fields.Date.today()
        for rec in self:
            balance = rec.amount - rec.paid_amount
            rec.balance_amount = max(0.0, balance)
            if rec.state == 'cancelled':
                continue
            if rec.amount > 0 and rec.balance_amount <= 0.0:
                rec.state = 'paid'
            elif rec.paid_amount > 0.0 and rec.balance_amount > 0.0:
                rec.state = 'partial'
            elif rec.due_date and rec.due_date < today and rec.balance_amount > 0.0:
                rec.state = 'overdue'
            else:
                rec.state = 'pending'

    def action_mark_paid(self):
        self.ensure_one()
        self.write({
            'paid_amount': self.amount,
            'balance_amount': 0.0,
            'payment_date': fields.Date.today(),
            'state': 'paid',
        })
        self.message_post(body=_('Rent schedule %s marked as fully paid.') % self.name)

    def action_record_payment(self, amount, pay_date=None):
        self.ensure_one()
        if amount <= 0:
            raise UserError(_('Payment amount must be greater than zero.'))
        new_paid = self.paid_amount + amount
        if new_paid > self.amount:
            raise UserError(_('Paid amount cannot exceed total schedule amount (%s).') % self.amount)
        self.write({
            'paid_amount': new_paid,
            'payment_date': pay_date or fields.Date.today(),
        })

    def action_create_invoice(self):
        """Creates an account.move customer invoice for this rent schedule."""
        self.ensure_one()
        if self.move_id:
            raise UserError(_('An invoice is already linked to this rent schedule.'))

        journal = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', self.company_id.id)
        ], limit=1)

        if not journal:
            raise UserError(_('Please configure a Sale Journal for company %s.') % self.company_id.name)

        move_vals = {
            'move_type': 'out_invoice',
            'partner_id': self.tenant_id.id,
            'invoice_date': self.due_date or fields.Date.today(),
            'journal_id': journal.id,
            'company_id': self.company_id.id,
            'currency_id': self.currency_id.id,
            'invoice_origin': self.contract_id.name,
            'invoice_line_ids': [(0, 0, {
                'name': _('Rent for %s (%s to %s)') % (self.unit_id.name, self.period_start, self.period_end),
                'quantity': 1,
                'price_unit': self.amount,
            })],
        }
        move = self.env['account.move'].create(move_vals)
        self.write({'move_id': move.id})
        self.message_post(body=_('Created Customer Invoice %s.') % move.name)
        return {
            'name': _('Customer Invoice'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': move.id,
            'view_mode': 'form',
        }
