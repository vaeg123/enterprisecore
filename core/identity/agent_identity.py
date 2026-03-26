from datetime import datetime
from typing import Dict, List
from uuid import uuid4

from .reputation import ReputationScore, ReputationEvent
from .trust_network import TrustNetwork


class AgentIdentity:
    """
    Entité cognitive autonome.
    """

    def __init__(self, name: str, role: str):
        self.id = str(uuid4())
        self.name = name
        self.role = role
        self.created_at = datetime.utcnow()

        # Capacités internes
        self.reputation = ReputationScore()
        self.trust_network = TrustNetwork()

        # Expertise dynamique
        self.expertise: Dict[str, float] = {}

        # Profil comportemental
        self.risk_tolerance: float = 0.5
        self.decision_style: str = "balanced"  # analytical / intuitive / balanced

        # Historique interne
        self.internal_log: List[str] = []

    # --- EXPERTISE ---

    def update_expertise(self, domain: str, delta: float):
        current = self.expertise.get(domain, 0.0)
        new_value = max(0.0, min(1.0, current + delta))
        self.expertise[domain] = new_value

    # --- REPUTATION ---

    def register_event(self, category: str, impact: float, context: Dict = None):
        event = ReputationEvent(
            timestamp=datetime.utcnow(),
            category=category,
            impact=impact,
            context=context or {}
        )
        self.reputation.add_event(event)

    # --- TRUST ---

    def interact(self, other_agent_id: str, outcome: str):
        """
        Enregistre une interaction avec un autre agent.
        """
        self.trust_network.update_trust(self.id, other_agent_id, outcome)

    # --- PROFIL GLOBAL ---

    def profile(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "reputation": self.reputation.get_profile(),
            "trust": self.trust_network.trust_profile(self.id),
            "expertise": self.expertise,
            "risk_tolerance": self.risk_tolerance,
            "decision_style": self.decision_style,
        }

    # --- LOGGING INTERNE ---

    def log(self, message: str):
        timestamped = f"{datetime.utcnow().isoformat()} - {message}"
        self.internal_log.append(timestamped)
