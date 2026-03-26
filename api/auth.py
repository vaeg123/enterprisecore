"""
Authentification FastAPI par clé API (header X-API-Key).
La clé complète n'est jamais stockée — seul son hash bcrypt est en base.
"""
import secrets
import bcrypt
from fastapi import Header, HTTPException, status
from database.db_config import get_connection


PREFIX_LEN = 8      # "ec_" + 8 chars affichés dans les listings
KEY_BYTES  = 32     # entropie totale


def generate_api_key() -> tuple[str, str, str]:
    """
    Retourne (full_key, prefix, hash).
    full_key  : "ec_<64 hex chars>"  — montré une seule fois
    prefix    : "ec_XXXXXXXX"        — stocké en clair pour identification
    hash      : bcrypt du full_key   — stocké en DB
    """
    raw    = secrets.token_hex(KEY_BYTES)
    full   = f"ec_{raw}"
    prefix = f"ec_{raw[:PREFIX_LEN]}"
    hashed = bcrypt.hashpw(full.encode(), bcrypt.gensalt()).decode()
    return full, prefix, hashed


def verify_key(full_key: str, stored_hash: str) -> bool:
    return bcrypt.checkpw(full_key.encode(), stored_hash.encode())


def get_all_keys() -> list[dict]:
    conn   = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, name, key_prefix, active, last_used, created_at FROM api_keys ORDER BY created_at DESC"
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    for r in rows:
        r["created_at"] = str(r["created_at"]) if r["created_at"] else None
        r["last_used"]  = str(r["last_used"])  if r["last_used"]  else None
    return rows


def save_key(name: str, prefix: str, key_hash: str) -> int:
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO api_keys (name, key_prefix, key_hash) VALUES (%s, %s, %s)",
        (name, prefix, key_hash)
    )
    key_id = cursor.lastrowid
    conn.commit()
    cursor.close()
    conn.close()
    return key_id


def deactivate_key(key_id: int) -> bool:
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE api_keys SET active=0 WHERE id=%s", (key_id,))
    ok = cursor.rowcount > 0
    conn.commit()
    cursor.close()
    conn.close()
    return ok


# ── Dépendance FastAPI ────────────────────────────────────────

async def require_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> str:
    """
    Vérifie la clé API envoyée dans le header X-API-Key.
    Lève HTTP 401 si absente ou invalide.
    """
    if not x_api_key or not x_api_key.startswith("ec_"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API manquante ou mal formée (format : ec_…)",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    conn   = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, key_hash, active FROM api_keys WHERE active=1 ORDER BY created_at DESC"
    )
    rows = cursor.fetchall()
    cursor.close()

    matched_id = None
    for row in rows:
        if verify_key(x_api_key, row["key_hash"]):
            matched_id = row["id"]
            break

    if not matched_id:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API invalide ou révoquée.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Mise à jour last_used (non bloquant)
    try:
        cursor2 = conn.cursor()
        cursor2.execute("UPDATE api_keys SET last_used=NOW() WHERE id=%s", (matched_id,))
        conn.commit()
        cursor2.close()
    except Exception:
        pass
    conn.close()

    return x_api_key
