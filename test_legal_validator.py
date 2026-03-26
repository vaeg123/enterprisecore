from core.legal.legal_multi_validator import LegalMultiValidatorEngine


engine = LegalMultiValidatorEngine()

question = "Assess GDPR risk for biometric data processing without explicit consent."

result = engine.analyze(question)

print("\n=== LEGAL ANALYSIS RESULT ===\n")
print(result)
