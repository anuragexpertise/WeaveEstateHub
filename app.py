import os
import jwt
import datetime
import qrcode
import io
import base64
import psycopg2
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2.extras
from psycopg2 import pool
from dotenv import load_dotenv
from flask import Flask, session
import dash
from dash import dcc, html, Input, Output, State, ALL, callback_context, dash_table
import dash_bootstrap_components as dbc
import pandas as pd
from werkzeug.utils import secure_filename

# Load environment variables
load_dotenv()

# Database Connection Pool
try:
    db_pool = psycopg2.pool.SimpleConnectionPool(
        1, 20, dsn=os.getenv("DATABASE_URL")
    )
    print("✅ Database connection pool created successfully")
except Exception as e:
    db_pool = None
    print(f"❌ Database connection failed: {e}")

server = Flask(__name__)
server.secret_key = os.getenv("FLASK_SECRET_KEY")

# Configure upload folder
UPLOAD_FOLDER = '/app/uploads'
ALLOWED_EXTENSIONS = {'csv', 'png', 'jpg', 'jpeg', 'svg'}
server.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

app = dash.Dash(
    __name__,
    server=server,
    external_stylesheets=[dbc.themes.FLATLY, dbc.icons.FONT_AWESOME],
    suppress_callback_exceptions=True,
    title="WeaveEstateHub - Estate Management"
)

# --- Database Helpers ---
def query_db(query, params=(), one=False):
    """Query database and return results"""
    if not db_pool:
        raise Exception("Database connection failed")
    conn = db_pool.getconn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(query, params)
            if query.strip().upper().startswith('SELECT'):
                rv = cur.fetchall()
                return (rv[0] if rv else None) if one else rv
            else:
                conn.commit()
                return cur.rowcount
    except Exception as e:
        conn.rollback()
        print(f"Database error: {e}")
        raise
    finally:
        db_pool.putconn(conn)

def execute_db(query, params=()):
    """Execute INSERT/UPDATE/DELETE queries"""
    return query_db(query, params)

# --- Layout Constants ---
ROLE_CONFIG = {
    'admin': {'color': '#ADD8E6', 'label': 'Admin Portal', 'tabs': [
        ('Dashboard', '/admin-portal', 'fa-th-large'),
        ('Cashbook', '/cashbook', 'fa-book'),
        ('Receipts', '/receipts', 'fa-file-invoice-dollar'),
        ('Expenses', '/expenses', 'fa-wallet'),
        ('Enroll', '/enroll', 'fa-user-plus'),
        ('Users', '/users', 'fa-users'),
        ('Events', '/events', 'fa-calendar-alt'),
        ('Evaluate Pass', '/evaluate-pass', 'fa-qrcode'),
        ('Customize', '/customize', 'fa-edit'),
        ('Settings', '/settings', 'fa-cog'),
    ]},
    'apartment': {'color': '#90EE90', 'label': 'Owner Portal', 'tabs': [
        ('Dashboard', '/owner-portal', 'fa-th-large'),
        ('Cashbook', '/owner-cashbook', 'fa-book'),
        ('Payments', '/payments', 'fa-credit-card'),
        ('Charges', '/charges', 'fa-file-invoice'),
        ('Events', '/owner-events', 'fa-calendar-alt'),
        ('Settings', '/owner-settings', 'fa-cog'),
    ]},
    'vendor': {'color': '#FFFF00', 'label': 'Vendor Portal', 'tabs': [
        ('Dashboard', '/vendor-portal', 'fa-th-large'),
        ('Cashbook', '/vendor-cashbook', 'fa-book'),
        ('Payments', '/vendor-payments', 'fa-credit-card'),
        ('Charges', '/vendor-charges', 'fa-file-invoice'),
        ('Events', '/vendor-events', 'fa-calendar-alt'),
        ('Settings', '/vendor-settings', 'fa-cog'),
    ]},
    'security': {'color': '#F08080', 'label': 'Security Portal', 'tabs': [
        ('Pass Evaluation', '/pass-evaluation', 'fa-qrcode'),
        ('Attendance', '/attendance', 'fa-clock'),
        ('Events', '/security-events', 'fa-calendar-alt'),
        ('New Receipt', '/security-receipt', 'fa-plus-circle'),
        ('Users', '/security-users', 'fa-users'),
        ('Settings', '/security-settings', 'fa-cog'),
    ]}
}

# --- UI Components for Layout ---

def get_header(user_data):
    """Generate header with logo, society name, portal label, and user avatar"""
    role = user_data.get('role', 'admin')
    config = ROLE_CONFIG.get(role, ROLE_CONFIG['admin'])
    society_name = user_data.get('society_name', 'WeaveEstateHub')
    
    return html.Header([
        dbc.Row([
            dbc.Col(html.Div([
                html.Img(src="/assets/logo.svg", height="40px", className="me-2"),
                html.Span(society_name, className="fw-bold h5 mb-0")
            ], className="d-flex align-items-center"), width=4),
            
            dbc.Col(html.H4(config['label'], className="text-center mb-0 fw-light"), width=4),
            
            dbc.Col(html.Div([
                html.Img(
                    id="user-avatar",
                    src="https://ui-avatars.com/api/?name=" + user_data.get('name', 'User')[:2] + "&size=256&background=18BC9C&color=fff", 
                    className="rounded-circle shadow-sm cursor-pointer",
                    style={"height": "45px", "width": "45px", "cursor": "pointer"}
                ),
                dbc.Popover([
                    dbc.PopoverHeader("User Session"),
                    dbc.PopoverBody([
                        html.Div(id="qr-container", className="text-center mb-3"),
                        html.P(user_data.get('name', 'User'), className="text-center fw-bold mb-1"),
                        html.P(user_data.get('role', 'Role').title(), className="text-center text-muted small mb-3"),
                        dbc.Button("Logout", id="logout-btn", color="danger", size="sm", className="w-100")
                    ])
                ], id="avatar-popover", target="user-avatar", trigger="click", placement="bottom")
            ], className="d-flex justify-content-end align-items-center"), width=4),
        ], className="align-items-center w-100 g-0 px-3")
    ], style={"backgroundColor": config['color'], "height": "70px", "display": "flex", "alignItems": "center", "borderBottom": "2px solid #ddd"})

def get_sidebar(role):
    """Generate sidebar navigation based on role"""
    config = ROLE_CONFIG.get(role, ROLE_CONFIG['admin'])
    nav_items = [
        dbc.NavLink([
            html.I(className=f"fa {icon} me-3"),
            html.Span(name)
        ], href=path, active="exact", className="py-3 px-4 text-dark border-bottom", style={"textDecoration": "none"})
        for name, path, icon in config['tabs']
    ]
    
    return html.Div(
        [html.Div("NAVIGATION", className="p-3 fw-bold text-muted small")] + nav_items,
        style={
            "width": "260px", "height": "calc(100vh - 70px)", "position": "fixed",
            "top": "70px", "left": 0, "backgroundColor": "#f8f9fa", "borderRight": "1px solid #ddd",
            "overflowY": "auto", "zIndex": 100
        }
    )

def get_breadcrumb(pathname):
    """Generate breadcrumb navigation"""
    path_map = {
        # Admin
        '/admin-portal': 'Dashboard',
        '/cashbook': 'Cashbook',
        '/receipts': 'Receipts',
        '/expenses': 'Expenses',
        '/enroll': 'Enroll',
        '/users': 'Users',
        '/events': 'Events',
        '/evaluate-pass': 'Evaluate Pass',
        '/customize': 'Customize',
        '/settings': 'Settings',
        # Owner
        '/owner-portal': 'Dashboard',
        '/owner-cashbook': 'Cashbook',
        '/payments': 'Payments',
        '/charges': 'Charges',
        '/owner-events': 'Events',
        '/owner-settings': 'Settings',
        # Vendor
        '/vendor-portal': 'Dashboard',
        '/vendor-cashbook': 'Cashbook',
        '/vendor-payments': 'Payments',
        '/vendor-charges': 'Charges',
        '/vendor-events': 'Events',
        '/vendor-settings': 'Settings',
        # Security
        '/pass-evaluation': 'Pass Evaluation',
        '/attendance': 'Attendance',
        '/security-events': 'Events',
        '/security-receipt': 'New Receipt',
        '/security-users': 'Users',
        '/security-settings': 'Settings',
    }
    
    # Determine home route based on pathname prefix
    home_routes = {
        'admin': '/admin-portal',
        'owner': '/owner-portal',
        'vendor': '/vendor-portal',
        'security': '/pass-evaluation',
    }
    home_href = '/admin-portal'
    for key, href in home_routes.items():
        if pathname and key in pathname:
            home_href = href
            break
    # Special paths
    if pathname in ['/cashbook', '/receipts', '/expenses', '/enroll', '/users', '/events',
                    '/evaluate-pass', '/customize', '/settings']:
        home_href = '/admin-portal'
    if pathname in ['/payments', '/charges']:
        home_href = '/owner-portal'
    if pathname in ['/attendance']:
        home_href = '/pass-evaluation'
    
    items = [{"label": "Home", "href": home_href, "external_link": False}]
    dashboards = ['/admin-portal', '/owner-portal', '/vendor-portal', '/pass-evaluation']
    if pathname and pathname not in dashboards:
        items.append({"label": path_map.get(pathname, pathname[1:].replace('-', ' ').title()), "active": True})
    
    return dbc.Breadcrumb(items=items, className="mb-4 bg-transparent p-0")

def render_app_shell(user_data, content, pathname='/'):
    """Main app shell with header, sidebar, content, and footer"""
    return html.Div([
        get_header(user_data),
        get_sidebar(user_data['role']),
        html.Div([
            get_breadcrumb(pathname),
            html.Div(id="alert-container"),
            content,
            html.Footer([
                "© 2025 WeaveEstateHub - Powered by ApexWeave | ",
                html.A("Support", href="mailto:support@weaveestatehub.com", className="text-decoration-none")
            ], className="text-center text-muted mt-5 py-3 border-top small")
        ], style={"marginLeft": "260px", "padding": "30px", "minHeight": "calc(100vh - 70px)", "backgroundColor": "#f5f7fa"})
    ])

# --- Helper UI Components ---

def kpi_card(title, icon, metrics):
    """KPI Card component for dashboard"""
    return dbc.Card([
        dbc.CardBody([
            html.Div([
                html.H6(title, className="card-title text-muted mb-0", style={"fontSize": "0.85rem"}),
                html.I(className=f"fa {icon} text-muted opacity-50", style={"fontSize": "1.5rem"})
            ], className="d-flex justify-content-between align-items-center mb-3"),
            dbc.Row([
                dbc.Col([
                    html.Small(label, className="text-muted d-block", style={"fontSize": "0.7rem"}),
                    html.H4(str(value), className=f"text-{color} fw-bold mb-0", style={"fontSize": "1.5rem"})
                ], width=12 // len(metrics)) for label, value, color in metrics
            ], className="g-2")
        ])
    ], className="shadow-sm border-0 h-100 hover-shadow", style={"transition": "all 0.3s"})

# ========== ADMIN PORTAL MODULES ==========

# MODULE 1: Dashboard
def get_admin_dashboard(user_data):
    """Admin Dashboard with KPIs"""
    soc_id = user_data.get('society_id')
    stats = {
        'apt_dues': 0, 'apt_nodues': 0, 'apt_total': 0,
        'ven_dues': 0, 'ven_nodues': 0, 'ven_total': 0,
        'sec_total': 0, 'balance': 0.0,
        'rec_p': 0, 'rec_v': 0,
        'exp_p': 0, 'exp_v': 0,
        'events_upcoming': 0, 'events_draft': 0
    }

    if soc_id:
        try:
            # Apartment Metrics
            res = query_db("SELECT count(*) as cnt FROM apartments WHERE society_id = %s AND active = TRUE", (soc_id,), one=True)
            stats['apt_total'] = res['cnt'] if res else 0
            
            res = query_db("SELECT count(DISTINCT apt_id) as cnt FROM apt_charges_fines WHERE society_id = %s AND apt_status = FALSE", (soc_id,), one=True)
            stats['apt_dues'] = res['cnt'] if res else 0
            stats['apt_nodues'] = stats['apt_total'] - stats['apt_dues']

            # Vendor Metrics
            res = query_db("SELECT count(*) as cnt FROM vendors WHERE society_id = %s AND active = TRUE", (soc_id,), one=True)
            stats['ven_total'] = res['cnt'] if res else 0
            
            res = query_db("SELECT count(DISTINCT ven_id) as cnt FROM ven_charges_fines WHERE society_id = %s AND ven_status = FALSE", (soc_id,), one=True)
            stats['ven_dues'] = res['cnt'] if res else 0
            stats['ven_nodues'] = stats['ven_total'] - stats['ven_dues']

            # Security Metrics
            res = query_db("SELECT count(*) as cnt FROM security_staff WHERE society_id = %s AND active = TRUE", (soc_id,), one=True)
            stats['sec_total'] = res['cnt'] if res else 0

            # Financial Balance - simplified calculation
            # Note: Proper implementation would need complex double-entry bookkeeping
            stats['balance'] = 0.0

        except Exception as e:
            print(f"Dashboard DB Error: {e}")

    return html.Div([
        html.H3("Dashboard Overview", className="mb-4 fw-light"),
        dbc.Row([
            dbc.Col(kpi_card("Apartment Owners", "fa-building", [
                ("With Dues", stats['apt_dues'], "danger"), 
                ("No Dues", stats['apt_nodues'], "success"), 
                ("Total", stats['apt_total'], "primary")
            ]), width=3),
            dbc.Col(kpi_card("Utility Contractors", "fa-tools", [
                ("With Dues", stats['ven_dues'], "danger"), 
                ("No Dues", stats['ven_nodues'], "success"), 
                ("Total", stats['ven_total'], "primary")
            ]), width=3),
            dbc.Col(kpi_card("Security Staff", "fa-shield-alt", [
                ("Active", stats['sec_total'], "success"),
                ("Total", stats['sec_total'], "primary")
            ]), width=3),
            dbc.Col(kpi_card("Balance", "fa-rupee-sign", [
                ("Available", f"₹{stats['balance']:,.0f}", "success")
            ]), width=3),
        ], className="mb-4 g-3"),
        dbc.Row([
            dbc.Col(kpi_card("Credits (Receipts)", "fa-chart-line", [
                ("Pending", stats['rec_p'], "warning"), 
                ("Verified", stats['rec_v'], "success")
            ]), width=4),
            dbc.Col(kpi_card("Debits (Expenses)", "fa-chart-area", [
                ("Pending", stats['exp_p'], "warning"), 
                ("Paid", stats['exp_v'], "success")
            ]), width=4),
            dbc.Col(kpi_card("Events", "fa-calendar-check", [
                ("Upcoming", stats['events_upcoming'], "primary"), 
                ("Drafts", stats['events_draft'], "secondary")
            ]), width=4),
        ], className="g-3")
    ])

# MODULE 2: Cashbook
def get_cashbook(user_data):
    """Cashbook - Financial Ledger"""
    soc_id = user_data.get('society_id')
    
    # Fetch transactions
    transactions = []
    if soc_id:
        try:
            transactions = query_db("""
                SELECT t.trx_date, a.name as account, t.acc_particulars, 
                       t.amount, t.mode, t.status, a.drcr_account
                FROM transactions t
                JOIN accounts a ON t.acc_id = a.id
                WHERE t.society_id = %s
                ORDER BY t.trx_date DESC, t.id DESC
                LIMIT 100
            """, (soc_id,))
        except Exception as e:
            print(f"Cashbook error: {e}")
    
    # Create table rows
    table_rows = []
    running_balance = 0.0
    
    for trx in transactions:
        amount = float(trx['amount'])
        if trx['drcr_account'] == 'Cr':
            running_balance += amount
            credit = amount
            debit = 0
        else:
            running_balance -= amount
            debit = amount
            credit = 0
            
        table_rows.append(html.Tr([
            html.Td(str(trx['trx_date'])),
            html.Td(trx['account']),
            html.Td(trx['acc_particulars'] or '-'),
            html.Td(f"₹{debit:,.2f}" if debit > 0 else '-', className="text-danger" if debit > 0 else ""),
            html.Td(f"₹{credit:,.2f}" if credit > 0 else '-', className="text-success" if credit > 0 else ""),
            html.Td(f"₹{running_balance:,.2f}", className=f"text-{'success' if running_balance >= 0 else 'danger'} fw-bold"),
            html.Td(dbc.Badge(trx['status'], color="success" if trx['status'] == 'paid' else "warning", className="text-capitalize"))
        ]))
    
    return html.Div([
        html.H3("Cashbook", className="mb-4 fw-light"),
        dbc.Card([
            dbc.CardBody([
                dbc.Table([
                    html.Thead(html.Tr([
                        html.Th("Date"),
                        html.Th("Account"),
                        html.Th("Particulars"),
                        html.Th("Debit"),
                        html.Th("Credit"),
                        html.Th("Balance"),
                        html.Th("Status")
                    ])),
                    html.Tbody(table_rows if table_rows else [html.Tr([html.Td("No transactions found", colSpan=7, className="text-center text-muted")])])
                ], bordered=True, hover=True, striped=True, className="mb-0")
            ])
        ], className="shadow-sm")
    ])

# MODULE 3: Receipts
def get_receipts(user_data):
    """Receipts Module - Create and verify receipts"""
    soc_id = user_data.get('society_id')
    
    # Fetch accounts for dropdown
    accounts = []
    receipts = []
    if soc_id:
        try:
            accounts = query_db("SELECT id, name, header FROM accounts WHERE society_id = %s AND drcr_account = 'Cr'", (soc_id,))
            receipts = query_db("""
                SELECT t.id, t.trx_date, a.name as account, t.acc_particulars, 
                       t.amount, t.status, t.entity_id
                FROM transactions t
                JOIN accounts a ON t.acc_id = a.id
                WHERE t.society_id = %s AND a.drcr_account = 'Cr'
                ORDER BY t.trx_date DESC
                LIMIT 50
            """, (soc_id,))
        except Exception as e:
            print(f"Receipts error: {e}")
    
    account_options = [{"label": f"{a['name']} - {a['header']}", "value": a['id']} for a in accounts]
    
    receipt_rows = []
    for r in receipts:
        receipt_rows.append(html.Tr([
            html.Td(str(r['trx_date'])),
            html.Td(r['account']),
            html.Td(r['acc_particulars'] or '-'),
            html.Td(f"₹{float(r['amount']):,.2f}", className="text-success fw-bold"),
            html.Td(dbc.Badge(r['status'], color="success" if r['status'] == 'paid' else "warning", className="text-capitalize")),
            html.Td([
                dbc.Button("Verify", id={"type": "verify-receipt", "index": r['id']}, 
                          color="success", size="sm", disabled=(r['status'] == 'paid'))
            ] if r['status'] != 'paid' else html.Span("✓ Verified", className="text-success"))
        ]))
    
    return html.Div([
        html.H3("Receipts", className="mb-4 fw-light"),
        
        dbc.Card([
            dbc.CardHeader(html.H5("Create New Receipt", className="mb-0")),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Credit Account"),
                        dcc.Dropdown(id="receipt-account", options=account_options, placeholder="Select account...")
                    ], width=4),
                    dbc.Col([
                        dbc.Label("Description/Particulars"),
                        dbc.Input(id="receipt-description", placeholder="e.g., Maintenance payment from Flat 101")
                    ], width=4),
                    dbc.Col([
                        dbc.Label("Amount (₹)"),
                        dbc.Input(id="receipt-amount", type="number", placeholder="0.00")
                    ], width=3),
                    dbc.Col([
                        dbc.Label("Action", className="d-block"),
                        dbc.Button("Add Receipt", id="add-receipt-btn", color="primary", className="w-100")
                    ], width=1, className="d-flex align-items-end")
                ], className="g-3")
            ])
        ], className="shadow-sm mb-4"),
        
        dbc.Card([
            dbc.CardHeader(html.H5("Receipts Log", className="mb-0")),
            dbc.CardBody([
                dbc.Table([
                    html.Thead(html.Tr([
                        html.Th("Date"), html.Th("Account"), html.Th("Description"), 
                        html.Th("Amount"), html.Th("Status"), html.Th("Action")
                    ])),
                    html.Tbody(receipt_rows if receipt_rows else [
                        html.Tr([html.Td("No receipts found", colSpan=6, className="text-center text-muted")])
                    ])
                ], bordered=True, hover=True, striped=True, responsive=True, className="mb-0")
            ])
        ], className="shadow-sm")
    ])

# MODULE 4: Expenses
def get_expenses(user_data):
    """Expenses Module - Create and track expenses"""
    soc_id = user_data.get('society_id')
    
    accounts = []
    expenses = []
    if soc_id:
        try:
            accounts = query_db("SELECT id, name, header FROM accounts WHERE society_id = %s AND drcr_account = 'Dr'", (soc_id,))
            expenses = query_db("""
                SELECT t.id, t.trx_date, a.name as account, t.acc_particulars, 
                       t.amount, t.status, t.mode
                FROM transactions t
                JOIN accounts a ON t.acc_id = a.id
                WHERE t.society_id = %s AND a.drcr_account = 'Dr'
                ORDER BY t.trx_date DESC
                LIMIT 50
            """, (soc_id,))
        except Exception as e:
            print(f"Expenses error: {e}")
    
    account_options = [{"label": f"{a['name']} - {a['header']}", "value": a['id']} for a in accounts]
    
    expense_rows = []
    for e in expenses:
        expense_rows.append(html.Tr([
            html.Td(str(e['trx_date'])),
            html.Td(e['account']),
            html.Td(e['acc_particulars'] or '-'),
            html.Td(f"₹{float(e['amount']):,.2f}", className="text-danger fw-bold"),
            html.Td(dbc.Badge(e['status'], color="success" if e['status'] == 'paid' else "warning", className="text-capitalize")),
            html.Td(e['mode'] or '-', className="text-capitalize")
        ]))
    
    return html.Div([
        html.H3("Expenses", className="mb-4 fw-light"),
        
        dbc.Card([
            dbc.CardHeader(html.H5("Record New Expense", className="mb-0")),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Debit Account"),
                        dcc.Dropdown(id="expense-account", options=account_options, placeholder="Select account...")
                    ], width=4),
                    dbc.Col([
                        dbc.Label("Description/Particulars"),
                        dbc.Input(id="expense-description", placeholder="e.g., Electricity bill payment")
                    ], width=4),
                    dbc.Col([
                        dbc.Label("Amount (₹)"),
                        dbc.Input(id="expense-amount", type="number", placeholder="0.00")
                    ], width=3),
                    dbc.Col([
                        dbc.Label("Action", className="d-block"),
                        dbc.Button("Add Expense", id="add-expense-btn", color="danger", className="w-100")
                    ], width=1, className="d-flex align-items-end")
                ], className="g-3")
            ])
        ], className="shadow-sm mb-4"),
        
        dbc.Card([
            dbc.CardHeader(html.H5("Expenses Log", className="mb-0")),
            dbc.CardBody([
                dbc.Table([
                    html.Thead(html.Tr([
                        html.Th("Date"), html.Th("Account"), html.Th("Description"), 
                        html.Th("Amount"), html.Th("Status"), html.Th("Mode")
                    ])),
                    html.Tbody(expense_rows if expense_rows else [
                        html.Tr([html.Td("No expenses found", colSpan=6, className="text-center text-muted")])
                    ])
                ], bordered=True, hover=True, striped=True, responsive=True, className="mb-0")
            ])
        ], className="shadow-sm")
    ])

# MODULE 5: Enroll
def get_enrollment(user_data):
    """Enrollment Module - Manual and CSV import"""
    return html.Div([
        html.H3("Enroll New Users", className="mb-4 fw-light"),
        
        dbc.Tabs([
            dbc.Tab(label="Manual Enrollment", children=[
                dbc.Card([
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Select Role"),
                                dcc.Dropdown(
                                    id="enroll-role",
                                    options=[
                                        {"label": "Apartment Owner", "value": "apartment"},
                                        {"label": "Utility Contractor", "value": "vendor"},
                                        {"label": "Security Staff", "value": "security"},
                                        {"label": "Admin", "value": "admin"}
                                    ],
                                    placeholder="Choose role...",
                                    className="mb-3"
                                )
                            ], width=12)
                        ]),
                        html.Div(id="enroll-form-container")
                    ])
                ], className="shadow-sm mt-3")
            ]),
            
            dbc.Tab(label="CSV Import", children=[
                dbc.Card([
                    dbc.CardBody([
                        html.P([
                            "Upload a CSV file to enroll multiple users at once. ",
                            dbc.Button("Download Template", id="download-csv-template", color="link", size="sm", className="p-0")
                        ]),
                        dcc.Upload(
                            id="upload-csv",
                            children=html.Div([
                                html.I(className="fa fa-upload fa-3x mb-3 text-muted"),
                                html.P("Drag and Drop or Click to Select CSV File", className="mb-0")
                            ], className="text-center p-5 border border-dashed rounded"),
                            multiple=False
                        ),
                        html.Div(id="csv-upload-output", className="mt-3")
                    ])
                ], className="shadow-sm mt-3")
            ])
        ])
    ])

# MODULE 6: Users
def get_users(user_data):
    """Users Module - Directory and management"""
    soc_id = user_data.get('society_id')
    
    users = []
    if soc_id:
        try:
            users = query_db("""
                SELECT u.id, u.email, u.role, u.linked_id,
                       CASE 
                           WHEN u.role = 'apartment' THEN a.owner_name
                           WHEN u.role = 'vendor' THEN v.name
                           WHEN u.role = 'security' THEN s.name
                           ELSE 'Admin User'
                       END as name,
                       CASE 
                           WHEN u.role = 'apartment' THEN a.mobile
                           WHEN u.role = 'vendor' THEN v.mobile
                           WHEN u.role = 'security' THEN s.mobile
                           ELSE NULL
                       END as phone
                FROM users u
                LEFT JOIN apartments a ON u.role = 'apartment' AND u.linked_id = a.id
                LEFT JOIN vendors v ON u.role = 'vendor' AND u.linked_id = v.id
                LEFT JOIN security_staff s ON u.role = 'security' AND u.linked_id = s.id
                WHERE u.society_id = %s
                ORDER BY u.role, u.id
            """, (soc_id,))
        except Exception as e:
            print(f"Users error: {e}")
    
    user_rows = []
    for u in users:
        role_badge_color = {
            'admin': 'primary',
            'apartment': 'success',
            'vendor': 'warning',
            'security': 'danger'
        }
        
        user_rows.append(html.Tr([
            html.Td(u['name'] or 'N/A'),
            html.Td(dbc.Badge(u['role'].title(), color=role_badge_color.get(u['role'], 'secondary'))),
            html.Td(u['email']),
            html.Td(u['phone'] or '-'),
            html.Td([
                dbc.Button("View", id={"type": "view-user", "index": u['id']}, 
                          color="info", size="sm", outline=True, className="me-1"),
                dbc.Button("Edit", id={"type": "edit-user", "index": u['id']}, 
                          color="warning", size="sm", outline=True)
            ])
        ]))
    
    return html.Div([
        html.H3("User Directory", className="mb-4 fw-light"),
        
        dbc.Card([
            dbc.CardHeader([
                dbc.Row([
                    dbc.Col(html.H5(f"Total Users: {len(users)}", className="mb-0"), width=6),
                    dbc.Col([
                        dbc.Input(id="user-search", placeholder="Search users...", type="text", size="sm")
                    ], width=6)
                ])
            ]),
            dbc.CardBody([
                dbc.Table([
                    html.Thead(html.Tr([
                        html.Th("Name"), html.Th("Role"), html.Th("Email"), 
                        html.Th("Phone"), html.Th("Actions")
                    ])),
                    html.Tbody(user_rows if user_rows else [
                        html.Tr([html.Td("No users found", colSpan=5, className="text-center text-muted")])
                    ])
                ], bordered=True, hover=True, striped=True, responsive=True, className="mb-0")
            ])
        ], className="shadow-sm")
    ])

# MODULE 7: Events
def get_events(user_data):
    """Events Module - Create and manage events"""
    soc_id = user_data.get('society_id')
    
    # Note: Events table doesn't exist in schema, so this is a placeholder
    # You would need to add an events table to fully implement this
    
    return html.Div([
        html.H3("Events & Announcements", className="mb-4 fw-light"),
        
        dbc.Card([
            dbc.CardHeader(html.H5("Create New Event", className="mb-0")),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Event Name"),
                        dbc.Input(id="event-name", placeholder="e.g., Society Meeting")
                    ], width=6),
                    dbc.Col([
                        dbc.Label("Event Date"),
                        dbc.Input(id="event-date", type="date")
                    ], width=3),
                    dbc.Col([
                        dbc.Label("Event Time"),
                        dbc.Input(id="event-time", type="time")
                    ], width=3)
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Description"),
                        dbc.Textarea(id="event-description", placeholder="Event details...", rows=3)
                    ], width=12)
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Target Audience"),
                        dbc.Checklist(
                            id="event-audience",
                            options=[
                                {"label": " Admin", "value": "admin"},
                                {"label": " Apartment Owners", "value": "apartment"},
                                {"label": " Contractors", "value": "vendor"},
                                {"label": " Security", "value": "security"}
                            ],
                            value=["admin", "apartment", "vendor", "security"],
                            inline=True
                        )
                    ], width=12)
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col([
                        dbc.Button("Save as Draft", id="save-event-draft", color="secondary", className="me-2"),
                        dbc.Button("Send Event", id="send-event", color="success")
                    ])
                ])
            ])
        ], className="shadow-sm mb-4"),
        
        dbc.Card([
            dbc.CardHeader(html.H5("Upcoming Events", className="mb-0")),
            dbc.CardBody([
                html.P("No events scheduled", className="text-center text-muted mb-0")
            ])
        ], className="shadow-sm")
    ])

# MODULE 8: Evaluate Pass
def get_evaluate_pass(user_data):
    """Evaluate Pass Module - QR Scanner"""
    return html.Div([
        html.H3("Evaluate Pass", className="mb-4 fw-light"),
        
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("QR Code Scanner", className="mb-0")),
                    dbc.CardBody([
                        html.Div([
                            html.I(className="fa fa-qrcode fa-5x text-muted mb-3"),
                            html.P("Camera-based QR scanning coming soon", className="text-muted"),
                            html.P("Use manual entry below for now", className="small text-muted")
                        ], className="text-center p-5 border rounded")
                    ])
                ], className="shadow-sm mb-3"),
                
                dbc.Card([
                    dbc.CardHeader(html.H5("Manual Evaluation", className="mb-0")),
                    dbc.CardBody([
                        dbc.Label("Enter Entity ID or Email"),
                        dbc.Input(id="manual-entity-id", placeholder="e.g., 123 or user@example.com"),
                        dbc.Button("Evaluate", id="evaluate-entity-btn", color="primary", className="w-100 mt-3"),
                        html.Div(id="evaluation-result", className="mt-3")
                    ])
                ], className="shadow-sm")
            ], width=6),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("Recent Evaluations", className="mb-0")),
                    dbc.CardBody([
                        html.P("No recent evaluations", className="text-center text-muted mb-0")
                    ])
                ], className="shadow-sm")
            ], width=6)
        ])
    ])

# MODULE 9: Customize
def get_customize(user_data):
    """Customize Module - Layout customization"""
    return html.Div([
        html.H3("Customize Portal Layouts", className="mb-4 fw-light"),
        
        dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Select Role to Customize"),
                        dcc.Dropdown(
                            id="customize-role",
                            options=[
                                {"label": "Admin Portal", "value": "admin"},
                                {"label": "Apartment Owner Portal", "value": "apartment"},
                                {"label": "Vendor Portal", "value": "vendor"},
                                {"label": "Security Portal", "value": "security"}
                            ],
                            placeholder="Choose role..."
                        )
                    ], width=6),
                    dbc.Col([
                        dbc.Label("Select Page"),
                        dcc.Dropdown(
                            id="customize-page",
                            options=[
                                {"label": "Dashboard", "value": "dashboard"}
                            ],
                            placeholder="Choose page..."
                        )
                    ], width=6)
                ], className="mb-4"),
                
                html.Div([
                    html.P("Drag-and-drop layout customization coming soon", className="text-center text-muted p-5 border rounded"),
                    html.P("This feature will allow you to rearrange dashboard KPI cards", className="text-center small text-muted")
                ])
            ])
        ], className="shadow-sm")
    ])

# MODULE 10: Settings
def get_settings(user_data):
    """Settings Module - Global, Admin, Accounts, Personnel"""
    soc_id = user_data.get('society_id')
    
    return html.Div([
        html.H3("Settings", className="mb-4 fw-light"),
        
        dbc.Tabs([
            # Tab 1: Global Settings
            dbc.Tab(label="Global Settings", children=[
                dbc.Card([
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Society Name"),
                                dbc.Input(id="society-name", placeholder="Enter society name", value=user_data.get('society_name', ''))
                            ], width=6),
                            dbc.Col([
                                dbc.Label("Society Email"),
                                dbc.Input(id="society-email", placeholder="contact@society.com", type="email")
                            ], width=6)
                        ], className="mb-3"),
                        
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Upload Society Logo"),
                                dcc.Upload(
                                    id="upload-logo",
                                    children=html.Div([
                                        html.I(className="fa fa-upload me-2"),
                                        "Click to upload logo"
                                    ], className="btn btn-outline-primary"),
                                )
                            ], width=6),
                            dbc.Col([
                                dbc.Label("Upload Login Background"),
                                dcc.Upload(
                                    id="upload-bg",
                                    children=html.Div([
                                        html.I(className="fa fa-upload me-2"),
                                        "Click to upload background"
                                    ], className="btn btn-outline-primary"),
                                )
                            ], width=6)
                        ], className="mb-3"),
                        
                        dbc.Button("Save Global Settings", id="save-global-settings", color="success")
                    ])
                ], className="shadow-sm mt-3")
            ]),
            
            # Tab 2: Admin Settings (Rates & Fines)
            dbc.Tab(label="Admin Settings", children=[
                dbc.Card([
                    dbc.CardBody([
                        html.H5("Apartment Maintenance Rates (per sq.ft)", className="mb-3"),
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("1 Month Rate (₹/sqft)"),
                                dbc.Input(id="rate-1m", type="number", placeholder="0.00")
                            ], width=3),
                            dbc.Col([
                                dbc.Label("3 Month Rate (₹/sqft)"),
                                dbc.Input(id="rate-3m", type="number", placeholder="0.00")
                            ], width=3),
                            dbc.Col([
                                dbc.Label("6 Month Rate (₹/sqft)"),
                                dbc.Input(id="rate-6m", type="number", placeholder="0.00")
                            ], width=3),
                            dbc.Col([
                                dbc.Label("1 Year Rate (₹/sqft)"),
                                dbc.Input(id="rate-1y", type="number", placeholder="0.00")
                            ], width=3)
                        ], className="mb-4"),
                        
                        html.Hr(),
                        html.H5("Contractor Pass Rates", className="mb-3"),
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("1 Day Pass (₹)"),
                                dbc.Input(id="vendor-1d", type="number", placeholder="0.00")
                            ], width=4),
                            dbc.Col([
                                dbc.Label("7 Day Pass (₹)"),
                                dbc.Input(id="vendor-7d", type="number", placeholder="0.00")
                            ], width=4),
                            dbc.Col([
                                dbc.Label("1 Month Pass (₹)"),
                                dbc.Input(id="vendor-1m", type="number", placeholder="0.00")
                            ], width=4)
                        ], className="mb-4"),
                        
                        html.Hr(),
                        html.H5("Late Fee Configuration", className="mb-3"),
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Fixed Late Fee (₹)"),
                                dbc.Input(id="late-fee-fixed", type="number", placeholder="0.00")
                            ], width=6),
                            dbc.Col([
                                dbc.Label("Daily Fine (₹/day)"),
                                dbc.Input(id="late-fee-daily", type="number", placeholder="0.00")
                            ], width=6)
                        ], className="mb-3"),
                        
                        dbc.Button("Save Admin Settings", id="save-admin-settings", color="success")
                    ])
                ], className="shadow-sm mt-3")
            ]),
            
            # Tab 3: Accounts
            dbc.Tab(label="Accounts", children=[
                dbc.Card([
                    dbc.CardBody([
                        html.H5("Account Configuration", className="mb-3"),
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Arrears Calculation Start Date"),
                                dbc.Input(id="arrear-start-date", type="date")
                            ], width=6)
                        ], className="mb-4"),
                        
                        html.Hr(),
                        html.H5("Create New Account", className="mb-3"),
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Account Code"),
                                dbc.Input(id="account-code", placeholder="e.g., A001")
                            ], width=3),
                            dbc.Col([
                                dbc.Label("Account Name"),
                                dbc.Input(id="account-name", placeholder="e.g., Maintenance Income")
                            ], width=6),
                            dbc.Col([
                                dbc.Label("Type"),
                                dcc.Dropdown(
                                    id="account-type",
                                    options=[
                                        {"label": "Credit (Income)", "value": "Cr"},
                                        {"label": "Debit (Expense)", "value": "Dr"}
                                    ]
                                )
                            ], width=3)
                        ], className="mb-3"),
                        
                        dbc.Button("Create Account", id="create-account-btn", color="primary")
                    ])
                ], className="shadow-sm mt-3")
            ]),
            
            # Tab 4: Personnel (Shifts)
            dbc.Tab(label="Personnel", children=[
                dbc.Card([
                    dbc.CardBody([
                        html.H5("Security Staff Shift Management", className="mb-3"),
                        html.P("View and manage work shifts for security personnel", className="text-muted"),
                        
                        dbc.Table([
                            html.Thead(html.Tr([
                                html.Th("Personnel"), html.Th("Shift"), html.Th("Status"), 
                                html.Th("Phone"), html.Th("Actions")
                            ])),
                            html.Tbody([
                                html.Tr([html.Td("No security staff found", colSpan=5, className="text-center text-muted")])
                            ])
                        ], bordered=True, hover=True, striped=True)
                    ])
                ], className="shadow-sm mt-3")
            ])
        ])
    ])

# ========== APARTMENT OWNER PORTAL MODULES ==========

def get_owner_dashboard(user_data):
    """Owner Dashboard: profile, QR pass, maintenance summary, events"""
    soc_id = user_data.get('society_id')
    linked_id = user_data.get('linked_id')
    
    apt_info = None
    dues_total = 0.0
    payments_total = 0.0
    
    if soc_id and linked_id:
        try:
            apt_info = query_db(
                "SELECT * FROM apartments WHERE id = %s AND society_id = %s",
                (linked_id, soc_id), one=True
            )
            # Sum of charges
            res = query_db("""
                SELECT COALESCE(SUM(apt_maintenance_rate * a.apartment_size), 0) as total_charges
                FROM apt_charges_fines acf
                JOIN apartments a ON acf.apt_id = a.id
                WHERE acf.apt_id = %s AND acf.society_id = %s
            """, (linked_id, soc_id), one=True)
            dues_total = float(res['total_charges']) if res else 0.0
            
            # Sum of payments
            res = query_db("""
                SELECT COALESCE(SUM(t.amount), 0) as total_paid
                FROM transactions t
                JOIN accounts acc ON t.acc_id = acc.id
                WHERE t.entity_id = %s AND t.society_id = %s
                  AND acc.drcr_account = 'Cr' AND t.status = 'paid'
            """, (linked_id, soc_id), one=True)
            payments_total = float(res['total_paid']) if res else 0.0
        except Exception as e:
            print(f"Owner dashboard error: {e}")
    
    flat_number = apt_info['flat_number'] if apt_info else 'N/A'
    owner_name = apt_info['owner_name'] if apt_info else user_data.get('name', 'Owner')
    apt_size = apt_info['apartment_size'] if apt_info else 0
    balance_due = dues_total - payments_total
    
    # QR data for pass
    qr_data = f"ESTATEHUB|APT:{linked_id}|FLAT:{flat_number}|SOC:{soc_id}"
    img = qrcode.make(qr_data, box_size=4, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()
    
    return html.Div([
        html.H3("Owner Dashboard", className="mb-4 fw-light"),
        dbc.Row([
            # Profile card
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.Img(
                                src=f"https://ui-avatars.com/api/?name={owner_name[:2]}&size=128&background=90EE90&color=fff",
                                className="rounded-circle mb-3", style={"width": "90px", "height": "90px"}
                            ),
                            html.H5(owner_name, className="fw-bold mb-1"),
                            html.P(f"Flat: {flat_number}", className="text-muted mb-0"),
                            html.P(f"Size: {apt_size} sq.ft", className="text-muted small"),
                        ], className="text-center")
                    ])
                ], className="shadow-sm h-100")
            ], width=3),
            
            # QR Pass
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6("Your Access Pass", className="text-muted mb-3 text-center"),
                        html.Div([
                            html.Img(src=f"data:image/png;base64,{qr_b64}",
                                     style={"width": "160px"}, className="border p-2 rounded")
                        ], className="text-center"),
                        html.P("Show this QR at the gate", className="text-muted small text-center mt-2 mb-0")
                    ])
                ], className="shadow-sm h-100")
            ], width=3),
            
            # Financial summary
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6("Financial Summary", className="text-muted mb-3"),
                        dbc.Row([
                            dbc.Col([
                                html.Small("Total Charges", className="text-muted d-block"),
                                html.H5(f"₹{dues_total:,.0f}", className="text-danger fw-bold mb-0")
                            ]),
                            dbc.Col([
                                html.Small("Total Paid", className="text-muted d-block"),
                                html.H5(f"₹{payments_total:,.0f}", className="text-success fw-bold mb-0")
                            ]),
                        ], className="mb-3"),
                        html.Hr(),
                        html.Div([
                            html.Small("Balance Due", className="text-muted d-block"),
                            html.H4(
                                f"₹{balance_due:,.0f}",
                                className=f"fw-bold mb-0 text-{'danger' if balance_due > 0 else 'success'}"
                            )
                        ])
                    ])
                ], className="shadow-sm h-100")
            ], width=6),
        ], className="g-3 mb-4"),
        
        # Events preview
        dbc.Card([
            dbc.CardHeader(html.H5("Events & Announcements", className="mb-0")),
            dbc.CardBody([
                html.P("No upcoming events or announcements.", className="text-muted text-center mb-0")
            ])
        ], className="shadow-sm")
    ])


def get_owner_cashbook(user_data):
    """Owner Cashbook: charges, fines, payments with running balance"""
    soc_id = user_data.get('society_id')
    linked_id = user_data.get('linked_id')
    
    rows = []
    if soc_id and linked_id:
        try:
            # Get charges
            charges = query_db("""
                SELECT acf.start_date as date, 
                       'Maintenance Charge' as description,
                       (acf.apt_maintenance_rate * a.apartment_size) as charge,
                       0 as payment
                FROM apt_charges_fines acf
                JOIN apartments a ON acf.apt_id = a.id
                WHERE acf.apt_id = %s AND acf.society_id = %s
                ORDER BY acf.start_date
            """, (linked_id, soc_id))
            
            # Get fines
            fines = query_db("""
                SELECT start_date as date,
                       'Late Fee / Fine' as description,
                       (apt_fine + apt_delay_fine) as charge,
                       0 as payment
                FROM apt_charges_fines
                WHERE apt_id = %s AND society_id = %s AND (apt_fine > 0 OR apt_delay_fine > 0)
                ORDER BY start_date
            """, (linked_id, soc_id))
            
            # Get payments
            payments = query_db("""
                SELECT t.trx_date as date,
                       COALESCE(t.acc_particulars, 'Payment') as description,
                       0 as charge,
                       t.amount as payment
                FROM transactions t
                JOIN accounts acc ON t.acc_id = acc.id
                WHERE t.entity_id = %s AND t.society_id = %s
                  AND acc.drcr_account = 'Cr' AND t.status = 'paid'
                ORDER BY t.trx_date
            """, (linked_id, soc_id))
            
            # Combine and sort
            all_entries = []
            for c in charges:
                all_entries.append((c['date'], c['description'], float(c['charge']), 0.0))
            for f in fines:
                all_entries.append((f['date'], f['description'], float(f['charge']), 0.0))
            for p in payments:
                all_entries.append((p['date'], p['description'], 0.0, float(p['payment'])))
            
            all_entries.sort(key=lambda x: x[0] if x[0] else datetime.date.min)
            
            running = 0.0
            for dt, desc, charge, payment in all_entries:
                running += charge - payment
                rows.append(html.Tr([
                    html.Td(str(dt) if dt else '-'),
                    html.Td(desc),
                    html.Td(f"₹{charge:,.2f}" if charge > 0 else '-', className="text-danger" if charge > 0 else ""),
                    html.Td(f"₹{payment:,.2f}" if payment > 0 else '-', className="text-success" if payment > 0 else ""),
                    html.Td(f"₹{running:,.2f}", className=f"fw-bold text-{'danger' if running > 0 else 'success'}")
                ]))
        except Exception as e:
            print(f"Owner cashbook error: {e}")
    
    return html.Div([
        html.H3("Charges & Payment History", className="mb-4 fw-light"),
        dbc.Card([
            dbc.CardBody([
                dbc.Table([
                    html.Thead(html.Tr([
                        html.Th("Date"), html.Th("Description"),
                        html.Th("Charge (Dr)"), html.Th("Payment (Cr)"), html.Th("Balance")
                    ])),
                    html.Tbody(rows if rows else [
                        html.Tr([html.Td("No records found.", colSpan=5, className="text-center text-muted")])
                    ])
                ], bordered=True, hover=True, striped=True, responsive=True, className="mb-0")
            ])
        ], className="shadow-sm")
    ])


def get_owner_payments(user_data):
    """Owner Payments: payment history"""
    soc_id = user_data.get('society_id')
    linked_id = user_data.get('linked_id')
    
    rows = []
    if soc_id and linked_id:
        try:
            payments = query_db("""
                SELECT t.trx_date, COALESCE(t.acc_particulars, 'Payment') as description,
                       t.status, t.amount, t.mode
                FROM transactions t
                JOIN accounts acc ON t.acc_id = acc.id
                WHERE t.entity_id = %s AND t.society_id = %s AND acc.drcr_account = 'Cr'
                ORDER BY t.trx_date DESC
            """, (linked_id, soc_id))
            
            for p in payments:
                rows.append(html.Tr([
                    html.Td(str(p['trx_date'])),
                    html.Td(p['description']),
                    html.Td(dbc.Badge(p['status'], color="success" if p['status'] == 'paid' else "warning")),
                    html.Td(p['mode'] or '-', className="text-capitalize"),
                    html.Td(f"₹{float(p['amount']):,.2f}", className="fw-bold text-success")
                ]))
        except Exception as e:
            print(f"Owner payments error: {e}")
    
    return html.Div([
        html.H3("Payment History", className="mb-4 fw-light"),
        dbc.Card([
            dbc.CardBody([
                dbc.Table([
                    html.Thead(html.Tr([
                        html.Th("Date"), html.Th("Description"), html.Th("Status"),
                        html.Th("Mode"), html.Th("Amount")
                    ])),
                    html.Tbody(rows if rows else [
                        html.Tr([html.Td("No payments found.", colSpan=5, className="text-center text-muted")])
                    ])
                ], bordered=True, hover=True, striped=True, responsive=True, className="mb-0")
            ])
        ], className="shadow-sm")
    ])


def get_owner_charges(user_data):
    """Owner Charges: all maintenance charges and fines"""
    soc_id = user_data.get('society_id')
    linked_id = user_data.get('linked_id')
    
    rows = []
    if soc_id and linked_id:
        try:
            charges = query_db("""
                SELECT acf.start_date, acf.end_date,
                       acf.apt_maintenance_rate, a.apartment_size,
                       (acf.apt_maintenance_rate * a.apartment_size) as total_charge,
                       acf.apt_fine, acf.apt_delay_fine, acf.apt_due_day,
                       acf.apt_status
                FROM apt_charges_fines acf
                JOIN apartments a ON acf.apt_id = a.id
                WHERE acf.apt_id = %s AND acf.society_id = %s
                ORDER BY acf.start_date DESC
            """, (linked_id, soc_id))
            
            for c in charges:
                total = float(c['total_charge']) if c['total_charge'] else 0
                fine = float(c['apt_fine'] or 0) + float(c['apt_delay_fine'] or 0)
                grand = total + fine
                
                rows.append(html.Tr([
                    html.Td(f"{c['start_date']} to {c['end_date']}" if c['end_date'] else str(c['start_date'])),
                    html.Td(f"₹{float(c['apt_maintenance_rate'] or 0):.2f}/sqft x {c['apartment_size']} sqft"),
                    html.Td(f"₹{total:,.2f}"),
                    html.Td(f"₹{fine:,.2f}" if fine > 0 else '-', className="text-danger" if fine > 0 else ""),
                    html.Td(f"₹{grand:,.2f}", className="fw-bold"),
                    html.Td(
                        dbc.Badge("Paid", color="success") if c['apt_status'] else dbc.Badge("Due", color="danger")
                    )
                ]))
        except Exception as e:
            print(f"Owner charges error: {e}")
    
    return html.Div([
        html.H3("Maintenance Charges", className="mb-4 fw-light"),
        dbc.Card([
            dbc.CardBody([
                dbc.Table([
                    html.Thead(html.Tr([
                        html.Th("Period"), html.Th("Rate Calculation"),
                        html.Th("Maintenance"), html.Th("Fine"),
                        html.Th("Total"), html.Th("Status")
                    ])),
                    html.Tbody(rows if rows else [
                        html.Tr([html.Td("No charges found.", colSpan=6, className="text-center text-muted")])
                    ])
                ], bordered=True, hover=True, striped=True, responsive=True, className="mb-0")
            ])
        ], className="shadow-sm")
    ])


def get_owner_events(user_data):
    """Owner Events: view society announcements"""
    return html.Div([
        html.H3("Events & Announcements", className="mb-4 fw-light"),
        dbc.Card([
            dbc.CardBody([
                html.P("No upcoming events or announcements for apartment owners.", className="text-muted text-center mb-0")
            ])
        ], className="shadow-sm")
    ])


def get_owner_settings(user_data):
    """Owner Settings: update profile and password"""
    return html.Div([
        html.H3("Personal Settings", className="mb-4 fw-light"),
        dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            html.Img(
                                src=f"https://ui-avatars.com/api/?name={user_data.get('name','U')[:2]}&size=128&background=90EE90&color=fff",
                                className="rounded-circle mb-3", style={"width": "100px", "height": "100px"}
                            ),
                            html.P("Update Profile Picture", className="small text-muted"),
                            dcc.Upload(
                                id="owner-upload-avatar",
                                children=dbc.Button("Upload Photo", color="outline-success", size="sm"),
                            )
                        ], className="text-center")
                    ], width=4),
                    dbc.Col([
                        dbc.Label("Phone Number"),
                        dbc.Input(id="owner-phone", placeholder="+91-XXXXXXXXXX", className="mb-3"),
                        dbc.Label("Email (read-only)"),
                        dbc.Input(value=user_data.get('email', ''), disabled=True, className="mb-3"),
                    ], width=8)
                ], className="mb-4"),
                html.Hr(),
                html.H5("Change Password", className="mb-3"),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Current Password"),
                        dbc.Input(id="owner-current-pwd", type="password", className="mb-3"),
                    ], width=4),
                    dbc.Col([
                        dbc.Label("New Password"),
                        dbc.Input(id="owner-new-pwd", type="password", className="mb-3"),
                    ], width=4),
                    dbc.Col([
                        dbc.Label("Confirm New Password"),
                        dbc.Input(id="owner-confirm-pwd", type="password", className="mb-3"),
                    ], width=4),
                ]),
                dbc.Button("Save Changes", id="owner-save-settings", color="success")
            ])
        ], className="shadow-sm")
    ])


# ========== VENDOR PORTAL MODULES ==========

def get_vendor_dashboard(user_data):
    """Vendor Dashboard: service info, QR pass, payment summary"""
    soc_id = user_data.get('society_id')
    linked_id = user_data.get('linked_id')
    
    vendor_info = None
    charges_total = 0.0
    payments_total = 0.0
    
    if soc_id and linked_id:
        try:
            vendor_info = query_db(
                "SELECT * FROM vendors WHERE id = %s AND society_id = %s",
                (linked_id, soc_id), one=True
            )
            # Charges
            res = query_db("""
                SELECT COALESCE(SUM(vendor_1day + vendor_7day + vendor_1mth + vendor_fine), 0) as total
                FROM ven_charges_fines
                WHERE ven_id = %s AND society_id = %s
            """, (linked_id, soc_id), one=True)
            charges_total = float(res['total']) if res else 0.0
            
            # Payments
            res = query_db("""
                SELECT COALESCE(SUM(t.amount), 0) as total
                FROM transactions t
                JOIN accounts acc ON t.acc_id = acc.id
                WHERE t.entity_id = %s AND t.society_id = %s
                  AND acc.drcr_account = 'Cr' AND t.status = 'paid'
            """, (linked_id, soc_id), one=True)
            payments_total = float(res['total']) if res else 0.0
        except Exception as e:
            print(f"Vendor dashboard error: {e}")
    
    v_name = vendor_info['name'] if vendor_info else user_data.get('name', 'Vendor')
    v_service = vendor_info['service_type'] if vendor_info else 'N/A'
    v_phone = vendor_info['mobile'] if vendor_info else '-'
    balance_due = charges_total - payments_total
    
    # QR
    qr_data = f"ESTATEHUB|VEN:{linked_id}|SVC:{v_service}|SOC:{soc_id}"
    img = qrcode.make(qr_data, box_size=4, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()
    
    return html.Div([
        html.H3("Vendor Dashboard", className="mb-4 fw-light"),
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.Img(
                                src=f"https://ui-avatars.com/api/?name={v_name[:2]}&size=128&background=FFD700&color=333",
                                className="rounded-circle mb-3", style={"width": "90px", "height": "90px"}
                            ),
                            html.H5(v_name, className="fw-bold mb-1"),
                            html.P(f"Service: {v_service}", className="text-muted mb-0"),
                            html.P(f"Phone: {v_phone}", className="text-muted small"),
                        ], className="text-center")
                    ])
                ], className="shadow-sm h-100")
            ], width=3),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6("Vendor Pass (QR)", className="text-muted mb-3 text-center"),
                        html.Div([
                            html.Img(src=f"data:image/png;base64,{qr_b64}",
                                     style={"width": "160px"}, className="border p-2 rounded")
                        ], className="text-center"),
                        html.P("Show this QR at the gate", className="text-muted small text-center mt-2 mb-0")
                    ])
                ], className="shadow-sm h-100")
            ], width=3),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6("Financial Summary", className="text-muted mb-3"),
                        dbc.Row([
                            dbc.Col([
                                html.Small("Total Charges", className="text-muted d-block"),
                                html.H5(f"₹{charges_total:,.0f}", className="text-danger fw-bold mb-0")
                            ]),
                            dbc.Col([
                                html.Small("Total Paid", className="text-muted d-block"),
                                html.H5(f"₹{payments_total:,.0f}", className="text-success fw-bold mb-0")
                            ]),
                        ], className="mb-3"),
                        html.Hr(),
                        html.Div([
                            html.Small("Balance Due", className="text-muted d-block"),
                            html.H4(f"₹{balance_due:,.0f}",
                                     className=f"fw-bold mb-0 text-{'danger' if balance_due > 0 else 'success'}")
                        ])
                    ])
                ], className="shadow-sm h-100")
            ], width=6),
        ], className="g-3 mb-4"),
        
        dbc.Card([
            dbc.CardHeader(html.H5("Events & Announcements", className="mb-0")),
            dbc.CardBody([
                html.P("No upcoming events or announcements.", className="text-muted text-center mb-0")
            ])
        ], className="shadow-sm")
    ])


def get_vendor_cashbook(user_data):
    """Vendor Cashbook: pass charges, fines, payments with running balance"""
    soc_id = user_data.get('society_id')
    linked_id = user_data.get('linked_id')
    
    rows = []
    if soc_id and linked_id:
        try:
            charges = query_db("""
                SELECT start_date as date,
                       vendor_1day, vendor_7day, vendor_1mth, vendor_fine, ven_status
                FROM ven_charges_fines
                WHERE ven_id = %s AND society_id = %s
                ORDER BY start_date
            """, (linked_id, soc_id))
            
            payments = query_db("""
                SELECT t.trx_date as date, COALESCE(t.acc_particulars, 'Payment') as description,
                       t.amount
                FROM transactions t
                JOIN accounts acc ON t.acc_id = acc.id
                WHERE t.entity_id = %s AND t.society_id = %s
                  AND acc.drcr_account = 'Cr' AND t.status = 'paid'
                ORDER BY t.trx_date
            """, (linked_id, soc_id))
            
            all_entries = []
            for c in charges:
                total_charge = float(c['vendor_1day'] or 0) + float(c['vendor_7day'] or 0) + float(c['vendor_1mth'] or 0)
                fine = float(c['vendor_fine'] or 0)
                if total_charge > 0:
                    all_entries.append((c['date'], 'Pass Charge', total_charge, 0.0))
                if fine > 0:
                    all_entries.append((c['date'], 'Fine', fine, 0.0))
            for p in payments:
                all_entries.append((p['date'], p['description'], 0.0, float(p['amount'])))
            
            all_entries.sort(key=lambda x: x[0] if x[0] else datetime.date.min)
            
            running = 0.0
            for dt, desc, charge, payment in all_entries:
                running += charge - payment
                rows.append(html.Tr([
                    html.Td(str(dt) if dt else '-'),
                    html.Td(desc),
                    html.Td(f"₹{charge:,.2f}" if charge > 0 else '-', className="text-danger" if charge > 0 else ""),
                    html.Td(f"₹{payment:,.2f}" if payment > 0 else '-', className="text-success" if payment > 0 else ""),
                    html.Td(f"₹{running:,.2f}", className=f"fw-bold text-{'danger' if running > 0 else 'success'}")
                ]))
        except Exception as e:
            print(f"Vendor cashbook error: {e}")
    
    return html.Div([
        html.H3("Charges & Payment History", className="mb-4 fw-light"),
        dbc.Card([
            dbc.CardBody([
                dbc.Table([
                    html.Thead(html.Tr([
                        html.Th("Date"), html.Th("Description"),
                        html.Th("Charge (Dr)"), html.Th("Payment (Cr)"), html.Th("Balance")
                    ])),
                    html.Tbody(rows if rows else [
                        html.Tr([html.Td("No records found.", colSpan=5, className="text-center text-muted")])
                    ])
                ], bordered=True, hover=True, striped=True, responsive=True, className="mb-0")
            ])
        ], className="shadow-sm")
    ])


def get_vendor_payments(user_data):
    """Vendor Payments: pass purchase history"""
    soc_id = user_data.get('society_id')
    linked_id = user_data.get('linked_id')
    
    rows = []
    if soc_id and linked_id:
        try:
            payments = query_db("""
                SELECT t.trx_date, COALESCE(t.acc_particulars, 'Payment') as description,
                       t.status, t.amount, t.mode
                FROM transactions t
                JOIN accounts acc ON t.acc_id = acc.id
                WHERE t.entity_id = %s AND t.society_id = %s AND acc.drcr_account = 'Cr'
                ORDER BY t.trx_date DESC
            """, (linked_id, soc_id))
            
            for p in payments:
                rows.append(html.Tr([
                    html.Td(str(p['trx_date'])),
                    html.Td(p['description']),
                    html.Td(dbc.Badge(p['status'], color="success" if p['status'] == 'paid' else "warning")),
                    html.Td(f"₹{float(p['amount']):,.2f}", className="fw-bold text-success")
                ]))
        except Exception as e:
            print(f"Vendor payments error: {e}")
    
    return html.Div([
        html.H3("Payment History", className="mb-4 fw-light"),
        dbc.Card([
            dbc.CardBody([
                dbc.Table([
                    html.Thead(html.Tr([
                        html.Th("Date"), html.Th("Description"),
                        html.Th("Status"), html.Th("Amount")
                    ])),
                    html.Tbody(rows if rows else [
                        html.Tr([html.Td("No payments found.", colSpan=4, className="text-center text-muted")])
                    ])
                ], bordered=True, hover=True, striped=True, responsive=True, className="mb-0")
            ])
        ], className="shadow-sm")
    ])


def get_vendor_charges(user_data):
    """Vendor Charges: pass fees & fines"""
    soc_id = user_data.get('society_id')
    linked_id = user_data.get('linked_id')
    
    rows = []
    if soc_id and linked_id:
        try:
            charges = query_db("""
                SELECT start_date, end_date,
                       vendor_1day, vendor_7day, vendor_1mth, vendor_fine, ven_status
                FROM ven_charges_fines
                WHERE ven_id = %s AND society_id = %s
                ORDER BY start_date DESC
            """, (linked_id, soc_id))
            
            for c in charges:
                desc_parts = []
                if float(c['vendor_1day'] or 0) > 0:
                    desc_parts.append(f"1-Day Pass Fee: ₹{float(c['vendor_1day']):.0f}")
                if float(c['vendor_7day'] or 0) > 0:
                    desc_parts.append(f"7-Day Pass Fee: ₹{float(c['vendor_7day']):.0f}")
                if float(c['vendor_1mth'] or 0) > 0:
                    desc_parts.append(f"1-Month Pass Fee: ₹{float(c['vendor_1mth']):.0f}")
                desc = ', '.join(desc_parts) if desc_parts else 'Pass Charge'
                
                total = float(c['vendor_1day'] or 0) + float(c['vendor_7day'] or 0) + float(c['vendor_1mth'] or 0)
                fine = float(c['vendor_fine'] or 0)
                
                rows.append(html.Tr([
                    html.Td(f"{c['start_date']} to {c['end_date']}" if c['end_date'] else str(c['start_date'])),
                    html.Td(desc),
                    html.Td(f"₹{fine:,.2f}" if fine > 0 else '-', className="text-danger" if fine > 0 else ""),
                    html.Td(f"₹{total + fine:,.2f}", className="fw-bold"),
                    html.Td(
                        dbc.Badge("Paid", color="success") if c['ven_status'] else dbc.Badge("Due", color="danger")
                    )
                ]))
        except Exception as e:
            print(f"Vendor charges error: {e}")
    
    return html.Div([
        html.H3("Charges to Contractor", className="mb-4 fw-light"),
        dbc.Card([
            dbc.CardBody([
                dbc.Table([
                    html.Thead(html.Tr([
                        html.Th("Period"), html.Th("Description"),
                        html.Th("Fine"), html.Th("Total"), html.Th("Status")
                    ])),
                    html.Tbody(rows if rows else [
                        html.Tr([html.Td("No charges found.", colSpan=5, className="text-center text-muted")])
                    ])
                ], bordered=True, hover=True, striped=True, responsive=True, className="mb-0")
            ])
        ], className="shadow-sm")
    ])


def get_vendor_events(user_data):
    """Vendor Events: view society announcements"""
    return html.Div([
        html.H3("Events & Announcements", className="mb-4 fw-light"),
        dbc.Card([
            dbc.CardBody([
                html.P("No upcoming events or announcements for contractors.", className="text-muted text-center mb-0")
            ])
        ], className="shadow-sm")
    ])


def get_vendor_settings(user_data):
    """Vendor Settings: update profile and password"""
    return html.Div([
        html.H3("User Settings", className="mb-4 fw-light"),
        dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            html.Img(
                                src=f"https://ui-avatars.com/api/?name={user_data.get('name','V')[:2]}&size=128&background=FFD700&color=333",
                                className="rounded-circle mb-3", style={"width": "100px", "height": "100px"}
                            ),
                            html.P("Update Profile Picture", className="small text-muted"),
                            dcc.Upload(
                                id="vendor-upload-avatar",
                                children=dbc.Button("Upload Photo", color="outline-warning", size="sm"),
                            )
                        ], className="text-center")
                    ], width=4),
                    dbc.Col([
                        dbc.Label("Phone Number"),
                        dbc.Input(id="vendor-phone", placeholder="+91-XXXXXXXXXX", className="mb-3"),
                        dbc.Label("Email (read-only)"),
                        dbc.Input(value=user_data.get('email', ''), disabled=True, className="mb-3"),
                    ], width=8)
                ], className="mb-4"),
                html.Hr(),
                html.H5("Change Password", className="mb-3"),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Current Password"),
                        dbc.Input(id="vendor-current-pwd", type="password", className="mb-3"),
                    ], width=4),
                    dbc.Col([
                        dbc.Label("New Password"),
                        dbc.Input(id="vendor-new-pwd", type="password", className="mb-3"),
                    ], width=4),
                    dbc.Col([
                        dbc.Label("Confirm New Password"),
                        dbc.Input(id="vendor-confirm-pwd", type="password", className="mb-3"),
                    ], width=4),
                ]),
                dbc.Button("Save Changes", id="vendor-save-settings", color="success")
            ])
        ], className="shadow-sm")
    ])


# ========== SECURITY PORTAL MODULES ==========

def get_security_pass_evaluation(user_data):
    """Security Pass Evaluation: QR scanner + manual evaluation"""
    return html.Div([
        html.H3("Pass Evaluation", className="mb-4 fw-light"),
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("QR Code Scanner", className="mb-0")),
                    dbc.CardBody([
                        html.Div([
                            html.I(className="fa fa-qrcode fa-5x text-muted mb-3"),
                            html.P("Point camera at user's QR code to scan", className="text-muted"),
                            dbc.Button([
                                html.I(className="fa fa-camera me-2"),
                                "Open Camera"
                            ], id="open-camera-btn", color="primary", size="lg", className="mt-2")
                        ], className="text-center p-4 border border-dashed rounded")
                    ])
                ], className="shadow-sm mb-3"),
                
                dbc.Card([
                    dbc.CardHeader(html.H5("Manual Evaluation", className="mb-0")),
                    dbc.CardBody([
                        dbc.Label("Enter Entity ID or Email"),
                        dbc.Input(id="sec-eval-entity", placeholder="e.g. 12 or user@example.com", className="mb-3"),
                        dbc.Label("Entity Type"),
                        dcc.Dropdown(
                            id="sec-eval-type",
                            options=[
                                {"label": "Apartment Owner", "value": "apartment"},
                                {"label": "Vendor / Contractor", "value": "vendor"},
                            ],
                            value="apartment",
                            className="mb-3"
                        ),
                        dbc.Button([
                            html.I(className="fa fa-search me-2"),
                            "Evaluate"
                        ], id="sec-evaluate-btn", color="success", className="w-100"),
                        html.Div(id="sec-evaluation-result", className="mt-3")
                    ])
                ], className="shadow-sm")
            ], width=6),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("Recent Evaluations", className="mb-0")),
                    dbc.CardBody([
                        html.Div(id="sec-recent-evals", children=[
                            html.P("No recent evaluations.", className="text-muted text-center mb-0")
                        ])
                    ])
                ], className="shadow-sm")
            ], width=6)
        ])
    ])


def get_security_attendance(user_data):
    """Security Attendance: clock in/out and shift log"""
    soc_id = user_data.get('society_id')
    linked_id = user_data.get('linked_id')
    
    staff_info = None
    recent_attendance = []
    has_open_entry = False
    
    if soc_id and linked_id:
        try:
            staff_info = query_db(
                "SELECT * FROM security_staff WHERE id = %s AND society_id = %s",
                (linked_id, soc_id), one=True
            )
            # Check for open clock-in (no time_out)
            open_entry = query_db("""
                SELECT id, time_in FROM attendance
                WHERE security_id = %s AND society_id = %s AND time_out IS NULL
                ORDER BY time_in DESC LIMIT 1
            """, (linked_id, soc_id), one=True)
            has_open_entry = open_entry is not None
            
            # Recent attendance
            recent_attendance = query_db("""
                SELECT time_in, time_out FROM attendance
                WHERE security_id = %s AND society_id = %s
                ORDER BY time_in DESC LIMIT 10
            """, (linked_id, soc_id))
        except Exception as e:
            print(f"Security attendance error: {e}")
    
    shift = staff_info['shift'] if staff_info else 'N/A'
    salary = float(staff_info['salary_per_shift']) if staff_info and staff_info['salary_per_shift'] else 0
    staff_name = staff_info['name'] if staff_info else user_data.get('name', 'Guard')
    
    attendance_rows = []
    for a in recent_attendance:
        t_in = a['time_in']
        t_out = a['time_out']
        duration = ''
        if t_in and t_out:
            delta = t_out - t_in
            hours = delta.total_seconds() / 3600
            duration = f"{hours:.1f} hrs"
        
        attendance_rows.append(html.Tr([
            html.Td(str(t_in.strftime('%Y-%m-%d %H:%M')) if t_in else '-'),
            html.Td(str(t_out.strftime('%Y-%m-%d %H:%M')) if t_out else dbc.Badge("Active", color="success")),
            html.Td(duration or '-')
        ]))
    
    return html.Div([
        html.H3("Attendance Relay", className="mb-4 fw-light"),
        dbc.Row([
            # Shift info
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6("Assigned Shift", className="text-muted mb-3"),
                        html.H4(shift, className="fw-bold mb-2"),
                        html.P(f"Salary: ₹{salary:,.0f}/shift", className="text-muted"),
                        html.P(f"Status: {'Active' if staff_info and staff_info['active'] else 'Inactive'}",
                               className=f"text-{'success' if staff_info and staff_info['active'] else 'danger'} fw-bold"),
                    ])
                ], className="shadow-sm mb-3")
            ], width=4),
            
            # Clock in/out
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6("Attendance Action", className="text-muted mb-3 text-center"),
                        html.Div([
                            html.P(staff_name, className="fw-bold h5 mb-3"),
                            dbc.Button([
                                html.I(className="fa fa-sign-out-alt me-2"),
                                "Clock Out"
                            ] if has_open_entry else [
                                html.I(className="fa fa-sign-in-alt me-2"),
                                "Clock In"
                            ],
                                id="sec-clock-btn",
                                color="danger" if has_open_entry else "success",
                                size="lg",
                                className="w-100 py-3"
                            ),
                            html.P(
                                "You are currently clocked in" if has_open_entry else "Not clocked in",
                                className=f"mt-3 text-{'success' if has_open_entry else 'muted'} small"
                            )
                        ], className="text-center")
                    ])
                ], className="shadow-sm mb-3")
            ], width=4),
            
            # Stats
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6("This Month", className="text-muted mb-3"),
                        html.Div([
                            html.Small("Shifts Completed", className="text-muted d-block"),
                            html.H4(str(len([a for a in recent_attendance if a['time_out']])), className="fw-bold text-primary mb-3"),
                            html.Small("Total Earnings", className="text-muted d-block"),
                            html.H4(f"₹{salary * len([a for a in recent_attendance if a['time_out']]):,.0f}", className="fw-bold text-success"),
                        ])
                    ])
                ], className="shadow-sm mb-3")
            ], width=4),
        ], className="g-3 mb-4"),
        
        # Attendance log
        dbc.Card([
            dbc.CardHeader(html.H5("Recent Attendance Log", className="mb-0")),
            dbc.CardBody([
                dbc.Table([
                    html.Thead(html.Tr([
                        html.Th("Clock In"), html.Th("Clock Out"), html.Th("Duration")
                    ])),
                    html.Tbody(attendance_rows if attendance_rows else [
                        html.Tr([html.Td("No attendance records found.", colSpan=3, className="text-center text-muted")])
                    ])
                ], bordered=True, hover=True, striped=True, responsive=True, className="mb-0")
            ])
        ], className="shadow-sm")
    ])


def get_security_events(user_data):
    """Security Events: view announcements"""
    return html.Div([
        html.H3("Events & Announcements", className="mb-4 fw-light"),
        dbc.Card([
            dbc.CardBody([
                html.P("No upcoming events or announcements for security staff.", className="text-muted text-center mb-0")
            ])
        ], className="shadow-sm")
    ])


def get_security_new_receipt(user_data):
    """Security New Receipt: create receipts for on-demand entry"""
    soc_id = user_data.get('society_id')
    
    accounts = []
    if soc_id:
        try:
            accounts = query_db("SELECT id, name, header FROM accounts WHERE society_id = %s AND drcr_account = 'Cr'", (soc_id,))
        except Exception as e:
            print(f"Security receipt accounts error: {e}")
    
    account_options = [{"label": f"{a['name']} - {a['header']}", "value": a['id']} for a in accounts]
    
    return html.Div([
        html.H3("Create New Receipt", className="mb-4 fw-light"),
        dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Credit Account"),
                        dcc.Dropdown(id="sec-receipt-account", options=account_options, placeholder="Select account...", className="mb-3")
                    ], width=12),
                ]),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Description / Particulars"),
                        dbc.Input(id="sec-receipt-desc", placeholder="e.g. On-demand entry fee for visitor", className="mb-3")
                    ], width=8),
                    dbc.Col([
                        dbc.Label("Amount (₹)"),
                        dbc.Input(id="sec-receipt-amount", type="number", placeholder="0.00", className="mb-3")
                    ], width=4),
                ]),
                dbc.Button([
                    html.I(className="fa fa-plus-circle me-2"),
                    "Record Receipt"
                ], id="sec-add-receipt-btn", color="success", size="lg", className="w-100"),
                html.Div(id="sec-receipt-feedback", className="mt-3")
            ])
        ], className="shadow-sm")
    ])


def get_security_users(user_data):
    """Security Users: KPI overview of apartments, vendors, security"""
    soc_id = user_data.get('society_id')
    
    stats = {
        'apt_dues': 0, 'apt_nodues': 0, 'apt_total': 0,
        'ven_dues': 0, 'ven_nodues': 0, 'ven_total': 0,
        'sec_active': 0, 'sec_inactive': 0, 'sec_total': 0,
        'pay_pending': 0, 'pay_verified': 0, 'pay_total': 0,
    }
    
    if soc_id:
        try:
            res = query_db("SELECT count(*) as cnt FROM apartments WHERE society_id = %s AND active = TRUE", (soc_id,), one=True)
            stats['apt_total'] = res['cnt'] if res else 0
            res = query_db("SELECT count(DISTINCT apt_id) as cnt FROM apt_charges_fines WHERE society_id = %s AND apt_status = FALSE", (soc_id,), one=True)
            stats['apt_dues'] = res['cnt'] if res else 0
            stats['apt_nodues'] = stats['apt_total'] - stats['apt_dues']

            res = query_db("SELECT count(*) as cnt FROM vendors WHERE society_id = %s AND active = TRUE", (soc_id,), one=True)
            stats['ven_total'] = res['cnt'] if res else 0
            res = query_db("SELECT count(DISTINCT ven_id) as cnt FROM ven_charges_fines WHERE society_id = %s AND ven_status = FALSE", (soc_id,), one=True)
            stats['ven_dues'] = res['cnt'] if res else 0
            stats['ven_nodues'] = stats['ven_total'] - stats['ven_dues']

            res = query_db("SELECT count(*) as cnt FROM security_staff WHERE society_id = %s AND active = TRUE", (soc_id,), one=True)
            stats['sec_active'] = res['cnt'] if res else 0
            res = query_db("SELECT count(*) as cnt FROM security_staff WHERE society_id = %s AND active = FALSE", (soc_id,), one=True)
            stats['sec_inactive'] = res['cnt'] if res else 0
            stats['sec_total'] = stats['sec_active'] + stats['sec_inactive']

            res = query_db("SELECT count(*) as cnt FROM transactions WHERE society_id = %s AND status = 'pending'", (soc_id,), one=True)
            stats['pay_pending'] = res['cnt'] if res else 0
            res = query_db("SELECT count(*) as cnt FROM transactions WHERE society_id = %s AND status = 'paid'", (soc_id,), one=True)
            stats['pay_verified'] = res['cnt'] if res else 0
            stats['pay_total'] = stats['pay_pending'] + stats['pay_verified']
        except Exception as e:
            print(f"Security users KPI error: {e}")
    
    return html.Div([
        html.H3("Users Overview", className="mb-4 fw-light"),
        dbc.Row([
            dbc.Col(kpi_card("Apartment Owners", "fa-building", [
                ("With Dues", stats['apt_dues'], "danger"),
                ("No Dues", stats['apt_nodues'], "success"),
                ("Total", stats['apt_total'], "primary")
            ]), width=6),
            dbc.Col(kpi_card("Security Staff", "fa-shield-alt", [
                ("Inactive", stats['sec_inactive'], "danger"),
                ("Active", stats['sec_active'], "success"),
                ("Total", stats['sec_total'], "primary")
            ]), width=6),
        ], className="g-3 mb-3"),
        dbc.Row([
            dbc.Col(kpi_card("Utility Contractors", "fa-tools", [
                ("With Dues", stats['ven_dues'], "danger"),
                ("No Dues", stats['ven_nodues'], "success"),
                ("Total", stats['ven_total'], "primary")
            ]), width=6),
            dbc.Col(kpi_card("Payments", "fa-credit-card", [
                ("Pending", stats['pay_pending'], "warning"),
                ("Verified", stats['pay_verified'], "success"),
                ("Total", stats['pay_total'], "primary")
            ]), width=6),
        ], className="g-3")
    ])


def get_security_settings(user_data):
    """Security Settings: update profile and password"""
    return html.Div([
        html.H3("User Settings", className="mb-4 fw-light"),
        dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            html.Img(
                                src=f"https://ui-avatars.com/api/?name={user_data.get('name','S')[:2]}&size=128&background=F08080&color=fff",
                                className="rounded-circle mb-3", style={"width": "100px", "height": "100px"}
                            ),
                            html.P("Update Profile Picture", className="small text-muted"),
                            dcc.Upload(
                                id="sec-upload-avatar",
                                children=dbc.Button("Upload Photo", color="outline-danger", size="sm"),
                            )
                        ], className="text-center")
                    ], width=4),
                    dbc.Col([
                        dbc.Label("Phone Number"),
                        dbc.Input(id="sec-phone", placeholder="+91-XXXXXXXXXX", className="mb-3"),
                        dbc.Label("Email (read-only)"),
                        dbc.Input(value=user_data.get('email', ''), disabled=True, className="mb-3"),
                    ], width=8)
                ], className="mb-4"),
                html.Hr(),
                html.H5("Change Password", className="mb-3"),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Current Password"),
                        dbc.Input(id="sec-current-pwd", type="password", className="mb-3"),
                    ], width=4),
                    dbc.Col([
                        dbc.Label("New Password"),
                        dbc.Input(id="sec-new-pwd", type="password", className="mb-3"),
                    ], width=4),
                    dbc.Col([
                        dbc.Label("Confirm New Password"),
                        dbc.Input(id="sec-confirm-pwd", type="password", className="mb-3"),
                    ], width=4),
                ]),
                dbc.Button("Save Changes", id="sec-save-settings", color="success")
            ])
        ], className="shadow-sm")
    ])


# ========== AUTHENTICATION UI ==========

def get_pin_pad():
    """PIN pad component"""
    return html.Div([
        dcc.Store(id='pin-store', data=''),
        html.H5("Enter PIN", className="text-center mb-3"),
        html.Div(id='pin-display', className="text-center mb-3 h3", style={'letterSpacing': '10px'}, children=""),
        dbc.Row([
            dbc.Col(dbc.Button(str(i), id={'type': 'pin-btn', 'index': i}, color="light", 
                              className="w-100 mb-2 py-3 btn-lg"), width=4)
            for i in range(1, 10)
        ], className="g-2"),
        dbc.Row([
            dbc.Col(dbc.Button("CLR", id={'type': 'pin-btn', 'index': 'clear'}, color="danger", 
                              className="w-100 py-3"), width=4),
            dbc.Col(dbc.Button("0", id={'type': 'pin-btn', 'index': 0}, color="light", 
                              className="w-100 py-3"), width=4),
            dbc.Col(dbc.Button(html.I(className="fa fa-backspace"), id={'type': 'pin-btn', 'index': 'back'}, 
                              color="warning", className="w-100 py-3"), width=4),
        ], className="g-2 mt-1")
    ])

def get_pattern_pad():
    """9-dot pattern component"""
    return html.Div([
        dcc.Store(id='pattern-store', data=[]),
        html.H5("Draw Pattern", className="text-center mb-3"),
        html.Div([
            html.Div([
                html.Button(
                    id={'type': 'dot-btn', 'index': i},
                    className="rounded-circle border border-2",
                    style={'width': '60px', 'height': '60px', 'margin': '15px', 'backgroundColor': '#f8f9fa', 'border': '2px solid #dee2e6'}
                ) for i in range(1, 10)
            ], style={'display': 'grid', 'gridTemplateColumns': 'repeat(3, 1fr)', 'width': '270px', 'margin': 'auto'})
        ]),
        dbc.Button("Reset Pattern", id="reset-pattern", color="link", size="sm", className="mt-2 w-100")
    ])

def render_secondary_login(society_id, is_master=False):
    """Secondary login page with password/PIN/pattern"""
    title = "Master Admin Login" if is_master else "Society Login"
    email_prefill = "master@estatehub.com" if is_master else ""
    
    return dbc.Container([
        html.Div([
            html.Div([
                html.Img(src="/assets/logo.svg", height="60px", className="mb-3"),
                html.H3(title, className="text-center mb-4 fw-light")
            ], className="text-center"),
            
            dbc.Input(id="login-email", placeholder="Email Address", value=email_prefill, className="mb-3", size="lg"),
            
            dbc.Tabs([
                dbc.Tab(label="Password", tab_id="pwd", children=[
                    dbc.Input(id="login-password", type="password", placeholder="Enter Password", className="mt-3", size="lg")
                ]),
                dbc.Tab(label="PIN", tab_id="pin", children=[
                    html.Div(get_pin_pad(), className="mt-3")
                ]),
                dbc.Tab(label="9-Dot Pattern", tab_id="pattern", children=[
                    html.Div(get_pattern_pad(), className="mt-3")
                ]),
            ], id="login-method-tabs", active_tab="pwd", className="mb-3"),
            
            dbc.Button([
                html.I(className="fa fa-sign-in-alt me-2"),
                "Verify & Login"
            ], id="final-login-btn", color="success", className="mt-3 w-100", size="lg"),
            
            dcc.Store(id="selected-soc-id", data=society_id),
            html.Div(id="login-error", className="mt-3"),
            
            html.Hr(className="my-4"),
            dbc.Button("← Back to Society Selection", id="back-to-stage-1", color="link", size="sm", className="w-100")
        ], style={"maxWidth": "500px", "margin": "80px auto", "padding": "50px"}, 
        className="bg-white shadow-lg rounded")
    ], fluid=True, style={"minHeight": "100vh", "backgroundColor": "#f5f7fa", "display": "flex", "alignItems": "center"})

# ========== MAIN LAYOUT ==========

app.layout = html.Div([
    dcc.Location(id="url", refresh=True),
    dcc.Store(id="user-session", storage_type="session"),
    dcc.Store(id="auth-stage", data=1),
    html.Div(id="page-content")
])

# ========== CALLBACKS ==========

# Main routing callback
@app.callback(
    Output("page-content", "children"),
    Input("url", "pathname"),
    State("user-session", "data"),
    State("auth-stage", "data")
)
def display_page(pathname, session_data, auth_stage):
    """Main page routing"""
    
    # Check database connection
    if not db_pool:
        return dbc.Container([
            html.Div([
                html.I(className="fa fa-wifi-slash text-danger mb-4", style={'fontSize': '4rem'}),
                html.H3("Network Unreachable", className="mb-3"),
                html.P("Unable to connect to WeaveEstateHub database servers.", className="text-muted"),
                dbc.Button([
                    html.I(className="fa fa-sync me-2"),
                    "Retry Connection"
                ], id="retry-db", color="primary", size="lg", className="mt-3")
            ], className="text-center p-5 shadow-lg mt-5 bg-white rounded", style={"maxWidth": "500px", "margin": "100px auto"})
        ], fluid=True, style={"minHeight": "100vh", "backgroundColor": "#f5f7fa", "display": "flex", "alignItems": "center"})
    
    # Stage 1: Society Selection
    if not session_data and auth_stage == 1:
        try:
            societies = query_db("SELECT id, name FROM societies ORDER BY name")
            
            if not societies:
                # No societies - go to master admin login
                return render_secondary_login(society_id=None, is_master=True)
            
            options = [{"label": s['name'], "value": s['id']} for s in societies]
            
            return dbc.Container([
                html.Div([
                    html.Div([
                        html.Img(src="/assets/logo.svg", height="80px", className="mb-4"),
                        html.H2("EstateHub", className="text-center mb-2 fw-bold"),
                        html.P("Estate Management System", className="text-center text-muted mb-4")
                    ], className="text-center"),
                    
                    html.Label("Select Your Society", className="fw-bold mb-2"),
                    dcc.Dropdown(
                        id="society-select", 
                        options=options, 
                        placeholder="Choose your estate community...",
                        className="mb-4"
                    ),
                    dbc.Button([
                        "Proceed to Login ",
                        html.I(className="fa fa-arrow-right ms-2")
                    ], id="to-stage-2", color="primary", className="w-100", size="lg")
                ], style={"maxWidth": "500px", "margin": "100px auto", "padding": "50px"}, 
                className="bg-white shadow-lg rounded")
            ], fluid=True, style={"minHeight": "100vh", "backgroundColor": "#f5f7fa", "display": "flex", "alignItems": "center"})
            
        except Exception as e:
            return html.Div(f"Database Error: {str(e)}", className="text-center text-danger p-5")
    
    # Authenticated user - show portal
    if session_data:
        role = session_data.get('role')
        
        # Admin route mapping
        if role == 'admin':
            if pathname == '/cashbook':
                content = get_cashbook(session_data)
            elif pathname == '/receipts':
                content = get_receipts(session_data)
            elif pathname == '/expenses':
                content = get_expenses(session_data)
            elif pathname == '/enroll':
                content = get_enrollment(session_data)
            elif pathname == '/users':
                content = get_users(session_data)
            elif pathname == '/events':
                content = get_events(session_data)
            elif pathname == '/evaluate-pass':
                content = get_evaluate_pass(session_data)
            elif pathname == '/customize':
                content = get_customize(session_data)
            elif pathname == '/settings':
                content = get_settings(session_data)
            else:
                content = get_admin_dashboard(session_data)
                pathname = '/admin-portal'
        
        # Apartment Owner route mapping
        elif role == 'apartment':
            if pathname == '/owner-cashbook':
                content = get_owner_cashbook(session_data)
            elif pathname == '/payments':
                content = get_owner_payments(session_data)
            elif pathname == '/charges':
                content = get_owner_charges(session_data)
            elif pathname == '/owner-events':
                content = get_owner_events(session_data)
            elif pathname == '/owner-settings':
                content = get_owner_settings(session_data)
            else:
                content = get_owner_dashboard(session_data)
                pathname = '/owner-portal'
        
        # Vendor route mapping
        elif role == 'vendor':
            if pathname == '/vendor-cashbook':
                content = get_vendor_cashbook(session_data)
            elif pathname == '/vendor-payments':
                content = get_vendor_payments(session_data)
            elif pathname == '/vendor-charges':
                content = get_vendor_charges(session_data)
            elif pathname == '/vendor-events':
                content = get_vendor_events(session_data)
            elif pathname == '/vendor-settings':
                content = get_vendor_settings(session_data)
            else:
                content = get_vendor_dashboard(session_data)
                pathname = '/vendor-portal'
        
        # Security route mapping
        elif role == 'security':
            if pathname == '/attendance':
                content = get_security_attendance(session_data)
            elif pathname == '/security-events':
                content = get_security_events(session_data)
            elif pathname == '/security-receipt':
                content = get_security_new_receipt(session_data)
            elif pathname == '/security-users':
                content = get_security_users(session_data)
            elif pathname == '/security-settings':
                content = get_security_settings(session_data)
            else:
                content = get_security_pass_evaluation(session_data)
                pathname = '/pass-evaluation'
        
        else:
            content = html.Div([
                html.H4("Unknown role", className="text-center mt-5 text-danger"),
            ])
        
        return render_app_shell(session_data, content, pathname)
    
    return dash.no_update

# Society selection to login
@app.callback(
    Output("page-content", "children", allow_duplicate=True),
    Input("to-stage-2", "n_clicks"),
    State("society-select", "value"),
    prevent_initial_call=True
)
def go_to_login(n, soc_id):
    """Move from society selection to login"""
    if n and soc_id:
        return render_secondary_login(soc_id)
    return dash.no_update

# Back to society selection
@app.callback(
    Output("page-content", "children", allow_duplicate=True),
    Input("back-to-stage-1", "n_clicks"),
    prevent_initial_call=True
)
def back_to_society(n):
    """Go back to society selection by re-rendering page"""
    if n:
        try:
            societies = query_db("SELECT id, name FROM societies ORDER BY name")
            if not societies:
                return render_secondary_login(society_id=None, is_master=True)
            options = [{"label": s['name'], "value": s['id']} for s in societies]
            return dbc.Container([
                html.Div([
                    html.Div([
                        html.Img(src="/assets/logo.svg", height="80px", className="mb-4"),
                        html.H2("EstateHub", className="text-center mb-2 fw-bold"),
                        html.P("Estate Management System", className="text-center text-muted mb-4")
                    ], className="text-center"),
                    html.Label("Select Your Society", className="fw-bold mb-2"),
                    dcc.Dropdown(id="society-select", options=options, placeholder="Choose your estate community...", className="mb-4"),
                    dbc.Button(["Proceed to Login ", html.I(className="fa fa-arrow-right ms-2")],
                              id="to-stage-2", color="primary", className="w-100", size="lg")
                ], style={"maxWidth": "500px", "margin": "100px auto", "padding": "50px"},
                className="bg-white shadow-lg rounded")
            ], fluid=True, style={"minHeight": "100vh", "backgroundColor": "#f5f7fa", "display": "flex", "alignItems": "center"})
        except Exception:
            return dash.no_update
    return dash.no_update

# PIN pad callbacks
@app.callback(
    Output("pin-store", "data"),
    Output("pin-display", "children"),
    Input({'type': 'pin-btn', 'index': ALL}, 'n_clicks'),
    State("pin-store", "data"),
    prevent_initial_call=True
)
def update_pin(n_clicks, current_pin):
    """Handle PIN pad input"""
    ctx = callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update
    
    btn_id = ctx.triggered[0]['prop_id'].split('.')[0]
    import json
    btn_index = json.loads(btn_id)['index']
    
    if btn_index == 'clear':
        new_pin = ''
    elif btn_index == 'back':
        new_pin = current_pin[:-1] if current_pin else ''
    else:
        if len(current_pin) < 6:  # Max 6 digits
            new_pin = current_pin + str(btn_index)
        else:
            new_pin = current_pin
    
    display = "●" * len(new_pin)
    return new_pin, display

# Pattern pad callbacks
@app.callback(
    Output('pattern-store', 'data'),
    Output({'type': 'dot-btn', 'index': ALL}, 'style'),
    Input({'type': 'dot-btn', 'index': ALL}, 'n_clicks'),
    Input('reset-pattern', 'n_clicks'),
    State('pattern-store', 'data'),
    prevent_initial_call=True
)
def update_pattern(n_clicks_list, reset_clicks, current_pattern):
    """Handle pattern pad input"""
    ctx = callback_context
    trigger = ctx.triggered[0]['prop_id']
    
    if "reset-pattern" in trigger:
        new_styles = [{'width': '60px', 'height': '60px', 'margin': '15px', 
                      'backgroundColor': '#f8f9fa', 'border': '2px solid #dee2e6'} for _ in range(9)]
        return [], new_styles
    
    import json
    btn_id_dict = json.loads(trigger.split('.')[0])
    idx = btn_id_dict['index']
    
    if idx not in current_pattern:
        current_pattern.append(idx)
    
    new_styles = []
    for i in range(1, 10):
        if i in current_pattern:
            color = "#18bc9c"
            border_color = "#18bc9c"
        else:
            color = "#f8f9fa"
            border_color = "#dee2e6"
        new_styles.append({'width': '60px', 'height': '60px', 'margin': '15px', 
                          'backgroundColor': color, 'border': f'3px solid {border_color}'})
    
    return current_pattern, new_styles

# Login callback
@app.callback(
    Output("user-session", "data"),
    Output("url", "pathname"),
    Output("login-error", "children"),
    Input("final-login-btn", "n_clicks"),
    State("login-email", "value"),
    State("login-password", "value"),
    State("pin-store", "data"),
    State("pattern-store", "data"),
    State("login-method-tabs", "active_tab"),
    State("selected-soc-id", "data"),
    prevent_initial_call=True
)
def process_login(n, email, pwd, pin, pattern, method, soc_id):
    """Process login with password/PIN/pattern"""
    if not n:
        return dash.no_update, dash.no_update, dash.no_update
    
    # Master admin check
    if email == "master@estatehub.com" and pwd == os.getenv("MASTER_ADMIN_PASSWORD"):
        user_data = {
            "role": "admin",
            "name": "Master Admin",
            "society_name": "WeaveEstateHub",
            "society_id": None,
            "user_id": 0
        }
        return user_data, "/admin-portal", ""
    
    # Regular user authentication
    if not soc_id:
        return dash.no_update, dash.no_update, dbc.Alert("Invalid society selection", color="danger")
    
    try:
        # Query user
        user = query_db("""
            SELECT u.*, s.name as soc_name 
            FROM users u 
            JOIN societies s ON u.society_id = s.id 
            WHERE u.email = %s AND u.society_id = %s
        """, (email, soc_id), one=True)
        
        if not user:
            return dash.no_update, dash.no_update, dbc.Alert("Invalid credentials", color="danger")
        
        # Verify credentials
        auth_success = False
        if method == "pwd" and pwd:
            auth_success = check_password_hash(user['password_hash'], pwd)
        elif method == "pin" and pin:
            if user['pin_hash']:
                auth_success = check_password_hash(user['pin_hash'], pin)
        elif method == "pattern" and pattern:
            if user['pattern_hash']:
                pattern_str = ','.join(map(str, pattern))
                auth_success = check_password_hash(user['pattern_hash'], pattern_str)
        
        if not auth_success:
            return dash.no_update, dash.no_update, dbc.Alert("Invalid credentials", color="danger")
        
        # Create JWT token
        token = jwt.encode({
            'user_id': user['id'],
            'role': user['role'],
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }, os.getenv("JWT_SECRET_KEY"), algorithm="HS256")
        
        # Create session data
        user_payload = {
            "user_id": user['id'],
            "token": token,
            "role": user['role'],
            "society_id": soc_id,
            "society_name": user['soc_name'],
            "linked_id": user['linked_id'],
            "email": email,
            "name": email.split('@')[0].capitalize()
        }
        
        # Route to appropriate portal
        role_paths = {
            'admin': '/admin-portal',
            'apartment': '/owner-portal',
            'vendor': '/vendor-portal',
            'security': '/pass-evaluation'
        }
        
        return user_payload, role_paths.get(user['role'], '/'), ""
        
    except Exception as e:
        print(f"Login error: {e}")
        return dash.no_update, dash.no_update, dbc.Alert(f"Error: {str(e)}", color="danger")

# QR code generation
@app.callback(
    Output("qr-container", "children"),
    Input("user-avatar", "n_clicks"),
    State("user-session", "data"),
    prevent_initial_call=True
)
def generate_user_qr(n, user_data):
    """Generate QR code for user"""
    if not user_data:
        return ""
    
    qr_data = f"ESTATEHUB|USER:{user_data.get('user_id', 'NA')}|ROLE:{user_data.get('role', 'NA')}|SOC:{user_data.get('society_id', 'NA')}"
    img = qrcode.make(qr_data, box_size=5, border=2)
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return html.Img(src=f"data:image/png;base64,{img_str}", style={"width": "180px"}, className="border p-2 rounded")

# Logout callback
@app.callback(
    Output("user-session", "data", allow_duplicate=True),
    Output("url", "pathname", allow_duplicate=True),
    Input("logout-btn", "n_clicks"),
    prevent_initial_call=True
)
def logout(n):
    """Clear session and logout"""
    if n:
        return None, "/"
    return dash.no_update, dash.no_update

# Security: Clock In/Out callback
@app.callback(
    Output("url", "pathname", allow_duplicate=True),
    Input("sec-clock-btn", "n_clicks"),
    State("user-session", "data"),
    prevent_initial_call=True
)
def security_clock_action(n, session_data):
    """Handle security staff clock in/out"""
    if not n or not session_data:
        return dash.no_update
    
    soc_id = session_data.get('society_id')
    linked_id = session_data.get('linked_id')
    if not soc_id or not linked_id:
        return dash.no_update
    
    try:
        # Check if there's an open clock-in
        open_entry = query_db("""
            SELECT id FROM attendance
            WHERE security_id = %s AND society_id = %s AND time_out IS NULL
            ORDER BY time_in DESC LIMIT 1
        """, (linked_id, soc_id), one=True)
        
        if open_entry:
            # Clock out
            execute_db("""
                UPDATE attendance SET time_out = NOW()
                WHERE id = %s
            """, (open_entry['id'],))
        else:
            # Clock in
            execute_db("""
                INSERT INTO attendance (society_id, security_id, time_in)
                VALUES (%s, %s, NOW())
            """, (soc_id, linked_id))
    except Exception as e:
        print(f"Clock action error: {e}")
    
    return "/attendance"

# Security: Pass Evaluation callback
@app.callback(
    Output("sec-evaluation-result", "children"),
    Input("sec-evaluate-btn", "n_clicks"),
    State("sec-eval-entity", "value"),
    State("sec-eval-type", "value"),
    State("user-session", "data"),
    prevent_initial_call=True
)
def evaluate_pass(n, entity_input, entity_type, session_data):
    """Evaluate pass for an entity"""
    if not n or not entity_input or not session_data:
        return dash.no_update
    
    soc_id = session_data.get('society_id')
    if not soc_id:
        return dbc.Alert("No society context", color="danger")
    
    try:
        if entity_type == 'apartment':
            # Try by ID or email
            if entity_input.isdigit():
                apt = query_db("SELECT * FROM apartments WHERE id = %s AND society_id = %s", (int(entity_input), soc_id), one=True)
            else:
                user = query_db("SELECT linked_id FROM users WHERE email = %s AND society_id = %s AND role = 'apartment'", (entity_input, soc_id), one=True)
                apt = query_db("SELECT * FROM apartments WHERE id = %s AND society_id = %s", (user['linked_id'], soc_id), one=True) if user else None
            
            if not apt:
                return dbc.Alert("Apartment owner not found.", color="warning")
            
            # Check dues
            dues = query_db("""
                SELECT count(*) as cnt FROM apt_charges_fines
                WHERE apt_id = %s AND society_id = %s AND apt_status = FALSE
            """, (apt['id'], soc_id), one=True)
            has_dues = dues['cnt'] > 0 if dues else False
            
            if has_dues:
                return dbc.Alert([
                    html.H4("FAIL", className="alert-heading"),
                    html.P(f"Owner: {apt['owner_name']} | Flat: {apt['flat_number']}"),
                    html.P(f"Reason: Outstanding dues ({dues['cnt']} unpaid charges)")
                ], color="danger")
            else:
                # Log gate access
                execute_db("INSERT INTO gate_access (society_id, role, entity_id, time_in) VALUES (%s, 'A', %s, NOW())", (soc_id, apt['id']))
                return dbc.Alert([
                    html.H4("PASS", className="alert-heading"),
                    html.P(f"Owner: {apt['owner_name']} | Flat: {apt['flat_number']}"),
                    html.P("No outstanding dues. Entry granted.")
                ], color="success")
        
        elif entity_type == 'vendor':
            if entity_input.isdigit():
                ven = query_db("SELECT * FROM vendors WHERE id = %s AND society_id = %s", (int(entity_input), soc_id), one=True)
            else:
                user = query_db("SELECT linked_id FROM users WHERE email = %s AND society_id = %s AND role = 'vendor'", (entity_input, soc_id), one=True)
                ven = query_db("SELECT * FROM vendors WHERE id = %s AND society_id = %s", (user['linked_id'], soc_id), one=True) if user else None
            
            if not ven:
                return dbc.Alert("Vendor not found.", color="warning")
            
            dues = query_db("""
                SELECT count(*) as cnt FROM ven_charges_fines
                WHERE ven_id = %s AND society_id = %s AND ven_status = FALSE
            """, (ven['id'], soc_id), one=True)
            has_dues = dues['cnt'] > 0 if dues else False
            
            if has_dues:
                return dbc.Alert([
                    html.H4("FAIL", className="alert-heading"),
                    html.P(f"Vendor: {ven['name']} | Service: {ven['service_type']}"),
                    html.P(f"Reason: Outstanding dues ({dues['cnt']} unpaid charges)")
                ], color="danger")
            else:
                execute_db("INSERT INTO gate_access (society_id, role, entity_id, time_in) VALUES (%s, 'V', %s, NOW())", (soc_id, ven['id']))
                return dbc.Alert([
                    html.H4("PASS", className="alert-heading"),
                    html.P(f"Vendor: {ven['name']} | Service: {ven['service_type']}"),
                    html.P("No outstanding dues. Entry granted.")
                ], color="success")
    
    except Exception as e:
        print(f"Evaluation error: {e}")
        return dbc.Alert(f"Error: {str(e)}", color="danger")
    
    return dbc.Alert("Entity not found.", color="warning")

# ========== RUN SERVER ==========

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🏢 WeaveEstateHub ERP - Starting Application")
    print("="*60)
    
    if db_pool:
        print("✅ Database: Connected")
        try:
            result = query_db("SELECT COUNT(*) as cnt FROM societies", one=True)
            print(f"✅ Societies: {result['cnt']} found")
        except:
            print("⚠️  Note: Run database initialization if tables don't exist")
    else:
        print("❌ Database: Connection failed")
    
    print("="*60)
    print("🚀 Starting Dash server on port 8050...")
    print("="*60 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=8050)
