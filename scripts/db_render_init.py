"""
Render build-time DB initialization.
- Creates all tables (safe to run multiple times)
- Creates admin user if none exists
- Creates first API key if none exists

Usage:
    python3 scripts/db_render_init.py
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_config import get_connection


def run_schema():
    """Execute schema.sql, replacing CREATE TABLE with CREATE TABLE IF NOT EXISTS."""
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    if not os.path.exists(schema_path):
        print("[db_init] schema.sql not found — skipping")
        return

    with open(schema_path) as f:
        raw = f.read()

    # Make all CREATE TABLE idempotent
    sql = re.sub(
        r"CREATE TABLE (`[^`]+`)",
        r"CREATE TABLE IF NOT EXISTS \1",
        raw,
    )

    conn = get_connection()
    cursor = conn.cursor()

    # Split by semicolons and execute each statement
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    ok = 0
    for stmt in statements:
        # Skip MySQL-specific SET / /*!... */ lines that can fail outside MySQL
        if stmt.startswith("/*!") or stmt.upper().startswith("SET @@SESSION"):
            continue
        try:
            cursor.execute(stmt)
            ok += 1
        except Exception as e:
            msg = str(e)
            # Ignore "already exists" or benign warnings
            if "already exists" in msg.lower() or "1050" in msg:
                pass
            else:
                print(f"[db_init] Warning: {msg[:120]}")

    conn.commit()
    cursor.close()
    conn.close()
    print(f"[db_init] Schema applied ({ok} statements OK).")


def create_admin():
    from web.flask_auth import create_user, get_user
    from api.auth import generate_api_key, save_key, get_all_keys

    admin_pass = os.getenv("ADMIN_PASSWORD", "admin123")

    if not get_user("admin"):
        create_user("admin", admin_pass)
        print(f"[db_init] Admin user created (password: {admin_pass})")
    else:
        print("[db_init] Admin user already exists.")

    if not get_all_keys():
        full, prefix, hashed = generate_api_key()
        save_key("default", prefix, hashed)
        print(f"[db_init] First API key: {full}")
    else:
        print("[db_init] API keys already present.")


if __name__ == "__main__":
    print("[db_init] Initializing database...")
    try:
        run_schema()
        create_admin()
        print("[db_init] Done.")
    except Exception as e:
        print(f"[db_init] ERROR: {e}")
        sys.exit(1)
