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

    # Disable FK checks so table creation order doesn't matter
    cursor.execute("SET FOREIGN_KEY_CHECKS=0")

    # Split by semicolons and execute each statement
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    ok = 0
    for stmt in statements:
        # Skip MySQL-specific SET / /*!... */ lines that can fail outside MySQL/TiDB
        upper = stmt.upper()
        if (stmt.startswith("/*!") or
                upper.startswith("SET @@SESSION") or
                upper.startswith("SET @OLD_") or
                upper.startswith("SET @@SESSION.SQL_LOG_BIN")):
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

    cursor.execute("SET FOREIGN_KEY_CHECKS=1")
    conn.commit()
    cursor.close()
    conn.close()
    print(f"[db_init] Schema applied ({ok} statements OK).")


def create_admin():
    from web.flask_auth import create_user, get_user
    from api.auth import generate_api_key, save_key, get_all_keys

    admin_pass = os.getenv("ADMIN_PASSWORD", "admin123")

    if not get_user("admin"):
        create_user("admin", admin_pass, role="admin")
        print(f"[db_init] Admin user created (password: {admin_pass})")
    else:
        print("[db_init] Admin user already exists.")

    if not get_all_keys():
        full, prefix, hashed = generate_api_key()
        save_key("default", prefix, hashed)
        print(f"[db_init] First API key: {full}")
    else:
        print("[db_init] API keys already present.")


def migrate_rbac():
    """Ajoute les colonnes RBAC + s'assure que l'admin a bien role='admin'."""
    conn   = get_connection()
    cursor = conn.cursor()

    for col_sql in [
        "ALTER TABLE users ADD COLUMN permissions JSON DEFAULT NULL",
        "ALTER TABLE users ADD COLUMN is_active TINYINT(1) NOT NULL DEFAULT 1",
    ]:
        try:
            cursor.execute(col_sql)
            conn.commit()
        except Exception as e:
            if "Duplicate column" not in str(e) and "1060" not in str(e):
                print(f"[db_init] migrate_rbac warning: {e}")

    # Garantir que l'utilisateur admin a bien role='admin'
    try:
        cursor.execute(
            "UPDATE users SET role='admin', is_active=1 WHERE username='admin'"
        )
        conn.commit()
        print("[db_init] Admin role enforced.")
    except Exception as e:
        print(f"[db_init] migrate_rbac admin fix warning: {e}")

    cursor.close()
    conn.close()


def migrate_service_queries():
    """Crée la table service_queries si elle n'existe pas."""
    conn   = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS service_queries (
                id             INT AUTO_INCREMENT PRIMARY KEY,
                service        VARCHAR(50) NOT NULL,
                agent_slug     VARCHAR(50) NOT NULL,
                question       TEXT        NOT NULL,
                result         JSON,
                priority_level VARCHAR(10),
                confidence     FLOAT,
                created_at     TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_service_agent (service, agent_slug)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        conn.commit()
    except Exception as e:
        print(f"[db_init] migrate_service_queries warning: {e}")
    cursor.close()
    conn.close()


def migrate_agent_queries():
    """Crée la table agent_queries (Service Juridique) si elle n'existe pas."""
    conn   = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_queries (
                id         INT AUTO_INCREMENT PRIMARY KEY,
                agent_role VARCHAR(20)  NOT NULL,
                question   TEXT         NOT NULL,
                result     JSON,
                risk_level VARCHAR(10),
                confidence FLOAT,
                created_at TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        conn.commit()
    except Exception as e:
        print(f"[db_init] migrate_agent_queries warning: {e}")
    cursor.close()
    conn.close()


if __name__ == "__main__":
    print("[db_init] Initializing database...")
    try:
        run_schema()
        migrate_rbac()
        migrate_service_queries()
        migrate_agent_queries()
        create_admin()
        print("[db_init] Done.")
    except Exception as e:
        print(f"[db_init] ERROR: {e}")
        sys.exit(1)
