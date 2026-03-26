import json
from providers.role_router import RoleBasedRouter


class LegalMultiValidatorEngine:
    """
    Interroge plusieurs modèles juridiques
    avec fallback automatique.
    """

    def __init__(self):
        self.router = RoleBasedRouter()

    def _build_system_prompt(self):
        return """
You are a senior corporate legal expert.

Respond ONLY in strict JSON format:

{
  "risk_level": "LOW | MEDIUM | HIGH",
  "legal_basis": "short explanation",
  "articles_referenced": ["Article X", "Article Y"],
  "recommendation": "clear recommendation",
  "confidence": 0.0
}

No extra text.
"""

    def analyze(self, question: str):

        system_prompt = self._build_system_prompt()

        # PRIORITÉ : Claude via rôle legal
        response = self.router.route(
            role="legal",
            prompt=question,
            system_prompt=system_prompt
        )

        if response.metadata.get("error"):
            # Fallback automatique vers OpenAI finance (car GPT stable)
            response = self.router.route(
                role="finance",
                prompt=question,
                system_prompt=system_prompt
            )

        try:
            parsed = json.loads(response.content)

            return {
                "provider": response.metadata,
                "analysis": parsed,
                "raw_confidence": response.confidence
            }

        except Exception:

            return {
                "provider": response.metadata,
                "analysis": None,
                "raw_confidence": 0.0,
                "error": "Parsing failed"
            }
