from datetime import datetime
from core.cognition.legal_debate_engine import LegalDebateEngine


class MissionEngine:

    def __init__(self):

        self.debate_engine = LegalDebateEngine()

    def run_mission(self, mission_title, mission_description):

        start_time = datetime.now()

        debate_result = self.debate_engine.run_debate(
            mission_description
        )

        report = {
            "mission_title": mission_title,
            "mission_description": mission_description,
            "analysis": debate_result,
            "generated_at": datetime.now(),
            "started_at": start_time
        }

        return report