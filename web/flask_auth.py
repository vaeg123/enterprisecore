"""
Authentification et RBAC (Role-Based Access Control) Flask.

Rôles :
  admin   → accès total + gestion des utilisateurs
  manager → accès à tous les services + missions (pas de gestion users)
  user    → accès uniquement aux services listés dans permissions[]

Services disponibles :
  missions, juridique, commercial, financier, projets, rd
"""
import json
import bcrypt
from functools import wraps
from flask import session, redirect, url_for, request, render_template
from database.db_config import get_connection


# ── Constantes ────────────────────────────────────────────────

ALL_SERVICES = ["missions", "juridique", "commercial", "financier", "projets", "rd"]

ROLES = {
    "admin":   {"label": "Administrateur", "color": "#ef4444",  "desc": "Accès total + gestion des utilisateurs"},
    "manager": {"label": "Manager",        "color": "#f59e0b",  "desc": "Accès à tous les services, sans gestion users"},
    "user":    {"label": "Utilisateur",    "color": "#22c55e",  "desc": "Accès aux services autorisés uniquement"},
}

SERVICE_LABELS = {
    "missions":   "Missions",
    "juridique":  "Service Juridique",
    "commercial": "Service Commercial",
    "financier":  "Service Financier",
    "projets":    "Gestion de Projets",
    "rd":         "R&D",
}


# ── Helpers mot de passe ──────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


# ── CRUD utilisateurs ─────────────────────────────────────────

def get_user(username: str) -> dict | None:
    conn   = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, username, password_hash, role, permissions, is_active "
        "FROM users WHERE username=%s",
        (username,)
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if row and row.get("permissions"):
        try:
            row["permissions"] = json.loads(row["permissions"])
        except Exception:
            row["permissions"] = []
    return row


def get_user_by_id(user_id: int) -> dict | None:
    conn   = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, username, role, permissions, is_active, created_at FROM users WHERE id=%s",
        (user_id,)
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if row and row.get("permissions"):
        try:
            row["permissions"] = json.loads(row["permissions"])
        except Exception:
            row["permissions"] = []
    return row


def get_all_users() -> list:
    conn   = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, username, role, permissions, is_active, created_at "
        "FROM users ORDER BY created_at ASC"
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    for r in rows:
        if r.get("permissions"):
            try:
                r["permissions"] = json.loads(r["permissions"])
            except Exception:
                r["permissions"] = []
        else:
            r["permissions"] = []
        r["created_at"] = str(r["created_at"])
    return rows


def create_user(username: str, password: str, role: str = "user",
                permissions: list = None) -> int:
    perms_json = json.dumps(permissions or [])
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (username, password_hash, role, permissions) VALUES (%s, %s, %s, %s)",
        (username, hash_password(password), role, perms_json)
    )
    uid = cursor.lastrowid
    conn.commit()
    cursor.close()
    conn.close()
    return uid


def update_user(user_id: int, role: str = None, permissions: list = None,
                password: str = None) -> bool:
    conn   = get_connection()
    cursor = conn.cursor()
    if role is not None:
        cursor.execute("UPDATE users SET role=%s WHERE id=%s", (role, user_id))
    if permissions is not None:
        cursor.execute("UPDATE users SET permissions=%s WHERE id=%s",
                       (json.dumps(permissions), user_id))
    if password:
        cursor.execute("UPDATE users SET password_hash=%s WHERE id=%s",
                       (hash_password(password), user_id))
    conn.commit()
    cursor.close()
    conn.close()
    return True


def toggle_user_active(user_id: int) -> bool:
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET is_active = 1 - is_active WHERE id=%s", (user_id,)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return True


def delete_user(user_id: int) -> bool:
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return True


# ── Vérification des permissions ──────────────────────────────

def current_role() -> str:
    return session.get("role", "user")


def is_admin() -> bool:
    return current_role() == "admin"


def has_service_access(service_key: str) -> bool:
    """Vérifie si l'utilisateur connecté peut accéder au service donné."""
    role = current_role()
    if role in ("admin", "manager"):
        return True
    perms = session.get("permissions", [])
    return service_key in perms


# ── Décorateurs ───────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login", next=request.path))
        if not session.get("is_active", True):
            session.clear()
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login", next=request.path))
        if current_role() != "admin":
            return render_template("403.html"), 403
        return f(*args, **kwargs)
    return decorated


def service_required(service_key: str):
    """Décorateur de permission par service."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not session.get("user_id"):
                return redirect(url_for("login", next=request.path))
            if not has_service_access(service_key):
                return render_template("403.html"), 403
            return f(*args, **kwargs)
        return decorated
    return decorator
