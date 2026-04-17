# WeaveEstateHub - Test Credentials

## 🔐 Login Access

### Master Admin (Global Access)
```
Email:    master@estatehub.com
Password: Master1234@estatehub.com
Access:   Manage all societies, full system access
```

---

### Society Admin (Green Valley Society)
```
Email:    admin@greenvalley.com
Password: admin123
PIN:      123456
Access:   Complete Admin Portal (all 10 modules)

Modules Available:
✓ Dashboard - Real-time KPIs
✓ Cashbook - Financial ledger
✓ Receipts - Income management
✓ Expenses - Expenditure tracking
✓ Enroll - Add users (manual/CSV)
✓ Users - User directory
✓ Events - Announcements
✓ Evaluate Pass - QR validation
✓ Customize - Layout builder
✓ Settings - System configuration
```

---

### Apartment Owners

**Owner 1**:
```
Email:     rajesh.sharma@greenvalley.com
Password:  owner123
PIN:       1234
Apartment: A-101
Size:      1200 sq.ft
```

**Owner 2**:
```
Email:     priya.patel@greenvalley.com
Password:  owner123
PIN:       1234
Apartment: A-102
Size:      1500 sq.ft
```

**Owner 3**:
```
Email:     amit.singh@greenvalley.com
Password:  owner123
PIN:       1234
Apartment: B-201
Size:      1000 sq.ft
```

**Owner 4**:
```
Email:     sneha.reddy@greenvalley.com
Password:  owner123
PIN:       1234
Apartment: B-202
Size:      1350 sq.ft
```

**Owner 5**:
```
Email:     vikram.malhotra@greenvalley.com
Password:  owner123
PIN:       1234
Apartment: C-301
Size:      1800 sq.ft
```

---

### Vendors/Contractors

**Vendor 1 - Plumbing Services**:
```
Email:    plumbing.services@vendor.com
Password: vendor123
Service:  Plumber
Phone:    +91-9876543230
```

**Vendor 2 - AC Repair Co.**:
```
Email:    ac.repair.co.@vendor.com
Password: vendor123
Service:  Electrician
Phone:    +91-9876543231
```

**Vendor 3 - Green Cleaners**:
```
Email:    green.cleaners@vendor.com
Password: vendor123
Service:  Housekeeping
Phone:    +91-9876543232
```

---

### Security Staff

**Security 1 - Ravi Kumar**:
```
Email:    ravi.kumar@security.com
Password: security123
Shift:    Day (6am-6pm)
Salary:   ₹500/shift
Phone:    +91-9876543240
```

**Security 2 - Suresh Yadav**:
```
Email:    suresh.yadav@security.com
Password: security123
Shift:    Night (6pm-6am)
Salary:   ₹600/shift
Phone:    +91-9876543241
```

---

## 🌐 Application URLs

**Local Access**: http://localhost:8050/
**Public Access**: Check deployment URL from ApexWeave

---

## 📱 Login Process

### Step 1: Society Selection
1. Go to application URL
2. Select "Ram Raghu Ananda Resident Welfare" (or available society)
3. Click "Proceed to Login"

### Step 2: Authentication
Choose one of three methods:

**Method 1: Password**
- Enter email
- Select "Password" tab
- Enter password
- Click "Verify & Login"

**Method 2: PIN**
- Enter email
- Select "PIN" tab
- Use number pad to enter PIN
- Click "Verify & Login"

**Method 3: 9-Dot Pattern**
- Enter email
- Select "9-Dot Pattern" tab
- Draw pattern by clicking dots in sequence
- Click "Verify & Login"

---

## 🎯 Testing Checklist

### Authentication Tests
- [ ] Login with Master Admin credentials
- [ ] Login with Society Admin (password)
- [ ] Login with Society Admin (PIN)
- [ ] Login with Apartment Owner
- [ ] Login with Vendor
- [ ] Login with Security Staff
- [ ] Test logout functionality
- [ ] Test "Back to Society Selection"

### Admin Portal Module Tests
- [ ] Dashboard - View all KPI cards
- [ ] Cashbook - View transactions
- [ ] Receipts - Create and verify receipt
- [ ] Expenses - Record new expense
- [ ] Enroll - Add new user manually
- [ ] Users - Browse user directory
- [ ] Events - Create new event
- [ ] Evaluate Pass - Manual evaluation
- [ ] Customize - Select role and page
- [ ] Settings - Update global settings

### UI/UX Tests
- [ ] Header displays correctly with logo
- [ ] Sidebar shows role-specific tabs
- [ ] Breadcrumb navigation works
- [ ] User avatar popover shows QR code
- [ ] Color scheme matches role
- [ ] Tables display data correctly
- [ ] Forms accept input
- [ ] Buttons are responsive

---

## 🐛 Reporting Issues

If you encounter any issues during testing:

1. **Check Logs**:
   ```bash
   tail -f /var/log/supervisor/weaveestatehub.out.log
   tail -f /var/log/supervisor/weaveestatehub.err.log
   ```

2. **Restart Application**:
   ```bash
   supervisorctl restart weaveestatehub
   ```

3. **Verify Database**:
   - Check NeonDB connection in `/app/.env`
   - Ensure all tables exist
   - Verify sample data was seeded

---

## 📊 Sample Data

**Society**: 1 society (Ram Raghu Ananda Resident Welfare)
**Users**: 11 users (1 admin, 5 owners, 3 vendors, 2 security)
**Apartments**: 5 apartments
**Vendors**: 3 vendors
**Security**: 2 security staff
**Accounts**: 5 financial accounts

---

**Last Updated**: 2025
**Version**: 1.0.0
