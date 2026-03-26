from typing import Dict, List


class ConsensusResult:
    def __init__(
        self,
        final_decision,
        weighted_support,
        dissenters,
        status,
        veto_by=None,
    ):
        self.final_decision = final_decision
        self.weighted_support = weighted_support
        self.dissenters = dissenters
        self.status = status
        self.veto_by = veto_by

    def summary(self):
        return {
            "final_decision": self.final_decision,
            "weighted_support": round(self.weighted_support, 2),
            "dissenters": self.dissenters,
            "status": self.status,
            "veto_by": self.veto_by,
        }


class ConsensusEngine:
    """
    Moteur de consensus exécutif avec hiérarchie et veto.
    """

    def reach_consensus(
        self,
        proposals: Dict[str, Dict],
        ceo_id: str = None,
        president_id: str = None,
        veto: Dict[str, bool] = None,
        min_support_threshold: float = 0.6,
    ):

        vote_counter = {}
        total_weight = 0.0

        for agent_id, data in proposals.items():
            proposal = data["proposal"]
            weight = data["reputation_weight"]

            vote_counter[proposal] = vote_counter.get(proposal, 0) + weight
            total_weight += weight

        if not vote_counter:
            return ConsensusResult(
                None, 0, [], status="NO_DECISION"
            )

        final_decision = max(vote_counter, key=vote_counter.get)
        weighted_support = (
            vote_counter[final_decision] / total_weight
            if total_weight else 0
        )

        dissenters = [
            agent_id
            for agent_id, data in proposals.items()
            if data["proposal"] != final_decision
        ]

        # Vérification seuil minimal
        if weighted_support < min_support_threshold:
            return ConsensusResult(
                final_decision,
                weighted_support,
                dissenters,
                status="INSUFFICIENT_SUPPORT",
            )

        # Gestion veto
        veto = veto or {}

        if ceo_id and veto.get(ceo_id):
            return ConsensusResult(
                final_decision,
                weighted_support,
                dissenters,
                status="VETOED_BY_CEO",
                veto_by=ceo_id,
            )

        if president_id and veto.get(president_id):
            return ConsensusResult(
                final_decision,
                weighted_support,
                dissenters,
                status="VETOED_BY_PRESIDENT",
                veto_by=president_id,
            )

        return ConsensusResult(
            final_decision,
            weighted_support,
            dissenters,
            status="APPROVED",
        )
