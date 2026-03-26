from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class MissionCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=255, description="Titre court de la mission")
    objective: str = Field(..., min_length=10, description="Description complète de la situation juridique à analyser")


class TaskOut(BaseModel):
    id: int
    task_order: int
    task_title: str
    task_description: str
    agent_type: str
    status: str
    risk_level: Optional[str]
    confidence: Optional[float]
    result: Optional[dict]
    created_at: Optional[str]
    completed_at: Optional[str]


class MissionOut(BaseModel):
    id: int
    title: str
    objective: str
    status: str
    tasks_count: int
    completed_tasks: int
    final_risk_level: Optional[str]
    created_at: Optional[str]
    completed_at: Optional[str]


class MissionDetail(MissionOut):
    final_report: Optional[dict]
    tasks: List[TaskOut] = []


class MissionStatusOut(BaseModel):
    run_id: str
    status: str                    # running | done | error
    mission_id: Optional[int]


class MissionCreateOut(BaseModel):
    run_id: str
    status: str = "running"
    message: str = "Mission démarrée. Utilisez GET /v1/missions/run/{run_id}/status pour suivre la progression."


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Nom descriptif de la clé (ex: mon-app)")


class ApiKeyOut(BaseModel):
    id: int
    name: str
    key_prefix: str
    active: bool
    created_at: Optional[str]
    last_used: Optional[str]


class ApiKeyCreated(BaseModel):
    id: int
    name: str
    key: str = Field(..., description="Clé complète — affichée une seule fois, à sauvegarder immédiatement")
    key_prefix: str


class HealthOut(BaseModel):
    status: str
    database: str
    version: str = "1.0.0"
    services: dict
