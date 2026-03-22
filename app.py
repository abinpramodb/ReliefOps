"""
ReliefOps — Flask Backend
Database: SQLite
Run: python app.py
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3, os, hashlib, datetime

app = Flask(__name__, static_folder='.')
CORS(app)

DB = 'reliefops.db'

# ─────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
    conn.executescript(open('schema.sql').read())
    conn.commit()
    conn.close()

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def rows_to_list(rows):
    return [dict(r) for r in rows]

def get_role(req):
    return req.headers.get('X-Role', '')

def get_user_id(req):
    uid = req.headers.get('X-User-Id', '')
    return int(uid) if uid.isdigit() else None

def require_admin(req):
    if get_role(req) != 'admin':
        return None, jsonify(error='Admin access required'), 403
    return get_user_id(req), None, None

def require_volunteer(req):
    role = get_role(req)
    if role not in ('admin', 'volunteer'):
        return None, jsonify(error='Volunteer access required'), 403
    return get_user_id(req), None, None

def require_donor(req):
    role = get_role(req)
    if role not in ('admin', 'donor'):
        return None, jsonify(error='Donor access required'), 403
    return get_user_id(req), None, None

def today():
    return datetime.date.today().isoformat()


# ─────────────────────────────────────────────
# SERVE HTML PAGES
# ─────────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory('.', 'dashboard.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('.', filename)


# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────
@app.route('/api/auth/register', methods=['POST'])
def register():
    data   = request.json or {}
    name   = (data.get('name') or '').strip()
    email  = (data.get('email') or '').strip().lower()
    pw     = data.get('password') or ''
    role   = data.get('role') or 'donor'
    phone  = data.get('phone') or ''
    org    = data.get('organization') or ''

    if not name or not email or not pw:
        return jsonify(error='Name, email and password are required'), 400
    if role not in ('admin', 'donor', 'volunteer'):
        return jsonify(error='Invalid role'), 400

    conn = get_db()
    try:
        existing = conn.execute('SELECT user_id FROM users WHERE email=?', (email,)).fetchone()
        if existing:
            return jsonify(error='Email already registered'), 409

        conn.execute(
            'INSERT INTO users (full_name,email,password_hash,role,phone,organization) VALUES (?,?,?,?,?,?)',
            (name, email, hash_password(pw), role, phone, org)
        )
        conn.commit()
        uid = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        return jsonify(message='Registered successfully', id=uid, name=name, email=email, role=role)
    finally:
        conn.close()


@app.route('/api/auth/login', methods=['POST'])
def login():
    data  = request.json or {}
    email = (data.get('email') or '').strip().lower()
    pw    = data.get('password') or ''

    if not email or not pw:
        return jsonify(error='Email and password required'), 400

    conn = get_db()
    try:
        user = conn.execute(
            'SELECT * FROM users WHERE email=? AND password_hash=?',
            (email, hash_password(pw))
        ).fetchone()
        if not user:
            return jsonify(error='Invalid email or password'), 401
        return jsonify(
            id=user['user_id'],
            name=user['full_name'],
            email=user['email'],
            role=user['role'],
            phone=user['phone'] or '',
            organization=user['organization'] or '',
            joined_date=user['joined_date'] or ''
        )
    finally:
        conn.close()


# ─────────────────────────────────────────────
# STATS (dashboard)
# ─────────────────────────────────────────────
@app.route('/api/stats')
def stats():
    conn = get_db()
    try:
        active_disasters = conn.execute("SELECT COUNT(*) FROM disaster WHERE status='Active'").fetchone()[0]
        total_disasters  = conn.execute("SELECT COUNT(*) FROM disaster").fetchone()[0]
        active_camps     = conn.execute("SELECT COUNT(*) FROM relief_camp WHERE status IN ('Active','Full')").fetchone()[0]
        total_camps      = conn.execute("SELECT COUNT(*) FROM relief_camp").fetchone()[0]
        total_victims    = conn.execute("SELECT COALESCE(SUM(current_occupancy),0) FROM relief_camp").fetchone()[0]
        resource_types   = conn.execute("SELECT COUNT(*) FROM resource").fetchone()[0]
        pending_donations= conn.execute("SELECT COUNT(*) FROM donation WHERE status='Pending'").fetchone()[0]
        return jsonify(
            active_disasters=active_disasters, total_disasters=total_disasters,
            active_camps=active_camps, total_camps=total_camps,
            total_victims=total_victims, resource_types=resource_types,
            pending_donations=pending_donations
        )
    finally:
        conn.close()


# ─────────────────────────────────────────────
# DISASTERS
# ─────────────────────────────────────────────
@app.route('/api/disasters', methods=['GET'])
def get_disasters():
    conn  = get_db()
    try:
        limit = request.args.get('limit')
        sql   = 'SELECT * FROM disaster ORDER BY start_date DESC'
        if limit:
            sql += f' LIMIT {int(limit)}'
        rows = rows_to_list(conn.execute(sql).fetchall())
        return jsonify(disasters=rows)
    finally:
        conn.close()


@app.route('/api/disasters', methods=['POST'])
def add_disaster():
    uid, err, code = require_admin(request)
    if err: return err, code
    d = request.json or {}
    required = ['disaster_name','disaster_type','location','severity_level','start_date','status']
    if not all(d.get(k) for k in required):
        return jsonify(error='Missing required fields'), 400

    conn = get_db()
    try:
        conn.execute(
            'INSERT INTO disaster (disaster_name,disaster_type,location,severity_level,start_date,end_date,status,lat,lng) VALUES (?,?,?,?,?,?,?,?,?)',
            (d['disaster_name'], d['disaster_type'], d['location'], d['severity_level'],
             d['start_date'], d.get('end_date'), d['status'], d.get('lat'), d.get('lng'))
        )
        conn.commit()
        return jsonify(message='Disaster added'), 201
    finally:
        conn.close()


@app.route('/api/disasters/<int:did>', methods=['PUT'])
def update_disaster(did):
    uid, err, code = require_admin(request)
    if err: return err, code
    d = request.json or {}
    conn = get_db()
    try:
        conn.execute(
            'UPDATE disaster SET disaster_name=?,disaster_type=?,location=?,severity_level=?,start_date=?,end_date=?,status=?,lat=?,lng=? WHERE disaster_id=?',
            (d.get('disaster_name'), d.get('disaster_type'), d.get('location'), d.get('severity_level'),
             d.get('start_date'), d.get('end_date'), d.get('status'), d.get('lat'), d.get('lng'), did)
        )
        conn.commit()
        return jsonify(message='Updated')
    finally:
        conn.close()


@app.route('/api/disasters/<int:did>', methods=['DELETE'])
def delete_disaster(did):
    uid, err, code = require_admin(request)
    if err: return err, code
    conn = get_db()
    try:
        conn.execute('DELETE FROM disaster WHERE disaster_id=?', (did,))
        conn.commit()
        return jsonify(message='Deleted')
    finally:
        conn.close()


# ─────────────────────────────────────────────
# CAMPS
# ─────────────────────────────────────────────
@app.route('/api/camps', methods=['GET'])
def get_camps():
    conn = get_db()
    try:
        limit = request.args.get('limit')
        sql = '''
            SELECT rc.*, d.disaster_name
            FROM relief_camp rc
            LEFT JOIN disaster d ON rc.disaster_id = d.disaster_id
            ORDER BY rc.camp_id DESC
        '''
        if limit:
            sql += f' LIMIT {int(limit)}'
        rows = rows_to_list(conn.execute(sql).fetchall())
        return jsonify(camps=rows)
    finally:
        conn.close()


@app.route('/api/camps/<int:cid>', methods=['GET'])
def get_camp(cid):
    conn = get_db()
    try:
        row = conn.execute('''
            SELECT rc.*, d.disaster_name
            FROM relief_camp rc
            LEFT JOIN disaster d ON rc.disaster_id = d.disaster_id
            WHERE rc.camp_id=?
        ''', (cid,)).fetchone()
        if not row:
            return jsonify(error='Camp not found'), 404
        return jsonify(camp=dict(row))
    finally:
        conn.close()


@app.route('/api/camps', methods=['POST'])
def add_camp():
    uid, err, code = require_admin(request)
    if err: return err, code
    d = request.json or {}
    if not all(d.get(k) for k in ['camp_name','location','total_capacity','disaster_id']):
        return jsonify(error='Missing required fields: camp_name, location, total_capacity, disaster_id'), 400
    conn = get_db()
    try:
        conn.execute(
            'INSERT INTO relief_camp (camp_name,location,total_capacity,current_occupancy,status,opened_date,disaster_id) VALUES (?,?,?,?,?,?,?)',
            (d['camp_name'], d['location'], int(d['total_capacity']),
             int(d.get('current_occupancy', 0)),
             d.get('status', 'Active'),
             d.get('opened_date'),
             int(d['disaster_id']))
        )
        conn.commit()
        return jsonify(message='Camp added'), 201
    finally:
        conn.close()


@app.route('/api/camps/<int:cid>', methods=['PUT'])
def update_camp(cid):
    uid, err, code = require_admin(request)
    if err: return err, code
    d = request.json or {}
    conn = get_db()
    try:
        conn.execute(
            'UPDATE relief_camp SET camp_name=?,location=?,total_capacity=?,current_occupancy=?,status=?,opened_date=?,disaster_id=? WHERE camp_id=?',
            (d.get('camp_name'), d.get('location'), d.get('total_capacity'),
             d.get('current_occupancy', 0), d.get('status'),
             d.get('opened_date'), d.get('disaster_id'), cid)
        )
        conn.commit()
        return jsonify(message='Updated')
    finally:
        conn.close()


@app.route('/api/camps/<int:cid>', methods=['DELETE'])
def delete_camp(cid):
    uid, err, code = require_admin(request)
    if err: return err, code
    conn = get_db()
    try:
        conn.execute('DELETE FROM relief_camp WHERE camp_id=?', (cid,))
        conn.commit()
        return jsonify(message='Deleted')
    finally:
        conn.close()


@app.route('/api/camps/<int:cid>/victims', methods=['PUT'])
def update_victims(cid):
    uid, err, code = require_volunteer(request)
    if err: return err, code
    count = (request.json or {}).get('count', 0)
    conn = get_db()
    try:
        camp = conn.execute('SELECT total_capacity FROM relief_camp WHERE camp_id=?', (cid,)).fetchone()
        if not camp:
            return jsonify(error='Camp not found'), 404
        status = 'Full' if count >= camp['total_capacity'] else 'Active'
        conn.execute('UPDATE relief_camp SET current_occupancy=?, status=? WHERE camp_id=?', (count, status, cid))
        conn.commit()
        return jsonify(message='Updated', status=status)
    finally:
        conn.close()


# ─────────────────────────────────────────────
# SHORTAGES
# ─────────────────────────────────────────────
@app.route('/api/camps/<int:cid>/shortages', methods=['GET'])
def get_camp_shortages(cid):
    conn = get_db()
    try:
        rows = conn.execute('''
            SELECT s.*, r.resource_name, r.unit
            FROM resource_shortage s
            JOIN resource r ON s.resource_id = r.resource_id
            WHERE s.camp_id=?
            ORDER BY s.reported_at DESC
        ''', (cid,)).fetchall()
        return jsonify(shortages=rows_to_list(rows))
    finally:
        conn.close()


@app.route('/api/camps/<int:cid>/shortages', methods=['POST'])
def report_shortage(cid):
    uid, err, code = require_volunteer(request)
    if err: return err, code
    d = request.json or {}
    if not d.get('resource_id') or not d.get('quantity_needed'):
        return jsonify(error='resource_id and quantity_needed required'), 400
    conn = get_db()
    try:
        conn.execute(
            'INSERT INTO resource_shortage (camp_id,resource_id,quantity_needed,remarks,status) VALUES (?,?,?,?,?)',
            (cid, d['resource_id'], d['quantity_needed'], d.get('remarks',''), 'Pending')
        )
        conn.commit()
        return jsonify(message='Shortage reported'), 201
    finally:
        conn.close()


@app.route('/api/shortages', methods=['GET'])
def get_all_shortages():
    conn = get_db()
    try:
        status = request.args.get('status')
        sql = '''
            SELECT s.*, r.resource_name, r.unit, rc.camp_name
            FROM resource_shortage s
            JOIN resource r ON s.resource_id = r.resource_id
            JOIN relief_camp rc ON s.camp_id = rc.camp_id
        '''
        params = []
        if status:
            sql += ' WHERE s.status=?'
            params.append(status)
        sql += ' ORDER BY s.reported_at DESC'
        rows = conn.execute(sql, params).fetchall()
        return jsonify(shortages=rows_to_list(rows))
    finally:
        conn.close()


@app.route('/api/shortages/<int:sid>/received', methods=['PUT'])
def mark_received(sid):
    uid, err, code = require_volunteer(request)
    if err: return err, code
    conn = get_db()
    try:
        conn.execute("UPDATE resource_shortage SET status='Received' WHERE shortage_id=?", (sid,))
        conn.commit()
        return jsonify(message='Marked as received')
    finally:
        conn.close()


# ─────────────────────────────────────────────
# RESOURCES
# ─────────────────────────────────────────────
@app.route('/api/resources', methods=['GET'])
def get_resources():
    conn = get_db()
    try:
        rows = rows_to_list(conn.execute('SELECT * FROM resource ORDER BY resource_name').fetchall())
        return jsonify(resources=rows)
    finally:
        conn.close()


@app.route('/api/resources', methods=['POST'])
def add_resource():
    uid, err, code = require_admin(request)
    if err: return err, code
    d = request.json or {}
    if not all(d.get(k) for k in ['resource_name','category','unit']):
        return jsonify(error='Missing required fields'), 400
    conn = get_db()
    try:
        conn.execute(
            'INSERT INTO resource (resource_name,category,unit,quantity_available,min_threshold) VALUES (?,?,?,?,?)',
            (d['resource_name'], d['category'], d['unit'],
             int(d.get('quantity_available',0)), int(d.get('min_threshold',0)))
        )
        conn.commit()
        return jsonify(message='Resource added'), 201
    finally:
        conn.close()


@app.route('/api/resources/<int:rid>', methods=['PUT'])
def update_resource(rid):
    uid, err, code = require_admin(request)
    if err: return err, code
    d = request.json or {}
    conn = get_db()
    try:
        conn.execute(
            'UPDATE resource SET resource_name=?,category=?,unit=?,quantity_available=?,min_threshold=? WHERE resource_id=?',
            (d.get('resource_name'), d.get('category'), d.get('unit'),
             d.get('quantity_available'), d.get('min_threshold'), rid)
        )
        conn.commit()
        return jsonify(message='Updated')
    finally:
        conn.close()


@app.route('/api/resources/<int:rid>', methods=['DELETE'])
def delete_resource(rid):
    uid, err, code = require_admin(request)
    if err: return err, code
    conn = get_db()
    try:
        conn.execute('DELETE FROM resource WHERE resource_id=?', (rid,))
        conn.commit()
        return jsonify(message='Deleted')
    finally:
        conn.close()


# ─────────────────────────────────────────────
# ALLOCATIONS
# ─────────────────────────────────────────────
@app.route('/api/allocations', methods=['GET'])
def get_allocations():
    conn = get_db()
    try:
        camp_id = request.args.get('camp_id')
        sql = '''
            SELECT ra.*, r.resource_name, r.unit, rc.camp_name
            FROM resource_allocation ra
            JOIN resource r ON ra.resource_id = r.resource_id
            JOIN relief_camp rc ON ra.camp_id = rc.camp_id
        '''
        params = []
        if camp_id:
            sql += ' WHERE ra.camp_id=?'
            params.append(int(camp_id))
        sql += ' ORDER BY ra.allocation_date DESC'
        rows = conn.execute(sql, params).fetchall()
        return jsonify(allocations=rows_to_list(rows))
    finally:
        conn.close()


@app.route('/api/allocations', methods=['POST'])
def allocate():
    uid, err, code = require_admin(request)
    if err: return err, code
    d = request.json or {}
    if not all(d.get(k) for k in ['resource_id','camp_id','quantity_dispatched','allocation_date']):
        return jsonify(error='Missing required fields'), 400

    conn = get_db()
    try:
        res = conn.execute('SELECT quantity_available FROM resource WHERE resource_id=?', (d['resource_id'],)).fetchone()
        if not res:
            return jsonify(error='Resource not found'), 404
        qty = int(d['quantity_dispatched'])
        if qty > res['quantity_available']:
            return jsonify(error=f"Not enough stock. Available: {res['quantity_available']}"), 400

        conn.execute('UPDATE resource SET quantity_available=quantity_available-? WHERE resource_id=?', (qty, d['resource_id']))
        conn.execute(
            'INSERT INTO resource_allocation (resource_id,camp_id,quantity_dispatched,allocation_date,status) VALUES (?,?,?,?,?)',
            (d['resource_id'], d['camp_id'], qty, d['allocation_date'], 'Dispatched')
        )
        conn.execute(
            "UPDATE resource_shortage SET status='Allocated' WHERE camp_id=? AND resource_id=? AND status='Pending'",
            (d['camp_id'], d['resource_id'])
        )
        conn.commit()
        return jsonify(message='Allocated successfully'), 201
    finally:
        conn.close()


# ─────────────────────────────────────────────
# DONORS
# ─────────────────────────────────────────────
@app.route('/api/donors', methods=['GET'])
def get_donors():
    uid, err, code = require_admin(request)
    if err: return err, code
    conn = get_db()
    try:
        rows = conn.execute('''
            SELECT u.user_id, u.full_name, u.email, u.phone, u.organization, u.joined_date,
                   COUNT(d.donation_id) as total_donations,
                   COALESCE(SUM(CASE WHEN d.status='Completed' THEN d.quantity ELSE 0 END),0) as total_qty
            FROM users u
            LEFT JOIN donation d ON u.user_id = d.donor_id
            WHERE u.role = 'donor'
            GROUP BY u.user_id
            ORDER BY total_donations DESC
        ''').fetchall()
        return jsonify(donors=rows_to_list(rows))
    finally:
        conn.close()


@app.route('/api/donors/<int:uid>', methods=['GET'])
def get_donor(uid):
    uid_me, err, code = require_donor(request)
    if err: return err, code
    # Admin can view any; donor can only view self
    role = get_role(request)
    if role != 'admin' and uid_me != uid:
        return jsonify(error='Access denied'), 403
    conn = get_db()
    try:
        user = conn.execute('SELECT * FROM users WHERE user_id=? AND role="donor"', (uid,)).fetchone()
        if not user:
            return jsonify(error='Donor not found'), 404
        donations = conn.execute('''
            SELECT dn.*, r.resource_name, r.unit
            FROM donation dn
            JOIN resource r ON dn.resource_id = r.resource_id
            WHERE dn.donor_id=?
            ORDER BY dn.donation_date DESC
        ''', (uid,)).fetchall()
        return jsonify(donor=dict(user), donations=rows_to_list(donations))
    finally:
        conn.close()


# ─────────────────────────────────────────────
# DONATIONS  (new approval workflow)
# status flow: Pending → Completed (admin approves, resource updated)
#                       → Rejected  (admin rejects, no resource change)
# ─────────────────────────────────────────────
@app.route('/api/donations', methods=['GET'])
def get_donations():
    uid, err, code = require_admin(request)
    if err: return err, code
    conn = get_db()
    try:
        status_filter = request.args.get('status')
        sql = '''
            SELECT dn.*, u.full_name as donor_name, u.email as donor_email,
                   u.phone as donor_phone, u.organization as donor_org,
                   r.resource_name, r.unit
            FROM donation dn
            JOIN users u ON dn.donor_id = u.user_id
            JOIN resource r ON dn.resource_id = r.resource_id
        '''
        params = []
        if status_filter:
            sql += ' WHERE dn.status=?'
            params.append(status_filter)
        sql += ' ORDER BY dn.donation_date DESC'
        rows = conn.execute(sql, params).fetchall()
        return jsonify(donations=rows_to_list(rows))
    finally:
        conn.close()


@app.route('/api/donations/mine', methods=['GET'])
def get_my_donations():
    uid, err, code = require_donor(request)
    if err: return err, code
    conn = get_db()
    try:
        rows = conn.execute('''
            SELECT dn.*, r.resource_name, r.unit
            FROM donation dn
            JOIN resource r ON dn.resource_id = r.resource_id
            WHERE dn.donor_id=?
            ORDER BY dn.donation_date DESC
        ''', (uid,)).fetchall()
        return jsonify(donations=rows_to_list(rows))
    finally:
        conn.close()


@app.route('/api/donations', methods=['POST'])
def add_donation():
    uid, err, code = require_donor(request)
    if err: return err, code
    d = request.json or {}
    if not d.get('resource_id') or not d.get('quantity'):
        return jsonify(error='resource_id and quantity required'), 400

    qty = int(d['quantity'])
    conn = get_db()
    try:
        # Donation is Pending until admin approves — resource NOT yet updated
        conn.execute(
            'INSERT INTO donation (donor_id,resource_id,quantity,donation_date,status,remarks) VALUES (?,?,?,?,?,?)',
            (uid, d['resource_id'], qty, today(), 'Pending', d.get('remarks',''))
        )
        conn.commit()
        return jsonify(message='Donation submitted. Awaiting admin approval.'), 201
    finally:
        conn.close()


@app.route('/api/donations/<int:did>/approve', methods=['PUT'])
def approve_donation(did):
    uid, err, code = require_admin(request)
    if err: return err, code
    conn = get_db()
    try:
        dn = conn.execute('SELECT * FROM donation WHERE donation_id=?', (did,)).fetchone()
        if not dn:
            return jsonify(error='Donation not found'), 404
        if dn['status'] != 'Pending':
            return jsonify(error='Donation is not pending'), 400
        # Mark completed and add to resource pool
        conn.execute("UPDATE donation SET status='Completed' WHERE donation_id=?", (did,))
        conn.execute('UPDATE resource SET quantity_available=quantity_available+? WHERE resource_id=?',
                     (dn['quantity'], dn['resource_id']))
        conn.commit()
        return jsonify(message='Donation approved and added to resource pool')
    finally:
        conn.close()


@app.route('/api/donations/<int:did>/reject', methods=['PUT'])
def reject_donation(did):
    uid, err, code = require_admin(request)
    if err: return err, code
    conn = get_db()
    try:
        dn = conn.execute('SELECT * FROM donation WHERE donation_id=?', (did,)).fetchone()
        if not dn:
            return jsonify(error='Donation not found'), 404
        if dn['status'] != 'Pending':
            return jsonify(error='Donation is not pending'), 400
        conn.execute("UPDATE donation SET status='Rejected' WHERE donation_id=?", (did,))
        conn.commit()
        return jsonify(message='Donation rejected')
    finally:
        conn.close()


@app.route('/api/donations/<int:did>', methods=['DELETE'])
def delete_donation(did):
    uid, err, code = require_admin(request)
    if err: return err, code
    conn = get_db()
    try:
        dn = conn.execute('SELECT * FROM donation WHERE donation_id=?', (did,)).fetchone()
        if not dn:
            return jsonify(error='Donation not found'), 404
        # Only reverse resource pool if donation was already completed
        if dn['status'] == 'Completed':
            conn.execute('UPDATE resource SET quantity_available=MAX(0,quantity_available-?) WHERE resource_id=?',
                         (dn['quantity'], dn['resource_id']))
        conn.execute('DELETE FROM donation WHERE donation_id=?', (did,))
        conn.commit()
        return jsonify(message='Donation removed')
    finally:
        conn.close()


# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────
if __name__ == '__main__':
    if not os.path.exists(DB):
        init_db()
        print('Database created.')
    app.run(debug=True, port=3000)