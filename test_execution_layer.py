from core.agents.domain_agent import DomainAgent
from execution.tool_registry import ToolRegistry
from execution.openclaw_executor import OpenClawExecutor
from execution.tools.code_executor import code_executor


# -------------------------
# Création Tool Registry
# -------------------------

registry = ToolRegistry()
registry.register_tool("code_executor", code_executor)


# -------------------------
# Création Agent Dev autorisé
# -------------------------

dev_agent = DomainAgent(
    name="DevAgent",
    role="developer",
    allowed_tools=["code_executor"],
    permissions=["execute_code"]
)


# -------------------------
# Création Agent Finance NON autorisé
# -------------------------

finance_agent = DomainAgent(
    name="FinanceAgent",
    role="finance",
    allowed_tools=[],
    permissions=[]
)


# -------------------------
# Executor
# -------------------------

executor = OpenClawExecutor(registry)


# -------------------------
# Test 1 : Dev autorisé
# -------------------------

payload = {
    "code": """
result = sum(range(10))
"""
}

print("\n--- DEV EXECUTION ---")
response_dev = executor.execute(dev_agent, "code_executor", payload)
print(response_dev)


# -------------------------
# Test 2 : Finance bloqué
# -------------------------

print("\n--- FINANCE EXECUTION ---")
response_finance = executor.execute(finance_agent, "code_executor", payload)
print(response_finance)
