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
from dash import dcc, html, Input, Output, State, ALL, callback_context
import dash_bootstrap_components as dbc
import pandas as pd

# Load environment variables
load_dotenv()

# Database Connection Pool
try:
    db_pool = psycopg2.pool.SimpleConnectionPool(
        1, 10, dsn=os.getenv("DATABASE_URL")
    )
except Exception as e:
    db_pool = None

server = Flask(__name__)
server.secret_key = os.getenv("FLASK_SECRET_KEY")

app = dash.Dash(
    __name__,
    server=server,
    external_stylesheets=[dbc.themes.FLATLY, dbc.icons.FONT_AWESOME],
    suppress_callback_exceptions=True
)

# --- Database Helpers ---
def query_db(query, params=(), one=False):
    if not db_pool:
        raise Exception("Database connection failed")
    conn = db_pool.getconn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(query, params)
            rv = cur.fetchall()
            conn.commit()
            return (rv[0] if rv else None) if one else rv
    finally:
        db_pool.putconn(conn)

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

# --- UI Components for Master Layout ---

def get_header(user_data):
    role = user_data.get('role', 'admin')
    config = ROLE_CONFIG.get(role, ROLE_CONFIG['admin'])
    society_name = user_data.get('society_name', 'WeaveEstateHub')
    
    return html.Header([
        dbc.Row([
            dbc.Col(html.Div([
                html.Img(src="/assets/logo.png", height="40px", className="me-2"),
                html.Span(society_name, className="fw-bold h5 mb-0")
            ], className="d-flex align-items-center"), width=4),
            
            dbc.Col(html.H4(config['label'], className="text-center mb-0 fw-light"), width=4),
            
            dbc.Col(html.Div([
                html.Img(
                    id="user-avatar",
                    src="https://via.placeholder.com/256", 
                    className="rounded-circle shadow-sm cursor-pointer",
                    style={"height": "45px", "width": "45px", "cursor": "pointer"}
                ),
                dbc.Popover([
                    dbc.PopoverHeader("User Session"),
                    dbc.PopoverBody([
                        html.Div(id="qr-container", className="text-center mb-3"),
                        dbc.Button("Logout", id="logout-btn", color="danger", size="sm", className="w-100")
                    ])
                ], id="avatar-popover", target="user-avatar", trigger="click", placement="bottom")
            ], className="d-flex justify-content-end align-items-center"), width=4),
        ], className="align-items-center w-100 g-0 px-3")
    ], style={"backgroundColor": config['color'], "height": "70px", "display": "flex", "alignItems": "center", "borderBottom": "1px solid #ddd"})

def get_sidebar(role):
    config = ROLE_CONFIG.get(role, ROLE_CONFIG['admin'])
    nav_items = [
        dbc.NavLink([
            html.I(className=f"fa {icon} me-3"),
            html.Span(name)
        ], href=path, active="exact", className="py-3 px-4 text-dark border-bottom")
        for name, path, icon in config['tabs']
    ]
    
    return html.Div(
        [html.Div("Navigation", className="p-3 fw-bold text-muted small text-uppercase")] + nav_items,
        style={
            "width": "260px", "height": "calc(100vh - 70px)", "position": "fixed",
            "top": "70px", "left": 0, "backgroundColor": "#f8f9fa", "borderRight": "1px solid #ddd",
            "overflowY": "auto"
        }
    )

def render_app_shell(user_data, content):
    return html.Div([
        get_header(user_data),
        get_sidebar(user_data['role']),
        html.Div([
            dbc.Breadcrumb(id="nav-crumb", className="mb-4 bg-transparent p-0"),
            content,
            html.Footer("© 2025 WeaveEstateHub - Powered by ApexWeave", className="text-center text-muted mt-5 py-3 border-top")
        ], style={"marginLeft": "260px", "padding": "30px", "minHeight": "calc(100vh - 70px)"})
    ])


# --- Admin Dashboard Modules ---

def kpi_card(title, icon, metrics):
    return dbc.Card([
        dbc.CardBody([
            html.Div([
                html.H6(title, className="card-title text-muted mb-0", style={"fontSize": "0.85rem"}),
                html.I(className=f"fa {icon} text-muted opacity-50")
            ], className="d-flex justify-content-between align-items-center mb-3"),
            dbc.Row([
                dbc.Col([
                    html.Small(label, className="text-muted d-block", style={"fontSize": "0.7rem"}),
                    html.H4(str(value), className=f"text-{color} fw-bold mb-0")
                ]) for label, value, color in metrics
            ], className="g-1")
        ])
    ], className="shadow-sm border-0 h-100")

def get_admin_dashboard(user_data):
    soc_id = user_data.get('society_id')
    stats = {
        'apt_dues': 0, 'apt_nodues': 0, 'apt_total': 0,
        'ven_dues': 0, 'ven_nodues': 0, 'ven_total': 0,
        'sec_total': 0, 'balance': 0.0,
        'rec_p': 0, 'rec_v': 0,
        'exp_p': 0, 'exp_v': 0
    }

    if soc_id:
        try:
            # Apartment Metrics
            res = query_db("SELECT count(*) FROM apartments WHERE society_id = %s", (soc_id,), one=True)
            stats['apt_total'] = res[0] if res else 0
            res = query_db("SELECT count(*) FROM apt_charges_fines WHERE society_id = %s AND apt_status = FALSE", (soc_id,), one=True)
            stats['apt_dues'] = res[0] if res else 0
            stats['apt_nodues'] = stats['apt_total'] - stats['apt_dues']

            # Vendor Metrics
            res = query_db("SELECT count(*) FROM vendors WHERE society_id = %s", (soc_id,), one=True)
            stats['ven_total'] = res[0] if res else 0
            res = query_db("SELECT count(*) FROM ven_charges_fines WHERE society_id = %s AND ven_status = FALSE", (soc_id,), one=True)
            stats['ven_dues'] = res[0] if res else 0
            stats['ven_nodues'] = stats['ven_total'] - stats['ven_dues']

            # Security Metrics
            res = query_db("SELECT count(*) FROM security_staff WHERE society_id = %s AND active = TRUE", (soc_id,), one=True)
            stats['sec_total'] = res[0] if res else 0

            # Financials
            res = query_db("""
                SELECT SUM(CASE WHEN a.drcr_account = 'Cr' THEN t.amount ELSE -t.amount END)
                FROM transactions t JOIN accounts a ON t.acc_id = a.id
                WHERE t.society_id = %s AND t.status = 'paid'
            """, (soc_id,), one=True)
            stats['balance'] = float(res[0]) if res and res[0] is not None else 0.0

            # Receipts/Expenses counts
            res = query_db("""
                SELECT a.drcr_account, t.status, count(*) 
                FROM transactions t JOIN accounts a ON t.acc_id = a.id 
                WHERE t.society_id = %s GROUP BY a.drcr_account, t.status
            """, (soc_id,))
            for row in res:
                if row['drcr_account'] == 'Cr':
                    if row['status'] == 'pending': stats['rec_p'] = row['count']
                    elif row['status'] == 'paid': stats['rec_v'] = row['count']
                else:
                    if row['status'] == 'pending': stats['exp_p'] = row['count']
                    elif row['status'] == 'paid': stats['exp_v'] = row['count']
        except Exception as e:
            print(f"DB Error on Dashboard: {e}")

    return html.Div([
        dbc.Row([
            dbc.Col(kpi_card("Apartment Owners", "fa-building", [
                ("With Dues", stats['apt_dues'], "danger"), ("No Dues", stats['apt_nodues'], "success"), ("Total", stats['apt_total'], "dark")
            ]), width=3),
            dbc.Col(kpi_card("Utility Contractors", "fa-tools", [
                ("With Dues", stats['ven_dues'], "danger"), ("No Dues", stats['ven_nodues'], "success"), ("Total", stats['ven_total'], "dark")
            ]), width=3),
            dbc.Col(kpi_card("Security Staff", "fa-shield-alt", [
                ("Total", stats['sec_total'], "dark")
            ]), width=2),
            dbc.Col(kpi_card("Balance", "fa-rupee-sign", [
                ("Available", f"₹{stats['balance']:,.0f}", "success")
            ]), width=4),
        ], className="mb-4 g-3"),
        dbc.Row([
            dbc.Col(kpi_card("Credits (Receipts)", "fa-chart-line", [
                ("Pending", stats['rec_p'], "warning"), ("Verified", stats['rec_v'], "success")
            ]), width=4),
            dbc.Col(kpi_card("Debits (Expenses)", "fa-chart-area", [
                ("Pending", stats['exp_p'], "warning"), ("Paid", stats['exp_v'], "success")
            ]), width=4),
            dbc.Col(kpi_card("Events", "fa-calendar-check", [
                ("Upcoming", 0, "primary"), ("Drafts", 0, "warning")
            ]), width=4),
        ], className="g-3")
    ])


# --- UI Components for Stage 2 ---

def get_pin_pad():
    return html.Div([
        dcc.Store(id='pin-store', data=''),
        html.H5("Enter PIN", className="text-center mb-3"),
        html.Div(id='pin-display', className="text-center mb-3 h3", style={'letterSpacing': '10px'}),
        dbc.Row([
            dbc.Col(dbc.Button(str(i), id={'type': 'pin-btn', 'index': i}, color="light", className="w-100 mb-2 py-3"), width=4)
            for i in range(1, 10)
        ], className="g-2"),
        dbc.Row([
            dbc.Col(dbc.Button("CLR", id={'type': 'pin-btn', 'index': 'clear'}, color="danger", className="w-100 py-3"), width=4),
            dbc.Col(dbc.Button("0", id={'type': 'pin-btn', 'index': 0}, color="light", className="w-100 py-3"), width=4),
            dbc.Col(dbc.Button(html.I(className="fa fa-backspace"), id={'type': 'pin-btn', 'index': 'back'}, color="warning", className="w-100 py-3"), width=4),
        ], className="g-2 mt-1")
    ])

def get_pattern_pad():
    # 3x3 Grid for 9-dot pattern
    return html.Div([
        dcc.Store(id='pattern-store', data=[]),
        html.H5("Draw Pattern", className="text-center mb-3"),
        html.Div([
            html.Div([
                html.Button(
                    id={'type': 'dot-btn', 'index': i},
                    className="rounded-circle border-2",
                    style={'width': '60px', 'height': '60px', 'margin': '15px', 'backgroundColor': '#f8f9fa'}
                ) for i in range(1, 10)
            ], style={'display': 'grid', 'gridTemplateColumns': 'repeat(3, 1fr)', 'width': '270px', 'margin': 'auto'})
        ]),
        dbc.Button("Reset Pattern", id="reset-pattern", color="link", size="sm", className="mt-2 w-100")
    ])

# --- Main Layout ---
app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    dcc.Store(id="user-session", storage_type="session"),
    dcc.Store(id="auth-stage", data=1), # 1: Society, 2: Login
    html.Div(id="page-content")
])

# --- Callbacks ---

@app.callback(
    Output("page-content", "children"),
    Input("auth-stage", "data"),
    State("user-session", "data")
)
def render_auth_flow(stage, session_data):
    # 1. Check for Network Error
    if not db_pool:
        return dbc.Container([
            html.Div([
                html.I(className="fa fa-wifi text-danger mb-3", style={'fontSize': '3rem'}),
                html.H3("Network Unreachable"),
                html.P("Unable to connect to WeaveEstateHub Servers."),
                dbc.Button("Retry Connection", id="retry-db", color="primary")
            ], className="text-center p-5 shadow mt-5 bg-white")
        ])

    # 2. Auth Logic
    if stage == 1:
        try:
            societies = query_db("SELECT id, name FROM societies")
            if not societies:
                # Jump to Stage 2 with Society=NULL for Master Admin
                return render_secondary_login(society_id=None, is_master=True)
            
            options = [{"label": s['name'], "value": s['id']} for s in societies]
            return dbc.Container([
                html.Div([
                    html.H2("EstateHub", className="text-center mb-4 fw-bold"),
                    html.Label("Select Society"),
                    dcc.Dropdown(id="society-select", options=options, placeholder="Choose your estate..."),
                    dbc.Button("Proceed", id="to-stage-2", color="primary", className="mt-4 w-100", size="lg")
                ], style={"maxWidth": "450px", "margin": "100px auto", "padding": "40px"} , className="bg-white shadow rounded")
            ])
        except:
            return html.Div("Database Error. Please contact support.")

    # 3. Render Dashboard / Portals
    if session_data:
        pathname = callback_context.states.get('url.pathname', '/')
        
        # Admin Portal Specific Routing
        if session_data['role'] == 'admin' and pathname in ['/admin-portal', '/']:
        if session_data['role'] == 'admin' and pathname == '/admin-portal':
            content = get_admin_dashboard(session_data)
        else:
            content = html.Div([
                html.H4(f"Module: {pathname}"),
                html.P("Functionality coming soon...")
            ], className="text-center mt-5 text-muted")
            
        if session_data['role'] == 'admin' and pathname == '/enroll':
            content = get_enrollment_page(session_data)

            
        return render_app_shell(session_data, content)

    return dash.no_update # Stage 2 is handled by switch_stages

def render_secondary_login(society_id, is_master=False):
    title = "Master Admin" if is_master else "Society Login"
    email_prefill = "master@estatehub.com" if is_master else ""
    
    return dbc.Container([
        html.Div([
            html.H3(title, className="text-center mb-4"),
            dbc.Input(id="login-email", placeholder="Email", value=email_prefill, className="mb-3"),
            
            dbc.Tabs([
                dbc.Tab(label="Password", tab_id="pwd", children=[
                    dbc.Input(id="login-password", type="password", placeholder="Enter Password", className="mt-3")
                ]),
                dbc.Tab(label="PIN", tab_id="pin", children=[
                    html.Div(get_pin_pad(), className="mt-3")
                ]),
                dbc.Tab(label="9-Dot Pattern", tab_id="pattern", children=[
                    html.Div(get_pattern_pad(), className="mt-3")
                ]),
            ], id="login-method-tabs", active_tab="pwd"),
            
            dbc.Button("Verify & Login", id="final-login-btn", color="success", className="mt-4 w-100", size="lg"),
            dcc.Store(id="selected-soc-id", data=society_id),
            html.Hr(),
            dbc.Button("Back to Society Selection", id="back-to-stage-1", color="link", size="sm", className="w-100")
        ], style={"maxWidth": "450px", "margin": "50px auto", "padding": "40px"}, className="bg-white shadow rounded")
    ])

# Navigation Callbacks
@app.callback(
    Output("auth-stage", "data"),
    Output("page-content", "children", allow_duplicate=True),
    Input("to-stage-2", "n_clicks"),
    Input("back-to-stage-1", "n_clicks"),
    State("society-select", "value"),
    prevent_initial_call=True
)
def switch_stages(n_to2, n_back, soc_id):
    ctx = callback_context
    trigger = ctx.triggered[0]['prop_id'].split('.')[0]
    
    if trigger == "to-stage-2" and soc_id:
        return 2, render_secondary_login(soc_id)
    elif trigger == "back-to-stage-1":
        return 1, dash.no_update
    return dash.no_update, dash.no_update

# PIN Pad Logic
@app.callback(
    Output("pin-store", "data"),
    Output("pin-display", "children"),
    Input({'type': 'pin-btn', 'index': ALL}, 'n_clicks'),
    State("pin-store", "data"),
    prevent_initial_call=True
)
def update_pin(n_clicks, current_pin):
    ctx = callback_context
    if not ctx.triggered: return dash.no_update
    
    btn_id = ctx.triggered[0]['prop_id'].split('.')[0]
    import json
    btn_index = json.loads(btn_id)['index']
    
    if btn_index == 'clear':
        new_pin = ''
    elif btn_index == 'back':
        new_pin = current_pin[:-1]
    else:
        new_pin = current_pin + str(btn_index)
    
    # Show dots for security
    display = "●" * len(new_pin)
    return new_pin, display

# Pattern Logic
@app.callback(
    Output('pattern-store', 'data'),
    Output({'type': 'dot-btn', 'index': ALL}, 'style'),
    Input({'type': 'dot-btn', 'index': ALL}, 'n_clicks'),
    Input('reset-pattern', 'n_clicks'),
    State('pattern-store', 'data'),
    State({'type': 'dot-btn', 'index': ALL}, 'style'),
    prevent_initial_call=True
)
def update_pattern(n_clicks_list, reset_clicks, current_pattern, current_styles):
    ctx = callback_context
    trigger = ctx.triggered[0]['prop_id']
    
    # Reset logic
    if "reset-pattern" in trigger:
        new_styles = [{**s, 'backgroundColor': '#f8f9fa'} for s in current_styles]
        return [], new_styles

    # Click logic
    import json
    btn_id_dict = json.loads(trigger.split('.')[0])
    idx = btn_id_dict['index']
    
    if idx not in current_pattern:
        current_pattern.append(idx)
        
    new_styles = []
    for i in range(1, 10):
        color = "#18bc9c" if i in current_pattern else "#f8f9fa"
        new_styles.append({'width': '60px', 'height': '60px', 'margin': '15px', 'backgroundColor': color})
        
    return current_pattern, new_styles

# Header Callbacks
@app.callback(
    Output("qr-container", "children"),
    Input("user-avatar", "n_clicks"),
    State("user-session", "data"),
    prevent_initial_call=True
)
def generate_user_qr(n, user_data):
    qr_data = f"USER:{user_data.get('user_id', 'NA')}|ROLE:{user_data.get('role', 'NA')}"
    img = qrcode.make(qr_data)
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return html.Img(src=f"data:image/png;base64,{base64.b64encode(buffered.getvalue()).decode()}", style={"width": "150px"})

# Final Login Logic
@app.callback(
    Output("user-session", "data"),
    Output("url", "pathname"),
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
    if not n: return dash.no_update
    
    # 1. Master Admin Logic
    if email == "master@estatehub.com" and pwd == os.getenv("MASTER_ADMIN_PASSWORD"):
        user_data = {"role": "admin", "name": "Master Admin", "society_name": "Global Admin"}
        return user_data, "/master-admin"
        return user_data, "/admin-portal" # Master admin goes to admin portal

    # 2. Database Verification
    try:
        user = query_db("""SELECT u.*, s.name as soc_name FROM users u 
                           JOIN societies s ON u.society_id = s.id 
                           WHERE u.email = %s AND u.society_id = %s""", (email, soc_id), one=True)
        if not user:
            return dash.no_update, dash.no_update # Add alert here
            
        auth_success = False
        if method == "pwd" and pwd: # check_password_hash(user['password_hash'], pwd)
            auth_success = True
        elif method == "pin" and pin: # user['pin_hash'] == hash(pin)
            auth_success = True
        elif method == "pattern" and pattern: # user['pattern_hash'] == hash(pattern)
            auth_success = True
            
        if auth_success:
            # Create JWT
            token = jwt.encode({
                'user_id': user['id'],
                'role': user['role'],
                'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
            }, os.getenv("JWT_SECRET_KEY"))
            
            user_payload = {
                "user_id": user['id'],
                "token": token,
                "role": user['role'],
                "society_id": soc_id,
                "society_name": user['soc_name'],
                "name": email.split('@')[0].capitalize()
            }
            
            # Redirect based on role
            role_paths = {
                'admin': '/admin-portal',
                'apartment': '/owner-portal',
                'vendor': '/vendor-portal',
                'security': '/security-portal'
            }
            return user_payload, role_paths.get(user['role'], '/')
            
    except Exception as e:
        print(f"Login error: {e}")
        
    return dash.no_update, dash.no_update

@app.callback(
    Output("user-session", "data", allow_duplicate=True),
    Input("logout-btn", "n_clicks"),
    prevent_initial_call=True
)
def logout(n):
    return None

if __name__ == "__main__":
    # Create Societies table if missing for first run
    if db_pool:
        try:
            query_db("SELECT 1 FROM societies LIMIT 1")
        except:
            print("Note: Societies table not found or connection failed.")
            
    app.run_server(debug=True, port=8050)