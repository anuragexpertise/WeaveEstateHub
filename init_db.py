#!/usr/bin/env python3
"""
Database Initialization Script for WeaveEstateHub
Reads weaveestatehub.sql and creates all tables in NeonDB
"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def init_database():
    """Initialize database with schema from weaveestatehub.sql"""
    try:
        # Connect to database
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        cur = conn.cursor()
        
        print("📊 Connected to NeonDB successfully!")
        
        # Read SQL file
        with open('weaveestatehub.sql', 'r') as f:
            sql_script = f.read()
        
        print("📄 Read schema file: weaveestatehub.sql")
        
        # Execute SQL script
        cur.execute(sql_script)
        conn.commit()
        
        print("✅ Database tables created successfully!")
        
        # Verify tables were created
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name;
        """)
        
        tables = cur.fetchall()
        print(f"\n📋 Created {len(tables)} tables:")
        for table in tables:
            print(f"   - {table[0]}")
        
        cur.close()
        conn.close()
        
        return True
        
    except psycopg2.errors.DuplicateTable as e:
        print("⚠️  Tables already exist. Skipping creation.")
        return True
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        return False

if __name__ == "__main__":
    print("🚀 WeaveEstateHub - Database Initialization\n")
    init_database()
