import sqlite3
import bcrypt
import os
import re
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins='*')

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, 'society.db')
NAMES_DIR = os.path.join(BASE, 'names')
PASS_FILE = os.path.join(BASE, 'pass')

os.makedirs(NAMES_DIR, exist_ok=True)

# ── File-based auth helpers ──────────────────────────────────────────────

def _next_id():
    ids = [0]
    for f in os.listdir(NAMES_DIR):
        m = re.match(r'(\d+)\.txt$', f)
        if m:
            ids.append(int(m.group(1)))
    for line in open(PASS_FILE).readlines() if os.path.exists(PASS_FILE) else []:
        line = line.strip()
        if line:
            m = re.match(r'(\d+):', line)
            if m:
                ids.append(int(m.group(1)))
    return max(ids) + 1

def _read_all_users():
    users = {}
    if os.path.exists(PASS_FILE):
        for line in open(PASS_FILE):
            line = line.strip()
            if not line:
                continue
            parts = line.split(':', 2)
            if len(parts) == 3:
                uid, hashed, role = parts
                users[uid] = {'id': int(uid), 'hashed': hashed, 'role': role}
    result = []
    for uid, data in users.items():
        fpath = os.path.join(NAMES_DIR, f'{uid}.txt')
        name = ''
        email = ''
        if os.path.exists(fpath):
            for fline in open(fpath):
                fline = fline.strip()
                if fline.startswith('Name:'):
                    name = fline.split(':', 1)[1].strip()
                elif fline.startswith('Email:'):
                    email = fline.split(':', 1)[1].strip()
        result.append({'id': data['id'], 'name': name, 'email': email, 'role': data['role']})
    return result

def _find_user(login_id):
    for u in _read_all_users():
        if u['email'].lower() == login_id.lower() or u['name'].lower() == login_id.lower():
            return u
    return None

def _get_user(uid):
    for u in _read_all_users():
        if u['id'] == uid:
            return u
    return None

# ── DB init (no users table) ─────────────────────────────────────────────

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS notices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                posted_by TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS complaints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                user_name TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT DEFAULT 'open' CHECK(status IN ('open', 'in_progress', 'resolved', 'discarded')),
                created_at TEXT DEFAULT (datetime('now'))
            )
        ''')
        try: conn.execute("ALTER TABLE complaints ADD COLUMN resolution TEXT DEFAULT ''")
        except: pass
        try: conn.execute("ALTER TABLE complaints ADD COLUMN resolved_at TEXT")
        except: pass
        try: conn.execute("ALTER TABLE complaints ADD COLUMN accepted_by TEXT DEFAULT ''")
        except: pass
        try: conn.execute("ALTER TABLE complaints ADD COLUMN fraud_warning INTEGER DEFAULT 0")
        except: pass
        conn.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                event_date TEXT NOT NULL,
                venue TEXT DEFAULT '',
                posted_by TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS residents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                flat_number TEXT NOT NULL,
                family_members INTEGER DEFAULT 1,
                occupation TEXT DEFAULT '',
                phone TEXT DEFAULT ''
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS maintenance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                month TEXT NOT NULL,
                year INTEGER NOT NULL,
                amount REAL NOT NULL DEFAULT 0,
                status TEXT DEFAULT 'pending' CHECK(status IN ('paid', 'pending')),
                paid_date TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        ''')

        c = conn.execute('SELECT COUNT(*) FROM notices').fetchone()[0]
        if c == 0:
            conn.execute("INSERT INTO notices (title, content, posted_by) VALUES ('Water Supply Schedule', 'Water supply will be available from 6:00 AM to 8:00 AM and 6:00 PM to 8:00 PM daily.', 'Admin')")
            conn.execute("INSERT INTO notices (title, content, posted_by) VALUES ('Annual Maintenance Fee', 'Annual maintenance fee of Rs. 12,000 is due by 31st July. Please pay at the office.', 'Admin')")
            conn.execute("INSERT INTO notices (title, content, posted_by) VALUES ('Security Update', 'All residents are requested to use the new RFID tags for gate entry from 1st August.', 'Admin')")
            conn.execute("INSERT INTO notices (title, content, posted_by) VALUES ('Yoga Session', 'Free yoga sessions every morning at 6:30 AM in the community park. All ages welcome.', 'Admin')")
            conn.execute("INSERT INTO notices (title, content, posted_by) VALUES ('Garbage Collection', 'Garbage collection timings changed to 7:00 AM. Please segregate wet and dry waste.', 'Admin')")

        c = conn.execute('SELECT COUNT(*) FROM events').fetchone()[0]
        if c == 0:
            conn.execute("INSERT INTO events (title, description, event_date, venue, posted_by) VALUES ('Independence Day Celebration', 'Flag hoisting followed by cultural programs and refreshments.', '2026-08-15', 'Main Lawn', 'Admin')")
            conn.execute("INSERT INTO events (title, description, event_date, venue, posted_by) VALUES ('Health Checkup Camp', 'Free health checkup including blood pressure, sugar, and BMI. Sponsored by City Hospital.', '2026-07-20', 'Community Hall', 'Admin')")
            conn.execute("INSERT INTO events (title, description, event_date, venue, posted_by) VALUES ('Diwali Milan', 'Annual Diwali celebration with lighting, sweets, and fireworks.', '2026-10-31', 'Entire Society', 'Admin')")
            conn.execute("INSERT INTO events (title, description, event_date, venue, posted_by) VALUES ('Kids Art Competition', 'Art competition for children aged 5-15. Bring your own colors.', '2026-08-05', 'Club House', 'Admin')")

init_db()

# ── Auth ──────────────────────────────────────────────────────────────────

@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.get_json()
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    role = data.get('role', 'resident')

    if not name or not email or not password:
        return jsonify({'ok': False, 'error': 'All fields are required.'}), 400

    if len(password) < 8:
        return jsonify({'ok': False, 'error': 'Password must be at least 8 characters.'}), 400

    if role not in ('resident', 'staff', 'admin'):
        return jsonify({'ok': False, 'error': 'Invalid role.'}), 400

    if _find_user(email):
        return jsonify({'ok': False, 'error': 'Email already registered.'}), 409

    uid = _next_id()
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    with open(os.path.join(NAMES_DIR, f'{uid}.txt'), 'w') as f:
        f.write(f'Name: {name}\nEmail: {email}\nRole: {role}\n')

    with open(PASS_FILE, 'a') as f:
        f.write(f'{uid}:{hashed}:{role}\n')

    if role == 'resident':
        with sqlite3.connect(DB_PATH) as conn:
            try:
                conn.execute('INSERT INTO residents (user_id, flat_number, family_members, occupation, phone) VALUES (?, ?, ?, ?, ?)',
                             (uid, 'TBD', 1, '', ''))
            except sqlite3.IntegrityError:
                pass

    return jsonify({'ok': True, 'message': 'Account created successfully!'}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    login_id = data.get('login_id', '').strip()
    password = data.get('password', '')
    role = data.get('role', 'resident')

    if not login_id or not password:
        return jsonify({'ok': False, 'error': 'Please fill in all fields.'}), 400

    user = _find_user(login_id)
    if not user:
        return jsonify({'ok': False, 'error': 'Invalid credentials.'}), 401

    stored_hash = None
    if os.path.exists(PASS_FILE):
        for line in open(PASS_FILE):
            parts = line.strip().split(':', 2)
            if len(parts) == 3 and parts[0] == str(user['id']):
                stored_hash = parts[1]
                break

    if not stored_hash or not bcrypt.checkpw(password.encode(), stored_hash.encode()):
        return jsonify({'ok': False, 'error': 'Invalid credentials.'}), 401

    if user['role'] != role:
        return jsonify({'ok': False, 'error': f'No {role} account found with these credentials.'}), 401

    return jsonify({
        'ok': True,
        'user': {'id': user['id'], 'name': user['name'], 'email': user['email'], 'role': user['role']},
        'message': f'Welcome back, {user["name"]}! Redirecting to {role} dashboard...'
    })

# ── Users (file-based) ───────────────────────────────────────────────────

@app.route('/api/users', methods=['GET'])
def get_users():
    role_filter = request.args.get('role')
    users = _read_all_users()
    if role_filter:
        users = [u for u in users if u['role'] == role_filter]
    return jsonify(users)

# ── Notices ───────────────────────────────────────────────────────────────

@app.route('/api/notices', methods=['GET'])
def get_notices():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute('SELECT * FROM notices ORDER BY created_at DESC').fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/notices', methods=['POST'])
def create_notice():
    data = request.get_json()
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    posted_by = data.get('posted_by', 'Admin').strip()
    if not title or not content:
        return jsonify({'ok': False, 'error': 'Title and content are required.'}), 400
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('INSERT INTO notices (title, content, posted_by) VALUES (?, ?, ?)', (title, content, posted_by))
    return jsonify({'ok': True, 'message': 'Notice added!'}), 201

@app.route('/api/notices/<int:notice_id>', methods=['PUT'])
def update_notice(notice_id):
    data = request.get_json()
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    if not title or not content:
        return jsonify({'ok': False, 'error': 'Title and content are required.'}), 400
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('UPDATE notices SET title = ?, content = ? WHERE id = ?', (title, content, notice_id))
    return jsonify({'ok': True, 'message': 'Notice updated!'})

@app.route('/api/notices/<int:notice_id>', methods=['DELETE'])
def delete_notice(notice_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('DELETE FROM notices WHERE id = ?', (notice_id,))
    return jsonify({'ok': True, 'message': 'Notice deleted!'})

# ── Events ────────────────────────────────────────────────────────────────

@app.route('/api/events', methods=['GET'])
def get_events():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM events WHERE event_date >= date('now') ORDER BY event_date ASC").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/events/all', methods=['GET'])
def get_all_events():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute('SELECT * FROM events ORDER BY event_date ASC').fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/events', methods=['POST'])
def create_event():
    data = request.get_json()
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    event_date = data.get('event_date', '').strip()
    venue = data.get('venue', '').strip()
    posted_by = data.get('posted_by', 'Admin').strip()
    if not title or not description or not event_date:
        return jsonify({'ok': False, 'error': 'Title, description, and date are required.'}), 400
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('INSERT INTO events (title, description, event_date, venue, posted_by) VALUES (?, ?, ?, ?, ?)',
                     (title, description, event_date, venue, posted_by))
    return jsonify({'ok': True, 'message': 'Event added!'}), 201

@app.route('/api/events/<int:event_id>', methods=['PUT'])
def update_event(event_id):
    data = request.get_json()
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    event_date = data.get('event_date', '').strip()
    venue = data.get('venue', '').strip()
    if not title or not description or not event_date:
        return jsonify({'ok': False, 'error': 'Title, description, and date are required.'}), 400
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('UPDATE events SET title = ?, description = ?, event_date = ?, venue = ? WHERE id = ?',
                     (title, description, event_date, venue, event_id))
    return jsonify({'ok': True, 'message': 'Event updated!'})

@app.route('/api/events/<int:event_id>', methods=['DELETE'])
def delete_event(event_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('DELETE FROM events WHERE id = ?', (event_id,))
    return jsonify({'ok': True, 'message': 'Event deleted!'})

# ── Complaints ────────────────────────────────────────────────────────────

@app.route('/api/complaints', methods=['GET'])
def get_complaints():
    user_id = request.args.get('user_id')
    warnings = request.args.get('warnings')
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        if warnings and user_id:
            rows = conn.execute("SELECT id, title, resolved_at FROM complaints WHERE user_id = ? AND status = 'discarded'", (user_id,)).fetchall()
        elif user_id:
            rows = conn.execute('SELECT * FROM complaints WHERE user_id = ? ORDER BY created_at DESC', (user_id,)).fetchall()
        else:
            rows = conn.execute('SELECT * FROM complaints ORDER BY created_at DESC').fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/complaints', methods=['POST'])
def raise_complaint():
    data = request.get_json()
    user_id = data.get('user_id')
    user_name = data.get('user_name', '').strip()
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    if not user_id or not title or not description:
        return jsonify({'ok': False, 'error': 'Title and description are required.'}), 400
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('INSERT INTO complaints (user_id, user_name, title, description) VALUES (?, ?, ?, ?)',
                     (user_id, user_name, title, description))
    return jsonify({'ok': True, 'message': 'Complaint registered successfully!'}), 201

@app.route('/api/complaints/<int:complaint_id>', methods=['PATCH'])
def update_complaint(complaint_id):
    data = request.get_json()
    status = data.get('status')
    if status not in ('open', 'in_progress', 'resolved', 'discarded'):
        return jsonify({'ok': False, 'error': 'Invalid status.'}), 400
    import datetime
    resolution = data.get('resolution', '').strip()
    accepted_by = data.get('accepted_by', '').strip()
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    with sqlite3.connect(DB_PATH) as conn:
        if status == 'resolved' and resolution:
            conn.execute('UPDATE complaints SET status = ?, resolution = ?, resolved_at = ? WHERE id = ?',
                         (status, resolution, now, complaint_id))
        elif status == 'in_progress':
            conn.execute('UPDATE complaints SET status = ?, accepted_by = ?, resolved_at = ? WHERE id = ?',
                         (status, accepted_by, now, complaint_id))
        elif status == 'discarded':
            conn.execute("UPDATE complaints SET status = ?, resolved_at = ?, fraud_warning = 1 WHERE id = ?",
                         (status, now, complaint_id))
        else:
            conn.execute('UPDATE complaints SET status = ? WHERE id = ?', (status, complaint_id))
    return jsonify({'ok': True, 'message': 'Complaint updated.'})

# ── Residents ─────────────────────────────────────────────────────────────

@app.route('/api/residents', methods=['GET'])
def get_residents():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute('SELECT * FROM residents ORDER BY flat_number ASC').fetchall()
    result = []
    for r in rows:
        d = dict(r)
        user = _get_user(d['user_id'])
        d['name'] = user['name'] if user else 'Unknown'
        d['email'] = user['email'] if user else ''
        result.append(d)
    return jsonify(result)

@app.route('/api/residents', methods=['POST'])
def add_resident():
    data = request.get_json()
    user_id = data.get('user_id')
    flat_number = data.get('flat_number', '').strip().upper()
    family_members = data.get('family_members', 1)
    occupation = data.get('occupation', '').strip()
    phone = data.get('phone', '').strip()
    if not user_id or not flat_number:
        return jsonify({'ok': False, 'error': 'User and flat number are required.'}), 400
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('INSERT INTO residents (user_id, flat_number, family_members, occupation, phone) VALUES (?, ?, ?, ?, ?)',
                         (user_id, flat_number, family_members, occupation, phone))
        return jsonify({'ok': True, 'message': 'Resident added!'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'ok': False, 'error': 'Resident already exists for this user.'}), 409

@app.route('/api/residents/<int:resident_id>', methods=['PUT'])
def update_resident(resident_id):
    data = request.get_json()
    flat_number = data.get('flat_number', '').strip().upper()
    family_members = data.get('family_members', 1)
    occupation = data.get('occupation', '').strip()
    phone = data.get('phone', '').strip()
    if not flat_number:
        return jsonify({'ok': False, 'error': 'Flat number is required.'}), 400
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('UPDATE residents SET flat_number = ?, family_members = ?, occupation = ?, phone = ? WHERE id = ?',
                     (flat_number, family_members, occupation, phone, resident_id))
    return jsonify({'ok': True, 'message': 'Resident updated!'})

@app.route('/api/residents/<int:resident_id>', methods=['DELETE'])
def delete_resident(resident_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('DELETE FROM residents WHERE id = ?', (resident_id,))
    return jsonify({'ok': True, 'message': 'Resident removed!'})

# ── Maintenance ──────────────────────────────────────────────────────────

@app.route('/api/maintenance', methods=['GET'])
def get_maintenance():
    user_id = request.args.get('user_id')
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        if user_id:
            rows = conn.execute('SELECT * FROM maintenance WHERE user_id = ? ORDER BY year DESC, month DESC', (user_id,)).fetchall()
        else:
            rows = conn.execute('SELECT m.*, r.flat_number FROM maintenance m LEFT JOIN residents r ON r.user_id = m.user_id ORDER BY m.year DESC, m.month DESC').fetchall()
    result = []
    for r in rows:
        d = dict(r)
        if not user_id:
            user = _get_user(d['user_id'])
            d['name'] = user['name'] if user else 'Unknown'
        result.append(d)
    return jsonify(result)

@app.route('/api/maintenance/current', methods=['GET'])
def get_current_maintenance():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400
    import datetime
    now = datetime.datetime.now()
    month = f'{now.month:02d}'
    year = now.year
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            'SELECT * FROM maintenance WHERE user_id = ? AND month = ? AND year = ?',
            (user_id, month, year)
        ).fetchone()
    if row:
        return jsonify(dict(row))
    return jsonify(None)

@app.route('/api/maintenance', methods=['POST'])
def create_maintenance():
    data = request.get_json()
    user_id = data.get('user_id')
    month = data.get('month')
    year = data.get('year')
    amount = data.get('amount', 0)
    status = data.get('status', 'pending')

    if not user_id or not month or not year:
        return jsonify({'ok': False, 'error': 'user_id, month, and year are required.'}), 400

    with sqlite3.connect(DB_PATH) as conn:
        existing = conn.execute(
            'SELECT id FROM maintenance WHERE user_id = ? AND month = ? AND year = ?',
            (user_id, month, year)
        ).fetchone()
        if existing:
            return jsonify({'ok': False, 'error': 'Maintenance record already exists for this period.'}), 409
        conn.execute(
            'INSERT INTO maintenance (user_id, month, year, amount, status) VALUES (?, ?, ?, ?, ?)',
            (user_id, month, year, amount, status)
        )
    return jsonify({'ok': True, 'message': 'Maintenance record created!'}), 201

@app.route('/api/maintenance/<int:mid>', methods=['PATCH'])
def update_maintenance(mid):
    data = request.get_json()
    status = data.get('status')
    if status not in ('paid', 'pending'):
        return jsonify({'ok': False, 'error': 'Invalid status.'}), 400
    import datetime
    paid_date = datetime.datetime.now().strftime('%Y-%m-%d') if status == 'paid' else None
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('UPDATE maintenance SET status = ?, paid_date = ? WHERE id = ?', (status, paid_date, mid))
    return jsonify({'ok': True, 'message': 'Maintenance updated.'})

@app.route('/api/maintenance/bulk', methods=['POST'])
def bulk_create_maintenance():
    data = request.get_json()
    month = data.get('month')
    year = data.get('year')
    amount = data.get('amount', 0)
    if not month or not year:
        return jsonify({'ok': False, 'error': 'month and year required.'}), 400
    with sqlite3.connect(DB_PATH) as conn:
        residents = conn.execute('SELECT user_id FROM residents').fetchall()
        count = 0
        for r in residents:
            existing = conn.execute(
                'SELECT id FROM maintenance WHERE user_id = ? AND month = ? AND year = ?',
                (r['user_id'], month, year)
            ).fetchone()
            if not existing:
                conn.execute(
                    'INSERT INTO maintenance (user_id, month, year, amount, status) VALUES (?, ?, ?, ?, ?)',
                    (r['user_id'], month, year, amount, 'pending')
                )
                count += 1
    return jsonify({'ok': True, 'message': f'{count} maintenance records created.'})

# ── Email ─────────────────────────────────────────────────────────────────

import smtplib
import random
import datetime as _dt
from email.mime.text import MIMEText

SMTP_HOST = os.environ.get('SMTP_HOST', '')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASS = os.environ.get('SMTP_PASS', '')
SMTP_FROM = os.environ.get('SMTP_FROM', SMTP_USER)

def _send_email(to, subject, body):
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS:
        return False
    msg = MIMEText(body, 'html')
    msg['Subject'] = subject
    msg['From'] = SMTP_FROM
    msg['To'] = to
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        return True
    except Exception:
        return False

# ── Forgot / Reset Password ──────────────────────────────────────────────

_codes = {}  # email -> {code, expires, user_id}

@app.route('/api/forgot-password', methods=['POST'])
def forgot_password():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    if not email:
        return jsonify({'ok': False, 'error': 'Email is required.'}), 400
    user = _find_user(email)
    if not user:
        return jsonify({'ok': False, 'error': 'No account found with this email.'}), 404

    code = f'{random.randint(0, 999999):06d}'
    _codes[email] = {'code': code, 'expires': _dt.datetime.now() + _dt.timedelta(minutes=10), 'user_id': user['id']}

    body = f'''<div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px">
      <div style="background:#1E4D31;border-radius:12px;padding:24px;text-align:center;color:#fff">
        <h2 style="margin:0 0 8px">Mahindra Gardens</h2>
        <p style="margin:0;opacity:0.8">Password Reset Code</p>
      </div>
      <div style="padding:24px;border:1px solid #E0E1D8;border-radius:12px;margin-top:16px">
        <p style="color:#111;font-size:14px">Your 6-digit verification code is:</p>
        <div style="font-size:36px;font-weight:800;letter-spacing:8px;text-align:center;color:#1E4D31;margin:24px 0">{code}</div>
        <p style="color:#666;font-size:13px">This code expires in <strong>10 minutes</strong>.</p>
        <p style="color:#999;font-size:12px">If you didn't request this, please ignore this email.</p>
      </div>
    </div>'''

    sent = _send_email(email, 'Your Password Reset Code', body)
    return jsonify({'ok': True, 'message': 'Verification code sent to your email.', 'demo_code': code if not sent else ''})

@app.route('/api/verify-code', methods=['POST'])
def verify_code():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    code = data.get('code', '').strip()
    record = _codes.get(email)
    if not record:
        return jsonify({'ok': False, 'error': 'No code requested for this email.'}), 400
    if _dt.datetime.now() > record['expires']:
        _codes.pop(email, None)
        return jsonify({'ok': False, 'error': 'Code expired. Request a new one.'}), 400
    if record['code'] != code:
        return jsonify({'ok': False, 'error': 'Invalid code.'}), 400
    return jsonify({'ok': True, 'message': 'Code verified.'})

@app.route('/api/reset-password', methods=['POST'])
def reset_password():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    code = data.get('code', '').strip()
    password = data.get('password', '')
    record = _codes.get(email)
    if not record or record['code'] != code:
        return jsonify({'ok': False, 'error': 'Invalid or expired code.'}), 400
    if _dt.datetime.now() > record['expires']:
        _codes.pop(email, None)
        return jsonify({'ok': False, 'error': 'Code expired.'}), 400
    if len(password) < 8:
        return jsonify({'ok': False, 'error': 'Password must be at least 8 characters.'}), 400

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    lines = []
    if os.path.exists(PASS_FILE):
        for line in open(PASS_FILE):
            parts = line.strip().split(':', 2)
            if len(parts) == 3 and parts[0] == str(record['user_id']):
                lines.append(f'{record["user_id"]}:{hashed}:{parts[2]}\n')
            else:
                lines.append(line)
    with open(PASS_FILE, 'w') as f:
        f.writelines(lines)

    _codes.pop(email, None)
    return jsonify({'ok': True, 'message': 'Password reset successfully!'})

@app.route('/')
def serve_index():
    return send_from_directory(BASE, 'login.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(BASE, filename)

if __name__ == '__main__':
    if not SMTP_HOST:
        print('=' * 60)
        print('  EMAIL NOT CONFIGURED — codes shown on-screen (demo mode)')
        print('  To enable real email, set these environment variables:')
        print('    SMTP_HOST=smtp.gmail.com')
        print('    SMTP_PORT=587')
        print('    SMTP_USER=your@gmail.com')
        print('    SMTP_PASS=your-gmail-app-password')
        print('  (Use a Gmail App Password, not your regular password)')
        print('=' * 60)
    app.run(host='0.0.0.0', port=5000, debug=False)
