from database.db_manager import DatabaseManager
import json
from typing import List, Dict
from providers.llm_router import LLMRouter
from core.cognition.consensus_engine import ConsensusEngine

class MeetingOrchestrator:

    def __init__(self, organization):
        self.organization = organization
        self.consensus_engine = ConsensusEngine()
        self.router = LLMRouter()

    def generate_strategic_options(self, topic: str):

        system_prompt = """
You are a senior enterprise strategist.

Generate 4 concise strategic response options.
Return ONLY valid JSON:

{
  "options": ["OPTION_1", "OPTION_2", "OPTION_3", "OPTION_4"]
}

Options must be short uppercase strategic labels.
"""

        response = self.router.generate(
            prompt=f"Topic: {topic}",
            system_prompt=system_prompt,
            task_type="critical"
        )

        try:
            parsed = json.loads(response.content)
            return parsed.get("options", [])
        except Exception:
            # fallback options
            return [
                "COST_REDUCTION",
                "CAPITAL_RAISE",
                "LEGAL_RESTRUCTURING",
                "WAIT_AND_MONITOR"
            ]

    def run_meeting(
        self,
        topic: str,
        participants: List[str],
        ceo_id: str,
        president_id: str,
        veto: Dict[str, bool] = None,
        simulated_positions: Dict[str, str] = None,
    ):

        # Phase 1: generate options
        options = self.generate_strategic_options(topic)

        proposals = {}
        detailed_reports = {}

        # Phase 2: agent deliberation
        for agent_id in participants:
            agent = self.organization.get_agent(agent_id)

            if simulated_positions and agent_id in simulated_positions:
                analysis = {
                    "decision": simulated_positions[agent_id],
                    "justification": "Simulated position",
                    "confidence": 0.8,
                }
            else:
                analysis = agent.analyze_topic(topic, options)

            proposals[agent_id] = {
                "proposal": analysis["decision"],
                "reputation_weight": agent.reputation.overall * analysis["confidence"]
            }

            detailed_reports[agent.name] = analysis

        # Phase 3: consensus
        result = self.consensus_engine.reach_consensus(
            proposals=proposals,
            ceo_id=ceo_id,
            president_id=president_id,
            veto=veto or {},
        )

        return {
            "topic": topic,
            "options_generated": options,
            "reports": detailed_reports,
            "decision": result.summary(),
        }
