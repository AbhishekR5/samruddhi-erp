# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    rent_schedule_ids = fields.One2many(
        'property.rent.schedule',
        'move_id',
        string='Rent Installments',
        readonly=True,
    )
    rent_schedule_count = fields.Integer(
        string='Rent Installment Count',
        compute='_compute_rent_schedule_count',
    )

    @api.depends('rent_schedule_ids')
    def _compute_rent_schedule_count(self):
        for rec in self:
            rec.rent_schedule_count = len(rec.rent_schedule_ids)

    def action_view_rent_schedules(self):
        self.ensure_one()
        schedules = self.rent_schedule_ids
        if len(schedules) == 1:
            return {
                'name': _('Rent Installment: %s') % schedules.name,
                'type': 'ir.actions.act_window',
                'res_model': 'property.rent.schedule',
                'res_id': schedules.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return {
            'name': _('Rent Installments'),
            'type': 'ir.actions.act_window',
            'res_model': 'property.rent.schedule',
            'domain': [('id', 'in', schedules.ids)],
            'view_mode': 'list,form',
            'target': 'current',
        }

    def _sync_rent_schedule_payments(self):
        """Auto sync payment to linked rent schedules when invoice payment status changes."""
        for move in self:
            for schedule in move.rent_schedule_ids:
                inv_paid = move.amount_total - move.amount_residual
                new_paid = min(schedule.amount, max(0.0, inv_paid))
                new_balance = max(0.0, schedule.amount - new_paid)
                vals = {
                    'paid_amount': new_paid,
                    'balance_amount': new_balance,
                }
                if move.payment_state in ('paid', 'in_payment') or new_balance <= 0.0:
                    vals['state'] = 'paid'
                    vals['payment_date'] = fields.Date.today()
                elif new_paid > 0.0:
                    vals['state'] = 'partial'
                schedule.write(vals)

    def _compute_payment_state(self):
        super()._compute_payment_state()
        self._sync_rent_schedule_payments()

    def _compute_amount(self):
        super()._compute_amount()
        self._sync_rent_schedule_payments()

    def write(self, vals):
        res = super().write(vals)
        if any(f in vals for f in ('payment_state', 'amount_residual', 'state')):
            self._sync_rent_schedule_payments()
        return res
