from typing import Dict, List, Tuple
from datetime import datetime


class OrganizationGraph:
    """
    Graphe organisationnel simple mais extensible.
    """

    def __init__(self):
        # id -> agent object
        self.agents: Dict[str, object] = {}

        # Relations hiérarchiques : (subordinate, manager)
        self.hierarchy: List[Tuple[str, str]] = []

        # Relations collaboratives : (agent_a, agent_b)
        self.collaborations: List[Tuple[str, str]] = []

        self.created_at = datetime.utcnow()

    # -------------------------
    # AGENTS
    # -------------------------

    def add_agent(self, agent):
        self.agents[agent.id] = agent

    def get_agent(self, agent_id: str):
        return self.agents.get(agent_id)

    def list_agents(self):
        return [agent.profile() for agent in self.agents.values()]

    # -------------------------
    # HIERARCHY
    # -------------------------

    def set_manager(self, subordinate_id: str, manager_id: str):
        self.hierarchy.append((subordinate_id, manager_id))

    def get_manager(self, agent_id: str):
        for sub, manager in self.hierarchy:
            if sub == agent_id:
                return manager
        return None

    def get_subordinates(self, manager_id: str):
        return [
            sub for sub, manager in self.hierarchy
            if manager == manager_id
        ]

    # -------------------------
    # COLLABORATIONS
    # -------------------------

    def add_collaboration(self, agent_a: str, agent_b: str):
        self.collaborations.append((agent_a, agent_b))

    def get_collaborators(self, agent_id: str):
        collaborators = []
        for a, b in self.collaborations:
            if a == agent_id:
                collaborators.append(b)
            elif b == agent_id:
                collaborators.append(a)
        return collaborators

    # -------------------------
    # ANALYTICS BASIQUES
    # -------------------------

    def organizational_snapshot(self):
        return {
            "total_agents": len(self.agents),
            "hierarchy_links": len(self.hierarchy),
            "collaborations": len(self.collaborations),
            "created_at": self.created_at.isoformat()
        }
