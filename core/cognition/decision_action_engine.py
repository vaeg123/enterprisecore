from execution.openclaw_executor import OpenClawExecutor
from execution.tool_registry import ToolRegistry
from database.db_manager import DatabaseManager
from execution.tools.code_executor import code_executor


class DecisionActionEngine:
    """
    Traduit une décision stratégique en plan d'action opérationnel.
    """

    def __init__(self):

        # Tool Registry
        self.registry = ToolRegistry()
        self.registry.register_tool("code_executor", code_executor)

        self.executor = OpenClawExecutor(self.registry)
        self.db = DatabaseManager()

    def build_action_plan(self, decision: str):

        """
        Map décision → plan structuré
        """

        if decision == "COST_CUTTING":
            return [
                {
                    "tool": "code_executor",
                    "payload": {
                        "code": "result = 'Simulated budget reduction analysis completed'"
                    }
                }
            ]

        if decision == "REVENUE_ENHANCEMENT":
            return [
                {
                    "tool": "code_executor",
                    "payload": {
                        "code": "result = 'Revenue optimization simulation executed'"
                    }
                }
            ]

        return []

    def execute_plan(self, agent, decision_summary):

        decision = decision_summary.get("final_decision")

        plan = self.build_action_plan(decision)

        execution_results = []

        for step in plan:

            response = self.executor.execute(
                agent,
                step["tool"],
                step["payload"]
            )

            # Persist execution log
            self.db.save_execution_log(
                agent_id=agent.id,
                tool_name=step["tool"],
                payload=step["payload"],
                result=response
            )

            execution_results.append(response)

        return execution_results
