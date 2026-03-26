from database.db_manager import DatabaseManager


def run_cognitive_meeting(
    topic: str,
    agents: list,
    options: list,
    consensus_engine
):
    """
    Orchestrateur officiel de réunion cognitive.
    """

    db = DatabaseManager()

    # -------------------------
    # 1️⃣ Sauvegarder agents
    # -------------------------
    for agent in agents:
        db.save_agent(agent)

    # -------------------------
    # 2️⃣ Collecter rapports
    # -------------------------
    reports = []

    for agent in agents:
        report = agent.analyze_topic(topic, options)
        reports.append((agent, report))

    # -------------------------
    # 3️⃣ Construire proposals pour consensus
    # -------------------------
    proposals = {}

    for agent, report in reports:

        # Pondération simple basée sur réputation globale
        reputation_weight = agent.reputation.overall / 1000.0

        proposals[agent.id] = {
            "proposal": report["decision"],
            "reputation_weight": reputation_weight
        }

    # -------------------------
    # 4️⃣ Appel du moteur de consensus
    # -------------------------
    consensus_result = consensus_engine.reach_consensus(
        proposals=proposals,
        ceo_id=None,
        president_id=None,
        veto=None
    )

    final_decision_summary = consensus_result.summary()

    # -------------------------
    # 5️⃣ Sauvegarder réunion
    # -------------------------
    meeting_id = db.save_meeting(
        topic,
        options,
        final_decision_summary
    )

    # -------------------------
    # 6️⃣ Sauvegarder rapports agents
    # -------------------------
    for agent, report in reports:
        db.save_agent_report(
            meeting_id,
            agent.id,
            {
                "decision": report.get("decision"),
                "justification": report.get("justification"),
                "confidence": report.get("confidence"),
                "provider_metadata": report.get("provider_metadata")
            }
        )

    # -------------------------
    # 7️⃣ Retour structuré
    # -------------------------
    return {
        "meeting_id": meeting_id,
        "topic": topic,
        "options": options,
        "reports": reports,
        "final_decision": final_decision_summary
    }
