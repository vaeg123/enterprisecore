"""
Non-interactive admin init for Docker / Fly.io deployment.
Reads credentials from environment variables.

Usage:
    ADMIN_PASSWORD=secret python3 scripts/init_admin.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.flask_auth import create_user, get_user
from api.auth import generate_api_key, save_key, get_all_keys


def main():
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")

    existing = get_user("admin")
    if existing:
        print("[init_admin] Admin user already exists.")
    else:
        create_user("admin", admin_password)
        print(f"[init_admin] Admin user created (username: admin).")

    existing_keys = get_all_keys()
    if existing_keys:
        print(f"[init_admin] {len(existing_keys)} API key(s) already present.")
    else:
        full, prefix, hashed = generate_api_key()
        save_key("default", prefix, hashed)
        print(f"[init_admin] First API key created: {full}")


if __name__ == "__main__":
    main()
