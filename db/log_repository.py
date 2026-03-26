import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv

load_dotenv()


class LogRepository:

    def __init__(self):

        self.connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",  # ⚠️ Mets ton mot de passe si nécessaire
            database="enterprise_core"
        )

    def get_latest_meetings(self, limit=5):

        try:
            cursor = self.connection.cursor(dictionary=True)

            query = """
                SELECT id, topic, final_decision, weighted_support, status, created_at
                FROM meetings
                ORDER BY created_at DESC
                LIMIT %s
            """

            cursor.execute(query, (limit,))
            results = cursor.fetchall()

            cursor.close()

            return results

        except Error as e:
            return [{"error": str(e)}]

    def close(self):
        if self.connection.is_connected():
            self.connection.close()
