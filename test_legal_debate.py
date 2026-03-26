from core.cognition.legal_debate_engine import LegalDebateEngine


engine = LegalDebateEngine()

result = engine.run_debate(
    "Une entreprise peut-elle utiliser la reconnaissance faciale pour contrôler l'accès à ses locaux ?"
)

print("\n=== LEGAL DEBATE RESULT ===\n")

print(result)