import os, psycopg2
from dotenv import load_dotenv

load_dotenv('/app/.env')
conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    society_id INT REFERENCES societies(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    event_date DATE,
    event_time TIME,
    audience TEXT[] DEFAULT ARRAY['admin','apartment','vendor','security'],
    status VARCHAR(20) CHECK (status IN ('draft','sent')) DEFAULT 'draft',
    created_by INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_events_society ON events(society_id);
CREATE INDEX IF NOT EXISTS idx_events_status ON events(society_id, status);
CREATE INDEX IF NOT EXISTS idx_events_date ON events(event_date);
""")
conn.commit()
print("events table created")

cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='events' ORDER BY ordinal_position")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}")

# Seed sample events
cur.execute("SELECT count(*) FROM events")
if cur.fetchone()[0] == 0:
    cur.execute("""
        INSERT INTO events (society_id, title, description, event_date, event_time, audience, status, created_by)
        VALUES
        (1, 'Annual General Meeting', 'Mandatory meeting for all society members to discuss budgets and upcoming projects.', '2026-02-15', '18:00', ARRAY['admin','apartment','vendor','security'], 'sent', NULL),
        (1, 'Water Tank Cleaning', 'Water supply will be interrupted from 9 AM to 3 PM for routine tank maintenance.', '2026-02-20', '09:00', ARRAY['admin','apartment'], 'sent', NULL),
        (1, 'Diwali Celebration', 'Grand Diwali party in the community hall. All residents and families welcome.', '2026-03-10', '19:00', ARRAY['admin','apartment','vendor','security'], 'draft', NULL)
    """)
    conn.commit()
    print("sample events inserted")

conn.close()
