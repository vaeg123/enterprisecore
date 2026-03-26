"""
Script de premier démarrage.
Crée le compte admin et la première clé API.

Usage :
    python3 scripts/setup_admin.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.flask_auth import create_user, get_user
from api.auth import generate_api_key, save_key, get_all_keys
from database.db_config import get_connection


def main():
    print("\n=== EnterpriseCore — Configuration initiale ===\n")

    # ── Compte admin ──────────────────────────────────────────
    existing = get_user("admin")
    if existing:
        print("✅  Compte admin déjà existant.")
    else:
        import getpass
        print("Création du compte administrateur.")
        password = getpass.getpass("  Mot de passe admin : ")
        if len(password) < 6:
            print("❌  Mot de passe trop court (minimum 6 caractères).")
            sys.exit(1)
        create_user("admin", password)
        print("✅  Compte admin créé (identifiant : admin).")

    # ── Première clé API ──────────────────────────────────────
    existing_keys = get_all_keys()
    if existing_keys:
        print(f"✅  {len(existing_keys)} clé(s) API déjà présente(s).")
    else:
        full, prefix, hashed = generate_api_key()
        save_key("default", prefix, hashed)
        print("\n🔑  Première clé API générée :")
        print(f"    {full}")
        print("\n    ⚠ Copiez cette clé — elle ne sera plus affichée.")
        print("    Ajoutez-la dans le header : X-API-Key: <clé>")

    # ── Générer un FLASK_SECRET_KEY stable ───────────────────
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            content = f.read()
        if "FLASK_SECRET_KEY" not in content:
            import secrets
            key = secrets.token_hex(32)
            with open(env_path, "a") as f:
                f.write(f"\nFLASK_SECRET_KEY={key}\n")
            print("✅  FLASK_SECRET_KEY ajouté au .env")

    print("\n=== Prêt ! ===")
    print("  Interface web : http://localhost:5050")
    print("  API REST      : http://localhost:8000")
    print("  Docs Swagger  : http://localhost:8000/docs\n")


if __name__ == "__main__":
    main()
