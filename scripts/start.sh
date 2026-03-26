#!/bin/bash
set -e

DB_NAME="${DB_NAME:-enterprise_core}"
DB_USER="${DB_USER:-ecuser}"
DB_PASSWORD="${DB_PASSWORD:-changeme}"

DATA_DIR="/data/mysql"
INIT_FLAG="/data/.initialized"

# ── 1. Prepare MariaDB data directory ────────────────────────────────────
mkdir -p "$DATA_DIR"
chown -R mysql:mysql "$DATA_DIR"

# Override datadir (Fly volume mount)
mkdir -p /etc/mysql/mariadb.conf.d/
cat > /etc/mysql/mariadb.conf.d/99-fly.cnf << EOF
[mysqld]
datadir = ${DATA_DIR}
bind-address = 127.0.0.1
EOF

# ── 2. First-run: init DB + schema + admin user ───────────────────────────
if [ ! -f "$INIT_FLAG" ]; then
    echo "[init] First run — initializing MariaDB..."

    mysql_install_db --user=mysql --datadir="$DATA_DIR" --skip-test-db > /dev/null 2>&1

    # Start a temporary MariaDB instance
    mysqld_safe --datadir="$DATA_DIR" &
    MPID=$!

    echo "[init] Waiting for MariaDB to be ready..."
    for i in $(seq 1 30); do
        if mysqladmin -u root ping --silent 2>/dev/null; then
            echo "[init] MariaDB ready after ${i}s."
            break
        fi
        sleep 1
    done

    # Create database and user
    mysql -u root << ENDSQL
CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\`
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${DB_USER}'@'127.0.0.1' IDENTIFIED BY '${DB_PASSWORD}';
GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'127.0.0.1';
FLUSH PRIVILEGES;
ENDSQL

    # Load schema
    echo "[init] Loading schema..."
    mysql -u root "${DB_NAME}" < /app/scripts/schema.sql

    # Create admin user via non-interactive script
    echo "[init] Creating admin user..."
    cd /app && python3 scripts/init_admin.py 2>&1 || echo "[init] Warning: init_admin.py failed (non-fatal)"

    # Gracefully stop temporary instance
    mysqladmin -u root shutdown 2>/dev/null || kill "$MPID" 2>/dev/null || true
    sleep 2

    touch "$INIT_FLAG"
    echo "[init] Database initialized successfully."
fi

# ── 3. Start all services via supervisord ────────────────────────────────
echo "[start] Launching supervisord (MariaDB + Flask + FastAPI)..."
exec /usr/bin/supervisord -n -c /etc/supervisor/conf.d/enterprisecore.conf
