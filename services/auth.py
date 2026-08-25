from functools import wraps
from flask import session, jsonify
from database.database import get_connection

def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return dict(row) if row else None

def login_user(user):
    session.clear()
    session["user_id"] = user["id"]
    session["role"] = user["role"]

def logout_user():
    session.clear()

def role_required(*roles):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user:
                return jsonify({"success":False,"message":"Silakan login terlebih dahulu."}),401
            if user["role"] not in roles:
                return jsonify({"success":False,"message":"Akses tidak diizinkan."}),403
            return fn(*args, **kwargs)
        return wrapper
    return deco
