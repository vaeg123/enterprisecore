"""
Authentification session Flask.
"""
import bcrypt
from functools import wraps
from flask import session, redirect, url_for, request
from database.db_config import get_connection


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def get_user(username: str) -> dict | None:
    conn   = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, username, password_hash, role FROM users WHERE username=%s", (username,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row


def create_user(username: str, password: str, role: str = "admin") -> int:
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
        (username, hash_password(password), role)
    )
    uid = cursor.lastrowid
    conn.commit()
    cursor.close()
    conn.close()
    return uid


def login_required(f):
    """Décorateur — redirige vers /login si non connecté."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return decorated
