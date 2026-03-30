"""
Agent générique pour tous les services métier (Commercial, Financier, Projets, R&D).
Utilise la même infrastructure que SpecializedLegalAgent mais avec des personas métier.
"""
from providers.role_router import RoleBasedRouter
from core.agents.services_config import SERVICES


class ServiceAgent:
    """
    Agent spécialisé pour un service métier donné.
    Instancié avec (service_key, agent_slug) depuis services_config.py.
    """

    JSON_FORMAT = """
Réponds UNIQUEMENT au format JSON strict — aucun texte hors du JSON :

{
  "priority_level": "LOW | MEDIUM | HIGH",
  "analysis": "analyse principale selon ta spécialité (2-4 phrases)",
  "key_points": ["point clé 1", "point clé 2", "point clé 3"],
  "recommendation": "action concrète et prioritaire selon ta spécialité",
  "confidence": 0.0,
  "expert_note": "observation spécifique à ton expertise (1 phrase)"
}"""

    def __init__(self, service_key: str, agent_slug: str):
        service = SERVICES.get(service_key)
        if not service:
            raise ValueError(f"Service inconnu : {service_key}")

        agent_config = service["agents"].get(agent_slug)
        if not agent_config:
            raise ValueError(f"Agent inconnu : {agent_slug} dans {service_key}")

        self.service_key  = service_key
        self.agent_slug   = agent_slug
        self.agent_config = agent_config
        self.router_role  = service["router_role"]
        self.router       = RoleBasedRouter()

    @property
    def name(self) -> str:
        return self.agent_config["name"]

    def analyze(self, question: str):
        system_prompt = f"{self.agent_config['persona']}\n{self.JSON_FORMAT}"
        return self.router.route(
            role=self.router_role,
            prompt=question,
            system_prompt=system_prompt,
        )
