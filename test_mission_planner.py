from core.planning.mission_orchestrator import MissionOrchestrator
import json

orchestrator = MissionOrchestrator()

print("=== MISSION PLANNER — TEST ===\n")

result = orchestrator.run(
    title="Audit RGPD — Startup Fintech",
    objective=(
        "Une startup fintech collecte des données biométriques (reconnaissance faciale), "
        "des données bancaires et de localisation de ses utilisateurs sans base légale explicite. "
        "Évaluer la conformité RGPD, identifier les risques et produire un plan d'action."
    )
)

print(f"Mission ID     : {result['mission_id']}")
print(f"Risque final   : {result['final_risk_level']}")
print(f"Confiance moy. : {result['average_confidence']}")
print(f"Tâches         : {result['tasks_completed']}/{result['tasks_total']} complétées")
print(f"Démarrée       : {result['started_at']}")
print(f"Terminée       : {result['completed_at']}")

if result.get("executive_summary"):
    print(f"\n--- SYNTHÈSE EXÉCUTIVE ---")
    print(result["executive_summary"])

if result.get("key_actions"):
    print(f"\n--- ACTIONS PRIORITAIRES ---")
    for i, action in enumerate(result["key_actions"], 1):
        print(f"  {i}. {action}")

print(f"\n--- DÉTAIL PAR TÂCHE ---")
for t in result["task_reports"]:
    status_icon = "✅" if t["status"] == "done" else "❌"
    print(f"  {status_icon} [{t['order']}] {t['title']} ({t['agent_type']}) — risque: {t['risk_level']} — confiance: {t['confidence']}")
