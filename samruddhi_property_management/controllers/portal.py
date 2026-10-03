# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


class PropertyCustomerPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id

        if 'landlord_contract_count' in counters:
            values['landlord_contract_count'] = request.env['property.landlord.contract'].search_count([
                ('landlord_id', '=', partner.id)
            ]) if partner.is_property_landlord else 0

        if 'landlord_payment_count' in counters:
            values['landlord_payment_count'] = request.env['property.landlord.payment'].search_count([
                ('landlord_id', '=', partner.id)
            ]) if partner.is_property_landlord else 0

        if 'tenant_contract_count' in counters:
            values['tenant_contract_count'] = request.env['property.tenant.contract'].search_count([
                ('tenant_id', '=', partner.id)
            ]) if partner.is_property_tenant else 0

        if 'rent_schedule_count' in counters:
            values['rent_schedule_count'] = request.env['property.rent.schedule'].search_count([
                ('tenant_id', '=', partner.id)
            ]) if partner.is_property_tenant else 0

        if 'maintenance_request_count' in counters:
            values['maintenance_request_count'] = request.env['property.maintenance.request'].search_count([
                ('tenant_id', '=', partner.id)
            ]) if partner.is_property_tenant else 0

        return values

    # ================= LANDLORD PORTAL =================
    @http.route(['/my/landlord_contracts'], type='http', auth='user', website=True)
    def portal_my_landlord_contracts(self, **kw):
        partner = request.env.user.partner_id
        contracts = request.env['property.landlord.contract'].search([('landlord_id', '=', partner.id)])
        return request.render('samruddhi_property_management.portal_my_landlord_contracts', {
            'contracts': contracts,
            'page_name': 'landlord_contracts',
        })

    @http.route(['/my/landlord_payments'], type='http', auth='user', website=True)
    def portal_my_landlord_payments(self, **kw):
        partner = request.env.user.partner_id
        payments = request.env['property.landlord.payment'].search([('landlord_id', '=', partner.id)])
        return request.render('samruddhi_property_management.portal_my_landlord_payments', {
            'payments': payments,
            'page_name': 'landlord_payments',
        })

    # ================= TENANT PORTAL =================
    @http.route(['/my/tenant_contracts'], type='http', auth='user', website=True)
    def portal_my_tenant_contracts(self, **kw):
        partner = request.env.user.partner_id
        contracts = request.env['property.tenant.contract'].search([('tenant_id', '=', partner.id)])
        return request.render('samruddhi_property_management.portal_my_tenant_contracts', {
            'contracts': contracts,
            'page_name': 'tenant_contracts',
        })

    @http.route(['/my/rent_schedules'], type='http', auth='user', website=True)
    def portal_my_rent_schedules(self, **kw):
        partner = request.env.user.partner_id
        schedules = request.env['property.rent.schedule'].search([('tenant_id', '=', partner.id)])
        return request.render('samruddhi_property_management.portal_my_rent_schedules', {
            'schedules': schedules,
            'page_name': 'rent_schedules',
        })

    @http.route(['/my/maintenance_requests'], type='http', auth='user', website=True)
    def portal_my_maintenance_requests(self, **kw):
        partner = request.env.user.partner_id
        tickets = request.env['property.maintenance.request'].search([('tenant_id', '=', partner.id)])
        return request.render('samruddhi_property_management.portal_my_maintenance_requests', {
            'tickets': tickets,
            'page_name': 'maintenance_requests',
        })

    @http.route(['/my/maintenance_requests/new'], type='http', auth='user', methods=['GET', 'POST'], website=True)
    def portal_create_maintenance_request(self, **post):
        partner = request.env.user.partner_id
        contracts = request.env['property.tenant.contract'].search([
            ('tenant_id', '=', partner.id),
            ('state', '=', 'active')
        ])

        if request.httprequest.method == 'POST':
            title = post.get('title')
            contract_id = int(post.get('contract_id', 0))
            description = post.get('description', '')
            priority = post.get('priority', '1')

            contract = contracts.filtered(lambda c: c.id == contract_id)
            if contract and title:
                request.env['property.maintenance.request'].create({
                    'title': title,
                    'tenant_id': partner.id,
                    'contract_id': contract.id,
                    'property_id': contract.property_id.id,
                    'unit_id': contract.unit_id.id,
                    'description': description,
                    'priority': priority,
                    'company_id': contract.company_id.id,
                })
                return request.redirect('/my/maintenance_requests')

        return request.render('samruddhi_property_management.portal_create_maintenance_request', {
            'contracts': contracts,
            'page_name': 'new_maintenance_request',
        })
