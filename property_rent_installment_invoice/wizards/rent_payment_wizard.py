# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PropertyRentPaymentWizard(models.TransientModel):
    _name = 'property.rent.payment.wizard'
    _description = 'Register or Update Rent Payment'

    schedule_id = fields.Many2one(
        'property.rent.schedule',
        string='Rent Schedule',
        required=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='schedule_id.currency_id',
        string='Currency',
        readonly=True,
    )
    total_amount = fields.Monetary(
        string='Total Rent Due',
        related='schedule_id.amount',
        readonly=True,
    )
    already_paid = fields.Monetary(
        string='Currently Paid',
        related='schedule_id.paid_amount',
        readonly=True,
    )
    remaining_balance = fields.Monetary(
        string='Remaining Balance',
        related='schedule_id.balance_amount',
        readonly=True,
    )
    payment_mode = fields.Selection([
        ('add_partial', 'Add Payment to Paid Amount (Partial/Installment)'),
        ('pay_full', 'Pay Full Remaining Balance'),
        ('set_total', 'Manually Override Total Paid to Date'),
    ], string='Payment Action', default='add_partial', required=True)

    payment_amount = fields.Monetary(
        string='Payment Amount',
        required=True,
        currency_field='currency_id',
    )
    payment_date = fields.Date(
        string='Payment Date',
        default=fields.Date.context_today,
        required=True,
    )
    payment_method = fields.Selection([
        ('bank', 'Bank Transfer / Wire'),
        ('cheque', 'Cheque / Demand Draft'),
        ('upi', 'UPI / Online Portal'),
        ('cash', 'Cash'),
        ('other', 'Other'),
    ], string='Payment Method', default='bank')

    payment_reference = fields.Char(
        string='Payment / Transaction Ref',
        help='Cheque Number, Bank UTR, UPI Reference, etc.'
    )
    note = fields.Text(string='Internal Notes')

    @api.onchange('payment_mode')
    def _onchange_payment_mode(self):
        if self.payment_mode == 'pay_full':
            self.payment_amount = self.remaining_balance
        elif self.payment_mode == 'set_total':
            self.payment_amount = self.already_paid
        else:
            self.payment_amount = self.remaining_balance

    def action_confirm_payment(self):
        self.ensure_one()
        schedule = self.schedule_id

        if self.payment_amount < 0:
            raise ValidationError(_('Payment amount cannot be negative.'))

        if self.payment_mode == 'add_partial':
            if self.payment_amount <= 0:
                raise ValidationError(_('Please enter a payment amount greater than zero.'))
            new_paid = schedule.paid_amount + self.payment_amount
        elif self.payment_mode == 'pay_full':
            new_paid = schedule.amount
        else:  # set_total
            new_paid = self.payment_amount

        if new_paid > schedule.amount:
            raise ValidationError(
                _('Total paid amount (%s) cannot exceed total rent due (%s).')
                % (new_paid, schedule.amount)
            )

        new_balance = max(0.0, schedule.amount - new_paid)

        # Determine status
        if new_balance <= 0.0 and schedule.amount > 0:
            new_state = 'paid'
        elif new_paid > 0.0:
            new_state = 'partial'
        else:
            today = fields.Date.today()
            new_state = 'overdue' if schedule.due_date and schedule.due_date < today else 'pending'

        schedule.write({
            'paid_amount': new_paid,
            'balance_amount': new_balance,
            'payment_date': self.payment_date,
            'state': new_state,
        })

        # Post audit note to chatter
        method_label = dict(self._fields['payment_method'].selection).get(self.payment_method, self.payment_method)
        ref_text = f" (Ref: {self.payment_reference})" if self.payment_reference else ""
        note_text = f"<br/>• Notes: {self.note}" if self.note else ""
        badge_color = 'success' if new_state == 'paid' else ('warning' if new_state == 'partial' else 'danger')

        schedule.message_post(body=_(
            '<b>Payment Recorded:</b><br/>'
            '• Payment Made: %(entered)s<br/>'
            '• Method: %(method)s%(ref)s<br/>'
            '• Date: %(pdate)s<br/>'
            '• Total Paid to Date: %(paid)s<br/>'
            '• <b>Remaining Rent Balance: %(balance)s</b><br/>'
            '• Status Updated: <span class="badge bg-%(badge)s">%(state)s</span>%(notes)s'
        ) % {
            'entered': f"{self.payment_amount:,.2f} {self.currency_id.symbol or ''}",
            'method': method_label,
            'ref': ref_text,
            'pdate': self.payment_date,
            'paid': f"{new_paid:,.2f} {self.currency_id.symbol or ''}",
            'balance': f"{new_balance:,.2f} {self.currency_id.symbol or ''}",
            'badge': badge_color,
            'state': new_state.upper(),
            'notes': note_text,
        })

        return {'type': 'ir.actions.act_window_close'}
