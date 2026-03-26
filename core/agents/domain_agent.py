from typing import List, Dict
from core.agents.cognitive_agent import CognitiveAgent


class DomainAgent(CognitiveAgent):
    """
    Agent métier avec permissions et outils autorisés.
    """

    def __init__(
        self,
        name: str,
        role: str,
        allowed_tools: List[str],
        permissions: List[str]
    ):
        super().__init__(name=name, role=role)

        self.allowed_tools = allowed_tools
        self.permissions = permissions

    # -------------------------
    # Permission Management
    # -------------------------

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions

    def can_use_tool(self, tool_name: str) -> bool:
        return tool_name in self.allowed_tools

    # -------------------------
    # Controlled Execution
    # -------------------------

    def request_tool_execution(self, tool_name: str, payload: Dict):

        if not self.can_use_tool(tool_name):
            return {
                "status": "DENIED",
                "reason": f"Tool '{tool_name}' not allowed for role '{self.role}'"
            }

        return {
            "status": "APPROVED",
            "tool": tool_name,
            "payload": payload
        }

    # -------------------------
    # Audit
    # -------------------------

    def get_access_profile(self):
        return {
            "name": self.name,
            "role": self.role,
            "allowed_tools": self.allowed_tools,
            "permissions": self.permissions
        }
