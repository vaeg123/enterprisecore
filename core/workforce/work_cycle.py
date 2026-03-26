from datetime import datetime
from typing import List, Dict
from core.workforce.base_autonomous_agent import BaseAutonomousAgent


class WorkCycleEngine:
    """
    Orchestre un cycle de travail complet :

    1. Distribution d'instructions
    2. Exécution des tâches
    3. Collecte des rapports
    4. Auto-évaluation
    """

    def __init__(self, agents: List[BaseAutonomousAgent]):

        self.agents = agents
        self.cycle_history: List[Dict] = []

    # -------------------------
    # 1️⃣ Distribution des tâches
    # -------------------------

    def distribute_instructions(self, instructions: Dict[str, str]):

        results = []

        for agent in self.agents:
            if agent.name in instructions:
                result = agent.receive_instruction(instructions[agent.name])
                results.append(result)

        return results

    # -------------------------
    # 2️⃣ Exécution
    # -------------------------

    def execute_cycle(self):

        cycle_result = {
            "started_at": datetime.utcnow(),
            "agent_outputs": [],
            "reports": [],
            "evaluations": []
        }

        # Travail
        for agent in self.agents:
            work_result = agent.work()
            cycle_result["agent_outputs"].append(work_result)

        # Reporting
        for agent in self.agents:
            report = agent.generate_report()
            cycle_result["reports"].append(report)

        # Auto-évaluation
        for agent in self.agents:
            evaluation = agent.self_evaluate()
            cycle_result["evaluations"].append(evaluation)

        cycle_result["finished_at"] = datetime.utcnow()

        self.cycle_history.append(cycle_result)

        return cycle_result

    # -------------------------
    # 3️⃣ Résumé stratégique
    # -------------------------

    def executive_summary(self):

        if not self.cycle_history:
            return {"status": "NO_CYCLE_EXECUTED"}

        last_cycle = self.cycle_history[-1]

        summary = {
            "total_agents": len(self.agents),
            "tasks_executed": len(last_cycle["agent_outputs"]),
            "average_performance": round(
                sum(a.performance_score for a in self.agents) / len(self.agents), 2
            ),
            "generated_at": datetime.utcnow()
        }

        return summary
