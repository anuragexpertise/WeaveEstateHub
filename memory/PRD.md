# WeaveEstateHub - PRD (Product Requirements Document)

## Original Problem Statement
Create a Dash/Flask webApp 'WeaveEstateHub' - ERP SaaS Application for estate management.
- Schema from weaveestatehub.sql, hosted on ApexWeave with NeonDB database
- Push+ JWT combined authentication, 2-staged login
- Primary Login = Society selection dropdown
- Secondary Login = Society-specific login (Password/PIN/9-dot pattern)
- Master admin: master@estatehub.com for Add/Update/Delete Societies
- 4 user roles: admin, owners, vendors, security
- Layout: header, sidebar, breadcrumb, footer
- Role-based color scheme

## Architecture
- **Frontend/Backend**: Dash (Plotly) + Flask (single process)
- **Database**: NeonDB PostgreSQL (12+ tables)
- **Auth**: werkzeug password hashing + JWT tokens
- **Session**: dcc.Store (session storage)
- **Port**: 8050 (supervisor managed)
- **File Storage**: /app/uploads/

## User Personas
1. **Admin** - Society administrator managing finances, users, events
2. **Apartment Owner** - Resident viewing charges, payments, QR pass
3. **Vendor/Contractor** - Service provider managing pass fees, payments
4. **Security Staff** - Gate security evaluating passes, logging attendance

## Core Requirements (Static)
- Two-stage login (society selection → password/PIN/pattern)
- Master admin access when no societies exist
- Network error handling with retry
- Role-based portals with color-coded headers
- QR code generation per user for gate access
- Financial ledger (cashbook) per society
- Maintenance charge calculation based on apartment size
- Fine/late fee management
- Attendance tracking for security staff

## What's Been Implemented (Jan 2026)

### Phase 1: Foundation ✅
- NeonDB connection with connection pooling
- Database schema (12+ tables with indexes)
- Seed data (1 society, 11 users, 5 apartments, 3 vendors, 2 security)
- Supervisor deployment on port 8050

### Phase 2: Admin Portal (10 modules) ✅
1. Dashboard - KPIs for apartments, vendors, security, financials
2. Cashbook - Double-entry financial ledger
3. Receipts - Create and verify income transactions
4. Expenses - Record and track expenditures
5. Enroll - Manual + CSV import user enrollment
6. Users - User directory with role badges
7. Events - Create and manage announcements
8. Evaluate Pass - Manual entity evaluation with PASS/FAIL
9. Customize - Layout customization interface
10. Settings - 4 tabs (Global, Admin, Accounts, Personnel)

### Phase 3: Owner Portal (6 modules) ✅
1. Dashboard - Profile, QR pass, financial summary
2. Cashbook - Charges & payment history with running balance
3. Payments - Payment history table
4. Charges - Maintenance charges and fines
5. Events - View announcements
6. Settings - Personal settings, change password

### Phase 4: Vendor Portal (6 modules) ✅
1. Dashboard - Service info, QR pass, financial summary
2. Cashbook - Pass charges, fines, payments
3. Payments - Pass purchase history
4. Charges - Pass fees and fines (1-Day, 7-Day, 1-Month)
5. Events - View announcements
6. Settings - Personal settings, change password

### Phase 5: Security Portal (6 modules) ✅
1. Pass Evaluation - QR scanner + manual evaluation with PASS/FAIL
2. Attendance - Clock In/Out with shift info and attendance log
3. Events - View announcements
4. New Receipt - Create receipts for on-demand entry payments
5. Users - KPI overview (apartments, vendors, security, payments)
6. Settings - Personal settings, change password

## Testing Results (Iteration 1)
- Backend: 100% pass
- Frontend: 95% pass (minor Dash session reload behavior)
- All 4 portals: PASS
- All 28+ modules: PASS
- All role-specific routing: PASS
- Header colors and labels: PASS

## Prioritized Backlog

### P0 (Critical)
- [x] All 4 portals implemented
- [x] Two-stage login with 3 auth methods
- [x] Role-based routing

### P1 (Important - Next Phase)
- [ ] Events table in database (currently placeholder)
- [ ] CSV import processing logic
- [ ] File upload handling (logo, background images)
- [ ] QR camera scanning (currently manual only)
- [ ] Maintenance charge automation (auto-generate monthly)
- [ ] Fine auto-calculation based on due date

### P2 (Nice to Have)
- [ ] Drag-drop customization for dashboards
- [ ] Email notifications for events/dues
- [ ] Report generation (PDF/Excel)
- [ ] Mobile-responsive layout optimization
- [ ] Advanced analytics with charts
- [ ] Multi-society management for master admin
- [ ] Audit trail/logging

## Next Tasks List
1. Add events table to database schema
2. Implement CSV bulk enrollment processing
3. Implement file upload endpoints (logo, background)
4. Add maintenance auto-charge scheduling
5. Implement QR camera scanning with JavaScript bridge
6. Build master admin society CRUD page
