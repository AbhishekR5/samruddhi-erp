# Samruddhi Property Management ERP Module (Odoo 19)

A comprehensive, production-ready Property Management ERP system engineered for **Samruddhi** on **Odoo 19 Community & Enterprise**.

---

## 1. Core Architectural Tenet

The system strictly decouples **Property Control** from **Tenant Agreements**:

```
                       PROPERTY
                          │
             ┌────────────┴────────────┐
             │                         │
     PROPERTY CONTROL            PROPERTY UNIT
             │                         │
      ┌──────┴──────┐                  │
      │             │                  │
    OWNED       EXTERNAL               │
                LANDLORD               │
                   │                   │
          LANDLORD CONTRACT            │
                   │                   │
                   └─────────┬─────────┘
                             │
                      TENANT CONTRACT
                             │
                           TENANT
```

### Property Control Types:
1. **OWNED**: Samruddhi owns the property directly (no landlord contract required).
2. **RENTED FROM LANDLORD**: Samruddhi pays recurring rent to an external landlord via `property.landlord.contract`.
3. **LEASED FROM LANDLORD**: Long-term lease agreement with an external landlord.

### Tenant Agreement Types:
1. **RENT**: Monthly / recurring rent agreement to tenant.
2. **LEASE**: Long-term lease agreement to tenant.

Both dimensions are completely orthogonal and can be combined in any combination (e.g., Leased from Landlord -> Sub-leased to Tenant, Owned -> Rented to Tenant, Rented from Landlord -> Leased to Tenant).

---

## 2. Technical Stack & Odoo 19 Conventions

* **Odoo 19 Framework**: Fully compatible with Odoo 19.0 (September 2026 build).
* **Python 3.12**: Strict PEP 8 styling, batch operations, type annotations.
* **Modern Constraint Architecture**: Uses Odoo 19 `models.Constraint` checks and `@api.constrains` rather than deprecated `_sql_constraints` lists.
* **Modern Security Privileges**: Configured with `res.groups.privilege` and modern `group_ids` mappings.
* **PostgreSQL 16**: Relational integrity with clean cascading and check constraints.
* **QWeb Reports**: Native PDF reports with dynamic tables and formatting.
* **Odoo Chatter**: Full audit trails via `mail.thread` and `mail.activity.mixin` on all contracts, tickets, and properties.
* **Accounting Integration**: Hooks directly into `account.move` (Customer Invoices and Vendor Bills) without tight coupling.

---

## 3. Data Models Overview

| Model | Technical Name | Purpose |
|---|---|---|
| **Property** | `property.property` | Physical asset / building / land record with occupancy and financial metrics. |
| **Property Unit** | `property.unit` | Specific unit / apartment / commercial floor with status and area details. |
| **Partner Extension** | `res.partner` | Classified as `is_property_landlord` or `is_property_tenant` with PAN, GSTIN, and ledger metrics. |
| **Landlord Contract** | `property.landlord.contract` | Samruddhi $\leftarrow$ Landlord contract tracking payables, terms, and auto-schedules. |
| **Tenant Contract** | `property.tenant.contract` | Samruddhi $\rightarrow$ Tenant agreement with rent schedules, deposits, and conflict checks. |
| **Rent Schedule** | `property.rent.schedule` | Recurring tenant payment obligations, invoicing, and overdue tracking. |
| **Landlord Payment** | `property.landlord.payment` | Outbound disbursements to landlords with bill generation. |
| **Security Deposit** | `property.security.deposit` | Escrow liability tracking segregated strictly from rental revenue. |
| **Property Expense** | `property.expense` | Operational costs across 10 categories linked to properties and units. |
| **Maintenance Request** | `property.maintenance.request` | Tenant helpdesk tickets auto-generating expenses upon cost completion. |
| **Executive Dashboard** | `property.dashboard` | Performance indicators, occupancy rates, and monthly net income aggregations. |

---

## 4. Key Workflows

### 4.1 Tenant Onboarding & Booking Conflict Prevention
- Contracts require start/end dates and unit selection.
- Overlapping active tenant contracts on the same unit are blocked at the ORM level via `@api.constrains('unit_id', 'start_date', 'end_date', 'state')`.
- Activating a tenant contract automatically transitions the unit status to `OCCUPIED`.

### 4.2 Automated Recurring Schedule Generation
- Activating a contract automatically generates payment/rent schedules for the entire tenure (monthly, quarterly, bi-annually, annually).
- Prevents duplicate schedule generation.

### 4.3 Security Deposit Escrow Liability
- Deposits are classified under `REQUIRED`, `RECEIVED`, `HELD`, `ADJUSTED`, `REFUNDED`.
- Deposits are never booked as rental revenue, preserving balance-sheet integrity.

### 4.4 Maintenance to Expense Conversion
- Completing a maintenance request with incurred actual costs automatically creates a verified `property.expense` record linked to the unit.

### 4.5 Property Profitability Model
$$\text{Net Property Income} = \text{Tenant Revenue} - \text{Landlord Cost} - \text{Operational Expenses}$$

---

## 5. Security & Access Control

Four role-based tiers:
1. **Property Management / User**: Day-to-day operations, read-only financials.
2. **Property Management / Finance**: Invoicing, disbursements, security deposits, financial statements.
3. **Property Management / Manager**: Full operational approval, contracts, and assignments.
4. **Property Management / Administrator**: Full technical control and configuration.

### Multi-Company Isolation:
All models enforce `check_company=True` and record rules `[('company_id', 'in', company_ids)]`.

### Portal Isolation:
- **Landlords**: Exclusively view their own properties, units, contracts, and disbursement statements.
- **Tenants**: Exclusively view their own unit, agreement, rent dues, deposits, and can submit maintenance requests.

---

## 6. Automated Scheduled Actions (Cron)

1. **Contract Expiry Checker**: Daily cron identifying contracts expiring in 30 days and transitioning expired contracts.
2. **Overdue Rent Schedule Marker**: Daily cron scanning unpaid schedules past their due date and marking them `OVERDUE`.

---

## 7. Reports Included

1. **Property Summary Report** (`samruddhi_property_management.action_report_property`): Overview of units, occupancy, and tenant details.
2. **Landlord Statement** (`samruddhi_property_management.action_report_landlord_statement`): Consolidated ledger of payables and disbursements.
3. **Tenant Statement** (`samruddhi_property_management.action_report_tenant_statement`): Rent ledger, deposit status, and outstanding balances.
4. **Rental / Lease Agreement** (`samruddhi_property_management.action_report_tenant_contract`): Formal contractual legal document with parties, terms, and signature blocks.
5. **Property Economics & Profitability** (`samruddhi_property_management.action_report_property_profitability`): Financial breakdown of revenue vs costs.

---

## 8. Automated Test Suite

Run tests via Odoo CLI:
```bash
odoo -d <database_name> -u samruddhi_property_management --test-enable --test-tags=samruddhi_property_management --stop-after-init
```

Tests validate:
- Property control and landlord constraint rules
- Landlord contract creation and schedule disbursement
- Tenant contract activation, unit occupancy auto-update, and security deposit escrow
- Double-booking / contract overlap conflict rejection
- Property profitability net income calculations
- Maintenance ticket resolution and automatic expense generation
- Portal data isolation for Landlords and Tenants
- Multi-company record boundaries
