from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Tuple


@dataclass
class TrustRelation:
    """
    Relation de confiance directionnelle entre deux agents.
    """
    trust_score: float = 0.5  # Neutre
    last_updated: datetime = field(default_factory=datetime.utcnow)
    interaction_count: int = 0


class TrustNetwork:
    """
    Réseau de confiance interne entre agents.
    """

    def __init__(self):
        # Clé = (agent_a, agent_b)
        self.relations: Dict[Tuple[str, str], TrustRelation] = {}

    def get_trust(self, agent_a: str, agent_b: str) -> float:
        relation = self.relations.get((agent_a, agent_b))
        return relation.trust_score if relation else 0.5

    def update_trust(self, agent_a: str, agent_b: str, outcome: str):
        """
        Met à jour la confiance après interaction.
        outcome = "success" ou "failure"
        """
        key = (agent_a, agent_b)

        if key not in self.relations:
            self.relations[key] = TrustRelation()

        relation = self.relations[key]

        if outcome == "success":
            delta = 0.05 * (1 - relation.trust_score)
        else:
            delta = -0.1 * relation.trust_score

        relation.trust_score = max(0.0, min(1.0, relation.trust_score + delta))
        relation.last_updated = datetime.utcnow()
        relation.interaction_count += 1

    def trust_profile(self, agent: str) -> Dict:
        """
        Profil global de confiance d’un agent.
        """
        outgoing = [
            rel.trust_score
            for (a, _), rel in self.relations.items()
            if a == agent
        ]

        incoming = [
            rel.trust_score
            for (_, b), rel in self.relations.items()
            if b == agent
        ]

        return {
            "average_outgoing": sum(outgoing) / len(outgoing) if outgoing else 0.5,
            "average_incoming": sum(incoming) / len(incoming) if incoming else 0.5,
            "relations_count": len(outgoing) + len(incoming),
        }
