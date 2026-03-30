"""
Migration : création de la table agent_queries
pour stocker les interrogations directes aux agents du Service Juridique.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_config import get_connection

SQL = """
CREATE TABLE IF NOT EXISTS agent_queries (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    agent_role   VARCHAR(20)  NOT NULL,
    question     TEXT         NOT NULL,
    result       JSON,
    risk_level   VARCHAR(10),
    confidence   FLOAT,
    created_at   TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

if __name__ == "__main__":
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute(SQL)
    conn.commit()
    cursor.close()
    conn.close()
    print("✓ Table agent_queries créée (ou déjà existante).")
