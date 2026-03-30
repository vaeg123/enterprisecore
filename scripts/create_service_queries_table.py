"""
Migration : création de la table service_queries
pour stocker les interrogations directes aux agents de tous les services métier
(Commercial, Financier, Projets, R&D).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_config import get_connection

SQL = """
CREATE TABLE IF NOT EXISTS service_queries (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    service      VARCHAR(50)  NOT NULL,
    agent_slug   VARCHAR(50)  NOT NULL,
    question     TEXT         NOT NULL,
    result       JSON,
    priority_level VARCHAR(10),
    confidence   FLOAT,
    created_at   TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_service_agent (service, agent_slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

if __name__ == "__main__":
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute(SQL)
    conn.commit()
    cursor.close()
    conn.close()
    print("✓ Table service_queries créée (ou déjà existante).")
