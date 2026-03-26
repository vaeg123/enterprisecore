from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict
import math


@dataclass
class ReputationEvent:
    """
    Événement impactant la réputation d’un agent.
    """
    timestamp: datetime
    category: str  # "accuracy", "reliability", "innovation", "collaboration"
    impact: float  # -100 à +100
    context: Dict = field(default_factory=dict)


class ReputationScore:
    """
    Système de réputation multi-dimensionnel avec decay temporel.
    """

    def __init__(self):
        self.overall: float = 500.0  # Score initial neutre
        self.dimensions: Dict[str, float] = {
            "accuracy": 0.0,
            "reliability": 0.0,
            "innovation": 0.0,
            "collaboration": 0.0,
        }
        self.history: List[ReputationEvent] = []

    def add_event(self, event: ReputationEvent):
        """
        Ajoute un événement et met à jour la réputation.
        """
        adjusted_impact = self._apply_time_decay(event)
        self.overall += adjusted_impact

        if event.category in self.dimensions:
            self.dimensions[event.category] += adjusted_impact

        self.history.append(event)

        # Clamp global score
        self.overall = max(0, min(1000, self.overall))

    def _apply_time_decay(self, event: ReputationEvent) -> float:
        """
        Les événements anciens ont moins d’impact.
        """
        now = datetime.utcnow()
        age = (now - event.timestamp).days

        decay_factor = math.exp(-age / 365)  # demi-vie ~ 1 an
        return event.impact * decay_factor

    def get_profile(self) -> Dict:
        """
        Retourne un résumé structuré de la réputation.
        """
        return {
            "overall": round(self.overall, 2),
            "dimensions": {k: round(v, 2) for k, v in self.dimensions.items()},
            "event_count": len(self.history),
        }

    def confidence_level(self) -> float:
        """
        Plus il y a d’événements, plus la réputation est fiable.
        """
        return min(1.0, len(self.history) / 50.0)
