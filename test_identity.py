from core.identity.agent_identity import AgentIdentity


# Création de deux agents
finance = AgentIdentity(name="FinanceAgent", role="finance")
legal = AgentIdentity(name="LegalAgent", role="legal")


# Finance prend une bonne décision
finance.register_event(category="accuracy", impact=25)

# Legal valide la décision
legal.register_event(category="collaboration", impact=15)

# Interaction positive entre eux
finance.interact(legal.id, "success")
legal.interact(finance.id, "success")


# Affichage des profils
print("\n--- FINANCE PROFILE ---")
print(finance.profile())

print("\n--- LEGAL PROFILE ---")
print(legal.profile())
