from core.agents.legal_agent_with_context import LegalAgentWithContext

agent = LegalAgentWithContext()

result = agent.analyze(
    "Peut-on collecter des données biométriques pour contrôler l'accès aux locaux ?"
)

print(result.content)