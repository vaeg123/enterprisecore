import json
from core.agents.specialized_legal_agent import SpecializedLegalAgent
from core.legal.confidence_scorer import ConfidenceScorer


def _strip_markdown(content: str) -> str:
    content = content.strip()
    if content.startswith("```"):
        content = content.split("```", 2)[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.rsplit("```", 1)[0].strip()
    return content


class LegalDebateEngine:

    ROLES = ["jurist", "lawyer", "compliance", "risk"]

    def __init__(self):
        self.agents = {role: SpecializedLegalAgent(role) for role in self.ROLES}
        self.scorer = ConfidenceScorer()

    def run_debate(self, question: str) -> dict:
        results = []

        for role in self.ROLES:
            agent = self.agents[role]
            response = agent.analyze(question)

            try:
                parsed = json.loads(_strip_markdown(response.content))
            except Exception:
                parsed = {
                    "risk_level": "UNKNOWN",
                    "raw_response": response.content,
                }

            results.append({
                "agent_role":  role,
                "expert_name": agent.persona["name"],
                "analysis":    parsed,
            })

        confidence_result = self.scorer.compute(results)
        consensus         = self._build_consensus(results)

        return {
            "agents_analysis":  results,
            "final_risk_level": consensus["final_risk"],
            "agents_count":     len(results),
            "confidence":       confidence_result["score"],
            "confidence_details": confidence_result["details"],
            "divergence":       confidence_result["details"].get("divergence", "unknown"),
        }

    # ─────────────────────────────────────────────────────────
    # Consensus : priorité au risque le plus élevé parmi les
    # agents valides ; en cas d'égalité → risque majoritaire
    # ─────────────────────────────────────────────────────────
    def _build_consensus(self, results: list) -> dict:
        PRIORITY = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

        levels = [
            r["analysis"].get("risk_level", "UNKNOWN")
            for r in results
            if r["analysis"].get("risk_level", "UNKNOWN") != "UNKNOWN"
        ]

        if not levels:
            return {"final_risk": "UNKNOWN"}

        if "HIGH" in levels:
            final = "HIGH"
        elif "MEDIUM" in levels:
            final = "MEDIUM"
        else:
            final = "LOW"

        return {"final_risk": final}
