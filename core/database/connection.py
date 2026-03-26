import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    """
    Retourne une connexion MySQL vers enterprise_core
    """

    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "enterprise_core"),
        port=int(os.getenv("DB_PORT", 3306)),
    )
