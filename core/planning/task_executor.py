import json
from core.planning.mission_task import MissionTask
from core.agents.legal_agent_with_context import LegalAgentWithContext
from core.cognition.legal_debate_engine import LegalDebateEngine
from providers.llm_router import LLMRouter


class TaskExecutor:
    """
    Exécute une MissionTask en la routant vers l'agent approprié.
    """

    def __init__(self):
        self.legal_agent = LegalAgentWithContext()
        self.debate_engine = LegalDebateEngine()
        self.router = LLMRouter()

    def execute(self, task: MissionTask) -> MissionTask:
        try:
            if task.agent_type == "debate":
                result = self._run_debate(task)
            elif task.agent_type == "summary":
                result = self._run_summary(task)
            else:
                result = self._run_legal_agent(task)

            task.mark_done(result)

        except Exception as e:
            task.mark_failed(str(e))

        return task

    def _run_legal_agent(self, task: MissionTask) -> dict:
        """
        Exécute une analyse juridique / compliance / risk via LegalAgentWithContext.
        Le prompt adapte le rôle selon l'agent_type.
        """
        role_directive = {
            "legal":      "Tu es juriste expert. Analyse la base légale applicable.",
            "compliance": "Tu es responsable conformité. Vérifie la conformité réglementaire.",
            "risk":       "Tu es gestionnaire des risques. Évalue les risques opérationnels et juridiques.",
        }.get(task.agent_type, "Tu es expert juridique.")

        question = f"{role_directive}\n\n{task.description}"

        response = self.legal_agent.analyze(question)

        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```", 2)[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.rsplit("```", 1)[0].strip()

        try:
            parsed = json.loads(content)
            return {
                "risk_level": parsed.get("risk_level", "UNKNOWN"),
                "legal_basis": parsed.get("legal_basis", ""),
                "articles_referenced": parsed.get("articles_referenced", []),
                "recommendation": parsed.get("recommendation", ""),
                "confidence": float(parsed.get("confidence", 0.7)),
                "agent_type": task.agent_type,
            }
        except Exception:
            return {
                "risk_level": "UNKNOWN",
                "raw_response": response.content,
                "agent_type": task.agent_type,
                "confidence": 0.3,
            }

    def _run_debate(self, task: MissionTask) -> dict:
        """Exécute un débat multi-agents et retourne le consensus."""
        debate_result = self.debate_engine.run_debate(task.description)
        return {
            "risk_level": debate_result.get("final_risk_level", "UNKNOWN"),
            "agents_count": debate_result.get("agents_count", 0),
            "agents_analysis": debate_result.get("agents_analysis", []),
            "confidence": 0.9,
            "agent_type": "debate",
        }

    def _run_summary(self, task: MissionTask) -> dict:
        """Génère une synthèse à partir de la description enrichie."""
        system_prompt = """
Tu es un conseiller juridique senior.
Rédige une synthèse exécutive claire et actionnable.

Retourne UNIQUEMENT du JSON valide :
{
  "risk_level": "LOW | MEDIUM | HIGH",
  "executive_summary": "synthèse en 3-5 phrases",
  "key_actions": ["action 1", "action 2", "action 3"],
  "priority": "IMMEDIATE | SHORT_TERM | LONG_TERM",
  "confidence": 0.0
}
"""
        response = self.router.generate(
            prompt=task.description,
            system_prompt=system_prompt,
            task_type="critical"
        )

        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```", 2)[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.rsplit("```", 1)[0].strip()

        try:
            parsed = json.loads(content)
            return {
                "risk_level": parsed.get("risk_level", "MEDIUM"),
                "executive_summary": parsed.get("executive_summary", ""),
                "key_actions": parsed.get("key_actions", []),
                "priority": parsed.get("priority", "SHORT_TERM"),
                "confidence": float(parsed.get("confidence", 0.8)),
                "agent_type": "summary",
            }
        except Exception:
            return {
                "risk_level": "UNKNOWN",
                "raw_response": response.content,
                "agent_type": "summary",
                "confidence": 0.3,
            }
