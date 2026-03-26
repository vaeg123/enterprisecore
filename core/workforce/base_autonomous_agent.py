from datetime import datetime
from typing import List, Dict, Optional
from core.agents.domain_agent import DomainAgent


class BaseAutonomousAgent(DomainAgent):
    """
    Agent autonome capable de :
    - Recevoir des instructions
    - Créer des tâches
    - Travailler
    - Produire un rapport
    - S'auto-évaluer
    """

    def __init__(
        self,
        name: str,
        role: str,
        allowed_tools: Optional[List[str]] = None,
        permissions: Optional[List[str]] = None,
    ):
        super().__init__(
            name=name,
            role=role,
            allowed_tools=allowed_tools or [],
            permissions=permissions or [],
        )

        self.current_tasks: List[Dict] = []
        self.completed_tasks: List[Dict] = []
        self.report_history: List[Dict] = []
        self.performance_score: float = 0.5  # Score initial neutre

    # -------------------------
    # 1️⃣ Recevoir instruction
    # -------------------------

    def receive_instruction(self, instruction: str):

        task = {
            "instruction": instruction,
            "created_at": datetime.utcnow(),
            "status": "PENDING",
        }

        self.current_tasks.append(task)

        return {
            "status": "TASK_REGISTERED",
            "agent": self.name,
            "task": instruction,
        }

    # -------------------------
    # 2️⃣ Travailler
    # -------------------------

    def work(self):

        if not self.current_tasks:
            return {
                "status": "NO_TASK",
                "agent": self.name
            }

        task = self.current_tasks.pop(0)

        # Simulation de travail
        task_result = {
            "instruction": task["instruction"],
            "completed_at": datetime.utcnow(),
            "result": f"{self.name} executed task: {task['instruction']}",
            "status": "COMPLETED"
        }

        self.completed_tasks.append(task_result)

        return task_result

    # -------------------------
    # 3️⃣ Produire rapport
    # -------------------------

    def generate_report(self):

        report = {
            "agent": self.name,
            "role": self.role,
            "completed_tasks": len(self.completed_tasks),
            "performance_score": round(self.performance_score, 2),
            "generated_at": datetime.utcnow()
        }

        self.report_history.append(report)

        return report

    # -------------------------
    # 4️⃣ Auto-évaluation
    # -------------------------

    def self_evaluate(self):

        if not self.completed_tasks:
            self.performance_score *= 0.98
        else:
            self.performance_score += 0.02

        self.performance_score = min(max(self.performance_score, 0), 1)

        return {
            "agent": self.name,
            "new_performance_score": round(self.performance_score, 2)
        }
