from database.db_config import get_connection
import json


class DatabaseManager:

    # -------------------------
    # Agents
    # -------------------------

    def save_agent(self, agent):
        conn = get_connection()
        cursor = conn.cursor()

        query = """
        INSERT INTO agents (id, name, role)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE name=%s, role=%s
        """

        cursor.execute(query, (
            agent.id,
            agent.name,
            agent.role,
            agent.name,
            agent.role
        ))

        conn.commit()
        cursor.close()
        conn.close()

    # -------------------------
    # Meetings
    # -------------------------

    def save_meeting(self, topic, options, decision_data):
        conn = get_connection()
        cursor = conn.cursor()

        query = """
        INSERT INTO meetings (topic, options_generated, final_decision, weighted_support, status)
        VALUES (%s, %s, %s, %s, %s)
        """

        cursor.execute(query, (
            topic,
            json.dumps(options),
            decision_data.get("final_decision"),
            decision_data.get("weighted_support"),
            decision_data.get("status")
        ))

        meeting_id = cursor.lastrowid

        conn.commit()
        cursor.close()
        conn.close()

        return meeting_id

    # -------------------------
    # Agent Reports
    # -------------------------

    def save_agent_report(self, meeting_id, agent_id, report):
        conn = get_connection()
        cursor = conn.cursor()

        query = """
        INSERT INTO agent_reports (meeting_id, agent_id, decision, justification, confidence, provider)
        VALUES (%s, %s, %s, %s, %s, %s)
        """

        cursor.execute(query, (
            meeting_id,
            agent_id,
            report.get("decision"),
            report.get("justification"),
            report.get("confidence"),
            json.dumps(report.get("provider_metadata"))
        ))

        conn.commit()
        cursor.close()
        conn.close()

    # -------------------------
    # Execution Logs
    # -------------------------

    def save_execution_log(self, agent_id, tool_name, payload, result):
        conn = get_connection()
        cursor = conn.cursor()

        query = """
        INSERT INTO execution_logs (agent_id, tool_name, payload, result)
        VALUES (%s, %s, %s, %s)
        """

        cursor.execute(query, (
            agent_id,
            tool_name,
            json.dumps(payload),
            json.dumps(result)
        ))

        conn.commit()
        cursor.close()
        conn.close()
