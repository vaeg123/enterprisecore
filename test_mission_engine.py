from core.execution.mission_engine import MissionEngine


engine = MissionEngine()

result = engine.run_mission(
    "Audit RGPD biométrie",
    "Une entreprise veut utiliser la reconnaissance faciale pour contrôler l'accès aux locaux."
)

print("\n=== MISSION RESULT ===\n")

print(result)