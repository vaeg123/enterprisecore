import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()


class ExpertiseRouter:

    def __init__(self):

        self.connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",   # adapte si besoin
            database="enterprise_core"
        )

    def get_agent_expertise(self, agent_id: str, domain_code: str):

        cursor = self.connection.cursor(dictionary=True)

        query = """
        SELECT ade.expertise_level
        FROM agent_domain_expertise ade
        JOIN knowledge_domains kd ON kd.id = ade.domain_id
        WHERE ade.agent_id = %s
        AND kd.code = %s
        AND ade.actif = TRUE
        """

        cursor.execute(query, (agent_id, domain_code))
        result = cursor.fetchone()

        cursor.close()

        if result:
            return float(result["expertise_level"])

        return 0.0

    def select_provider(self, expertise_level: float):

        """
        Logique stratégique de sélection IA
        """

        if expertise_level >= 4.5:
            return "premium"

        elif expertise_level >= 3:
            return "advanced"

        else:
            return "standard"
