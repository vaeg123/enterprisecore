import json
from providers.llm_router import LLMRouter
from core.planning.mission_task import MissionTask


class MissionPlanner:
    """
    Cerveau stratégique : décompose un objectif en tâches assignées à des agents.
    """

    AGENT_TYPES = ["legal", "compliance", "risk", "debate", "summary"]

    def __init__(self):
        self.router = LLMRouter()

    def plan(self, objective: str) -> list[MissionTask]:
        """
        Analyse l'objectif et retourne une liste ordonnée de MissionTask.
        """
        system_prompt = """
Tu es un architecte de missions IA spécialisé en droit et conformité.

Décompose l'objectif en 3 à 6 tâches atomiques ordonnées.
Chaque tâche doit être assignée à l'un de ces types d'agent :
- legal     : analyse juridique avec doctrine interne
- compliance: vérification de conformité réglementaire
- risk      : évaluation des risques opérationnels
- debate    : débat multi-agents (4 experts) pour décision complexe
- summary   : synthèse et recommandations finales

Retourne UNIQUEMENT du JSON valide :

{
  "tasks": [
    {
      "order": 1,
      "title": "Titre court de la tâche",
      "description": "Description précise de ce que l'agent doit analyser",
      "agent_type": "legal"
    }
  ]
}
"""
        response = self.router.generate(
            prompt=f"Objectif de la mission : {objective}",
            system_prompt=system_prompt,
            task_type="critical"
        )

        try:
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```", 2)[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.rsplit("```", 1)[0].strip()

            parsed = json.loads(content)
            raw_tasks = parsed.get("tasks", [])

        except Exception:
            raw_tasks = self._fallback_plan(objective)

        tasks = []
        for t in raw_tasks:
            agent_type = t.get("agent_type", "legal")
            if agent_type not in self.AGENT_TYPES:
                agent_type = "legal"

            tasks.append(MissionTask(
                task_order=int(t.get("order", len(tasks) + 1)),
                title=t.get("title", f"Tâche {len(tasks)+1}"),
                description=t.get("description", objective),
                agent_type=agent_type,
            ))

        tasks.sort(key=lambda t: t.task_order)
        return tasks

    def _fallback_plan(self, objective: str) -> list[dict]:
        """Plan de secours si le LLM ne retourne pas du JSON valide."""
        return [
            {"order": 1, "title": "Analyse juridique", "description": objective, "agent_type": "legal"},
            {"order": 2, "title": "Vérification de conformité", "description": objective, "agent_type": "compliance"},
            {"order": 3, "title": "Évaluation des risques", "description": objective, "agent_type": "risk"},
            {"order": 4, "title": "Débat multi-experts", "description": objective, "agent_type": "debate"},
            {"order": 5, "title": "Synthèse et recommandations", "description": objective, "agent_type": "summary"},
        ]
