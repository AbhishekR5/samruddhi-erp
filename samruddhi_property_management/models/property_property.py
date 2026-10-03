# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PropertyProperty(models.Model):
    _name = 'property.property'
    _description = 'Managed Real Estate Property'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True
    _order = 'name, id'

    name = fields.Char(string='Property Name', required=True, tracking=True)
    code = fields.Char(
        string='Property Code',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        index=True
    )
    property_type = fields.Selection([
        ('apartment_building', 'Apartment Building'),
        ('residential', 'Residential Complex'),
        ('commercial', 'Commercial Complex'),
        ('villa', 'Villa / Bungalow'),
        ('house', 'Independent House'),
        ('office', 'Office Complex'),
        ('shop', 'Retail / Shop Space'),
        ('warehouse', 'Warehouse / Industrial'),
        ('land', 'Plot / Land'),
        ('other', 'Other'),
    ], string='Property Type', default='apartment_building', required=True, tracking=True)

    control_type = fields.Selection([
        ('owned', 'OWNED (Samruddhi Owned)'),
        ('rented', 'RENTED FROM LANDLORD'),
        ('leased', 'LEASED FROM LANDLORD'),
    ], string='Control Type', default='owned', required=True, tracking=True,
       help='Defines how Samruddhi acquires control of the property.')

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

    landlord_id = fields.Many2one(
        'res.partner',
        string='Landlord / Owner',
        domain="[('is_property_landlord', '=', True)]",
        tracking=True,
        help='External landlord who owns the property if rented or leased by Samruddhi.'
    )

    # Address Details
    street = fields.Char(string='Street')
    street2 = fields.Char(string='Street 2')
    city = fields.Char(string='City')
    state_id = fields.Many2one('res.country.state', string='State', domain="[('country_id', '=?', country_id)]")
    country_id = fields.Many2one('res.country', string='Country', default=lambda self: self.env.company.country_id)
    zip = fields.Char(string='Postal / PIN Code')
    latitude = fields.Float(string='Latitude', digits=(10, 7))
    longitude = fields.Float(string='Longitude', digits=(10, 7))
    map_embed_html = fields.Html(
        string='Map View',
        compute='_compute_map_embed_html',
        sanitize=False
    )

    total_area = fields.Float(string='Total Area (sq. ft.)', tracking=True)
    number_of_floors = fields.Integer(string='Number of Floors', default=1)
    description = fields.Html(string='Description')

    status = fields.Selection([
        ('draft', 'Draft'),
        ('available', 'Available'),
        ('occupied', 'Fully Occupied'),
        ('maintenance', 'Under Maintenance'),
        ('inactive', 'Inactive'),
    ], string='Status', default='draft', required=True, tracking=True)
    active = fields.Boolean(string='Active', default=True)

    # Relational Fields
    unit_ids = fields.One2many('property.unit', 'property_id', string='Rentable Units')
    landlord_contract_ids = fields.One2many('property.landlord.contract', 'property_id', string='Landlord Contracts')
    tenant_contract_ids = fields.One2many('property.tenant.contract', 'property_id', string='Tenant Contracts')
    maintenance_ids = fields.One2many('property.maintenance.request', 'property_id', string='Maintenance Requests')
    expense_ids = fields.One2many('property.expense', 'property_id', string='Operating Expenses')

    # Computed Counts and Financials
    total_units_count = fields.Integer(string='Total Units', compute='_compute_unit_metrics', store=True, aggregator='sum')
    occupied_units_count = fields.Integer(string='Occupied Units', compute='_compute_unit_metrics', store=True, aggregator='sum')
    vacant_units_count = fields.Integer(string='Vacant Units', compute='_compute_unit_metrics', store=True, aggregator='sum')
    occupancy_rate = fields.Float(string='Occupancy Rate (%)', compute='_compute_unit_metrics', store=True, aggregator='avg')

    total_monthly_revenue = fields.Monetary(
        string='Monthly Tenant Revenue',
        compute='_compute_financial_metrics',
        store=True,
        aggregator='sum',
        currency_field='currency_id'
    )
    total_monthly_cost = fields.Monetary(
        string='Monthly Landlord Cost',
        compute='_compute_financial_metrics',
        store=True,
        aggregator='sum',
        currency_field='currency_id'
    )
    monthly_net_income = fields.Monetary(
        string='Monthly Net Income',
        compute='_compute_financial_metrics',
        store=True,
        aggregator='sum',
        currency_field='currency_id'
    )

    landlord_contract_count = fields.Integer(compute='_compute_counts')
    tenant_contract_count = fields.Integer(compute='_compute_counts')
    maintenance_count = fields.Integer(compute='_compute_counts')
    expense_count = fields.Integer(compute='_compute_counts')

    _code_company_unique = models.Constraint('UNIQUE(code, company_id)', 'Property code must be unique per company!')
    _positive_area = models.Constraint('CHECK(total_area >= 0)', 'Total area must be non-negative!')
    _positive_floors = models.Constraint('CHECK(number_of_floors >= 0)', 'Number of floors must be non-negative!')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', _('New')) == _('New'):
                vals['code'] = self.env['ir.sequence'].next_by_code('property.property') or _('New')
        return super().create(vals_list)

    @api.constrains('control_type', 'landlord_id')
    def _check_control_and_landlord(self):
        for record in self:
            if record.control_type in ('rented', 'leased') and not record.landlord_id:
                raise ValidationError(_('A Landlord must be specified for properties that are Rented or Leased from a landlord.'))
            if record.control_type == 'owned' and record.landlord_id:
                # Owned property belongs to Samruddhi; clear or forbid external landlord confusion
                pass

    @api.depends('unit_ids', 'unit_ids.status')
    def _compute_unit_metrics(self):
        for prop in self:
            total = len(prop.unit_ids)
            occupied = len(prop.unit_ids.filtered(lambda u: u.status == 'occupied'))
            vacant = len(prop.unit_ids.filtered(lambda u: u.status == 'available'))
            prop.total_units_count = total
            prop.occupied_units_count = occupied
            prop.vacant_units_count = vacant
            prop.occupancy_rate = (occupied / total * 100.0) if total > 0 else 0.0

    @api.depends('tenant_contract_ids.monthly_rent', 'tenant_contract_ids.state',
                 'landlord_contract_ids.monthly_amount', 'landlord_contract_ids.state')
    def _compute_financial_metrics(self):
        for prop in self:
            active_tenant_contracts = prop.tenant_contract_ids.filtered(lambda c: c.state == 'active')
            active_landlord_contracts = prop.landlord_contract_ids.filtered(lambda c: c.state == 'active')

            revenue = sum(active_tenant_contracts.mapped('monthly_rent'))
            cost = sum(active_landlord_contracts.mapped('monthly_amount'))
            prop.total_monthly_revenue = revenue
            prop.total_monthly_cost = cost
            prop.monthly_net_income = revenue - cost

    def _compute_counts(self):
        for prop in self:
            prop.landlord_contract_count = len(prop.landlord_contract_ids)
            prop.tenant_contract_count = len(prop.tenant_contract_ids)
            prop.maintenance_count = len(prop.maintenance_ids)
            prop.expense_count = len(prop.expense_ids)

    # Action methods for smart buttons
    def action_view_units(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('samruddhi_property_management.action_property_unit')
        action['domain'] = [('property_id', '=', self.id)]
        action['context'] = {'default_property_id': self.id}
        return action

    def action_view_landlord_contracts(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('samruddhi_property_management.action_landlord_contract')
        action['domain'] = [('property_id', '=', self.id)]
        action['context'] = {'default_property_id': self.id}
        return action

    def action_view_tenant_contracts(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('samruddhi_property_management.action_tenant_contract')
        action['domain'] = [('property_id', '=', self.id)]
        action['context'] = {'default_property_id': self.id}
        return action

    def action_view_maintenance(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('samruddhi_property_management.action_maintenance_request')
        action['domain'] = [('property_id', '=', self.id)]
        action['context'] = {'default_property_id': self.id}
        return action

    def action_view_expenses(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('samruddhi_property_management.action_property_expense')
        action['domain'] = [('property_id', '=', self.id)]
        action['context'] = {'default_property_id': self.id}
        return action

    @api.depends('name', 'street', 'street2', 'city', 'state_id', 'zip', 'country_id', 'latitude', 'longitude')
    def _compute_map_embed_html(self):
        import urllib.parse
        for rec in self:
            query = ""
            if rec.latitude and rec.longitude:
                query = f"{rec.latitude},{rec.longitude}"
            else:
                addr_parts = [
                    rec.street,
                    rec.street2,
                    rec.city,
                    rec.state_id.name if rec.state_id else '',
                    rec.zip,
                    rec.country_id.name if rec.country_id else ''
                ]
                query = ", ".join([p for p in addr_parts if p])
                if not query and rec.name:
                    query = rec.name

            if query:
                encoded_query = urllib.parse.quote(query)
                map_url = f"https://maps.google.com/maps?q={encoded_query}&amp;t=&amp;z=15&amp;ie=UTF8&amp;iwloc=&amp;output=embed"
                rec.map_embed_html = f'''
                    <div style="width: 100%; height: 180px; margin-top: 10px; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,0.1); border: 1px solid #ced4da;">
                        <iframe width="100%" height="180" frameborder="0" scrolling="no" marginheight="0" marginwidth="0" src="{map_url}" style="border:0; display:block;" loading="lazy"></iframe>
                    </div>
                '''
            else:
                rec.map_embed_html = '''
                    <div class="alert alert-light text-muted d-flex align-items-center justify-content-center" style="height: 180px; width: 100%; margin-top: 10px; border: 1px dashed #ced4da; border-radius: 8px;">
                        <span><i class="fa fa-map-marker text-secondary me-2"></i> Enter property address to display map</span>
                    </div>
                '''

    def action_open_map(self):
        self.ensure_one()
        addr_parts = [
            self.street,
            self.street2,
            self.city,
            self.state_id.name if self.state_id else '',
            self.zip,
            self.country_id.name if self.country_id else ''
        ]
        query = ", ".join([p for p in addr_parts if p]) or self.name or ''
        import urllib.parse
        url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(query)}"
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }
