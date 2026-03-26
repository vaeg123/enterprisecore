import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    params = dict(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "enterprise_core"),
        port=int(os.getenv("DB_PORT", 3306)),
    )
    # Enable SSL for cloud databases (e.g. TiDB Cloud, PlanetScale)
    if os.getenv("DB_SSL", "").lower() in ("1", "true", "yes"):
        params["ssl_disabled"] = False
        params["ssl_verify_cert"] = False
        params["ssl_verify_identity"] = False
    return mysql.connector.connect(**params)
