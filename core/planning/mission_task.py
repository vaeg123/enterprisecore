from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class MissionTask:
    """Représente une tâche atomique dans une mission."""

    task_order: int
    title: str
    description: str
    agent_type: str  # legal | compliance | risk | debate | summary

    status: str = "pending"       # pending | running | done | failed
    result: Optional[dict] = None
    risk_level: Optional[str] = None
    confidence: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    def mark_done(self, result: dict):
        self.status = "done"
        self.result = result
        self.risk_level = result.get("risk_level") or result.get("analysis", {}).get("risk_level")
        self.confidence = float(result.get("confidence", 0.0) or result.get("analysis", {}).get("confidence", 0.0))
        self.completed_at = datetime.now()

    def mark_failed(self, error: str):
        self.status = "failed"
        self.result = {"error": error}
        self.completed_at = datetime.now()
