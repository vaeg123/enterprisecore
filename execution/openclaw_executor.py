from typing import Dict, Any
from execution.tool_registry import ToolRegistry


class OpenClawExecutor:
    """
    Couche d'exécution contrôlée.
    """

    def __init__(self, tool_registry: ToolRegistry):
        self.tool_registry = tool_registry
        self.execution_log = []

    def execute(self, agent, tool_name: str, payload: Dict[str, Any]):

        # Vérifier permission outil
        if not agent.can_use_tool(tool_name):
            return {
                "status": "DENIED",
                "reason": f"Agent '{agent.name}' not allowed to use tool '{tool_name}'"
            }

        tool = self.tool_registry.get_tool(tool_name)

        if not tool:
            return {
                "status": "ERROR",
                "reason": f"Tool '{tool_name}' not found in registry"
            }

        try:
            result = tool(payload)

            log_entry = {
                "agent": agent.name,
                "role": agent.role,
                "tool": tool_name,
                "payload": payload,
                "result": result
            }

            self.execution_log.append(log_entry)

            return {
                "status": "SUCCESS",
                "result": result
            }

        except Exception as e:
            return {
                "status": "ERROR",
                "reason": str(e)
            }

    def get_execution_log(self):
        return self.execution_log
