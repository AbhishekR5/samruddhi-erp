# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PropertyLandlordPayment(models.Model):
    _name = 'property.landlord.payment'
    _description = 'Landlord Payment Schedule (Samruddhi Payout)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True
    _order = 'due_date asc, id asc'

    name = fields.Char(
        string='Payment Ref',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        index=True
    )
    contract_id = fields.Many2one(
        'property.landlord.contract',
        string='Landlord Contract',
        required=True,
        ondelete='cascade',
        check_company=True,
        index=True,
        tracking=True
    )
    landlord_id = fields.Many2one(
        'res.partner',
        string='Landlord / Payee',
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
        string='Unit (Optional)',
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

    amount = fields.Monetary(string='Amount Payable', required=True, currency_field='currency_id', tracking=True)
    paid_amount = fields.Monetary(string='Disbursed Amount', default=0.0, currency_field='currency_id', tracking=True)
    balance_amount = fields.Monetary(
        string='Balance Payable',
        compute='_compute_balance',
        store=True,
        aggregator='sum',
        currency_field='currency_id'
    )
    payment_date = fields.Date(string='Disbursement Date')

    state = fields.Selection([
        ('pending', 'PENDING'),
        ('partial', 'PARTIALLY PAID'),
        ('paid', 'PAID'),
        ('overdue', 'OVERDUE'),
        ('cancelled', 'CANCELLED'),
    ], string='Status', compute='_compute_balance', store=True, readonly=False, tracking=True)

    move_id = fields.Many2one(
        'account.move',
        string='Vendor Bill',
        check_company=True,
        copy=False,
        help='Linked Odoo Vendor Bill for accounting payout.'
    )

    _positive_amount = models.Constraint('CHECK(amount >= 0)', 'Payment amount cannot be negative!')
    _positive_paid = models.Constraint('CHECK(paid_amount >= 0)', 'Disbursed amount cannot be negative!')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('property.landlord.payment') or _('New')
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
        self.message_post(body=_('Landlord payment %s marked as disbursed.') % self.name)

    def action_create_vendor_bill(self):
        """Creates an account.move vendor bill for this landlord payout."""
        self.ensure_one()
        if self.move_id:
            raise UserError(_('A vendor bill is already linked to this payment schedule.'))

        journal = self.env['account.journal'].search([
            ('type', '=', 'purchase'),
            ('company_id', '=', self.company_id.id)
        ], limit=1)

        if not journal:
            raise UserError(_('Please configure a Purchase Journal for company %s.') % self.company_id.name)

        unit_str = f" - Unit {self.unit_id.name}" if self.unit_id else ""
        move_vals = {
            'move_type': 'in_invoice',
            'partner_id': self.landlord_id.id,
            'invoice_date': self.due_date or fields.Date.today(),
            'journal_id': journal.id,
            'company_id': self.company_id.id,
            'currency_id': self.currency_id.id,
            'invoice_origin': self.contract_id.name,
            'invoice_line_ids': [(0, 0, {
                'name': _('Landlord rent for %s%s (%s to %s)') % (
                    self.property_id.name, unit_str, self.period_start, self.period_end
                ),
                'quantity': 1,
                'price_unit': self.amount,
            })],
        }
        move = self.env['account.move'].create(move_vals)
        self.write({'move_id': move.id})
        self.message_post(body=_('Created Landlord Vendor Bill %s.') % move.name)
        return {
            'name': _('Vendor Bill'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': move.id,
            'view_mode': 'form',
        }
