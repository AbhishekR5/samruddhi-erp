# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PropertyExpense(models.Model):
    _name = 'property.expense'
    _description = 'Property Operating Expense'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Expense Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        index=True
    )
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
        index=True
    )
    expense_category = fields.Selection([
        ('maintenance', 'Maintenance'),
        ('repair', 'Repair & Overhaul'),
        ('electricity', 'Electricity / Utility'),
        ('water', 'Water Charges'),
        ('cleaning', 'Cleaning & Housekeeping'),
        ('security', 'Security Services'),
        ('insurance', 'Property Insurance'),
        ('property_tax', 'Property Tax / Municipal Cess'),
        ('management', 'Management & Admin Fee'),
        ('other', 'Other Operational Expense'),
    ], string='Expense Category', default='maintenance', required=True, tracking=True)

    vendor_id = fields.Many2one(
        'res.partner',
        string='Vendor / Service Provider',
        check_company=True,
        tracking=True
    )
    date = fields.Date(string='Expense Date', required=True, default=fields.Date.today, tracking=True)

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
        string='Expense Amount',
        required=True,
        currency_field='currency_id',
        tracking=True
    )
    description = fields.Text(string='Description / Line Details')

    attachment_ids = fields.Many2many(
        'ir.attachment',
        'property_expense_attachment_rel',
        'expense_id',
        'attachment_id',
        string='Bills & Invoices'
    )

    payment_state = fields.Selection([
        ('draft', 'DRAFT'),
        ('submitted', 'SUBMITTED'),
        ('approved', 'APPROVED'),
        ('paid', 'PAID'),
        ('cancelled', 'CANCELLED'),
    ], string='Status', default='draft', required=True, tracking=True)

    move_id = fields.Many2one(
        'account.move',
        string='Accounting Bill',
        check_company=True,
        copy=False,
        help='Linked Vendor Bill in Odoo Accounting.'
    )

    _positive_expense = models.Constraint('CHECK(amount >= 0)', 'Expense amount must be positive!')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('property.expense') or _('New')
        return super().create(vals_list)

    def action_submit(self):
        self.write({'payment_state': 'submitted'})

    def action_approve(self):
        self.write({'payment_state': 'approved'})

    def action_pay(self):
        self.write({'payment_state': 'paid'})

    def action_cancel(self):
        self.write({'payment_state': 'cancelled'})

    def action_create_vendor_bill(self):
        """Creates vendor bill for this property expense."""
        self.ensure_one()
        if self.move_id:
            raise UserError(_('A vendor bill is already linked to this expense.'))
        if not self.vendor_id:
            raise UserError(_('Please assign a Vendor / Service Provider before generating a vendor bill.'))

        journal = self.env['account.journal'].search([
            ('type', '=', 'purchase'),
            ('company_id', '=', self.company_id.id)
        ], limit=1)

        if not journal:
            raise UserError(_('Please configure a Purchase Journal for company %s.') % self.company_id.name)

        unit_str = f" - Unit {self.unit_id.name}" if self.unit_id else ""
        move = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.vendor_id.id,
            'invoice_date': self.date,
            'journal_id': journal.id,
            'company_id': self.company_id.id,
            'currency_id': self.currency_id.id,
            'invoice_origin': self.name,
            'invoice_line_ids': [(0, 0, {
                'name': _('[%s] %s%s: %s') % (
                    dict(self._fields['expense_category'].selection).get(self.expense_category),
                    self.property_id.name,
                    unit_str,
                    self.description or ''
                ),
                'quantity': 1,
                'price_unit': self.amount,
            })],
        })
        self.write({'move_id': move.id, 'payment_state': 'approved'})
        self.message_post(body=_('Generated Accounting Vendor Bill %s.') % move.name)
        return {
            'name': _('Vendor Bill'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': move.id,
            'view_mode': 'form',
        }
