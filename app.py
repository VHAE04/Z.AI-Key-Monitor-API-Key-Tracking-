from flask import Flask, request, jsonify, render_template
import sqlite3
import json as json_mod
import requests as req_lib
from datetime import datetime
import threading
import os

app = Flask(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'keys.db')
API_URL = "https://api.z.ai/api/monitor/usage/quota/limit"
db_lock = threading.Lock()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT UNIQUE NOT NULL,
        status TEXT DEFAULT 'pending',
        level TEXT DEFAULT NULL,
        limits TEXT DEFAULT NULL,
        raw_response TEXT DEFAULT NULL,
        error TEXT DEFAULT NULL,
        last_checked TEXT DEFAULT NULL,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )''')
    conn.commit()
    conn.close()


def row_to_dict(row):
    d = dict(row)
    if d.get('limits'):
        try:
            d['limits'] = json_mod.loads(d['limits'])
        except Exception:
            d['limits'] = None
    if d.get('raw_response'):
        try:
            d['raw_response'] = json_mod.loads(d['raw_response'])
        except Exception:
            d['raw_response'] = None
    return d


def db_add_key(key):
    key = key.strip()
    if not key:
        return False
    with db_lock:
        conn = get_db()
        try:
            conn.execute("INSERT OR IGNORE INTO keys (key) VALUES (?)", (key,))
            conn.commit()
            return conn.total_changes > 0
        finally:
            conn.close()


def db_add_keys_bulk(keys_text):
    keys = [k.strip() for k in keys_text.replace('\n', ',').replace(';', ',').split(',') if k.strip()]
    added = []
    with db_lock:
        conn = get_db()
        try:
            for key in keys:
                cur = conn.execute("INSERT OR IGNORE INTO keys (key) VALUES (?)", (key,))
                if cur.rowcount > 0:
                    added.append(key)
            conn.commit()
        finally:
            conn.close()
    return added


def db_remove_key(key):
    with db_lock:
        conn = get_db()
        try:
            conn.execute("DELETE FROM keys WHERE key = ?", (key,))
            conn.commit()
        finally:
            conn.close()


def db_clear_all():
    with db_lock:
        conn = get_db()
        try:
            conn.execute("DELETE FROM keys")
            conn.commit()
        finally:
            conn.close()


def db_get_all_keys(search=''):
    with db_lock:
        conn = get_db()
        try:
            if search:
                rows = conn.execute(
                    "SELECT * FROM keys WHERE LOWER(key) LIKE ? OR LOWER(level) LIKE ? ORDER BY id DESC",
                    (f'%{search}%', f'%{search}%')
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM keys ORDER BY id DESC").fetchall()
            return [row_to_dict(r) for r in rows]
        finally:
            conn.close()


def db_get_key(key):
    with db_lock:
        conn = get_db()
        try:
            row = conn.execute("SELECT * FROM keys WHERE key = ?", (key,)).fetchone()
            return row_to_dict(row) if row else None
        finally:
            conn.close()


def db_update_key(key, **kwargs):
    with db_lock:
        conn = get_db()
        try:
            sets = []
            vals = []
            for k, v in kwargs.items():
                sets.append(f"{k} = ?")
                vals.append(v)
            vals.append(key)
            conn.execute(f"UPDATE keys SET {', '.join(sets)} WHERE key = ?", vals)
            conn.commit()
        finally:
            conn.close()


def db_get_stats():
    with db_lock:
        conn = get_db()
        try:
            total = conn.execute("SELECT COUNT(*) FROM keys").fetchone()[0]
            valid = conn.execute("SELECT COUNT(*) FROM keys WHERE status='valid'").fetchone()[0]
            invalid = conn.execute("SELECT COUNT(*) FROM keys WHERE status='invalid'").fetchone()[0]
            error = conn.execute("SELECT COUNT(*) FROM keys WHERE status='error'").fetchone()[0]
            pending = conn.execute("SELECT COUNT(*) FROM keys WHERE status='pending'").fetchone()[0]
            return {'total': total, 'valid': valid, 'invalid': invalid, 'error': error, 'pending': pending}
        finally:
            conn.close()


def validate_key(key):
    key = key.strip()
    db_add_key(key)
    headers = {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json"
    }
    try:
        resp = req_lib.get(API_URL, headers=headers, timeout=15)
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if resp.status_code == 200:
            json_resp = resp.json()
            data = json_resp.get('data', json_resp)
            level = data.get('level', 'unknown')
            limits = data.get('limits', [])
            db_update_key(key,
                          status='valid',
                          level=level,
                          limits=json_mod.dumps(limits),
                          raw_response=json_mod.dumps(json_resp),
                          error=None,
                          last_checked=now)
            return {'valid': True, 'status_code': resp.status_code, 'data': json_resp}
        else:
            db_update_key(key,
                          status='invalid',
                          level=None,
                          limits=None,
                          raw_response=None,
                          error=f"HTTP {resp.status_code}",
                          last_checked=now)
            return {'valid': False, 'status_code': resp.status_code, 'data': None}
    except Exception as e:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        db_update_key(key,
                      status='error',
                      level=None,
                      limits=None,
                      raw_response=None,
                      error=str(e),
                      last_checked=now)
        return {'valid': False, 'status_code': None, 'data': None, 'error': str(e)}


init_db()

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/keys', methods=['GET'])
def get_keys():
    search = request.args.get('search', '').lower()
    rows = db_get_all_keys(search)
    result = {}
    for r in rows:
        result[r['key']] = {
            'status': r['status'],
            'last_checked': r['last_checked'],
            'level': r['level'],
            'limits': r['limits'],
            'raw_response': r['raw_response'],
            'error': r['error'],
            'created_at': r['created_at']
        }
    return jsonify(result)


@app.route('/api/keys', methods=['POST'])
def add_key():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data'}), 400
    if 'keys' in data:
        added = db_add_keys_bulk(data['keys'])
        return jsonify({'message': f'Added {len(added)} keys', 'added': added})
    elif 'key' in data:
        db_add_key(data['key'])
        return jsonify({'message': 'Key added', 'key': data['key']})
    return jsonify({'error': 'Key required'}), 400


@app.route('/api/keys/<key>', methods=['DELETE'])
def delete_key(key):
    db_remove_key(key)
    return jsonify({'message': 'Key removed'})


@app.route('/api/keys/clear', methods=['POST'])
def clear_keys():
    db_clear_all()
    return jsonify({'message': 'All keys cleared'})


@app.route('/api/validate/<key>', methods=['POST'])
def validate_single(key):
    result = validate_key(key)
    return jsonify(result)


@app.route('/api/validate-all', methods=['POST'])
def validate_all():
    rows = db_get_all_keys()
    results = {}
    for r in rows:
        results[r['key']] = validate_key(r['key'])
    return jsonify(results)


@app.route('/api/stats', methods=['GET'])
def get_stats():
    return jsonify(db_get_stats())


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
