from core.identity.agent_identity import AgentIdentity
from core.organization.org_graph import OrganizationGraph
from core.cognition.meeting_orchestrator import MeetingOrchestrator


# -------------------------
# Création des agents
# -------------------------

president = AgentIdentity(name="President", role="president")
ceo = AgentIdentity(name="CEO", role="ceo")
finance = AgentIdentity(name="FinanceAgent", role="finance")
legal = AgentIdentity(name="LegalAgent", role="legal")
strategy = AgentIdentity(name="StrategyAgent", role="strategy")


# Simulation réputation différente
finance.register_event("accuracy", 50)
finance.register_event("reliability", 20)

legal.register_event("accuracy", 10)

strategy.register_event("innovation", 30)
strategy.register_event("accuracy", 30)


# -------------------------
# Organisation
# -------------------------

org = OrganizationGraph()

for agent in [president, ceo, finance, legal, strategy]:
    org.add_agent(agent)

org.set_manager(ceo.id, president.id)
org.set_manager(finance.id, ceo.id)
org.set_manager(legal.id, ceo.id)
org.set_manager(strategy.id, ceo.id)


# -------------------------
# Orchestration
# -------------------------

orchestrator = MeetingOrchestrator(org)

participants = [finance.id, legal.id, strategy.id]

simulated_positions = {
    finance.id: "Reduce Marketing Budget",
    legal.id: "Secure Legal Position First",
    strategy.id: "Reduce Marketing Budget",
}


# -------------------------
# 1️⃣ Réunion normale
# -------------------------

result = orchestrator.run_meeting(
    topic="Cashflow Risk Response",
    participants=participants,
    ceo_id=ceo.id,
    president_id=president.id,
    simulated_positions=simulated_positions,
)

print("\n--- EXECUTIVE MEETING (NORMAL) ---")
print(result)


# -------------------------
# 2️⃣ CEO bloque
# -------------------------

result_ceo_veto = orchestrator.run_meeting(
    topic="Cashflow Risk Response",
    participants=participants,
    ceo_id=ceo.id,
    president_id=president.id,
    simulated_positions=simulated_positions,
    veto={ceo.id: True},
)

print("\n--- EXECUTIVE MEETING (CEO VETO) ---")
print(result_ceo_veto)
