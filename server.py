import os, datetime, random
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, auth as admin_auth, firestore

app = Flask(__name__)
CORS(app, origins='*')

BASE = os.path.dirname(os.path.abspath(__file__))

cred = credentials.Certificate(os.path.join(BASE, 'firebase-key.json'))
firebase_admin.initialize_app(cred)
db = firestore.client()

FIREBASE_API_KEY = "AIzaSyAEtvIqs0Vw-b8CWU9jSLsUAFANOjbDpEs"

def _now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

def _today():
    return datetime.datetime.now().strftime('%Y-%m-%d')

def _doc_to_dict(doc):
    if doc is None or not doc.exists:
        return None
    d = doc.to_dict()
    d['id'] = doc.id
    return d

def _get_user_by_uid(uid):
    doc = db.collection('users').document(uid).get()
    return _doc_to_dict(doc)

def _get_resident_by_uid(uid):
    docs = db.collection('residents').where('user_id', '==', uid).limit(1).get()
    for d in docs:
        return _doc_to_dict(d)
    return None

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

# ── Seed data ──────────────────────────────────────────────────────────

def seed_db():
    if len(db.collection('notices').limit(1).get()) == 0:
        notices = [
            {'title': 'Water Supply Schedule', 'content': 'Water supply will be available from 6:00 AM to 8:00 AM and 6:00 PM to 8:00 PM daily.', 'posted_by': 'Admin', 'created_at': _now()},
            {'title': 'Annual Maintenance Fee', 'content': 'Annual maintenance fee of Rs. 12,000 is due by 31st July. Please pay at the office.', 'posted_by': 'Admin', 'created_at': _now()},
            {'title': 'Security Update', 'content': 'All residents are requested to use the new RFID tags for gate entry from 1st August.', 'posted_by': 'Admin', 'created_at': _now()},
            {'title': 'Yoga Session', 'content': 'Free yoga sessions every morning at 6:30 AM in the community park. All ages welcome.', 'posted_by': 'Admin', 'created_at': _now()},
            {'title': 'Garbage Collection', 'content': 'Garbage collection timings changed to 7:00 AM. Please segregate wet and dry waste.', 'posted_by': 'Admin', 'created_at': _now()},
        ]
        for n in notices:
            db.collection('notices').add(n)
    if len(db.collection('events').limit(1).get()) == 0:
        events = [
            {'title': 'Independence Day Celebration', 'description': 'Flag hoisting followed by cultural programs and refreshments.', 'event_date': '2026-08-15', 'venue': 'Main Lawn', 'posted_by': 'Admin', 'created_at': _now()},
            {'title': 'Health Checkup Camp', 'description': 'Free health checkup including blood pressure, sugar, and BMI.', 'event_date': '2026-07-20', 'venue': 'Community Hall', 'posted_by': 'Admin', 'created_at': _now()},
            {'title': 'Diwali Milan', 'description': 'Annual Diwali celebration with lighting, sweets, and fireworks.', 'event_date': '2026-10-31', 'venue': 'Entire Society', 'posted_by': 'Admin', 'created_at': _now()},
            {'title': 'Kids Art Competition', 'description': 'Art competition for children aged 5-15. Bring your own colors.', 'event_date': '2026-08-05', 'venue': 'Club House', 'posted_by': 'Admin', 'created_at': _now()},
        ]
        for e in events:
            db.collection('events').add(e)
    print('Firestore seeded with default data')

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
    user_data = {'name': name, 'email': email, 'role': role}
    db.collection('users').document(uid).set(user_data)

    if role == 'resident':
        db.collection('residents').add({'user_id': uid, 'flat_number': 'TBD', 'family_members': 1, 'occupation': '', 'phone': ''})

    return jsonify({'ok': True, 'message': 'Account created successfully!', 'user': {'id': uid, 'name': name, 'email': email, 'role': role}}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    login_id = data.get('login_id', '').strip()
    password = data.get('password', '')
    role = data.get('role', 'resident')

    if not login_id or not password:
        return jsonify({'ok': False, 'error': 'Please fill in all fields.'}), 400

    # Try email login
    uid, err = firebase_sign_in(login_id, password)
    if err:
        # Try looking up by name
        users = db.collection('users').get()
        matched = None
        for u in users:
            d = _doc_to_dict(u)
            if d and d.get('name', '').lower() == login_id.lower():
                # Found by name, try their email
                uid2, err2 = firebase_sign_in(d['email'], password)
                if not err2:
                    uid = uid2
                    matched = d
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


# ── Users (Firestore) ──────────────────────────────────────────────────

@app.route('/api/users', methods=['GET'])
def get_users():
    role_filter = request.args.get('role')
    docs = db.collection('users').get()
    result = []
    for d in docs:
        u = _doc_to_dict(d)
        if role_filter and u['role'] != role_filter:
            continue
        result.append(u)
    return jsonify(result)

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
    docs = db.collection('notices').order_by('created_at', direction=firestore.Query.DESCENDING).get()
    return jsonify([_doc_to_dict(d) for d in docs])

@app.route('/api/notices', methods=['POST'])
def create_notice():
    data = request.get_json()
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    posted_by = data.get('posted_by', 'Admin').strip()
    if not title or not content:
        return jsonify({'ok': False, 'error': 'Title and content are required.'}), 400
    db.collection('notices').add({'title': title, 'content': content, 'posted_by': posted_by, 'created_at': _now()})
    return jsonify({'ok': True, 'message': 'Notice added!'}), 201

@app.route('/api/notices/<notice_id>', methods=['PUT'])
def update_notice(notice_id):
    data = request.get_json()
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    if not title or not content:
        return jsonify({'ok': False, 'error': 'Title and content are required.'}), 400
    db.collection('notices').document(notice_id).update({'title': title, 'content': content})
    return jsonify({'ok': True, 'message': 'Notice updated!'})

@app.route('/api/notices/<notice_id>', methods=['DELETE'])
def delete_notice(notice_id):
    db.collection('notices').document(notice_id).delete()
    return jsonify({'ok': True, 'message': 'Notice deleted!'})

# ── Events ────────────────────────────────────────────────────────────────

@app.route('/api/events', methods=['GET'])
def get_events():
    today = _today()
    docs = db.collection('events').where('event_date', '>=', today).order_by('event_date').get()
    return jsonify([_doc_to_dict(d) for d in docs])

@app.route('/api/events/all', methods=['GET'])
def get_all_events():
    docs = db.collection('events').order_by('event_date').get()
    return jsonify([_doc_to_dict(d) for d in docs])

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
    db.collection('events').add({'title': title, 'description': description, 'event_date': event_date, 'venue': venue, 'posted_by': posted_by, 'created_at': _now()})
    return jsonify({'ok': True, 'message': 'Event added!'}), 201

@app.route('/api/events/<event_id>', methods=['PUT'])
def update_event(event_id):
    data = request.get_json()
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    event_date = data.get('event_date', '').strip()
    venue = data.get('venue', '').strip()
    if not title or not description or not event_date:
        return jsonify({'ok': False, 'error': 'Title, description, and date are required.'}), 400
    db.collection('events').document(event_id).update({'title': title, 'description': description, 'event_date': event_date, 'venue': venue})
    return jsonify({'ok': True, 'message': 'Event updated!'})

@app.route('/api/events/<event_id>', methods=['DELETE'])
def delete_event(event_id):
    db.collection('events').document(event_id).delete()
    return jsonify({'ok': True, 'message': 'Event deleted!'})

# ── Complaints ────────────────────────────────────────────────────────────

@app.route('/api/complaints', methods=['GET'])
def get_complaints():
    user_id = request.args.get('user_id')
    warnings = request.args.get('warnings')
    coll = db.collection('complaints')
    if warnings and user_id:
        docs = coll.where('user_id', '==', user_id).where('status', '==', 'discarded').get()
        return jsonify([{'id': d.id, 'title': d.to_dict().get('title'), 'resolved_at': d.to_dict().get('resolved_at')} for d in docs])
    elif user_id:
        docs = coll.where('user_id', '==', user_id).order_by('created_at', direction=firestore.Query.DESCENDING).get()
    else:
        docs = coll.order_by('created_at', direction=firestore.Query.DESCENDING).get()
    return jsonify([_doc_to_dict(d) for d in docs])

@app.route('/api/complaints', methods=['POST'])
def raise_complaint():
    data = request.get_json()
    user_id = data.get('user_id')
    user_name = data.get('user_name', '').strip()
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    if not user_id or not title or not description:
        return jsonify({'ok': False, 'error': 'Title and description are required.'}), 400
    db.collection('complaints').add({'user_id': user_id, 'user_name': user_name, 'title': title, 'description': description, 'status': 'open', 'created_at': _now(), 'resolution': '', 'resolved_at': '', 'accepted_by': '', 'fraud_warning': 0})
    return jsonify({'ok': True, 'message': 'Complaint registered successfully!'}), 201

@app.route('/api/complaints/<complaint_id>', methods=['PATCH'])
def update_complaint(complaint_id):
    data = request.get_json()
    status = data.get('status')
    if status not in ('open', 'in_progress', 'resolved', 'discarded'):
        return jsonify({'ok': False, 'error': 'Invalid status.'}), 400
    resolution = data.get('resolution', '').strip()
    accepted_by = data.get('accepted_by', '').strip()
    now = _now()
    ref = db.collection('complaints').document(complaint_id)
    if status == 'resolved' and resolution:
        ref.update({'status': status, 'resolution': resolution, 'resolved_at': now})
    elif status == 'in_progress':
        ref.update({'status': status, 'accepted_by': accepted_by, 'resolved_at': now})
    elif status == 'discarded':
        ref.update({'status': status, 'resolved_at': now, 'fraud_warning': 1})
    else:
        ref.update({'status': status})
    return jsonify({'ok': True, 'message': 'Complaint updated.'})

@app.route('/api/complaints/<complaint_id>', methods=['DELETE'])
def delete_complaint(complaint_id):
    db.collection('complaints').document(complaint_id).delete()
    return jsonify({'ok': True, 'message': 'Complaint deleted.'})

# ── Residents ─────────────────────────────────────────────────────────────

@app.route('/api/residents', methods=['GET'])
def get_residents():
    docs = db.collection('residents').order_by('flat_number').get()
    result = []
    for d in docs:
        r = _doc_to_dict(d)
        user = _get_user_by_uid(r.get('user_id', ''))
        r['name'] = user['name'] if user else 'Unknown'
        r['email'] = user['email'] if user else ''
        result.append(r)
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
    existing = _get_resident_by_uid(user_id)
    if existing:
        return jsonify({'ok': False, 'error': 'Resident already exists for this user.'}), 409
    db.collection('residents').add({'user_id': user_id, 'flat_number': flat_number, 'family_members': family_members, 'occupation': occupation, 'phone': phone})
    return jsonify({'ok': True, 'message': 'Resident added!'}), 201

@app.route('/api/residents/<resident_id>', methods=['PUT'])
def update_resident(resident_id):
    data = request.get_json()
    flat_number = data.get('flat_number', '').strip().upper()
    family_members = data.get('family_members', 1)
    occupation = data.get('occupation', '').strip()
    phone = data.get('phone', '').strip()
    if not flat_number:
        return jsonify({'ok': False, 'error': 'Flat number is required.'}), 400
    db.collection('residents').document(resident_id).update({'flat_number': flat_number, 'family_members': family_members, 'occupation': occupation, 'phone': phone})
    return jsonify({'ok': True, 'message': 'Resident updated!'})

@app.route('/api/residents/<resident_id>', methods=['DELETE'])
def delete_resident(resident_id):
    db.collection('residents').document(resident_id).delete()
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
    existing = _get_resident_by_uid(user_id)
    if existing:
        db.collection('residents').document(existing['id']).update({'flat_number': flat_number, 'family_members': family_members, 'occupation': occupation, 'phone': phone})
    else:
        db.collection('residents').add({'user_id': user_id, 'flat_number': flat_number, 'family_members': family_members, 'occupation': occupation, 'phone': phone})
    return jsonify({'ok': True, 'message': 'Profile updated!'})

# ── Maintenance ──────────────────────────────────────────────────────────

@app.route('/api/maintenance', methods=['GET'])
def get_maintenance():
    user_id = request.args.get('user_id')
    coll = db.collection('maintenance')
    if user_id:
        docs = coll.where('user_id', '==', user_id).order_by('year', direction=firestore.Query.DESCENDING).order_by('month', direction=firestore.Query.DESCENDING).get()
    else:
        docs = coll.order_by('year', direction=firestore.Query.DESCENDING).order_by('month', direction=firestore.Query.DESCENDING).get()
    result = []
    for d in docs:
        m = _doc_to_dict(d)
        user = _get_user_by_uid(m.get('user_id', ''))
        m['name'] = user['name'] if user else 'Unknown'
        if not user_id:
            r = _get_resident_by_uid(m.get('user_id', ''))
            m['flat_number'] = r['flat_number'] if r else ''
        result.append(m)
    return jsonify(result)

@app.route('/api/maintenance/current', methods=['GET'])
def get_current_maintenance():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400
    now = datetime.datetime.now()
    month = f'{now.month:02d}'
    year = now.year
    docs = db.collection('maintenance').where('user_id', '==', user_id).where('month', '==', month).where('year', '==', year).limit(1).get()
    for d in docs:
        m = _doc_to_dict(d)
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
    existing = db.collection('maintenance').where('user_id', '==', user_id).where('month', '==', month).where('year', '==', year).limit(1).get()
    if len(existing) > 0:
        return jsonify({'ok': False, 'error': 'Maintenance record already exists for this period.'}), 409
    db.collection('maintenance').add({'user_id': user_id, 'month': month, 'year': year, 'amount': float(amount), 'status': status, 'paid_date': '', 'created_at': _now()})
    return jsonify({'ok': True, 'message': 'Maintenance record created!'}), 201

@app.route('/api/maintenance/<mid>', methods=['PATCH'])
def update_maintenance(mid):
    data = request.get_json()
    status = data.get('status')
    if status not in ('paid', 'pending'):
        return jsonify({'ok': False, 'error': 'Invalid status.'}), 400
    paid_date = _today() if status == 'paid' else ''
    db.collection('maintenance').document(mid).update({'status': status, 'paid_date': paid_date})
    return jsonify({'ok': True, 'message': 'Maintenance updated.'})

@app.route('/api/maintenance/bulk', methods=['POST'])
def bulk_create_maintenance():
    data = request.get_json()
    month = data.get('month')
    year = data.get('year')
    amount = data.get('amount', 0)
    if not month or not year:
        return jsonify({'ok': False, 'error': 'month and year required.'}), 400
    residents = db.collection('residents').get()
    count = 0
    for r in residents:
        rd = _doc_to_dict(r)
        uid = rd['user_id']
        existing = db.collection('maintenance').where('user_id', '==', uid).where('month', '==', month).where('year', '==', year).limit(1).get()
        if len(existing) == 0:
            db.collection('maintenance').add({'user_id': uid, 'month': month, 'year': year, 'amount': float(amount), 'status': 'pending', 'paid_date': '', 'created_at': _now()})
            count += 1
    return jsonify({'ok': True, 'message': f'{count} maintenance records created.'})

@app.route('/')
def serve_index():
    return send_from_directory(BASE, 'login.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(BASE, filename)

if __name__ == '__main__':
    print('Server running with Firebase Auth + Firestore')
    app.run(host='0.0.0.0', port=5000, debug=False)
