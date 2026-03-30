"""
Migration RBAC : ajout des colonnes permissions et is_active à la table users.
Sûr à relancer plusieurs fois (ALTER IGNORE / IF NOT EXISTS).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_config import get_connection

MIGRATIONS = [
    # Colonne permissions : liste JSON des services autorisés (utilisateurs "user")
    """ALTER TABLE users ADD COLUMN IF NOT EXISTS
       permissions JSON DEFAULT NULL""",
    # Colonne is_active : permet de désactiver un compte sans le supprimer
    """ALTER TABLE users ADD COLUMN IF NOT EXISTS
       is_active TINYINT(1) NOT NULL DEFAULT 1""",
]

# TiDB Cloud ne supporte pas IF NOT EXISTS sur ALTER ADD COLUMN
# → on tente, on ignore si la colonne existe déjà
MIGRATIONS_TIDB = [
    "ALTER TABLE users ADD COLUMN permissions JSON DEFAULT NULL",
    "ALTER TABLE users ADD COLUMN is_active TINYINT(1) NOT NULL DEFAULT 1",
]

if __name__ == "__main__":
    conn   = get_connection()
    cursor = conn.cursor()

    for sql in MIGRATIONS_TIDB:
        try:
            cursor.execute(sql)
            conn.commit()
            col = sql.split("ADD COLUMN ")[1].split(" ")[0]
            print(f"✓ Colonne {col} ajoutée.")
        except Exception as e:
            msg = str(e)
            if "Duplicate column" in msg or "1060" in msg:
                col = sql.split("ADD COLUMN ")[1].split(" ")[0]
                print(f"⟳ Colonne {col} déjà présente — ignorée.")
            else:
                print(f"✗ Erreur : {msg}")

    cursor.close()
    conn.close()
    print("Migration RBAC terminée.")
