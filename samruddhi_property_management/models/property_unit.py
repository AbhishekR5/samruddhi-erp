# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PropertyUnit(models.Model):
    _name = 'property.unit'
    _description = 'Rentable Property Unit'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True
    _order = 'property_id, name, id'

    name = fields.Char(string='Unit Number / Name', required=True, tracking=True)
    unit_code = fields.Char(
        string='Unit Code',
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
        ondelete='cascade',
        check_company=True,
        index=True,
        tracking=True
    )
    company_id = fields.Many2one(
        'res.company',
        related='property_id.company_id',
        string='Company',
        store=True,
        index=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string='Currency',
        readonly=True
    )

    floor = fields.Char(string='Floor / Level', default='Ground Floor')
    unit_type = fields.Selection([
        ('apartment', 'Apartment / Flat'),
        ('studio', 'Studio Apartment'),
        ('penthouse', 'Penthouse'),
        ('shop', 'Retail Shop'),
        ('office', 'Commercial Office'),
        ('villa', 'Villa / Row House'),
        ('warehouse', 'Warehouse / Storage'),
        ('room', 'Single Room'),
        ('other', 'Other'),
    ], string='Unit Type', default='apartment', required=True)

    area = fields.Float(string='Carpet Area (sq. ft.)', tracking=True)
    bedrooms = fields.Integer(string='Bedrooms (BHK)', default=1)
    bathrooms = fields.Integer(string='Bathrooms', default=1)
    furnishing = fields.Selection([
        ('unfurnished', 'Unfurnished'),
        ('semi_furnished', 'Semi-Furnished'),
        ('fully_furnished', 'Fully Furnished'),
    ], string='Furnishing Status', default='unfurnished')

    market_rent = fields.Monetary(
        string='Market Monthly Rent',
        currency_field='currency_id',
        tracking=True,
        help='Estimated or standard asking rent per month for this unit.'
    )

    status = fields.Selection([
        ('available', 'AVAILABLE'),
        ('reserved', 'RESERVED'),
        ('occupied', 'OCCUPIED'),
        ('maintenance', 'MAINTENANCE'),
        ('inactive', 'INACTIVE'),
    ], string='Unit Status', default='available', required=True, tracking=True)

    description = fields.Html(string='Unit Description / Amenities')
    active = fields.Boolean(string='Active', default=True)

    # Relational Links
    tenant_contract_ids = fields.One2many(
        'property.tenant.contract',
        'unit_id',
        string='Tenant Contracts'
    )
    active_contract_id = fields.Many2one(
        'property.tenant.contract',
        string='Current Active Contract',
        compute='_compute_active_contract',
        store=True
    )
    current_tenant_id = fields.Many2one(
        'res.partner',
        string='Current Tenant',
        related='active_contract_id.tenant_id',
        store=True
    )
    maintenance_ids = fields.One2many(
        'property.maintenance.request',
        'unit_id',
        string='Maintenance Requests'
    )
    rent_schedule_ids = fields.One2many(
        'property.rent.schedule',
        'unit_id',
        string='Rent Schedules'
    )

    _code_company_unique = models.Constraint('UNIQUE(unit_code, company_id)', 'Unit code must be unique per company!')
    _positive_unit_area = models.Constraint('CHECK(area >= 0)', 'Area must be non-negative!')
    _positive_market_rent = models.Constraint('CHECK(market_rent >= 0)', 'Market rent must be non-negative!')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('unit_code', _('New')) == _('New'):
                vals['unit_code'] = self.env['ir.sequence'].next_by_code('property.unit') or _('New')
        return super().create(vals_list)

    @api.depends('tenant_contract_ids.state', 'tenant_contract_ids.start_date', 'tenant_contract_ids.end_date')
    def _compute_active_contract(self):
        today = fields.Date.today()
        for unit in self:
            # Active contracts currently in effect
            active_contracts = unit.tenant_contract_ids.filtered(
                lambda c: c.state == 'active' and c.start_date <= today and (not c.end_date or c.end_date >= today)
            )
            unit.active_contract_id = active_contracts[:1].id if active_contracts else False
            # Update unit status accordingly if not in maintenance or inactive
            if unit.status not in ('maintenance', 'inactive'):
                if unit.active_contract_id:
                    unit.status = 'occupied'
                elif any(c.state == 'draft' for c in unit.tenant_contract_ids):
                    unit.status = 'reserved'
                else:
                    unit.status = 'available'

    def action_set_available(self):
        self.write({'status': 'available'})

    def action_set_maintenance(self):
        self.write({'status': 'maintenance'})

    def action_view_tenant_contracts(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('samruddhi_property_management.action_tenant_contract')
        action['domain'] = [('unit_id', '=', self.id)]
        action['context'] = {'default_unit_id': self.id, 'default_property_id': self.property_id.id}
        return action
