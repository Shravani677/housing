import os, datetime, json, uuid
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, auth as admin_auth

app = Flask(__name__)
CORS(app, origins='*')

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

cred = credentials.Certificate(os.path.join(BASE, 'firebase-key.json'))
firebase_admin.initialize_app(cred)

FIREBASE_API_KEY = "AIzaSyAEtvIqs0Vw-b8CWU9jSLsUAFANOjbDpEs"

# ── JSON file helpers ────────────────────────────────────────────────────

def _load(name):
    path = os.path.join(DATA_DIR, f'{name}.json')
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def _save(name, data):
    path = os.path.join(DATA_DIR, f'{name}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def _now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

def _today():
    return datetime.datetime.now().strftime('%Y-%m-%d')

def _next_id(name):
    items = _load(name)
    ids = [x.get('id', 0) for x in items]
    return max(ids) + 1 if ids else 1

# ── Firebase Auth helpers ──────────────────────────────────────────────

def firebase_sign_in(email, password):
    import requests
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
    resp = requests.post(url, json={"email": email, "password": password, "returnSecureToken": True})
    data = resp.json()
    if "idToken" not in data:
        return None, data.get("error", {}).get("message", "Invalid credentials")
    decoded = admin_auth.verify_id_token(data["idToken"])
    return decoded['uid'], None

def _get_user_by_uid(uid):
    users = _load('users')
    for u in users:
        if u['id'] == uid:
            return u
    return None

def _get_resident_by_uid(uid):
    residents = _load('residents')
    for r in residents:
        if r['user_id'] == uid:
            return r
    return None

# ── Seed ────────────────────────────────────────────────────────────────

def seed_db():
    if len(_load('notices')) == 0:
        notices = [
            {'id': 1, 'title': 'Water Supply Schedule', 'content': 'Water supply will be available from 6:00 AM to 8:00 AM and 6:00 PM to 8:00 PM daily.', 'posted_by': 'Admin', 'created_at': _now()},
            {'id': 2, 'title': 'Annual Maintenance Fee', 'content': 'Annual maintenance fee of Rs. 12,000 is due by 31st July. Please pay at the office.', 'posted_by': 'Admin', 'created_at': _now()},
            {'id': 3, 'title': 'Security Update', 'content': 'All residents are requested to use the new RFID tags for gate entry from 1st August.', 'posted_by': 'Admin', 'created_at': _now()},
            {'id': 4, 'title': 'Yoga Session', 'content': 'Free yoga sessions every morning at 6:30 AM in the community park. All ages welcome.', 'posted_by': 'Admin', 'created_at': _now()},
            {'id': 5, 'title': 'Garbage Collection', 'content': 'Garbage collection timings changed to 7:00 AM. Please segregate wet and dry waste.', 'posted_by': 'Admin', 'created_at': _now()},
        ]
        _save('notices', notices)
    if len(_load('events')) == 0:
        events = [
            {'id': 1, 'title': 'Independence Day Celebration', 'description': 'Flag hoisting followed by cultural programs and refreshments.', 'event_date': '2026-08-15', 'venue': 'Main Lawn', 'posted_by': 'Admin', 'created_at': _now()},
            {'id': 2, 'title': 'Health Checkup Camp', 'description': 'Free health checkup including blood pressure, sugar, and BMI.', 'event_date': '2026-07-20', 'venue': 'Community Hall', 'posted_by': 'Admin', 'created_at': _now()},
            {'id': 3, 'title': 'Diwali Milan', 'description': 'Annual Diwali celebration with lighting, sweets, and fireworks.', 'event_date': '2026-10-31', 'venue': 'Entire Society', 'posted_by': 'Admin', 'created_at': _now()},
            {'id': 4, 'title': 'Kids Art Competition', 'description': 'Art competition for children aged 5-15. Bring your own colors.', 'event_date': '2026-08-05', 'venue': 'Club House', 'posted_by': 'Admin', 'created_at': _now()},
        ]
        _save('events', events)
    print('Seeded default data')

seed_db()

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

    try:
        user = admin_auth.create_user(email=email, password=password, display_name=name)
    except admin_auth.EmailAlreadyExistsError:
        return jsonify({'ok': False, 'error': 'Email already registered.'}), 409
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400

    uid = user.uid
    users = _load('users')
    users.append({'id': uid, 'name': name, 'email': email, 'role': role})
    _save('users', users)

    if role == 'resident':
        residents = _load('residents')
        residents.append({'id': _next_id('residents'), 'user_id': uid, 'flat_number': 'TBD', 'family_members': 1, 'occupation': '', 'phone': ''})
        _save('residents', residents)

    return jsonify({'ok': True, 'message': 'Account created successfully!', 'user': {'id': uid, 'name': name, 'email': email, 'role': role}}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    login_id = data.get('login_id', '').strip()
    password = data.get('password', '')
    role = data.get('role', 'resident')

    if not login_id or not password:
        return jsonify({'ok': False, 'error': 'Please fill in all fields.'}), 400

    uid, err = firebase_sign_in(login_id, password)
    if err:
        users = _load('users')
        matched = None
        for u in users:
            if u.get('name', '').lower() == login_id.lower():
                uid2, err2 = firebase_sign_in(u['email'], password)
                if not err2:
                    uid = uid2
                    matched = u
                    break
        if not matched:
            return jsonify({'ok': False, 'error': 'Invalid credentials.'}), 401

    profile = _get_user_by_uid(uid)
    if not profile:
        return jsonify({'ok': False, 'error': 'User profile not found.'}), 404

    if profile['role'] != role:
        return jsonify({'ok': False, 'error': f'No {role} account found with these credentials.'}), 401

    return jsonify({
        'ok': True,
        'user': {'id': uid, 'name': profile['name'], 'email': profile['email'], 'role': profile['role']},
        'message': f'Welcome back, {profile["name"]}! Redirecting to {role} dashboard...'
    })

# ── Forgot Password ──────────────────────────────────────────────────────

@app.route('/api/forgot-password', methods=['POST'])
def forgot_password():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    if not email:
        return jsonify({'ok': False, 'error': 'Email is required.'}), 400

    try:
        import requests as req
        resp = req.post(f'https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={FIREBASE_API_KEY}', json={
            "requestType": "PASSWORD_RESET", "email": email
        })
        data = resp.json()
        if "error" in data:
            return jsonify({'ok': False, 'error': data["error"]["message"]}), 400
        return jsonify({'ok': True, 'message': 'Password reset email sent! Check your inbox (and spam).'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

# ── Users ─────────────────────────────────────────────────────────────────

@app.route('/api/users', methods=['GET'])
def get_users():
    role_filter = request.args.get('role')
    users = _load('users')
    if role_filter:
        users = [u for u in users if u['role'] == role_filter]
    return jsonify(users)

@app.route('/api/profile', methods=['POST'])
def get_profile():
    data = request.get_json()
    uid = data.get('uid', '')
    if not uid:
        return jsonify({'ok': False, 'error': 'uid required'}), 400
    profile = _get_user_by_uid(uid)
    if not profile:
        return jsonify({'ok': False, 'error': 'User not found'}), 404
    return jsonify(profile)

# ── Notices ───────────────────────────────────────────────────────────────

@app.route('/api/notices', methods=['GET'])
def get_notices():
    notices = _load('notices')
    notices.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return jsonify(notices)

@app.route('/api/notices', methods=['POST'])
def create_notice():
    data = request.get_json()
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    posted_by = data.get('posted_by', 'Admin').strip()
    if not title or not content:
        return jsonify({'ok': False, 'error': 'Title and content are required.'}), 400
    notices = _load('notices')
    notices.append({'id': _next_id('notices'), 'title': title, 'content': content, 'posted_by': posted_by, 'created_at': _now()})
    _save('notices', notices)
    return jsonify({'ok': True, 'message': 'Notice added!'}), 201

@app.route('/api/notices/<int:notice_id>', methods=['PUT'])
def update_notice(notice_id):
    data = request.get_json()
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    if not title or not content:
        return jsonify({'ok': False, 'error': 'Title and content are required.'}), 400
    notices = _load('notices')
    for n in notices:
        if n['id'] == notice_id:
            n['title'] = title
            n['content'] = content
            break
    _save('notices', notices)
    return jsonify({'ok': True, 'message': 'Notice updated!'})

@app.route('/api/notices/<int:notice_id>', methods=['DELETE'])
def delete_notice(notice_id):
    notices = _load('notices')
    notices = [n for n in notices if n['id'] != notice_id]
    _save('notices', notices)
    return jsonify({'ok': True, 'message': 'Notice deleted!'})

# ── Events ────────────────────────────────────────────────────────────────

@app.route('/api/events', methods=['GET'])
def get_events():
    today = _today()
    events = _load('events')
    events = [e for e in events if e.get('event_date', '') >= today]
    events.sort(key=lambda x: x.get('event_date', ''))
    return jsonify(events)

@app.route('/api/events/all', methods=['GET'])
def get_all_events():
    events = _load('events')
    events.sort(key=lambda x: x.get('event_date', ''))
    return jsonify(events)

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
    events = _load('events')
    events.append({'id': _next_id('events'), 'title': title, 'description': description, 'event_date': event_date, 'venue': venue, 'posted_by': posted_by, 'created_at': _now()})
    _save('events', events)
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
    events = _load('events')
    for e in events:
        if e['id'] == event_id:
            e['title'] = title
            e['description'] = description
            e['event_date'] = event_date
            e['venue'] = venue
            break
    _save('events', events)
    return jsonify({'ok': True, 'message': 'Event updated!'})

@app.route('/api/events/<int:event_id>', methods=['DELETE'])
def delete_event(event_id):
    events = _load('events')
    events = [e for e in events if e['id'] != event_id]
    _save('events', events)
    return jsonify({'ok': True, 'message': 'Event deleted!'})

# ── Complaints ────────────────────────────────────────────────────────────

@app.route('/api/complaints', methods=['GET'])
def get_complaints():
    user_id = request.args.get('user_id')
    warnings = request.args.get('warnings')
    complaints = _load('complaints')
    if warnings and user_id:
        return jsonify([{'id': c['id'], 'title': c.get('title'), 'resolved_at': c.get('resolved_at')} for c in complaints if c.get('user_id') == user_id and c.get('status') == 'discarded'])
    if user_id:
        complaints = [c for c in complaints if c.get('user_id') == user_id]
    complaints.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return jsonify(complaints)

@app.route('/api/complaints', methods=['POST'])
def raise_complaint():
    data = request.get_json()
    user_id = data.get('user_id')
    user_name = data.get('user_name', '').strip()
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    if not user_id or not title or not description:
        return jsonify({'ok': False, 'error': 'Title and description are required.'}), 400
    complaints = _load('complaints')
    complaints.append({'id': _next_id('complaints'), 'user_id': user_id, 'user_name': user_name, 'title': title, 'description': description, 'status': 'open', 'created_at': _now(), 'resolution': '', 'resolved_at': '', 'accepted_by': '', 'fraud_warning': 0})
    _save('complaints', complaints)
    return jsonify({'ok': True, 'message': 'Complaint registered successfully!'}), 201

@app.route('/api/complaints/<int:complaint_id>', methods=['PATCH'])
def update_complaint(complaint_id):
    data = request.get_json()
    status = data.get('status')
    if status not in ('open', 'in_progress', 'resolved', 'discarded'):
        return jsonify({'ok': False, 'error': 'Invalid status.'}), 400
    resolution = data.get('resolution', '').strip()
    accepted_by = data.get('accepted_by', '').strip()
    now = _now()
    complaints = _load('complaints')
    for c in complaints:
        if c['id'] == complaint_id:
            if status == 'resolved' and resolution:
                c['status'] = status; c['resolution'] = resolution; c['resolved_at'] = now
            elif status == 'in_progress':
                c['status'] = status; c['accepted_by'] = accepted_by; c['resolved_at'] = now
            elif status == 'discarded':
                c['status'] = status; c['resolved_at'] = now; c['fraud_warning'] = 1
            else:
                c['status'] = status
            break
    _save('complaints', complaints)
    return jsonify({'ok': True, 'message': 'Complaint updated.'})

@app.route('/api/complaints/<int:complaint_id>', methods=['DELETE'])
def delete_complaint(complaint_id):
    complaints = _load('complaints')
    complaints = [c for c in complaints if c['id'] != complaint_id]
    _save('complaints', complaints)
    return jsonify({'ok': True, 'message': 'Complaint deleted.'})

# ── Residents ─────────────────────────────────────────────────────────────

@app.route('/api/residents', methods=['GET'])
def get_residents():
    residents = _load('residents')
    residents.sort(key=lambda x: x.get('flat_number', ''))
    users = {u['id']: u for u in _load('users')}
    for r in residents:
        u = users.get(r.get('user_id', ''))
        r['name'] = u['name'] if u else 'Unknown'
        r['email'] = u['email'] if u else ''
    return jsonify(residents)

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
    if _get_resident_by_uid(user_id):
        return jsonify({'ok': False, 'error': 'Resident already exists for this user.'}), 409
    residents = _load('residents')
    residents.append({'id': _next_id('residents'), 'user_id': user_id, 'flat_number': flat_number, 'family_members': family_members, 'occupation': occupation, 'phone': phone})
    _save('residents', residents)
    return jsonify({'ok': True, 'message': 'Resident added!'}), 201

@app.route('/api/residents/<int:resident_id>', methods=['PUT'])
def update_resident(resident_id):
    data = request.get_json()
    flat_number = data.get('flat_number', '').strip().upper()
    family_members = data.get('family_members', 1)
    occupation = data.get('occupation', '').strip()
    phone = data.get('phone', '').strip()
    if not flat_number:
        return jsonify({'ok': False, 'error': 'Flat number is required.'}), 400
    residents = _load('residents')
    for r in residents:
        if r['id'] == resident_id:
            r['flat_number'] = flat_number; r['family_members'] = family_members; r['occupation'] = occupation; r['phone'] = phone
            break
    _save('residents', residents)
    return jsonify({'ok': True, 'message': 'Resident updated!'})

@app.route('/api/residents/<int:resident_id>', methods=['DELETE'])
def delete_resident(resident_id):
    residents = _load('residents')
    residents = [r for r in residents if r['id'] != resident_id]
    _save('residents', residents)
    return jsonify({'ok': True, 'message': 'Resident removed!'})

@app.route('/api/resident/<user_id>', methods=['GET'])
def get_resident_by_user(user_id):
    r = _get_resident_by_uid(user_id)
    if not r:
        return jsonify({'ok': False, 'error': 'Resident not found.'}), 404
    user = _get_user_by_uid(user_id)
    r['name'] = user['name'] if user else ''
    r['email'] = user['email'] if user else ''
    return jsonify(r)

@app.route('/api/resident/<user_id>', methods=['PUT'])
def update_resident_by_user(user_id):
    data = request.get_json()
    flat_number = data.get('flat_number', '').strip().upper()
    occupation = data.get('occupation', '').strip()
    phone = data.get('phone', '').strip()
    family_members = data.get('family_members', 1)
    if not flat_number:
        return jsonify({'ok': False, 'error': 'Flat number is required.'}), 400
    residents = _load('residents')
    existing = _get_resident_by_uid(user_id)
    if existing:
        for r in residents:
            if r['id'] == existing['id']:
                r['flat_number'] = flat_number; r['family_members'] = family_members; r['occupation'] = occupation; r['phone'] = phone
                break
    else:
        residents.append({'id': _next_id('residents'), 'user_id': user_id, 'flat_number': flat_number, 'family_members': family_members, 'occupation': occupation, 'phone': phone})
    _save('residents', residents)
    return jsonify({'ok': True, 'message': 'Profile updated!'})

# ── Maintenance ──────────────────────────────────────────────────────────

@app.route('/api/maintenance', methods=['GET'])
def get_maintenance():
    user_id = request.args.get('user_id')
    records = _load('maintenance')
    users = {u['id']: u for u in _load('users')}
    residents = {r['user_id']: r for r in _load('residents')}
    if user_id:
        records = [m for m in records if m['user_id'] == user_id]
    records.sort(key=lambda x: (x.get('year', 0), x.get('month', 0)), reverse=True)
    for m in records:
        u = users.get(m.get('user_id', ''))
        m['name'] = u['name'] if u else 'Unknown'
        if not user_id:
            rr = residents.get(m.get('user_id', ''))
            m['flat_number'] = rr['flat_number'] if rr else ''
    return jsonify(records)

@app.route('/api/maintenance/current', methods=['GET'])
def get_current_maintenance():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400
    now = datetime.datetime.now()
    month = f'{now.month:02d}'
    year = now.year
    records = _load('maintenance')
    for m in records:
        if m['user_id'] == user_id and m['month'] == month and m['year'] == year:
            user = _get_user_by_uid(user_id)
            m['name'] = user['name'] if user else ''
            r = _get_resident_by_uid(user_id)
            m['flat_number'] = r['flat_number'] if r else ''
            return jsonify(m)
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
    records = _load('maintenance')
    for m in records:
        if m['user_id'] == user_id and m['month'] == month and m['year'] == year:
            return jsonify({'ok': False, 'error': 'Maintenance record already exists for this period.'}), 409
    records.append({'id': _next_id('maintenance'), 'user_id': user_id, 'month': month, 'year': year, 'amount': float(amount), 'status': status, 'paid_date': '', 'created_at': _now()})
    _save('maintenance', records)
    return jsonify({'ok': True, 'message': 'Maintenance record created!'}), 201

@app.route('/api/maintenance/<int:mid>', methods=['PATCH'])
def update_maintenance(mid):
    data = request.get_json()
    status = data.get('status')
    if status not in ('paid', 'pending'):
        return jsonify({'ok': False, 'error': 'Invalid status.'}), 400
    paid_date = _today() if status == 'paid' else ''
    records = _load('maintenance')
    for m in records:
        if m['id'] == mid:
            m['status'] = status; m['paid_date'] = paid_date
            break
    _save('maintenance', records)
    return jsonify({'ok': True, 'message': 'Maintenance updated.'})

@app.route('/api/maintenance/bulk', methods=['POST'])
def bulk_create_maintenance():
    data = request.get_json()
    month = data.get('month')
    year = data.get('year')
    amount = data.get('amount', 0)
    if not month or not year:
        return jsonify({'ok': False, 'error': 'month and year required.'}), 400
    residents = _load('residents')
    records = _load('maintenance')
    count = 0
    existing_set = {(m['user_id'], m['month'], m['year']) for m in records}
    for r in residents:
        uid = r['user_id']
        if (uid, month, year) not in existing_set:
            records.append({'id': _next_id('maintenance'), 'user_id': uid, 'month': month, 'year': year, 'amount': float(amount), 'status': 'pending', 'paid_date': '', 'created_at': _now()})
            count += 1
    _save('maintenance', records)
    return jsonify({'ok': True, 'message': f'{count} maintenance records created.'})

@app.route('/')
def serve_index():
    return send_from_directory(BASE, 'login.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(BASE, filename)

if __name__ == '__main__':
    print('Server running with Firebase Auth + JSON storage')
    app.run(host='0.0.0.0', port=5000, debug=False)
