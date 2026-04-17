#!/usr/bin/env python3
"""
Seed data script for WeaveEstateHub
Creates sample society, users, and accounts for testing
"""
import os
import psycopg2
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv
from datetime import date, datetime, timedelta

load_dotenv()

def seed_database():
    """Add seed data to database"""
    try:
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        cur = conn.cursor()
        
        print("🌱 Seeding WeaveEstateHub database...\n")
        
        # Check if society already exists
        cur.execute("SELECT COUNT(*) FROM societies")
        soc_count = cur.fetchone()[0]
        
        if soc_count == 0:
            # Insert sample society
            cur.execute("""
                INSERT INTO societies (name, address, email, phone, secretary_name, secretary_phone, 
                                     plan, plan_validity, arrear_start_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                'Green Valley Society',
                '123 Main Street, Bangalore, Karnataka - 560001',
                'admin@greenvalley.com',
                '+91-9876543210',
                'Mr. Ramesh Kumar',
                '+91-9876543211',
                'Paid',
                date.today() + timedelta(days=365),
                date.today()
            ))
            society_id = cur.fetchone()[0]
            print(f"✅ Created society: Green Valley Society (ID: {society_id})")
        else:
            # Get existing society
            cur.execute("SELECT id, name FROM societies LIMIT 1")
            society_id, soc_name = cur.fetchone()
            print(f"ℹ️  Using existing society: {soc_name} (ID: {society_id})")
        
        # Create admin user
        cur.execute("SELECT COUNT(*) FROM users WHERE society_id = %s AND role = 'admin'", (society_id,))
        admin_count = cur.fetchone()[0]
        
        if admin_count == 0:
            admin_pwd = generate_password_hash("admin123")
            admin_pin = generate_password_hash("123456")
            
            cur.execute("""
                INSERT INTO users (society_id, email, password_hash, pin_hash, role, login_method)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (society_id, 'admin@greenvalley.com', admin_pwd, admin_pin, 'admin', 'password'))
            admin_id = cur.fetchone()[0]
            print(f"✅ Created admin user: admin@greenvalley.com (password: admin123, PIN: 123456)")
        
        # Create sample apartments
        cur.execute("SELECT COUNT(*) FROM apartments WHERE society_id = %s", (society_id,))
        apt_count = cur.fetchone()[0]
        
        if apt_count < 5:
            apartments = [
                ('A-101', 'Rajesh Sharma', '+91-9876543220', 1200, True),
                ('A-102', 'Priya Patel', '+91-9876543221', 1500, True),
                ('B-201', 'Amit Singh', '+91-9876543222', 1000, True),
                ('B-202', 'Sneha Reddy', '+91-9876543223', 1350, True),
                ('C-301', 'Vikram Malhotra', '+91-9876543224', 1800, True)
            ]
            
            for flat, owner, mobile, size, active in apartments:
                cur.execute("""
                    INSERT INTO apartments (society_id, flat_number, owner_name, mobile, apartment_size, active)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (society_id, flat, owner, mobile, size, active))
                apt_id = cur.fetchone()[0]
                
                # Create user for apartment owner
                email = f"{owner.lower().replace(' ', '.')}@greenvalley.com"
                pwd_hash = generate_password_hash("owner123")
                pin_hash = generate_password_hash("1234")
                
                cur.execute("""
                    INSERT INTO users (society_id, email, password_hash, pin_hash, role, linked_id, login_method)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (society_id, email, pwd_hash, pin_hash, 'apartment', apt_id, 'password'))
                
                print(f"✅ Created apartment: {flat} - {owner} (Email: {email})")
        
        # Create sample vendors
        cur.execute("SELECT COUNT(*) FROM vendors WHERE society_id = %s", (society_id,))
        ven_count = cur.fetchone()[0]
        
        if ven_count < 3:
            vendors = [
                ('Plumbing Services', 'Plumber', '+91-9876543230', 'General plumbing and repairs', True),
                ('AC Repair Co.', 'Electrician', '+91-9876543231', 'AC installation and maintenance', True),
                ('Green Cleaners', 'Housekeeping', '+91-9876543232', 'Professional cleaning services', True)
            ]
            
            for name, service_type, mobile, desc, active in vendors:
                cur.execute("""
                    INSERT INTO vendors (society_id, name, service_type, mobile, service_description, active)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (society_id, name, service_type, mobile, desc, active))
                ven_id = cur.fetchone()[0]
                
                # Create user for vendor
                email = f"{name.lower().replace(' ', '.')}@vendor.com"
                pwd_hash = generate_password_hash("vendor123")
                
                cur.execute("""
                    INSERT INTO users (society_id, email, password_hash, role, linked_id, login_method)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (society_id, email, pwd_hash, 'vendor', ven_id, 'password'))
                
                print(f"✅ Created vendor: {name} (Email: {email})")
        
        # Create sample security staff
        cur.execute("SELECT COUNT(*) FROM security_staff WHERE society_id = %s", (society_id,))
        sec_count = cur.fetchone()[0]
        
        if sec_count < 2:
            security = [
                ('Ravi Kumar', '+91-9876543240', 'Day (6am-6pm)', 500.00, True),
                ('Suresh Yadav', '+91-9876543241', 'Night (6pm-6am)', 600.00, True)
            ]
            
            for name, mobile, shift, salary, active in security:
                cur.execute("""
                    INSERT INTO security_staff (society_id, name, mobile, shift, salary_per_shift, active)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (society_id, name, mobile, shift, salary, active))
                sec_id = cur.fetchone()[0]
                
                # Create user for security
                email = f"{name.lower().replace(' ', '.')}@security.com"
                pwd_hash = generate_password_hash("security123")
                
                cur.execute("""
                    INSERT INTO users (society_id, email, password_hash, role, linked_id, login_method)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (society_id, email, pwd_hash, 'security', sec_id, 'password'))
                
                print(f"✅ Created security staff: {name} (Email: {email})")
        
        # Create sample accounts if none exist
        cur.execute("SELECT COUNT(*) FROM accounts WHERE society_id = %s", (society_id,))
        acc_count = cur.fetchone()[0]
        
        if acc_count < 5:
            accounts = [
                ('A001', 'Maintenance', 'Apartment Maintenance Collection', None, 'Cr', False, None, 0, 0, False),
                ('A002', 'Vendor Pass', 'Vendor Pass Fees', None, 'Cr', False, None, 0, 0, False),
                ('E001', 'Electricity', 'Electricity Bill Payments', None, 'Dr', False, None, 0, 0, False),
                ('E002', 'Water', 'Water Bill Payments', None, 'Dr', False, None, 0, 0, False),
                ('E003', 'Salaries', 'Staff Salary Payments', None, 'Dr', False, None, 0, 0, False)
            ]
            
            for code, name, header, parent, drcr, has_bf, bf_type, bf_amt, dep_pct, is_dep in accounts:
                cur.execute("""
                    INSERT INTO accounts (society_id, name, tab_name, header, parent_account_id, drcr_account, 
                                        has_bf, bf_type, bf_amount, depreciation_percent, is_depreciable)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (society_id, code, name, header, parent, drcr, has_bf, bf_type, bf_amt, dep_pct, is_dep))
            
            print(f"✅ Created {len(accounts)} sample accounts")
        
        conn.commit()
        
        print("\n" + "="*60)
        print("🎉 Database seeding completed successfully!")
        print("="*60)
        print("\n📝 Test Credentials:")
        print("-" * 60)
        print("Master Admin:")
        print("  Email: master@estatehub.com")
        print(f"  Password: {os.getenv('MASTER_ADMIN_PASSWORD')}")
        print("\nSociety Admin:")
        print("  Email: admin@greenvalley.com")
        print("  Password: admin123")
        print("  PIN: 123456")
        print("\nApartment Owners:")
        print("  Email: rajesh.sharma@greenvalley.com")
        print("  Password: owner123")
        print("  PIN: 1234")
        print("\nVendor:")
        print("  Email: plumbing.services@vendor.com")
        print("  Password: vendor123")
        print("\nSecurity:")
        print("  Email: ravi.kumar@security.com")
        print("  Password: security123")
        print("="*60 + "\n")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error seeding database: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    seed_database()
