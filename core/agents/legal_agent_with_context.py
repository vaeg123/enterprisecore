from core.intelligence.context_injector import ContextInjector
from providers.role_router import RoleBasedRouter


class LegalAgentWithContext:

    def __init__(self):

        self.context_injector = ContextInjector()
        self.router = RoleBasedRouter()

    def analyze(self, question):

        # 1️⃣ récupérer le contexte interne
        context = self.context_injector.build_context(question)

        system_prompt = f"""
Tu es un juriste expert en droit européen et français.

Tu dois analyser la situation juridique en respectant :
- le droit applicable
- la doctrine interne de l'entreprise

{context}

Réponds au format JSON strict :

{{
"risk_level": "LOW | MEDIUM | HIGH",
"legal_basis": "explication juridique",
"articles_referenced": ["Article ..."],
"recommendation": "action recommandée",
"confidence": 0.0
}}
"""

        response = self.router.route(
            role="legal",
            prompt=question,
            system_prompt=system_prompt
        )

        return response