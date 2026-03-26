from typing import Dict, Callable


class ToolRegistry:
    """
    Registre central des outils disponibles.
    """

    def __init__(self):
        self.tools: Dict[str, Callable] = {}

    def register_tool(self, name: str, tool_callable: Callable):
        self.tools[name] = tool_callable

    def get_tool(self, name: str):
        return self.tools.get(name)

    def list_tools(self):
        return list(self.tools.keys())
