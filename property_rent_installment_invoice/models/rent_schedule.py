# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PropertyRentSchedule(models.Model):
    _inherit = 'property.rent.schedule'

    invoice_count = fields.Integer(
        string='Invoice Count',
        compute='_compute_invoice_info',
    )
    invoice_name = fields.Char(
        string='Invoice Ref',
        compute='_compute_invoice_info',
    )
    invoice_display_status = fields.Char(
        string='Invoice Status',
        compute='_compute_invoice_info',
    )
    invoice_payment_state = fields.Selection(
        related='move_id.payment_state',
        string='Invoice Payment State',
        readonly=True,
    )
    invoice_state = fields.Selection(
        related='move_id.state',
        string='Invoice State',
        readonly=True,
    )
    percent_paid = fields.Float(
        string='% Paid',
        compute='_compute_percent_paid',
    )

    @api.depends('move_id', 'move_id.name', 'move_id.payment_state', 'move_id.state')
    def _compute_invoice_info(self):
        for rec in self:
            rec.invoice_count = 1 if rec.move_id else 0
            if rec.move_id:
                rec.invoice_name = rec.move_id.name if rec.move_id.name != '/' else _('Draft Invoice')
                state_dict = dict(rec.move_id._fields['payment_state'].selection) if 'payment_state' in rec.move_id._fields else {}
                status_label = state_dict.get(rec.move_id.payment_state, rec.move_id.payment_state or rec.move_id.state)
                rec.invoice_display_status = f"{rec.invoice_name} ({status_label})"
            else:
                rec.invoice_name = False
                rec.invoice_display_status = False

    @api.depends('amount', 'paid_amount', 'due_date', 'move_id.payment_state', 'move_id.amount_residual', 'move_id.amount_total', 'move_id.state')
    def _compute_balance(self):
        today = fields.Date.today()
        for rec in self:
            # Sync directly with linked accounting invoice if present
            if rec.move_id:
                inv = rec.move_id
                inv_paid = inv.amount_total - inv.amount_residual
                if inv_paid > 0 or inv.payment_state in ('partial', 'paid', 'in_payment'):
                    rec.paid_amount = min(rec.amount, max(0.0, inv_paid))
                if inv.payment_state in ('paid', 'in_payment'):
                    rec.payment_date = rec.payment_date or fields.Date.today()

            balance = rec.amount - rec.paid_amount
            rec.balance_amount = max(0.0, balance)
            if rec.state == 'cancelled' or (rec.move_id and rec.move_id.state == 'cancel'):
                rec.state = 'cancelled'
                continue
            if rec.amount > 0 and rec.balance_amount <= 0.0:
                rec.state = 'paid'
            elif (rec.paid_amount > 0.0 and rec.balance_amount > 0.0) or (rec.move_id and rec.move_id.payment_state == 'partial'):
                rec.state = 'partial'
            elif rec.due_date and rec.due_date < today and rec.balance_amount > 0.0:
                rec.state = 'overdue'
            else:
                rec.state = 'pending'

    @api.depends('amount', 'paid_amount')
    def _compute_percent_paid(self):
        for rec in self:
            if rec.amount > 0:
                pct = (rec.paid_amount / rec.amount) * 100.0
                rec.percent_paid = round(min(100.0, max(0.0, pct)), 1)
            else:
                rec.percent_paid = 100.0 if rec.state == 'paid' else 0.0

    def action_view_invoice(self):
        self.ensure_one()
        if not self.move_id:
            raise UserError(_('No accounting invoice is currently linked to this rent installment.'))
        return {
            'name': _('Customer Invoice: %s') % (self.move_id.name or self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_payment_wizard(self):
        self.ensure_one()
        return {
            'name': _('Register / Update Rent Payment: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'property.rent.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_schedule_id': self.id,
                'default_payment_amount': self.balance_amount,
            },
        }

    def action_sync_from_invoice(self):
        """Syncs payment state and amounts from the linked account.move invoice."""
        self.ensure_one()
        if not self.move_id:
            raise UserError(_('No accounting invoice linked to sync.'))
        inv = self.move_id
        inv_paid = inv.amount_total - inv.amount_residual
        new_paid = min(self.amount, max(0.0, inv_paid))
        new_balance = max(0.0, self.amount - new_paid)

        vals = {
            'paid_amount': new_paid,
            'balance_amount': new_balance,
        }
        if inv.payment_state in ('paid', 'in_payment') or new_balance <= 0.0:
            vals['state'] = 'paid'
            vals['payment_date'] = fields.Date.today()
        elif new_paid > 0.0:
            vals['state'] = 'partial'
        elif inv.state == 'cancel':
            vals['state'] = 'cancelled'
        else:
            today = fields.Date.today()
            vals['state'] = 'overdue' if self.due_date and self.due_date < today else 'pending'

        self.write(vals)
        self.message_post(body=_(
            '<b>Payment Synchronized with Invoice %s:</b><br/>'
            '• Paid to Date: %s<br/>'
            '• Remaining Balance: %s<br/>'
            '• Status: %s'
        ) % (
            inv.name or 'Draft',
            f"{new_paid:,.2f} {self.currency_id.symbol or ''}",
            f"{new_balance:,.2f} {self.currency_id.symbol or ''}",
            vals.get('state', '').upper()
        ))
        return True
