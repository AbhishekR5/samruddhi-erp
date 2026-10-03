# -*- coding: utf-8 -*-
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError, UserError


@tagged('post_install', '-at_install', 'property_mgmt')
class TestPropertyLifecycle(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        # Create Landlord Partner
        cls.landlord = cls.env['res.partner'].create({
            'name': 'Landlord Test Sharma',
            'is_property_landlord': True,
            'pan_number': 'TESTP1234A',
        })

        # Create Tenant Partner
        cls.tenant = cls.env['res.partner'].create({
            'name': 'Tenant Test Verma',
            'is_property_tenant': True,
            'pan_number': 'TESTT5678B',
            'emergency_contact_phone': '+91 99999 88888',
        })

        # Create Owned Property
        cls.owned_property = cls.env['property.property'].create({
            'name': 'Samruddhi Residency (Owned)',
            'property_type': 'residential',
            'control_type': 'owned',
            'city': 'Mumbai',
            'total_area': 10000,
        })

        # Create Rentable Unit
        cls.unit_1 = cls.env['property.unit'].create({
            'name': 'Unit 101',
            'property_id': cls.owned_property.id,
            'floor': '1st Floor',
            'unit_type': 'apartment',
            'market_rent': 50000,
            'status': 'available',
        })

        # Create Rented Property from Landlord
        cls.rented_property = cls.env['property.property'].create({
            'name': 'Green Park (Rented from Landlord)',
            'property_type': 'residential',
            'control_type': 'rented',
            'landlord_id': cls.landlord.id,
            'city': 'Mumbai',
            'total_area': 5000,
        })
        cls.unit_rp = cls.env['property.unit'].create({
            'name': 'Flat G-1',
            'property_id': cls.rented_property.id,
            'market_rent': 35000,
            'status': 'available',
        })

    def test_01_property_control_constraints(self):
        """Test control type validation rules."""
        # Rented property without landlord should fail constraint
        with self.assertRaises(ValidationError):
            self.env['property.property'].create({
                'name': 'Invalid Rented Property',
                'property_type': 'commercial',
                'control_type': 'rented',
                'landlord_id': False,
            })

        # Cannot create Landlord Contract on Owned Property
        with self.assertRaises(ValidationError):
            self.env['property.landlord.contract'].create({
                'landlord_id': self.landlord.id,
                'property_id': self.owned_property.id,
                'contract_type': 'rent',
                'start_date': date(2026, 1, 1),
                'end_date': date(2026, 12, 31),
                'monthly_amount': 25000,
            })

    def test_02_landlord_contract_and_schedule_generation(self):
        """Test Landlord Contract lifecycle and automatic payout generation."""
        ll_contract = self.env['property.landlord.contract'].create({
            'landlord_id': self.landlord.id,
            'property_id': self.rented_property.id,
            'contract_type': 'rent',
            'start_date': date(2026, 10, 1),
            'end_date': date(2027, 3, 31),
            'monthly_amount': 30000,
            'payment_frequency': 'monthly',
            'payment_due_day': 5,
        })

        # Activate contract (should auto-generate schedules)
        ll_contract.action_activate()
        self.assertEqual(ll_contract.state, 'active')
        self.assertEqual(len(ll_contract.payment_ids), 6, "Expected 6 monthly payment schedules from Oct to Mar")

        # Test partial payment on first schedule
        sched1 = ll_contract.payment_ids[0]
        sched1.write({'paid_amount': 15000})
        self.assertEqual(sched1.state, 'partial')
        self.assertEqual(sched1.balance_amount, 15000)

        # Mark paid
        sched1.action_mark_paid()
        self.assertEqual(sched1.state, 'paid')
        self.assertEqual(sched1.balance_amount, 0)

    def test_03_tenant_contract_and_rent_schedules(self):
        """Test Tenant Contract activation, unit occupancy, and rent collection."""
        tenant_contract = self.env['property.tenant.contract'].create({
            'tenant_id': self.tenant.id,
            'property_id': self.owned_property.id,
            'unit_id': self.unit_1.id,
            'contract_type': 'rent',
            'start_date': date(2026, 10, 1),
            'end_date': date(2027, 9, 30),
            'monthly_rent': 55000,
            'security_deposit': 100000,
            'payment_frequency': 'monthly',
        })

        # Unit should initially be available
        self.assertEqual(self.unit_1.status, 'available')

        # Activate contract
        tenant_contract.action_activate()
        self.assertEqual(tenant_contract.state, 'active')
        self.assertEqual(self.unit_1.status, 'occupied', "Unit should be marked OCCUPIED once contract is active")
        self.assertEqual(len(tenant_contract.rent_schedule_ids), 12, "Expected 12 monthly rent schedules")

        # Check security deposit was created and segregated
        self.assertTrue(tenant_contract.security_deposit_ids)
        dep = tenant_contract.security_deposit_ids[0]
        self.assertEqual(dep.amount, 100000)
        self.assertEqual(dep.state, 'required')

        # Receive deposit into escrow
        dep.action_receive_deposit()
        self.assertEqual(dep.state, 'held')
        self.assertEqual(dep.outstanding_amount, 100000)

    def test_04_double_booking_conflict(self):
        """Ensure two active tenant contracts cannot overlap on the same unit."""
        # Contract 1: Oct 2026 to Sep 2027
        c1 = self.env['property.tenant.contract'].create({
            'tenant_id': self.tenant.id,
            'property_id': self.owned_property.id,
            'unit_id': self.unit_1.id,
            'contract_type': 'rent',
            'start_date': date(2026, 10, 1),
            'end_date': date(2027, 9, 30),
            'monthly_rent': 50000,
        })
        c1.action_activate()

        # Contract 2: Nov 2026 to Mar 2027 on SAME unit -> Must raise ValidationError
        with self.assertRaises(ValidationError):
            self.env['property.tenant.contract'].create({
                'tenant_id': self.tenant.id,
                'property_id': self.owned_property.id,
                'unit_id': self.unit_1.id,
                'contract_type': 'rent',
                'start_date': date(2026, 11, 1),
                'end_date': date(2027, 3, 31),
                'monthly_rent': 50000,
                'state': 'active',
            })

    def test_05_property_profitability_economics(self):
        """Validate Revenue - Landlord Cost - Expenses = Net Property Income."""
        # Property has tenant contract of 55,000 monthly
        c_tenant = self.env['property.tenant.contract'].create({
            'tenant_id': self.tenant.id,
            'property_id': self.rented_property.id,
            'unit_id': self.unit_rp.id,
            'contract_type': 'rent',
            'start_date': date(2026, 10, 1),
            'end_date': date(2027, 9, 30),
            'monthly_rent': 55000,
        })
        c_tenant.action_activate()

        # Landlord contract of 40,000 monthly
        c_landlord = self.env['property.landlord.contract'].create({
            'landlord_id': self.landlord.id,
            'property_id': self.rented_property.id,
            'contract_type': 'rent',
            'start_date': date(2026, 10, 1),
            'end_date': date(2027, 9, 30),
            'monthly_amount': 40000,
        })
        c_landlord.action_activate()

        # Recompute property metrics
        self.rented_property._compute_financial_metrics()
        self.assertEqual(self.rented_property.total_monthly_revenue, 55000.0)
        self.assertEqual(self.rented_property.total_monthly_cost, 40000.0)
        self.assertEqual(self.rented_property.monthly_net_income, 15000.0)

    def test_06_maintenance_ticket_auto_expense(self):
        """Test maintenance ticket workflow and auto-logging of incurred expense."""
        ticket = self.env['property.maintenance.request'].create({
            'title': 'Plumbing Repair in Unit 101',
            'property_id': self.owned_property.id,
            'unit_id': self.unit_1.id,
            'priority': '2',
            'estimated_cost': 2000,
            'actual_cost': 2500,
        })
        self.assertEqual(ticket.state, 'new')
        ticket.action_start()
        self.assertEqual(ticket.state, 'in_progress')
        ticket.action_complete()
        self.assertEqual(ticket.state, 'completed')

        # Check expense was created
        self.assertTrue(ticket.expense_id, "Expense record should be auto-created on ticket completion with actual cost")
        self.assertEqual(ticket.expense_id.amount, 2500.0)
        self.assertEqual(ticket.expense_id.expense_category, 'maintenance')
